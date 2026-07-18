# Use the box as your AI backend

> Point VS Code, Claude Code, or any Anthropic-/OpenAI-compatible tool at the box
> and it drives your **own local model** over loopback — nothing crosses the
> network, no cloud, no API bill. Built by SDD-205 (Anthropic Messages API),
> SDD-062/103 (the OpenAI shim), and SDD-011 (the inference backend).

The gateway daemon **`sovereign-gatewayd`** (loopback `127.0.0.1:8787`) is the one
door. It speaks two industry-standard shapes over the same locally-served model:

- the **Anthropic Messages API** (`POST /v1/messages`) — primary,
- the **OpenAI Chat Completions** shape (`POST /v1/chat/completions`) — secondary,

plus the box's own sovereign **routing/decision** and **reasoning** surfaces
(`/v1/infer`, `/v1/deliberate`, `/v1/coat`). It never phones home; a request only
generates on the model you have loaded locally.

## Start it

```bash
# 1. get a model dir (config.json + *.safetensors + tokenizer.json)
scripts/intelligence/fetch-model.sh /var/lib/sovereign-os/models/smollm-135m

# 2. run the gateway with that model loaded, HTTP mode
SOVEREIGN_GATEWAY_MODEL=/var/lib/sovereign-os/models/smollm-135m \
  sovereign-gatewayd --http        # binds 127.0.0.1:8787
```

On a flashed box the `sovereign-gatewayd.service` unit does this for you. Check it:

```bash
curl -s 127.0.0.1:8787/health | python3 -m json.tool     # never_cloud_spill_holds: true
sovereign-osctl gateway                                   # human summary (ledger, surfaces, memory)
```

> **No model, no fabrication.** If no model is loaded, a generate call returns an
> honest error (Anthropic error envelope / OpenAI 503) — never a faked answer
> (SB-077). Load a model to generate.

## Wire up your editor

The box is **loopback-trust**: it accepts the `x-api-key` / `anthropic-version`
headers but does not validate them — there is no cloud auth on a sovereign box, so
any key string works. It serves *your* local model regardless of the model id the
client sends (the id is echoed back).

### Claude Code

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:8787 \
ANTHROPIC_API_KEY=sk-local \
  claude
```

Claude Code POSTs to `<base>/v1/messages` — which is exactly the surface below.

### VS Code — Cline / Claude Dev

In the extension's settings:

| Field | Value |
|-------|-------|
| API Provider | **Anthropic** |
| Base URL | `http://127.0.0.1:8787` |
| API Key | any string (e.g. `sk-local`) |
| Model | any (the box serves its one local model) |

### The Anthropic SDK (Python / TS)

```python
from anthropic import Anthropic
client = Anthropic(base_url="http://127.0.0.1:8787", api_key="sk-local")
msg = client.messages.create(
    model="sovereign-local", max_tokens=128,
    messages=[{"role": "user", "content": "Explain ZFS tiering in one line."}],
)
print(msg.content[0].text)
```

### OpenAI-compatible tools

Anything that speaks OpenAI Chat Completions can use the shim instead — point its
base URL at `http://127.0.0.1:8787` and call `POST /v1/chat/completions` (SSE).

## Gateway endpoint reference

All `POST` bodies are JSON. Generation surfaces need a model loaded; the decision
and read-only surfaces run on the deterministic engine and never need one.

