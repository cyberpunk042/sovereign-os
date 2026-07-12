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
| `GET /v1/models` | Anthropic models list | `{data:[{type:"model", id, display_name}], has_more:false}` |
| `POST /v1/messages/count_tokens` | Anthropic token count | `{input_tokens:N}` |
| `POST /v1/chat/completions` | **OpenAI shim** (generate, SSE) | OpenAI chat request → OpenAI `chat.completion.chunk` deltas + `[DONE]` |
| `POST /v1/infer` (alias `/mcp`) | routing **DECISION** (no generation) | cortex request → `{kind:"decision", decision:{route, device, verdict, …}}` |
| `POST /v1/simple` | simplified decision (7 axes + `expected_quality`) — learns | `{axes:{…}, expected_quality}` → `{kind:"decision", learned}` |
| `POST /v1/simple-explain` | decision **preview** — does NOT learn | as above → `{kind:"decision", learned:false}` |
| `POST /v1/explain` | dry-run rationale (read-only) | cortex request → `{kind:"explanation"}` |
| `POST /v1/deliberate` | best-of-N deliberation (read-only) | `{request, candidates[], tier}` → `{kind:"deliberation"}` |
| `POST /v1/coat` | **CoAT reasoning** (read-only) — see [Reasoning & operability](./reasoning-operability.md) | `{problem, rung, topic?}` → `{kind:"coat-trace", trace:{best_path, …}}` |
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

## See also

- Design: `docs/sdd/205-anthropic-messages-api.md`, `docs/sdd/011-inference-backend-stack.md`,
  `docs/sdd/062-functional-lm-chat.md`.
- The box's reasoning + operability surfaces: [Reasoning & operability](./reasoning-operability.md).