| Method + path | Purpose | Shape |
|---|---|---|
| `POST /v1/messages` | **Anthropic Messages API** (generate) | `{model, max_tokens, system?, messages[], stream?}` → `{type:"message", content:[{type:"text",text}], stop_reason, usage}`; `stream:true` = Anthropic SSE |
| `GET /v1/models` | Anthropic models list (loaded residents + proxies, with `device`/`vram_gb`); `architecture` describes the primary in-process model (`layers`/`vocab`/`model_dim`, plus a `mixture_of_experts` block — experts / top-k / sparse-layer count — when it is a MoE, else `null`) | `{data:[{type:"model", id, display_name, device, vram_gb}], has_more:false, architecture:{layers, vocab, model_dim, mixture_of_experts}\|null}` |
| `POST /v1/messages/count_tokens` | Anthropic token count | `{input_tokens:N}` |
| `POST /v1/models/load` | load a **secondary** CPU model | `{id, dir}` → `{loaded:id}` |
| `POST /v1/models/unload` | unload a secondary / unregister a proxy | `{id}` → `{unloaded:bool}` |
| `POST /v1/models/register` | register a **GPU serve-process** backend (a `model-serve` job does this) | `{id, endpoint, device?, vram_gb?, dialect?}` → `{registered:id}` |
| `POST /v1/models/background` | designate the model the `"background"` alias routes to | `{id}` → `{background:id, active:id\|null}` |
| `POST /v1/corpus/reload` | re-index the RAG corpus from `SOVEREIGN_GATEWAY_CORPUS` **without a daemon restart** (edit the corpus dir, then reload) | *(no body)* → `{reloaded:true, corpus_docs:N}` |
| `POST /v1/cache/clear` | flush the opt-in completion cache (`SOVEREIGN_GATEWAY_CACHE_CAPACITY`) without a restart | *(no body)* → `{cleared:true, entries_dropped:N}` |
| `GET /v1/events` | recent runtime observability spans (one `model_call` per local generation) | `{count:N, events:[{kind:"model_call", model, tokens, latency_ms, provider, …}]}` |
| `POST /v1/chat/completions` | **OpenAI shim** (generate, SSE) | OpenAI chat request → OpenAI `chat.completion.chunk` deltas + `[DONE]` |
| `POST /v1/infer` (alias `/mcp`) | routing **DECISION** (no generation) | cortex request → `{kind:"decision", decision:{route, device, verdict, …}}` |
| `POST /v1/simple` | simplified decision (7 axes + `expected_quality`) — learns | `{axes:{…}, expected_quality}` → `{kind:"decision", learned}` |
| `POST /v1/simple-explain` | decision **preview** — does NOT learn | as above → `{kind:"decision", learned:false}` |
| `POST /v1/explain` | dry-run rationale (read-only) | cortex request → `{kind:"explanation"}` |
| `POST /v1/deliberate` | best-of-N deliberation (read-only) | `{request, candidates[], tier}` → `{kind:"deliberation"}` |
| `POST /v1/coat` | **CoAT reasoning** (read-only) — see [Reasoning & operability](./reasoning-operability.md) | `{problem, rung, topic?}` → `{kind:"coat-trace", trace:{best_path, …}}` |
| `POST /v1/control-word/round` | **M002 control-word round engine** — reads the live `avx-mode` switch (state file, or `avx_mode` body override); runs the 8-lane bit-machine only under `custom`/`hybrid` (AVX-512 when present), else an honest engine-off envelope. Returns per-lane DNA fingerprints + lifecycle events + service metrics | `{state:{state[],memory[],rule[],random[]}, config?, rounds?, avx_mode?}` → `{kind:"control-word-round", avx_mode, engine_active, result?, fingerprints[], diversity_index, events[], metrics}` |
| `GET /v1/control-word/config` | **M002 live runtime config** — the resolved `avx-mode` (from the hot-swappable state file), whether the bit-machine is active, and the env-resolved round + control-word knobs. Curl it to confirm a hot-swap took effect | — → `{kind:"control-word-config", avx_mode, engine_active, round_config, control_word_config}` |
| `POST /v1/branch-scheduler/tick` | **M007 branch loop** — one tick of the 8-step loop (Spawn→…→Learn) over an 8-branch SoA batch; the M002+M007+M008 capstone. Commit gate reads control-word permissions; Filter/Verify short-circuit (M008 speculative-accept); survivors packed dense (VPCOMPRESS) | `{batch:{id[],control[],budget[],score[],grammar[],memory[],route[]}, verify_min_score?}` → `{kind:"branch-scheduler-tick", result:{steps[], alive_after_filter, alive_after_verify, committed, committed_ids[], survivors}}` |
| `POST /v1/branch-scheduler/tick-v2` | **M007 tick v2** — the richer tick that *consumes* the M008 building blocks: memory recall (bloom), the branch predictor (M00121), the two-level rule table (M00119) for Verify, and microcode (M00113) for Commit. A `session_id` persists the predictor across requests (M00121 learns across ticks) | `{batch, rule_table:[[u8,…],…], event_class:[usize;8], memory_bank:[u64,…], verify_min_score?, session_id?}` → `{kind:"branch-scheduler-tick-v2", session_id, result:{base, recall[], predicted_commit, rule_verified, predictor_accuracy}}` |
| `POST /v1/math/dot-i8` | **M085 T1 VNNI** — INT8 dot product `Σ a·b` (`VPDPBUSD` when `avx512vnni`, else scalar reference) | `{a:[u8,…], b:[i8,…]}` → `{kind:"math-dot-i8", dot, avx512vnni}` |
| `POST /v1/math/attention-fuse` | **M085 T2** — `VPTERNLOG` attention-mask fusion `query ∧ key ∧ causal` (single-instruction per 8 words on any `avx512f` host) | `{query:[u64,…], key:[u64,…], causal:[u64,…]}` → `{kind:"math-attention-fuse", allow[]}` |
| `POST /v1/token-law/allowed-mask` | **M008 token-law** (M00117, F00623) — combine grammar/schema/tool/safety/route vocab bitsets into one allowed-token mask | `{laws:[[u64,…],…], combine?:"and"\|"or"}` → `{kind:"token-law-allowed-mask", combine, mask[], allowed_tokens}` |
| `POST /v1/microcode/decode` | **M008 bitfields-as-microcode** (M00113) — decode a control word's bitfields as an executable micro-op program and run it to a policy outcome | `{control_word:u64}` → `{kind:"microcode-decode", control_word, program[], outcome:{commit, sandboxed, speculative, replay, audited, gate_required}}` |
| `GET /health` · `/manifest` · `/admin/ledger` · `/metrics` | liveness · 6-surface manifest · cost/route ledger · Prometheus | — |

### Try it with curl

Non-streaming Anthropic message:

```bash
curl -s http://127.0.0.1:8787/v1/messages \
  -H 'x-api-key: sk-local' -H 'anthropic-version: 2023-06-01' \
  -H 'content-type: application/json' \
  -d '{"model":"sovereign-local","max_tokens":64,
       "system":"Be brief.",
       "messages":[{"role":"user","content":"Say hi in one sentence."}]}'
```

Streaming (Anthropic SSE — `message_start` → `content_block_delta`* → `message_stop`):

```bash
curl -N http://127.0.0.1:8787/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"sovereign-local","max_tokens":64,"stream":true,
       "messages":[{"role":"user","content":"Say hi."}]}'
```

## Multiple models & background compute

The gateway hosts more than one model at once, so background work never blocks your
interactive chat:

- **Primary** — the CPU model loaded at startup (`SOVEREIGN_GATEWAY_MODEL`). This is
  what interactive requests hit by default.
- **Secondaries** — additional CPU models loaded at runtime with
  `POST /v1/models/load {id, dir}`. Address one by name: `{"model":"<id>", …}`.
  Different models generate concurrently; the same model serialises.
- **GPU serve-processes** — big models run as a **separate** llama-server / vLLM
  process on a GPU. One command launches one:

  ```bash
  # place on a GPU by free VRAM, launch the engine, register a gateway proxy.
  # vLLM is provisioned (operator-deps [pip]) → --engine vllm works out of the box;
  # llama-server (llama.cpp) is a manual install. `start` preflights the engine and
  # refuses with a hint if it isn't installed.
  sovereign-osctl model-serve start big-llama --model /models/llama-70b --vram 40 --engine vllm
  sovereign-osctl model-serve list          # serving jobs + the gateway registry
  sovereign-osctl model-serve stop big-llama # cancel → unregister + release VRAM
  ```

  Under the hood a `model-serve` job places it on a device by free VRAM (the compute
  plane), launches it, and calls `POST /v1/models/register` so the gateway **proxies**
  requests to it — translating between the Anthropic surface and the backend's OpenAI
  dialect automatically. Then address it by id (`{"model":"big-llama"}`) from any
  Anthropic/OpenAI client, or make it the background target.
- **The `"background"` alias** — send `{"model":"background", …}` and the gateway
  routes to whichever model you designated with `sovereign-osctl model-serve
  background <id>` (or `POST /v1/models/background {id}`, or
  `SOVEREIGN_GATEWAY_BACKGROUND_MODEL`). Background deliberation jobs use this by
  default. If nothing is designated (or the designated model isn't loaded), it falls
  back to the primary — an honest default, never a dead route.

```bash
# designate a loaded secondary (or a registered GPU proxy) as the background model
curl -s http://127.0.0.1:8787/v1/models/background \
  -H 'content-type: application/json' -d '{"id":"fast"}'
# → {"background":"fast","active":"fast"}

# now background work targets it, leaving the primary free
curl -s http://127.0.0.1:8787/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"background","max_tokens":64,
       "messages":[{"role":"user","content":"summarise this log…"}]}'
```

> Streaming (`stream:true`) works against every backend: a CPU secondary streams
> directly, and a GPU **proxy** streams too — the gateway transcodes the upstream
> serve-process's SSE into the Anthropic event sequence as tokens arrive. So VS Code
> / Claude Code get token-by-token output from a GPU-hosted model with no extra setup.

## The sovereign posture (what makes this different from a cloud endpoint)

- **Loopback by default.** Bound to `127.0.0.1`; exposing it beyond loopback is
  your explicit §1g decision (a systemd drop-in setting the bind address).
- **Never fabricated (SB-077).** No model loaded → an honest error, never invented
  output. Nothing is mocked to look live.
- **No cloud spill.** The gateway's headline invariant is `never_cloud_spill == true`
  (visible in `/health` + `/metrics`); a sovereign request never reaches a cloud
  provider, whatever the client asked.
- **Quality is model-gated.** The *shape* (what your editor consumes) is complete;
  the *answers* are only as good as the model you loaded. A small base model
  (SmolLM-135M) rambles; load a stronger instruct model for real work.

## The desktop + the agent runtimes (SDD-704–707)

The gateway above is the *engine*. On top of it the box ships a **swappable face**
and two **AI agent runtimes**, all built-time-selectable in the profile and
runtime-switchable with `sovereign-osctl` — no reflash.

### The face — what the box shows at boot (SDD-704)

```bash
sovereign-osctl frontend list                    # what's staged / active
sovereign-osctl frontend set gnome               # the GNOME desktop + dashboards launcher (default)
sovereign-osctl frontend set dashboards-kiosk    # fullscreen kiosk → the :8100 dashboards hub
sovereign-osctl frontend set open-computer-kiosk # fullscreen kiosk → the open-computer sandbox UI
sovereign-osctl frontend set none                # headless (multi-user.target)
```

Build-time default + staged set come from `profiles/<id>.yaml`:
```yaml
provisioning:
  frontend:
    default: gnome                        # what boots
    install: [gnome, dashboards-kiosk]    # which stacks are staged so the live switch works
```

### The agent runtimes — installed-off, preconfigured to the local model

Both consume the local gateway by default and ship **installed-off** (staged at
build, started on your word). Turn on with a bake toggle in the profile
(`provisioning.bake.openclaw` / `provisioning.bake.open_computer`), then:

```bash
# OpenClaw — a Node gateway daemon (SDD-705)
sovereign-osctl openclaw status
sudo sovereign-osctl openclaw install        # first-boot installer (Node + npm + preconfig)
sudo sovereign-osctl openclaw on             # start it (installed-off until now)

# open-computer — a QEMU AI-sandbox VM the agent drives (SDD-706)
sovereign-osctl open-computer status
sudo sovereign-osctl open-computer install   # QEMU/KVM + Node + ~3GB base image
sudo sovereign-osctl open-computer on
sovereign-osctl open-computer url             # the sandbox UI (http://localhost:9800)
```

### The backend hotswap — local model ↔ hosted Claude (SDD-707)

Each runtime flips between the **local** model (the on-box `:8787` safety-spine
gateway) and **hosted Claude** (`api.anthropic.com`) — clear and easy, parallel to
`frontend set`:

```bash
sovereign-osctl openclaw       backend show
sudo sovereign-osctl openclaw       backend anthropic --key sk-ant-...   # → hosted Claude
sudo sovereign-osctl openclaw       backend local                       # → back to the sovereign model
sudo sovereign-osctl open-computer  backend anthropic --key sk-ant-...
```

- **`local`** routes every agent turn through the box's own safety spine (auth +
  injection/secret/PII/toxicity — SDD-206) — nothing leaves the box.
- **`anthropic`** uses the real Claude API. The key is a real secret: it lives in a
  root-only `/etc/sovereign-os/anthropic-key.env` (supplied via `--key`), **never baked
  into the image**. Swapping to `anthropic` without a key still works but warns.

Under the hood one engine (`scripts/operator/agent-backend.py`) renders both configs:
for OpenClaw (Anthropic-native) it flips `agents.defaults.model.primary` between two
coexisting providers; for open-computer (OpenAI-format) it flips `OPENAI_BASE_URL`
between the local shim and Anthropic's OpenAI-compat endpoint.

## The sovereign posture (what makes this different from a cloud endpoint)

- **Loopback by default.** Bound to `127.0.0.1`; exposing it beyond loopback is
  your explicit §1g decision (a systemd drop-in setting the bind address).
- **Installed-off optional components.** The agent runtimes are present but dormant
  until you turn them on — nothing you didn't ask for runs at boot.
- **No baked credentials.** The hosted-Claude key is operator-supplied at runtime,
  never in the image (same discipline as external channels).

## See also

- Design: `docs/sdd/205-anthropic-messages-api.md`, `docs/sdd/011-inference-backend-stack.md`,
  `docs/sdd/062-functional-lm-chat.md`.
- The agent layer: `docs/sdd/704-frontend-selector.md`, `705-openclaw-agent-runtime.md`,
  `706-open-computer-sandbox.md`, `707-agent-runtime-backend-hotswap.md`.
- Lifecycle verbs: [Lifecycle management](./ops/manage.md).
- The box's reasoning + operability surfaces: [Reasoning & operability](./reasoning-operability.md).
