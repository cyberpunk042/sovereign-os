# Changelog

All notable changes to sovereign-os land here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
sovereign-os uses date-based phase markers rather than SemVer
until Stage 3+ when a public-distributable artifact lands.

Cross-references:
- Decisions: `docs/decisions.md` (every D-NNN entry)
- SDDs: `docs/sdd/INDEX.md` (every spec)
- Handoffs: `docs/handoff/` (cold-start anchors)

## [Unreleased] — Stage-2 onset (post-Gate-5)

### Fixed — auto-mode permission classifier: flag normalization + honest framing (2026-07-12)

Phase-1 audit (SDD-954; closes ledger F-2026-092). The Auto-mode safety classifier
(`scripts/operator/lib/permission_classifier.py`) matched destructive `rm` via a single combined-token regex, so
split (`rm -r -f`) and uppercase (`rm -R -f`) flags escaped the `destructive` verdict and fell to `confirm` —
undercutting Auto mode's job to block the recursive-delete class.

- **`permission_classifier.py`**: the two fragile `rm` regexes are replaced by `_rm_recursive_or_force()`, which
  flag-normalizes recursive (`-r`/`-R`/`--recursive`) and force (`-f`/`--force`) across split / combined / reordered
  / uppercase / long forms (and `sudo rm …`). Tightening-only (nothing that blocked/confirmed becomes allow) and
  fail-safe (unrecognized / obfuscated mutations still land in `unknown` → confirm, never a silent allow).
- **Doctrine reframe**: the module docstring and the plan-mode/user-approval directive now state the classifier is a
  **best-effort UX heuristic, not a security boundary** — the real boundary is the allowlisted execute daemon
  (`control-exec-api`) + fs sandbox (F-2026-081); a `block` means "spared the operator a mistake", not "an attacker
  was stopped".
- Regression + framing tests in `tests/lint/test_plan_mode_contract.py`.


### Added — configurable model load: the loader stops hardcoding F32-greedy (2026-07-12)

Phase-1 audit (SDD-953; closes the self-contained halves of ledger F-2026-085 + F-2026-086). `sovereign-safetensors-loader::load`
assembled every model at a hardcoded `Precision::F32` (a 7B model needs ~28GB, undercutting the "local sovereign"
premise) with a hardcoded `Sampler::greedy()` (so temperature/top_p/top_k were unreachable at the model level) —
even though the decoder stack is already precision-heterogeneous and the sampler/quant machinery are built and tested.

- **`sovereign-safetensors-loader`**: `load` refactored into `load_configured(bytes, config, precision, sampler)` plus
  delegating wrappers `load_at_precision` (caller precision, greedy) and `load_with_sampler` (F32, caller sampler).
  `load` keeps its exact signature and defaults (F32/greedy), so all existing call sites are byte-identical. A real
  checkpoint can now load as Ternary/NVFP4/INT8/BF16 in-memory. `Precision` + `Sampler` are re-exported.
- **`sovereign-quant-model`**: new `with_sampler(Sampler)` builder + `sampler()` getter — an assembled model can be
  re-pointed at a warm sampler and introspected (the hook the gateway's future per-request sampling wiring plugs into).
- **Deferred (tracked):** GGUF/pre-quantized-checkpoint dequant (no dequant-from-disk path exists — milestone-scoped)
  and threading per-request HTTP sampling params into `generate_chat` (owned by the parallel Anthropic-Messages-API
  session; this change only provides the model-side hook).
- Also removes two zombie `docs/sdd/INDEX.md` rows (900/901) a `merge=union` re-added for SDD files that had been
  renumbered to 950/951 — the union-merge deletion hazard; the canonical rows are 950/951.


### Fixed — context.md counts-as-contract: the re-orientation surface can't silently drift again (2026-07-12)

Phase-1 audit (SDD-952; closes ledger F-2026-030). `context.md` — the operator's "read me first after every
compaction" surface — was ~6 weeks stale and self-contradictory (it stated both "29 crates" and "476 crates"
while the tree held 714; "17 of 21 dashboards"; "29 SDDs"), despite its own "never silently let it drift" banner.

- **`context.md`**: a new "Current state (2026-07-12 — counts machine-verified)" section at the top (the stale
  "Current arc" header retitled "Historical arc") with a fenced `COUNTS-CONTRACT` block (crates 714 / dashboards
  25 / panels 55 / SDDs 134 / milestones 85, each with its source path) + a recent-arcs summary. The historical
  resume-cycle log below is left intact.
- **`tests/lint/test_context_md_counts.py`**: a new lint that parses the block and asserts every count against
  the live tree — a drift now **fails CI** with a `stated -> actual` diff, so the surface can't rot silently.
- The same pattern is the fix for MASTER-PLAN / mdbook drift (F-2026-032/033), tracked separately.


### Fixed — durable memory is never silently lost: corruption recovery + bounded growth (2026-07-12)

Phase-1 audit (SDD-951; closes ledger F-2026-084 partially). The gateway daemon persists its learning Cortex's
`MemoryStore` to `SOVEREIGN_GATEWAY_MEMORY`, but the load was `from_str(&json).unwrap_or_else(seed_memory)` — any
parse failure (a torn file from a hard kill, a manual edit, a struct-shape change) **silently discarded all
learned memory** and reseeded with no signal; and the store grew unbounded.

- **`sovereign-memory-os`**: new `MemoryStore::set_capacity(Option<usize>)` (sets the bound and evicts the
  lowest-value residents down to it — value-based, needs no clock, can never over-evict) + `capacity()` getter.
- **`sovereign-gatewayd`**: new pure `load_memory_from(path)` — an unparseable store is **moved aside to
  `<path>.corrupt` (atomic rename) and reseeded loudly**, preserving the old bytes for recovery instead of
  discarding them; the store is then capped via `SOVEREIGN_GATEWAY_MEMORY_CAP` (default 4096, `0` = unbounded).
- Backward-compatible on-disk format; zero behaviour change when `SOVEREIGN_GATEWAY_MEMORY` is unset.
- Deferred (Q-901-001): the M028 decay pass stays unscheduled until the admission clock is unified — bounded
  growth already caps accumulation clock-independently. Verified: memory-os 40 tests (2 new), gatewayd lib 55
  (4 new incl. corruption-recovery), clippy `-D warnings` clean, downstream unchanged. MS003 `unsigned-pending-MS003`.


### Fixed — real RoPE: `rope_theta` + `rope_scaling` from the model config (modern models decode coherently) (2026-07-12)

Arc 1 of the Phase-1 audit (SDD-950; closes ledger F-2026-080). Every decoder block was built with a **hardcoded
RoPE base of 10000**, so Llama-3 (500000), Qwen2 (1000000), Mistral etc. decoded as garbage — the single biggest
blocker to running a real model, and it made SDD-205's Anthropic endpoint return gibberish from VS Code / Claude Code.

- **`sovereign-mha-block`**: new `MhaDecoderBlock::with_rope(theta_base, scaling)` builder (additive — existing
  callers/tests untouched) + public `RopeScalingKind` (Linear/Dynamic/Yarn/Llama3) + `RopeScaling`, mapping onto
  `sovereign-rope`'s existing (previously-unplumbed) `with_base` / `ntk_aware_base` / `with_yarn`.
- **`sovereign-safetensors-loader`**: `Config` now parses `rope_theta` (default 10000) + `rope_scaling` (both the
  newer `rope_type` and older `type` key), resolves it, and threads it into every block. Unknown scaling type ⇒
  base-theta only (never a fabricated scaling, never a parse failure — SB-077).
- Honest partial support: YaRN without a known original context, and the llama3 frequency ramp, fall back to the
  correct base theta (the dominant win) rather than fabricating a scaling.
- Verified: mha-block 28 tests (8 new, incl. "a distinct base yields distinct decode output"), loader 13 (6 new);
  clippy `-D warnings` clean; downstream quant-llm/gatewayd/decoder-layer/inference-demo build unchanged. Sampling
  params + chat template + quantized loading are the tracked next arcs. MS003 `unsigned-pending-MS003`.
### Added — Compute Plane Phase 2, increment 4: the Code Console UX loop — the model registry reaches the chat (2026-07-12)

The multi-model registry + the `"background"` alias become visible and usable from the operator's actual chat
surface (the Code Console). SDD-902.

- **The OpenAI shim is now a full peer of the Anthropic surface.** The Console chat rides `prompt.py` → the
  gateway OpenAI shim (`/v1/chat/completions`), which now **expands the `"background"` alias** and **routes GPU
  proxies**: an `openai`-dialect backend's SSE is relayed verbatim (`stream_proxy_chat_completions`), an
  `anthropic`-dialect proxy is an honest error pointing at `/v1/messages`. So `"background"`-that-resolves-to-a-
  proxy no longer silently falls back to the primary. The proxy transport is factored into shared
  `open_proxy_stream` / `next_proxy_block` helpers used by both streaming paths.
- **`GET /v1/models` reports the `background` target** so a UI can show where the alias points.
- **Console wiring.** `code-console-api` gains a read-only `GET /api/code-console/models` (proxying the gateway
  registry) and threads a `model` id from the chat body into the inference runner. The webapp composer gains a
  **Model picker** (primary / secondaries / GPU proxies / the `"background"` alias / `auto`) + a live "N models
  loaded · background → …" status, and sends the chosen model on every chat; it degrades to `auto` offline.
- Verified: a transport test streams a proxy through the OpenAI shim; an http test asserts `GET /v1/models`
  reports the background target; a jobs-runtime test locks the console-api proxy + composer wiring. 16 transport +
  62 lib+http + 15 jobs-runtime tests; clippy `-D warnings` clean.

### Added — Compute Plane Phase 2, increment 2b: streaming to a GPU proxy (VS Code / Claude Code stream from GPU-hosted models) (2026-07-12)

Editors stream by default, so this is what makes a GPU-hosted model actually usable from them. SDD-902.

- A `stream:true` request for a proxy model now opens a streaming connection to the upstream serve-process and
  **transcodes its SSE into the Anthropic event sequence as tokens arrive** (`stream_proxy_message`) — replacing
  the increment-2 honest-error gate.
- An `openai` backend's `/v1/chat/completions` deltas become `content_block_delta` events (dechunking
  `Transfer-Encoding: chunked`, as llama-server / vLLM emit); an `anthropic` backend's SSE is relayed verbatim.
  A pre-stream upstream failure is an honest Anthropic error; a client hang-up mid-stream ends the relay cleanly.
- Verified end-to-end: a mock chunked OpenAI-SSE upstream registered as a proxy → `POST /v1/messages {stream:true}`
  yields `message_start → content_block_delta* → message_stop` with the transcoded text + `stop_reason:end_turn`.
  15 gateway transport tests (1 new); clippy `-D warnings` clean.

### Added — Compute Plane Phase 2, increment 3: background routing — work targets the secondary, the primary stays free (2026-07-12)

The routing that makes the two backend kinds usable as background compute. SDD-902.

- **The reserved `"background"` model alias.** A request for `model: "background"` (Anthropic `/v1/messages`, the
  OpenAI shim, or `/v1/coat`) routes to a *designated* secondary — CPU resident or GPU proxy. `set_background` /
  `background_id` / `expand_alias` on the gateway; NEW `POST /v1/models/background {id}` designates it (loopback-
  trust), seeded from `SOVEREIGN_GATEWAY_BACKGROUND_MODEL`. **Honest fallback:** a designated-but-unloaded id (or
  none) resolves to the primary, never a dead id. `expand_alias` runs at every entry point (message, streaming,
  and inside `generate_chat`), so the alias targets the same backend whichever kind it is.
- **Background deliberations run on the secondary.** `GatewayRequest::Coat` + the `/v1/coat` body carry an
  optional `model`; `ModelThoughts` expands the reasoning through it. The jobs-api deliberation runner sends
  `model: "background"` by default (override via `meta.model`), so a background CoAT job keeps the interactive
  primary responsive — falling back to the primary when nothing is designated.
- Verified: gateway lib/http tests (alias designates + falls back on unload, `POST /v1/models/background` reports
  `active`, a `model:"background"` message reaches the designated proxy end-to-end, `/v1/coat` accepts the hint) +
  a jobs-runtime test asserting the deliberation sends the `"background"` alias. 62 gateway lib+http + 14 jobs-
  runtime tests; clippy `-D warnings` clean.

### Added — Compute Plane Phase 2, increment 2: a GPU serve-process backend the gateway proxies to (2026-07-12)

The second backend kind (option c): a real large model runs on the RTX PRO 6000 / VFIO-passed 4090 while the
CPU primary keeps serving interactive chat. SDD-902.

- **Gateway proxy registry.** `ProxyBackend { endpoint, device, vram_gb, dialect }`; `register_proxy` /
  `resolve_proxy`; `unload_model` removes proxies too; `GET /v1/models` now reports each resident's `device` +
  `vram_gb`. NEW `POST /v1/models/register {id, endpoint, device?, vram_gb?, dialect?}` (loopback-trust).
- **Dialect translation.** llama-server / vLLM speak OpenAI `/v1/chat/completions`, not Anthropic — so an
  `openai`-dialect backend has the Anthropic `/v1/messages` request translated (`anthropic_to_openai_chat`) and
  the reply mapped back (`openai_to_anthropic_message`: content, stop_reason, usage); an `anthropic`-dialect
  backend (another sovereign-gatewayd) is forwarded verbatim. Two http tests (mock Anthropic + mock OpenAI
  upstreams) prove both paths. Streaming to a proxy is honestly gated (retry non-streaming), never silently
  served by the primary.
- **`model-serve` job kind** (jobs-api). A VRAM-needing job: the compute plane PLACES + CLAIMS the device, the
  runner launches the serve-process argv (`meta.command`, no shell), waits for `meta.endpoint` to accept
  connections (bounded, degrade-safe), registers the gateway proxy on the ACTUAL placed device, stays running
  until cancelled; on ANY exit it terminates the process + unregisters the proxy, and run_job's `finally`
  releases the plane claim — no leaked VRAM or stale proxy.
- Verified LIVE (mock gateway + mock serve process): place → launch → register on `gpu0` → cancel → unregister →
  the plane frees the claim. 60 gateway lib+http tests (2 new proxy tests) + 13 jobs-runtime tests (1 new
  model-serve integration test); clippy `-D warnings` clean.

### Added — Compute Plane Phase 2, increment 1: the gateway hosts a secondary model (2026-07-12)

Operator-directed (the Background Tasks "massive" pass, option c). The gateway's own generator is CPU, so
"a secondary model" is two backend kinds under one registry (in-gateway CPU + GPU serve-process proxy) over
the shared plane. Increment 1 ships the in-gateway CPU multi-model registry. SDD-902 (the shared general 900 band; renumbered from 900 to avoid a collision with a parallel general-session's SDD-900/901).

- The gateway's single `generator` becomes a **registry**: a primary + an `RwLock` map of secondaries. A
  generation clones the resident `Arc` and releases the registry, so different models run concurrently, the
  same model serialises, and load/unload never blocks an in-flight request.
- `generate_chat(model, …)` **routes** by model id (a named secondary else the primary); all four call sites
  pass it; the **safety spine** (injection screen + secret/PII redaction) is preserved on every route.
- NEW `POST /v1/models/load {id, dir}` + `POST /v1/models/unload {id}` (loopback-trust operator actions);
  `GET /v1/models` now lists the **loaded** residents. A bad dir is an honest Anthropic 422, never a fabricated
  model.
- The shared VRAM authority (SDD-207): jobs-api `POST /plane/{place,claim,release}` — so model residents and
  GPU jobs claim from ONE view and never double-book (CPU residents claim no VRAM).
- Verified LIVE with a real model: `/v1/models` → load `fast` → `[primary, fast]` → a `{"model":"fast"}` message
  routed to the secondary → unload → `[primary]`. 53 lib + 4 bin + 14 transport tests; clippy clean.
- Honest gating: increment 1 is CPU-scale; big GPU models are increment 2 (a plane-placed llama-server/vLLM
  serve process the gateway proxies to), where the shared-plane authority becomes load-bearing.

### Added — the gateway safety spine: input screening + output redaction, made real on the daemon (2026-07-12)

First chunk of the Phase-1 audit's Arc 2 (SDD-206; closes ledger F-2026-081 + F-2026-082). The running
`sovereign-gatewayd` now enforces the Privacy + Redaction responsibilities the M048 gateway declares — previously
those crates were built and tested but wired only into the non-daemon `sovereign-serve`, so the daemon did none of it.

- **Safety spine wired into `generate_chat`** (the single chokepoint behind all four generation surfaces — OpenAI
  + Anthropic, stream + non-stream): input prompts screened for injection (`sovereign-injection-detect`); generated
  output redacted for secrets (`sovereign-secret-scan`) + PII (`sovereign-pii-redact`) and scored for toxicity
  (`sovereign-toxicity`, flag-only, never censors). `GuardConfig` is env-resolved, secure-by-default; injection
  *blocking* is opt-in (fail-open) so a false positive never silently swallows a prompt.
- **`StreamGuard`** — a cross-decode-chunk-safe streaming redactor: holds back a 256-byte window and releases only
  to the last ASCII-whitespace boundary, so a secret split across two generated chunks is caught before any byte
  leaves the box. Bounded memory; guard-disabled ⇒ exact legacy passthrough.
- **Transport hardening**: bearer auth (`SOVEREIGN_GATEWAY_TOKEN`, constant-time compare, `401` else — the minimum
  gate for a non-loopback bind); per-connection read/write deadline (`SOVEREIGN_GATEWAY_TIMEOUT_SECS`, default 30s,
  bounds slow-loris); honest over-capacity back-pressure (HTTP `503` + `Retry-After` / NDJSON error line instead of
  a silent drop).
- **Observability**: `/metrics` gains `sovereign_gateway_guard_{injections,redactions,enabled}`.
- Verified: `cargo test -p sovereign-gatewayd` (lib 51 incl. 11 new spine tests, main 4, transports 14), clippy
  `-D warnings` clean, fmt clean. TLS deferred (SDD-206 non-goal). MS003 `unsigned-pending-MS003`.
### Added — the Sovereign Compute Plane, Phase 1: a GPU job never OOMs the box (2026-07-12)

Operator-directed (the Background Tasks "massive" pass — "my rtx4090 jobs or a secondary model in general …
lets discuss and plan"). Discussed + planned: ONE compute plane placing both background models and GPU jobs
across the host PRO 6000 + the VFIO-passed 4090/3090 by live VRAM. A 4-phase roadmap was approved; this is
**Phase 1** (the plane core). SDD-207.

- NEW `scripts/operator/lib/compute_plane.py` — extends the M075 SRP doctrine (Conductor=CPU, Logic=4090,
  Oracle=PRO 6000; fit by precision + VRAM) from static capacities to **live free VRAM**. Probes host GPUs via
  `nvidia-smi`, tracks **claims** (a device + VRAM held for a job's life), and `place(need_gb, role_pref)`
  returns a device whose effective free VRAM (live − claims) covers the need (prefer role, else wait); a
  no-VRAM job → the CPU. Degrade-safe (no `nvidia-smi` → CPU-only; a GPU job honestly waits, never fabricates).
- `jobs-api` (SDD-204) now **places a `meta.vram_gb>0` job before it runs** — it waits (`queued`, "waiting for
  N GB free VRAM…") until a device fits, claims it, runs, and releases on completion. So a GPU job **never OOMs
  the box**; concurrent GPU jobs serialise by VRAM. NEW `GET /plane.json` + `sovereign-osctl plane` (read-only
  devices + claims); feature-coverage maps `plane → code-console`.
- `tests/lint/test_jobs_runtime_contract.py` extended: fit-by-live-VRAM (a 40 GB model excludes the 24 GB
  Logic; a claim removes headroom → queue), the CPU-only degrade, and jobs-api queues-not-OOMs a job when VRAM
  is exhausted (and keeps it cancellable while waiting). Verified live (`/plane.json` + `sovereign-osctl plane`).
- Honest gating: the canonical rule is the Rust `sovereign-srp-scheduler::place()` (Phase 2 wires the gateway
  for model residents); the 4090 is VM-isolated so Phase 1 sees host devices only (Phase 3 adds the VM); the
  wait holds a worker (a Phase-4 admission scheduler refines it).

### Added — user documentation: "Use the box as your AI backend" + "Reasoning & operability" (2026-07-12)

Operator-directed ("we need to do the documentation too"). The session's features had design docs (SDDs) but
no user-facing guide. Two new mdBook chapters, integrated into the existing book + README (not a new system).

- NEW `docs/src/ai-backend.md` — run the gateway + load a model; wire **VS Code (Cline/Claude Dev)**, **Claude
  Code (`ANTHROPIC_BASE_URL`)**, and the **Anthropic SDK**; the OpenAI-shim alternative; a full **gateway
  endpoint reference** (`/v1/messages`, `/v1/models`, `/v1/messages/count_tokens`, `/v1/chat/completions`,
  `/v1/infer` decision, `/v1/simple`, `/v1/explain`, `/v1/deliberate`, `/v1/coat`, health/manifest/ledger/metrics)
  with curl examples; and the sovereign posture (loopback-trust, never-fabricated, no cloud spill, model-gated).
- NEW `docs/src/reasoning-operability.md` — the CoT→ToT→MCTS→C-MCTS→CoAT ladder + `/v1/coat`; the Brain
  observatory (`/brain/`); Background Tasks (the jobs runtime + `sovereign-osctl jobs` + the 4090-VM bridge);
  the Code Console (the unified questions/plans/tasks/reasoning surface); and the interaction doctrine.
- Registered both in `docs/src/SUMMARY.md` (new "Using the box" section) + linked from `README.md`'s "Where to
  read next"; cross-linked the design SDDs (205/204/112/011) + the standing directives.
- NEW `tests/lint/test_ai_backend_docs_contract.py` guards the pages exist, are registered + linked, cover the
  load-bearing content (editor wiring, the endpoint reference, the ladder, tasks, the console), and that every
  relative link in them RESOLVES (no broken cross-links).

### Added — the Anthropic Messages API on the gateway: use the box from VS Code / Claude Code (2026-07-12)

Operator-directed ("make it compatible with Anthropic Messages API structure, so I can use it in vscode and
whatever else compatible"). `sovereign-gatewayd` (:8787) now speaks the **Anthropic Messages API**, so VS Code
extensions (Cline / Claude Dev), Claude Code (`ANTHROPIC_BASE_URL`), and the Anthropic SDKs drive the box's
OWN local model on loopback. Fulfils the pre-existing M034 "Anthropic-first" spec (`/v1/messages` had been a
decision stub). SDD-205.

- **`POST /v1/messages`** is the Anthropic Messages API: accepts `{model, max_tokens, system?, messages[],
  stream?}` (content a string OR a `[{type:"text",text}]` block array), generates from the local model, and
  returns the Anthropic shape — non-stream `{type:"message", role:"assistant", content:[{type:"text",text}],
  stop_reason:"end_turn", usage:{input_tokens,output_tokens}}` OR, on `stream:true`, the SSE event sequence
  `message_start → content_block_start → content_block_delta(text_delta)* → content_block_stop → message_delta
  → message_stop` (intercepted in main.rs like the OpenAI shim; non-stream in http.rs).
- NEW **`GET /v1/models`** (Anthropic models list) + **`POST /v1/messages/count_tokens`**.
- The sovereign routing **DECISION** that `/v1/messages` used to return moved fully to **`/v1/infer`**
  (`{kind:"decision"}`); the OpenAI shim `/v1/chat/completions` stays as the secondary compat surface.
- **Loopback-trust** (`x-api-key` / `anthropic-version` accepted, not validated — no cloud auth on a sovereign
  box); **never fabricated** (no model → an honest Anthropic error envelope 503, SB-077); the requested model
  id is echoed back, the box serves its one local model.
- **Verified LIVE end-to-end with SmolLM-135M:** non-stream returned the Anthropic message shape; `stream:true`
  emitted the full Anthropic SSE token-by-token. Output *quality* is model-gated (a base model rambles; a
  stop-sequence + instruct model is a follow-up), but the *compatibility* the editors need is complete.
- NEW `docs/sdd/205-anthropic-messages-api.md` (mission + wiring how-to for VS Code / Claude Code / Cline) +
  `tests/lint/test_anthropic_messages_contract.py`; the gateway lib + transport tests were repointed.

### Changed — the Code Console, brought to a high standard: the Plan pane goes live and unifies questions / plans / tasks / reasoning (2026-07-12)

Operator-directed ("make sure the console is fully developed and proper relative to everything — questions /
plans / background tasks — aim for high standards"). The console had the pieces but they didn't cohere: the
Plan pane was a static placeholder while Plan Mode rendered plans only in chat and a background deliberation
threw its reasoning away. Now the Plan pane is the live home for "what the AI is thinking right now" (SDD-204).

- The **Plan pane is live**: it mirrors the **active Plan-Mode plan** from the conversation (summary + numbered
  steps + the four approvals, which feed back to the chat), and renders a clicked deliberation's **CoAT
  reasoning trace** (a mini observatory: per-step category, backpropagated value, ↑ recall-lifted, recalled
  memory). The header reflects its mode — plan / reasoning / artifact. Artifacts + repo chips stay honest-
  deferred (SB-077) until a producer lands.
- **Deliberation jobs now keep the full compact trace** (best_path + values + recall), not just a summary line
  — so a finished background deliberation is clickable and its reasoning renders in the pane, and can be
  **brought into the conversation** as a turn.
- Background Task rows for deliberations are clickable ("◔ reasoning"); everything stays R10212 (reads + the
  one chat POST; submit/cancel are copied osctl verbs) and DEMO-safe (a demo trace ships).
- **Fixed** a latent bug: a Plan-Mode card whose question carried raw newlines (the numbered steps) failed
  `JSON.parse` and rendered as a `<pre>` fallback instead of an interactive card. A lenient `parseAUQ` now
  escapes raw control chars in an otherwise-compact envelope, and the DEMO plan card's steps are properly
  escaped — so questions AND plans render interactively in the console. The same lenient `parseAUQ` was
  applied to the other two chat surfaces (the Sovereign Brain observatory + lm-status), so a real model
  emitting raw-newline plan cards renders interactively there too; `test_all_chat_surfaces_render_auq_interactively`
  now asserts the lenient parse + a no-stray-control-bytes guard on all three panels.
- `tests/lint/test_code_console_webapp_contract.py` gains `test_plan_pane_is_live_for_plans_and_reasoning`;
  the scaffold contract tracks `renderPlanPane()`.

### Added — Background Tasks: a job runtime + a Code Console Plan-pane split, like claude.ai/code (2026-07-12)

The box now runs long-running work OFF the request path and shows it in a supplementary pane that splits the
Code Console's right Plan pane 50/50 — a background CoAT deliberation, a model eval, a secondary-model load, a
GPU job, and jobs mirrored from the RTX-4090 passthrough VM (operator-directed; plan approved: runtime +
Plan-pane split + 4090-VM bridge). SDD-204.

- NEW `scripts/operator/lib/jobs_store.py` — a PERSISTED job registry (atomic temp+rename → survives restart)
  with create/update/list/ingest/prune + a summary.
- NEW `scripts/operator/jobs-api.py` (:8142) — the runtime: a bounded worker pool drives a job
  queued→running→(done|failed|cancelled) with live progress. Kinds: `deliberation` (calls the gateway
  `/v1/coat`), `eval`/`model-load`/`gpu-job` (a no-shell subprocess runner with PID-tracked cancellation),
  `demo`, and `vm-job` (mirrored from the VM, not host-run). Orphaned `running` jobs are marked failed on
  restart — never a zombie. Read endpoints feed the pane; submit/cancel/ingest are the runtime control surface.
- NEW `sovereign-osctl jobs list|status|submit|cancel` (`scripts/operator/lib/jobs_cli.py`). `list`/`status`
  are read-only; **submit/cancel are the ACTIONS** the cockpit routes through the sanctioned `control-exec-api`
  — the pane never POSTs a mutation (R10212), it copies the signed osctl verb.
- The **Code Console Plan pane splits 50/50** (`webapp/code-console/`): Plan/artifact on top, a live
  **Background Tasks** list below (state · progress · kind · device · cancel), fed by a read-only
  `code-console-api` proxy `/api/code-console/jobs`. A header toggle shows/hides it (persisted); "＋ deliberate"
  and per-task cancel copy the `sovereign-osctl jobs …` verb; graceful when the runtime is down; DEMO-safe
  (zero network in DEMO — SB-077).
- NEW `scripts/jobs/vm-bridge-guest.py` — the **4090-VM bridge**: runs inside the VFIO passthrough VM, probes
  its `nvidia-smi`, and POSTs entries to the host `jobs-api` `POST /jobs/ingest` (upserted as `vm-job` rows), so
  the host cockpit sees jobs on the passed-through GPU.
- NEW `systemd/system/sovereign-jobs-api.service` (R171-hardened; jobs dir read-write). feature-coverage maps
  `jobs → code-console`. `tests/lint/test_jobs_runtime_contract.py` guards the registry, the worker lifecycle,
  cancellation, graceful failure without a gateway, the surfaces, the unit, and the bridge.
- Honest gating (SB-077): runtime + pane + CLI + ingest are live and tested; the guest→host **channel** for the
  VM bridge (libvirt NAT gateway / vsock, via `SOVEREIGN_JOBS_HOST`) is the deployment step and is inert until
  wired — and says so.

### Changed — reasoning engine hardened: an adversarial review found the mechanics were presets/labels; made them real (2026-07-12)

A "push it to the limits" review (three independent adversarial reviewers + live verification) found the
search *harness* was correct but several reasoning *mechanics* were presets/labels, and the CoAT centerpiece
was inert in production (recall *lifted* values but did not *steer* which path won). Every finding is now
closed — the ladder rungs are behaviourally distinct:

- **CoAT now steers, not just lifts.** `CortexRecall` keys recall on the **per-thought** `ctx.text`
  (FNV-1a sketch OR'd with the problem sketch), not only the problem — so different thoughts recall
  different memory and recall can change which path wins. Relevance now uses an **absolute** `rel/(rel+K)`
  scale so a weak hit stays weak (the old within-batch-max faked maximal support). Recall also conditions
  thought **generation** (RAG). Proven by `coat_recall_steers_the_winning_path` + a normalization test.
- **Simulation is a real look-ahead rollout** to `max_depth` (not a one-step value relabeled "playout").
- **Backtracking is real** — a thought below `prune_below` is abandoned and its M007 branch pruned during
  the search; the trace reports `abandoned` / `branches_committed` / `branches_pruned`.
- **ToT offers real BFS and DFS** search strategies (`SearchStrategy`), not only UCT.
- **C-MCTS is load-bearing** — categories are phase-gated per depth, so constraining changes the search;
  there is a `cmcts()` preset and a "C-MCTS" rung. `rung()` is now behavioural (can't mislabel).
- **Model-backed thoughts when a model is loaded** (`ModelThoughts` via the generator); the trace's new
  `thought_source` field says `"model"` vs `"heuristic"`, and the panel shows a chip — placeholders are
  never passed off as reasoning. The `expand()` seed set is truncated to `expand_k` (protects the CoT
  chain invariant); degenerate configs are rejected.
- **Defects fixed:** brain-api now surfaces a gateway 4xx (e.g. a bad rung) as its **structured message**
  instead of "unreachable"; `now`/`half_life` are caller-supplied (not a frozen constant); the `dry_runs`
  metric/doc now names all four read-only ops; `esc()` escapes single quotes; the read-only-memory invariant
  is asserted (`learned==0`, `dry_runs>=1`). The directive's overstatements (BFS/DFS, the `value-plane`
  mapping, "external" info, C-MCTS as a rung) are corrected to match the code.

### Added — the CoAT engine: one parameterized MCTS that IS the whole reasoning ladder, recalling the live Memory-OS (2026-07-12)

Increment 2 of "both, sequenced": the runtime that makes the reasoning progression real. `sovereign-coat`
is a single iterative-MCTS engine over the M007 branch tree, and the earlier rungs fall out as presets —
CoT (`expand_k = 1`), ToT (branch, greedy), MCTS (UCT select/expand/simulate/backprop), C-MCTS (a bounded
five-category action space), and **CoAT** (the default): every expansion recalls associative memory that
modulates the thought's value. The two model-gated inputs are traits (`ThoughtSource`, `AssociativeMemory`),
so the search harness is deterministic + fully tested without a model; only the thought *content* is
model-gated.

- NEW crate `sovereign-coat` — the engine (`CoatEngine`, `CoatConfig::{cot,tot,mcts,coat}`, `ThoughtCategory`,
  `CoatTrace`). 8 unit tests prove each rung, the UCT/backprop invariants (root visits == budget; parent
  dominates child), the constrained action space, determinism, and — the centerpiece — that **recall lifts
  a memory-supported thought onto the winning path** while an equal-prior bare thought does not. Clippy
  `-D warnings` clean.
- The gateway exposes **`POST /v1/coat`** (`GatewayRequest::Coat` → `CoatTrace`), running the engine with the
  daemon's **live Cortex Memory-OS as CoAT's associative memory** (`CortexRecall` adapter over the new
  `Cortex::recall`). Read-only: it decides without learning (only the dry-run counter moves). A heuristic,
  model-free `ThoughtSource` makes the search + recall demonstrable today; a model-driven source replaces it
  when a generator is loaded. Verified live: a CoAT deliberation recalls 128 items from the seeded store and
  the recall boosts each step's value above its bare prior.
- The Sovereign Brain observatory gains a **CoAT deliberation** card (`/brain/coat` in `brain-api.py`,
  `webapp/brain/`): pick a rung, deliberate, and watch the winning reasoning chain with each step's
  backpropagated value vs prior, visit count, and the memory recalled there (↑ marks a memory-lifted thought).
- `tests/lint/test_deliberate_reasoning_contract.py` extended: the crate is the whole ladder, the gateway
  endpoint runs over the live memory, and the observatory surfaces it.

### Added — deliberate reasoning: the CoT → ToT → MCTS → C-MCTS → CoAT progression, mapped onto the box's own primitives (2026-07-12)

Third in the reasoning/interaction trilogy after QCFA (align on intent) and Plan Mode (review the plan):
this codifies how the AI *thinks* — deliberate, search-based reasoning instead of a single reactive pass.
The sovereign thesis: each rung of the ladder already maps onto a real execution primitive, not a borrowed
metaphor. Increment 1 of "both, sequenced" — the directive + scaffold posture; the `sovereign-coat` engine
follows.

- NEW standing directive `docs/standing-directives/2026-07-12-deliberate-reasoning.md` (registered in
  INDEX) — maps **CoT** → a single `Cortex::act` path, **ToT** → `sovereign-branch-tree`
  (fork/commit/prune/lineage) + `sovereign-value-plane` scoring, **MCTS** → the same tree + the value-plane
  "MCTS + PRM" critic + backprop over `lineage()`, **C-MCTS** → the cortex's bounded `NextAction` /
  constrained routing categories, and **CoAT** (the centerpiece) → `Cortex::deliberate` forking branches
  against the **recalled** context where "recalled memory modulates the reward" — the Memory-OS `retrieve()`
  IS CoAT's associative memory. Honest gating: the search harness ships + is tested today; useful thoughts
  are model-gated.
- The reasoning scaffold (`config/prompts/qcfa-system-prompt.md`) gains a **DELIBERATE REASONING** posture:
  CoT (reason step by step, show your work) for the routine, branch-and-backtrack ToT for the genuinely
  hard, and always recall before concluding (CoAT).
- `tests/lint/test_deliberate_reasoning_contract.py` guards the progression, the primitive mapping, that
  the mapped crates actually exist, and the scaffold posture.

### Added — Plan Mode presented for approval in the cockpit (2026-07-11)

Completes the plan → approve flow: the sovereign AI proposes a PLAN (summary + numbered steps) and
presents it for approval, reusing the interactive-clarification rendering already on every chat surface.

- The scaffold (`config/prompts/qcfa-system-prompt.md`) now instructs Plan Mode: for a mutating /
  consequential task, propose a plan inside the ` ```askuserquestion ` envelope with the four approvals
  as options (Approve / Reject / Approve with changes / Approve and remember), holding execution until
  approved. So the plan renders as a clickable card on code-console, the Sovereign Brain panel, and
  lm-status — no new UI. A destructive step is auto-blocked by Auto regardless.
- The AUQ question class now preserves newlines so numbered plan steps render as lines; the
  code-console DEMO thread shows a live plan card.

### Added — Plan Mode + User Approval + Auto-mode safety classifier (2026-07-11)

Companion to the QCFA framework: where QCFA aligns on intent before acting, this reviews the plan
before executing. The AI proposes a plan and holds execution; the operator Approves / Rejects /
Approves-with-changes / Approves-and-remembers; permission modes (manual/auto/bypass) control how
often it stops; and an Auto-mode safety classifier auto-blocks destructive ops. Built on
sovereign-os's existing approval gates. One framework, two homes.

- NEW standing directive `docs/standing-directives/2026-07-11-plan-mode-user-approval.md` (registered
  in INDEX) — canonical for both the local sovereign AI and external agents/operators.
- NEW `scripts/operator/lib/permission_classifier.py` — the Auto-mode safety classifier: classifies a
  command destructive / routine / unknown and decides allow / block / confirm per mode. **manual** →
  confirm mutating (destructive flagged DANGER); **auto** → BLOCK destructive, allow routine, confirm
  unknown; **bypass** → allow. Destructive families: `rm -rf`, `dd of=/dev/*`, `mkfs`/`wipefs`, `nvme
  format`, `zpool`/`zfs destroy`, force-push, `git reset --hard`, fork bomb, `curl|sh`, `poweroff`, …
  Extensible via config; stdlib-only; tested.
- NEW `config/permission-modes.yaml` — the modes + the 4 approvals + the operator-tunable
  `destructive_extra` extension point. `SOVEREIGN_OS_PERMISSION_MODE` (default manual).
- `control-exec-api` (the ONE sanctioned execute daemon) now consults the classifier under the active
  mode: **Auto BLOCKS a destructive control (403) before it reaches the primitive**; the verdict rides
  on every response. Layers onto the existing dry-run-default + operator-key + type-to-confirm gate.
- NEW osctl verb `sovereign-osctl permission [--mode …] <command>`; `tests/lint/test_plan_mode_contract.py`
  guards the directive, config, classifier decisions, and enforcement.

### Added — interactive clarification across every chat surface (2026-07-11)

Extends the QCFA/AUQ interactive rendering (first shipped on the code console) to the other chat
surfaces, so the thinking-partner behaviour is consistent everywhere.

- The **Sovereign Brain panel chat** (`/brain/`) and **lm-status (D-22)** chats now detect the fenced
  ` ```askuserquestion ` envelope and render clickable options + a free-text "Other", feeding the
  picked answer back as the next turn — graceful `<pre>` fallback if unparseable. The brain chat also
  gained a small in-page history so a clarification answer continues the thread.
- `tests/lint/test_qcfa_framework_contract.py` now asserts ALL chat surfaces (code-console, brain,
  lm-status) render AUQ interactively. The renderers are functionally verified (node); full lint green.

### Added — QCFA + interactive-clarification framework (2026-07-11)

Codifies the operator's directive to make AI an interactive thinking partner (not a typewriter):
QCFA (Task / Context / References / Framework-Evaluate) + AskUserQuestion (hold execution, interview)
+ suggestions. One framework, two homes.

- NEW standing directive `docs/standing-directives/2026-07-11-qcfa-interactive-clarification.md`
  (registered in INDEX) — the canonical interaction model for BOTH the local sovereign AI (the
  gateway model + agent-runtime + chat surfaces) AND external agents/operators working on the repo.
- NEW reusable scaffold `config/prompts/qcfa-system-prompt.md` — the QCFA/AUQ system prompt: structure
  intent; hold execution + ask 1–4 decision-shaped questions + suggest; iterate; then execute.
- `scripts/inference/prompt.py` injects the scaffold as a leading `system` turn, OPT-IN via
  `SOVEREIGN_OS_QCFA` (default off, so a base completion model's chat is never degraded; recommended
  on once a capable instruct model is loaded). Never double-injects over a caller-supplied system
  turn; every chat surface routes through it, so one switch applies everywhere. The 20 prompt tests
  stay green.
- The scaffold has the model emit questions in a machine-parseable envelope (a fenced
  ` ```askuserquestion ` JSON block), and the **code console renders it interactively**: the chat
  (`webapp/code-console/index.html`) parses the block into clickable options + a free-text "Other"
  and feeds the picked answer back as the next turn — a graceful `<pre>` fallback if unparseable, so
  a question is never raw-swallowed. The DEMO thread shows a live card. This is the difference
  between a thinking partner and raw text.
- `tests/lint/test_qcfa_framework_contract.py` guards the directive, the scaffold + its envelope, the
  opt-in wiring, and the console's interactive rendering.

### Added — Sovereign Brain refinements: second-brain browser, cross-links, memory controls (2026-07-11)

Three follow-ups closing out the brain panel's observability + operability.

- **The second brain is now browsable.** The panel showed the Rust cortex memory in full but the
  Python Memory-OS only as a summary; it now renders the operational entries (id / type / stage /
  state / summary) as a table beside the cortex store — the two brains, side by side.
- **One clear home.** The `trinity` + `d-03-model-health` "Live Gateway" strips now link to the
  Sovereign Brain observatory (framed as summaries), so there is a single detailed home.
- **Memory lifecycle from the panel.** The CLI-gated Memory-OS controls (forget / undo / decide /
  request; SDD-052/059) are surfaced on the brain panel via the control-surface — copy-able,
  refuse-by-default, mutation stays CLI (`applies_to: […, brain]`). Contract-asserted.

### Added — read-only routing probe: preview without polluting memory (2026-07-11)

The Sovereign Brain panel's routing probe sent `/v1/simple`, which LEARNS — so every probe grew the
brain's memory. This adds a read-only decide path so previewing is side-effect-free.

- NEW gateway endpoint **`POST /v1/simple-explain`** — the read-only sibling of `/v1/simple`: it
  decides via `Cortex::act` (tick + execute, both `&self`) and returns the FULL decision
  (route/device/verdict/summary) with `learned: false`. No memory admit and no request/learned ledger
  movement — only the honest `dry_runs` counter (`GatewayServer::decide` + `GatewayRequest::SimpleExplain`).
- `brain-api.py`'s routing probe now POSTs `/v1/simple-explain`, and the panel labels it a read-only
  preview. Proven: 3 probes left memory unchanged (2 → 2); a control `/v1/simple` then grew it (2 → 3);
  ledger `dry_runs 3, learned 1, total_requests 1`.
- Rust unit test `simple_explain_decides_without_learning`; the brain contract asserts the probe uses
  the no-learn endpoint.

### Added — the Sovereign Brain panel: observe + operate the intelligence layer (2026-07-11)

The earlier cockpit work bolted a status *strip* onto trinity/model-health — a tripwire, ledger
counters, and a memory *count*. That is not observing the brain, and it left the crates nebulous.
This is the dedicated observatory + console: you look INTO the brain and drive it.

- NEW `scripts/operator/brain-api.py` (port 8141) — read-only over the gateway's read surfaces + a
  non-mutating decide/chat compute; reuses `gateway_probe`. Endpoints: `/brain.json` (status +
  memory summary + daemon map), `/brain/memory` (the DECODED cortex store — every hot meta's CoALA
  type / trust / value / freshness / flags + its cold ground-truth episode·summary·facts — beside
  the Python Memory-OS operational store), `/brain/route` (a 7-axis decide probe), `POST /brain/chat`
  (streamed from the :8787 OpenAI shim), `/brain/daemons` (the 9-daemon crate map). Forget/clear stay
  CLI-gated (SDD-052).
- NEW `webapp/brain/index.html` — a full contract-compliant panel: the **memory browser** (the
  actual learned memories, not a count; both stores side by side), live gateway telemetry + the
  never-cloud-spill tripwire, a **routing probe** (pick the 7 axes → watch the brain decide, and
  learn), inline **chat** with the local model, and the **daemon/crate map** that de-nebulizes the
  layer. Demo-capable.
- Wired in: `sovereign-brain-api.service`, a `dashboard-catalog` entry + app-shell nav entry (slug
  `brain`, category trinity), the demo manifest, the app-shell/controls-audit baselines, and
  `tests/lint/test_brain_panel_contract.py`. Full lint green (5924); the panel serves live and its
  feeds decode real memory + stream real generation.

### Added — the compiled brain ships in the image: host-copy bake path (2026-07-11)

A freshly flashed SAIN-01 can boot with the sovereign brain already compiled + enabled (and
optionally a model), so it generates out of the box — no first-boot compile.

- **Host-copy staging (not in-container).** The bake has no external network (snapshot mirror only)
  and apt cargo predates the pinned 1.89, so rustup cannot fetch the toolchain there — an
  in-container build is impossible. So `scripts/build/07-image-build.sh` builds the intelligence
  layer on the BUILD HOST (rustup 1.89) and stages the daemon binaries into
  `mkosi.extra/usr/local/bin` (`stage_intelligence_binaries`) — the same "staged from the build
  host" pattern as Claude Code. The binaries link only glibc/libm/libgcc, so they run in the image
  with zero added packages.
- **Optional baked model.** `stage_intelligence_model` fetches a small real model (default
  SmolLM-135M) into `mkosi.extra/var/lib/sovereign-os/models/…` so the gateway generates on first
  boot.
- **Auto-start.** `provision-bake.sh` installs + enables `sovereign-gatewayd.service` when the
  binary was staged (guarded so a source-only image never enables a unit with no `ExecStart`).
- Gated on opt-in knobs `SOVEREIGN_OS_BAKE_INTELLIGENCE` + `SOVEREIGN_OS_BAKE_MODEL` (env, dry-run
  safe). Absent ⇒ the image ships source and builds the brain at provision time (the prior
  behaviour). Verified: `SOVEREIGN_OS_RUST_BINDIR=<stage> build-intelligence.sh` stages all 9
  daemons; the gatewayd binary is glibc-only portable.

### Added — the gateway generates: OpenAI chat shim on :8787 + the cockpit talks to the brain (2026-07-11)

`sovereign-gatewayd` stops being a pure decision surface and becomes a local generation brain: it
loads real weights + a real tokenizer at startup and serves the OpenAI chat shim, and the cockpit
chat console now talks to it.

- **Local generation in the daemon.** When `SOVEREIGN_GATEWAY_MODEL` names a model dir
  (`config.json` + `*.safetensors` + `tokenizer.json`), the gateway loads it into a `QuantModel` +
  `HfBpeTokenizer` at startup and flips the manifest's `open-ai-shim` surface **Live**. Absent /
  not-yet-fetched ⇒ it stays a pure decision surface (no error). New `GatewayServer::generate_chat`
  streams decoded UTF-8 chunks token-by-token.
- **`POST /v1/chat/completions` (OpenAI SSE).** A new streaming path in the HTTP transport emits
  `data: {chunk}` deltas + a final `finish_reason`/`usage` chunk + `data: [DONE]` — the exact shape
  `scripts/inference/prompt.py` consumes. A modelless gateway answers an honest `503`.
- **`DecoderLayer: … + Send`** — a one-line supertrait so a built model can be owned by the
  thread-per-connection daemon (every block is plain owned data, so `Send` was already satisfied;
  no call-site changes; workspace + the inference-crate tests stay green).
- **The cockpit talks to the brain.** `prompt.py` (the code-console / lm-status chat engine) now
  targets the sovereign gateway (:8787) first, falling back to the tier router (:8080) when the
  gateway is down or carries no model — chat degrades gracefully. Env-overridable; the honest-error
  contract (SB-077) is preserved. Verified end-to-end: prompt.py → gateway :8787 → *"The capital of
  France is"* → *" Paris. It is the largest city in France…"* (streamed SSE, real SmolLM-135M).
- The `sovereign-gatewayd.service` unit gains the optional `SOVEREIGN_GATEWAY_MODEL` env.

### Added — the sovereign brain does REAL inference: HF tokenizer bridge + real-model generation (2026-07-11)

The Rust intelligence layer's weight loader was real but tokenizer-crippled (a hardcoded 256-vocab
byte tokenizer, so any genuine 32k+ vocab model hit `VocabMismatch`). This closes the gap:
`sovereign-serve --model DIR` now runs a real trained checkpoint and generates COHERENT text.

- NEW crate **`sovereign-hf-tokenizer`** — a faithful loader for a HuggingFace `tokenizer.json`
  (GPT-2 byte-level BPE: explicit vocab + ranked merges + the byte↔unicode alphabet). Pure Rust +
  `serde_json` with a **hand-rolled GPT-2 pre-tokenizer** — no external `tokenizers`/`regex`/
  `sentencepiece` dependency (the workspace rolls its own; sovereignty-clean). Validated against
  SmolLM's real vocab (`the`→1195, ` the`→260, ` quick`→2365, individual-digit splitting, exact
  round-trip decode); 6 unit tests.
- **`sovereign-serve --model DIR`** now uses it when a `<dir>/tokenizer.json` is present: it loads
  the weights into a `QuantModel` (the loader carve-out), pairs them with the real tokenizer,
  prepends BOS, and generates through the engine directly — a **zero-ripple** path that touches
  neither `QuantLlm` nor its tests. Falls back to the byte tokenizer for the vocab-256 fixtures.
- **Proof (real SmolLM-135M, ~0.5 GB, CPU, 4.2 s for 3×24 tokens):**
  - *"The capital of France is"* → *" Paris. It is the largest city in France…"*
  - *"Once upon a time"* → *", there was a little girl named Lily. She loved to play with her friends…"*
  This proves the whole sovereign transformer (RoPE, GQA, SwiGLU, RMSNorm, the HF q/k permute,
  greedy sampling) is **numerically HF-Llama-compatible** — the runtime does genuine local
  inference on real downloaded weights, not just synthetic filler.
- NEW `scripts/intelligence/fetch-model.sh` — opt-in, manual-only helper to fetch a small real
  model (default SmolLM-135M). Never wired into provisioning or first-boot.

### Added — the sovereign gateway brain: durable memory + live cockpit (2026-07-11)

The dormant Rust intelligence layer's `sovereign-gatewayd` (M048 provider-inversion gateway
over the deterministic cortex engine) becomes a real, self-remembering daemon the cockpit can
watch — the durable-memory + cockpit activations of the brain arc.

- **Durable Memory-OS.** `MemoryStore` now serialises (serde); `sovereign-gatewayd` resumes
  from `SOVEREIGN_GATEWAY_MEMORY` at boot and a background thread atomically snapshots the
  learning Cortex (temp-write + rename; cadence `SOVEREIGN_GATEWAY_MEMORY_SAVE_SECS`). The unit
  points it at `/var/lib/sovereign-os/memory/cortex.json` (`StateDirectory` — the one writable
  path under `ProtectSystem=strict`). Verified end-to-end: an empty store stays empty (load
  works, no cold re-seed), a fresh seed persists to disk (save works), and learned commits
  accumulate across restarts (the store grew 3→4→5 over three daemon lifetimes). Recall no
  longer resets each boot.
- **Cockpit ↔ live gateway (read-only).** NEW `scripts/operator/lib/gateway_probe.py` — a
  stdlib server-side probe of the running gateway (:8787): `GET /health` + `/admin/ledger` +
  `/manifest` plus the persisted snapshot on disk, degrading to a structured `{up:false}` when
  the daemon is down (a browser can't cross-origin fetch :8787, so the same-origin api daemons
  proxy it). Wired into `trinity-api` (`GET /gateway`) and `model-health-api`
  (`GET /api/models/gateway`); the **trinity** and **d-03-model-health** panels render a "Live
  Sovereign Gateway" section — the never-cloud-spill sovereignty tripwire, the cost/route
  ledger (committed / learned / by-role), the live gateway surfaces, and the persisted-memory
  item count. New osctl verb `sovereign-osctl gateway [--json]` prints the same probe.
  Read-only at every surface. `tests/lint/test_gateway_cockpit_contract.py` guards the shape +
  graceful degradation; the 93 panel-contract lints stay green.

### Added — Live-reload for the dev operator panels (2026-07-11)

Operator directive (verbatim): *"couldn't there be a live-reload feature now that I think
about it that is enabled by default ? so that I dont have to redo make panel everytime. one
way that doesn't even need to kill anything if possible ? aren't those static assets ? in
the page if a panel has updated there could be a notification at the bottom center and offer
to refresh the page. and we dont reload something for nothing I guess but the reload include
the services / apis behind. no matter how complex and long we can take the time. no rush, do
this right and performant"*.

Editing a panel no longer needs a stop + rerun — in dev (`make panel`) AND on a flashed box
(the operator keeps developing on the live `/opt/sovereign-os` checkout). Shipped ON by
default; a locked build sets `bake.livereload:false`. See SDD-203.

- Round 559 — NEW `scripts/operator/lib/reload-run.py`: a **self-re-exec launcher** every
  panel daemon runs through. It `runpy`-runs the daemon in-process (same PID, owns the
  socket) and, on an edit to the daemon's OWN `.py`, `os.execv`s the **same process image**
  in place — no external kill, no `Ctrl-C` (the operator's "doesn't even need to kill
  anything"); the socket re-binds in milliseconds (`allow_reuse_address`). Lazy-import files
  appearing later are absorbed (never bounce mid-request); a crashed daemon stays recoverable
  (a non-daemon watcher re-execs on the next save). Disabled it is a transparent pass-through.
- Round 559 — NEW `scripts/operator/livereload-broker.py`: ONE loopback file-watcher on
  `:8136` for the whole fleet (performant — not one watcher per daemon) that pushes
  `event: reload` over SSE **only for paths a panel depends on** (its `webapp/<slug>/`,
  `webapp/_shared/`, its daemon source + the `scripts/…`/`config/…` that daemon shells —
  parsed once at startup, stdlib-only). Nothing reloads "for nothing". Read-only; never
  leaves 127.0.0.1; not shipped/enabled in the image.
- Round 559 — the SDD-067 app-shell block (`webapp/_shared/app-shell-snippet.html`, synced
  byte-identical to all 52 adopted panels) gains a small `EventSource` client that shows a
  **bottom-centre "This panel updated — Refresh"** toast on a relevant change. It is
  loopback-gated (inert in the image), **non-mutating** (a GET stream + a `location.reload()`
  navigation — adds no `fetch`/XHR/POST, so `test_app_shell_chrome_is_non_mutating` stays
  green), coalesces a burst into one toast, and never auto-reloads (it *offers*, per "offer
  to refresh the page"). Static HTML + shelled-script edits need NO restart (a pure refresh);
  only a daemon's own `.py` triggers the in-place re-exec ("include the services / apis
  behind").
- Round 559 — `scripts/operator/panel.sh` starts the broker first, then wraps the two main
  servers + every panel daemon in `reload-run.py`. **ON by default**; opt out
  `SOVEREIGN_OS_LIVERELOAD=0`.
- Round 559 — **installed-box wiring** (so it works on a flashed OS, no `make panel`): NEW
  `systemd/system/sovereign-livereload-broker.service` (R171-hardened, loopback :8136);
  `scripts/build/provision-bake.sh` §5c (mkosi image) + `scripts/install/install-gui-dashboards.sh`
  §3c (root-reflash) enable the broker and generate a systemd **drop-in** per enabled panel
  API + the hub that wraps `ExecStart` through `reload-run.py` and sets
  `SOVEREIGN_OS_LIVERELOAD=1` — so a daemon's own `.py` edit re-execs it in place (same PID,
  no `systemctl restart`). **Shipped unit files stay byte-identical** (the wrap lives only in
  the drop-in), so every per-unit lint is untouched. Gated on the NEW bake flag
  `SOVEREIGN_OS_BAKE_LIVERELOAD` (`profiles/*.yaml` `provisioning.bake.livereload`, default
  true; mkosi-emit + schema); `sain-01` sets it on.
- Round 559 — NEW `tests/lint/test_live_reload_contract.py` (client present + loopback-gated
  + `EventSource`-only + broker/port consistency + daemons compile + panel.sh wiring) + NEW
  `tests/nspawn/test_live_reload.sh` (broker SSE relevant-notifies / irrelevant-stays-silent
  + in-place self-re-exec proven by **same PID + fresh code**).

### Added — Science-tools catalog + NVIDIA Warp particle-sim integration & panel (2026-07-09)

Operator directive (verbatim): *"There should be somewhere something about Science
experiment, tools of such type, we will add to it Nvidia Warp / warp-lang and we
will start coding it, its integration and panel"* → *"the full job, planned properly"*.

Materialises the operator's Image-2 "scientific / merge / specialist catalog"
(info-hub `model-catalog` `dna`/`protein`/`particles`) into sovereign-os, and ships
NVIDIA Warp end-to-end. See SDD-070.

- Round 558 — NEW `config/science-tools.yaml` + `schemas/science-tools.schema.yaml`
  + `tests/schema/test_science_tools_schema_conformance.py`: a schema-validated
  catalog of 7 non-LLM domain compute tools (DNA / protein / particles), kept OUT
  of the LLM model catalog. Anchored to the `simulation` REPL kind (m023 / M00374).
- Round 558 — NEW `scripts/science/warp-runner.py` (the ONLY warp-importing script):
  device-selects `cuda:0` if `wp.is_cuda_available()` else `cpu`, runs a
  `warp.sim`-class particle drop-and-bounce sim, `--json`/`--emit-metrics`, exit-0
  clean even when warp-lang is absent or no CUDA is present. Verified on CPU
  (50k particles) in an isolated venv.
- Round 558 — NEW `scripts/science/science.py` (stdlib-only `list`/`status`/`run`/
  `install`/`info`) + the `sovereign-osctl science` bridge; read-only
  `scripts/operator/science-api.py` (:8134, POST→405) + `webapp/science/index.html`
  + `sovereign-science-api.service`; new `science` dashboard category + catalog entry;
  `surface-map` `science` module = core/cli/api/service/webapp.
- Round 558 — first-boot install: `scripts/hooks/post-install/warp-setup.sh` +
  `sovereign-warp-setup.service` (in `FB_UNITS`); `warp-lang` added to
  `operator-deps.toml [pip]`; enabled at bake (`provision-bake.sh §5`) and on live
  hosts (`install-gui-dashboards.sh`). L3 `tests/nspawn/test_science_panel.sh` (19/19)
  + a CI layer-3 step. Metrics `sovereign_os_post_install_warp_setup_total` +
  `sovereign_os_science_warp_*`.

### Added — GUI + dashboards ON by default for the root-of-machine install (2026-07-02)

Operator directive (verbatim): *"lets make with GUI by default when we install
at the root of the machine, I will keep Debian 13 GUI to explore the dashboards
and lets make sure we have them running by default and that I can easily find
them on a fresh install."* This **reverses the prior non-GUI-by-default stance**
(R225, `scripts/dashboard/serve.py`) for the root install only — headless is
still available via `SOVEREIGN_OS_INSTALL_GUI=0`.

- **New `scripts/install/install-gui-dashboards.sh`** (idempotent, root): installs
  a Debian 13 desktop (GNOME by default; `minimal`=XFCE or `none` selectable via
  `SOVEREIGN_OS_DESKTOP`) + a browser, deploys the dashboard app tree to
  `/usr/local/lib/sovereign-os`, enables the dashboard services on boot, and drops
  a discoverable **"Sovereign Dashboards"** launcher into the app menu, the
  desktop, and login autostart. Runs both in the install chroot (offline
  wants-symlink) and on a live system.
- **New `systemd/system/sovereign-dashboards.service`**: runs the panel **hub**
  (`build-configurator-api.py`) on boot, loopback-bound (`127.0.0.1:8100`), full
  R171 defense-in-depth block (passes the systemd fleet-hardening gate). The hub
  statically serves every `webapp/` panel — verified serving **37 panels**
  (master-dashboard + d-01..d-20 + siblings) with a `/panels/` discovery index.
- **New `share/applications/sovereign-dashboards.desktop`**: XDG launcher that
  `xdg-open`s `http://127.0.0.1:8100/` in the operator's browser.
- **`scripts/install/install-sovereign-root.sh`**: `SOVEREIGN_OS_INSTALL_GUI`
  (default `1`) now provisions GUI + dashboards inside the chroot before unmount;
  the closing message tells the operator exactly where to find them.
- **`scripts/hooks/post-install/first-login-assistant.sh`**: prints the dashboard
  hub URL + how to find the launcher when the GUI path is installed.

Exposure stays the operator's call: everything binds loopback; a documented
`bind.conf` drop-in opens it to LAN/tailscale for a headless box.

### Added — ternary BitLinear MLP: the engine composes a real FFN block (M073) (2026-06-10)

The bitlinear-core crate had a real single-layer ternary projection
(`BitLinearLayer`) but the engine only ever ran it as a one-layer
self-check. `BitLinearMlp` (new `crates/sovereign-bitlinear-core/src/mlp.rs`)
composes the primitive into the transformer **feed-forward block** — the
dominant ternary compute — with a ReLU between layers and the standard
`d_model → d_ff → d_model` `ffn()` constructor. It preserves both core
invariants *across the stack*: every layer's inner products stay
multiplication-free (summed `OpCount`), and the stacked forward is
bit-for-bit identical to a dense multiply-based reference (ReLU + ±1 muls
are exact) — proven by `forward_matches_dense_reference` over `Base3` +
`TwoBit` packings, plus deep-stack (3-layer), ReLU-gating, op-accounting,
dim-chain-validation, and serde tests (7 new, all green on
`cargo +1.88.0`). The cortex's Conductor self-check
(`compute.rs::ternary_kernel_live`) now runs a real two-layer FFN block
instead of one layer, asserting mul-free composition end-to-end — so
`kernel_verified` means "a real multi-layer ternary FFN ran
multiplication-free," a strictly stronger guarantee. Moves the runtime a
concrete step from "single kernel callable" toward "a network block that
runs." Additive: two new `BitLinearError` variants (`EmptyStack`,
`StackShapeMismatch`); no existing API changed.

`BitLinearMlp::forward_residual` then completes the block into a real
transformer **FFN sublayer** (`y = x + block(x)`, the residual-wrapped
shape a decoder uses), guarded to `input_dim == output_dim`. Tests prove
the residual is exactly `x + block(x)`, that an all-zero block is the
residual *identity* (the trainability property deep stacks rely on), and
that a non-square block is rejected — the missing piece to drop the
multiplication-free ternary FFN into the residual stream where the quant
decoder block today still runs a float SwiGLU. Additive variant
`ResidualShapeMismatch`.

`TernarySwiGlu` (new `swiglu.rs`) then builds the *gated* FFN the decoder
actually runs — `h = SiLU(W_gate·x) ⊙ (W_up·x)`, `out = W_down·h` — with
all three projections as multiplication-free `BitLinearLayer`s. The heavy
`O(hidden·dim)` matmuls are fully ternary (every inner-product multiply
eliminated, summed `OpCount`); the only genuine multiplies left are the
`O(hidden)` elementwise SiLU-gate products — exactly the BitNet trade.
Proven bit-for-bit equal to a dense SwiGLU on the de-quantized weights
(over `Base3` + `TwoBit`), with mul-free accounting, the zero-weight
residual identity, and shape-rejection tests (6 new). This is the genuine
multiplication-free drop-in for the float SwiGLU the quant decoder block
runs today — the M073 FFN at the shape a real decoder uses.

`BitLinearLayer::forward_packed` implements the dump's still-unbuilt
F06060-F06062 ask: a forward that runs **directly on the 2-bit packed
codes** — a single pass over the packed bytes, no intermediate
`Vec<Trit>`, each weight a `01`→add / `10`→subtract / `00`→skip decision
read in place. This is the scalar form of the AVX-512 lookup-table matmul
("no de-quantization, single-pass through CPU registers") — the
correctness foundation a SIMD lane must reproduce. Gated bit-for-bit
(output *and* `OpCount`) against `forward()` over random weights;
restricted to `Packing::TwoBit` (the byte-aligned LUT target) via the new
`PackedForwardUnsupported` variant. `BitLinearMlp::forward_packed` and
`TernarySwiGlu::forward_packed` propagate it to the block level, so a
whole FFN (or gated FFN) runs single-pass on packed codes — each
bit-for-bit equal to its `forward()`.

### Added — guardian dropout metrics + flap alert (M084 R14127–R14133) (2026-06-10)

A single Tetragon-stream EOF is self-healing (BindsTo + Restart=always close
the blind window in ~1–2s); what must page is **churn**. The guardian now
emits `sovereign_os_auditor_stream_eof_total` on the EOF fall-through
(inventoried), and `sovereign-os-auditor.rules.yml` pages
`SovereignOsAuditorStreamEofChurn` (warning) at ≥3 dropouts in 30m — the
dump's flapping OPNsense/SD-WAN management-path scenario — with a runbook
section routing the operator to the firewall/lease behavior, not the
guardian (which is recovering itself).

### Added — M084: OPNsense/SD-WAN boundary contract catalogued + guardian dropout prevention built (audit gap #3 closed) (2026-06-10)

The audit's gap #3: "the VLAN concept is catalogued (M003) but the firewall
interface + Tetragon-socket-dropout gotcha isn't." Two-part closure:

- **Built first**: the transposition dump's prevention (lines 761–765,
  verbatim) was only half-implemented — `sovereign-guardian-core.service`
  gains the required `BindsTo=tetragon.service`, and guardian-core.py's
  read-loop EOF fall-through (which silently returned 0, hiding the
  "blinding your real-time exploit containment system" event) now logs
  `[EOF] … perimeter blind` + exits nonzero so the `Restart=always` recovery
  is a journal-recorded failure-restart.
- **Catalogued**: `M084-opnsense-sdwan-boundary-contract-tetragon-dropout-resilience.md`
  — 170 R-rows decomposing the dual-NIC Zero-Trust topology (VLAN 100
  management/telemetry on the Intel 2.5GbE; VLAN 200 model-ingestion with NO
  outbound WAN on the Marvell 10GbE), the firewall observation surface
  (E11.M8 reachability ladder), and the gotcha/prevention pair; the
  reconfig-detector, dropout metrics, and flap alert are catalogued as
  explicitly pending. Catalog totals: 82 milestones / 14,080 R-rows
  (lockstep across INDEX, MASTER-PLAN, SHIPPED + gate literal); SHIPPED
  gains an M084 section citing the prevention commit.

### Added — M083: DFlash speculative decoding catalogued (audit gap #2 closed) (2026-06-10)

The 2026-06 catalog audit named DFlash as under-catalogued — "survives only as
one incidental clause; no dedicated epic, unlike Ling-2.6 / Nemotron-3 which
got full treatment." `backlog/milestones/M083-dflash-speculative-decoding-fast-path.md`
closes it: 10 epics / 17 modules / 85 features / 170 R-rows decomposing the
operator's verbatim dump-tail addition (transposition dump 1115–1131: "3 times
faster" on code, "does not work on creative tasks in general") + the SDD-026
design (task-type gating table, ENABLE/DISABLE override knobs with
DISABLE-wins, vllm/llama_cpp/transformers argv shaping, disabled-no-install
graceful fallback, `sovereign_os_dflash_*` Layer-B metrics) + the R161 router
task-type closure. Layer-5 benchmarking + draft-model tuning catalogued as
explicitly pending. Catalog totals updated in lockstep: 81 sovereign-os
milestones / 13,910 R-rows (INDEX, MASTER-PLAN, SHIPPED roll-up, and the
SHIPPED-gate literal).

### Added — gateway Grafana dashboard: the sovereignty tripwire is now visual (2026-06-10)

`docs/observability/dashboards/sovereign-os-gatewayd.json` completes the
gateway observability triad (metrics → alerts → dashboard): headline
never-cloud-spill tripwire stat (HOLDS/BROKEN, pairs with the
SovereignGatewayCloudSpill alerts), cloud-spill counter, live surfaces,
request + dry-run rates, decisions by disposition, routing per SRP role, M030
World-Model prior-agreement ratio, and the force_local doctrine panel. The
json-valid gate's sanctioned metric-family list gains `sovereign_gateway_*`
(the daemon's own `GET /metrics` namespace, scraped directly over HTTP — same
dedicated-binary precedent as `sovereign_telemetry_*`).

### Fixed — small operational symmetry + diagnosability gaps (2026-06-10)

- **`make uninstall` now removes what `make bins` installs.** It removed
  sovereign-osctl + lib + manpage but left the three Rust binaries behind in
  `PREFIX/bin`. Verified symmetric via a DESTDIR sandbox.
- **Layer-3 `make lint` failures now show WHICH tests broke.** The
  makefile-execution harness captured the 4644-test pytest output and then
  printed only `FAIL — make lint failed`; a CI flake on 2026-06-10 was
  diagnosable only by inference from the sibling layer-1 job. On failure the
  harness now prints the FAILED/ERROR lines + the summary tail.

### Added — the never-cloud-spill invariant now pages (2026-06-10)

The gateway daemon has tracked its sovereignty tripwire since birth
(`sovereign_gateway_never_cloud_spill_holds` on `GET /metrics`), but nothing
*paged* on it — a spill would sit unread in a ledger until someone looked at a
dashboard. New `config/prometheus/alerts/sovereign-gatewayd.rules.yml`:

- **SovereignGatewayCloudSpill** (critical, deliberately `for:`-less — one
  confirmed scrape pages): the holds-gauge dropped to 0, meaning a decision
  routed to the cloud plane despite `force_local`. An incident, never tuning.
- **SovereignGatewayTripwireUnmonitored** (warning, 10m): `absent()` on the
  gauge — an invariant nobody can see is not enforced from the operator's
  seat (daemon down / scrape job broken / bind moved).

Runbook sections (meaning → diagnosis → fix, with the scrape-job snippet —
the daemon serves `/metrics` itself, no textfile collector) added to
`docs/operator/m060-deployment-guide.md`; per-file contract gate
`tests/lint/test_sovereign_gatewayd_alerts_contract.py` reads the emitted
metric set straight out of `lib.rs` so an exporter rename kills the alert
file in CI instead of leaving a dead alert.

### Added — gateway `simple` op: a client need not build a full CortexRequest (2026-06-09)

`POST /v1/messages` required a full `CortexRequest` (7 axes + workload +
pressures + 12-axis reward). The new `simple` op lets a client send only the
task `axes` + an explicit `expected_quality` dial (+ optional `query_topic` /
`profile`); the gateway fills the engine-internal fields and runs it like
`infer`. Additive — the full `CortexRequest` path is unchanged.

- NDJSON `{"op":"simple-infer","request":{"axes":{…},"expected_quality":0.8}}`
  and HTTP `POST /v1/simple` → `{"kind":"decision",…}`. Verified live (minimal
  `{axes, quality}` → a real conductor/commit decision).

> **⚠ Operator review needed on the fill-in defaults.** The gateway invents no
> *hidden* quality policy — `expected_quality` is a **required** field, so the
> client always supplies the quality dial — but the convenience does choose
> conservative defaults for the remaining under-specified (mostly mechanical or
> non-decision-affecting) fields, and in a sovereign system those are a policy
> you should own. They are deliberately transparent and tunable in
> `SimpleRequest::into_cortex`:
> runtime pressures → **idle** (no live telemetry → assume capacity);
> `allow_cloud` → **false** (sovereign default); workload class + precision →
> derived from `axes.complexity` (simple → CPU/ternary, complex → GPU/fp16);
> `min_vram_gb` → 0 (don't over-constrain placement); `profile` → `careful`;
> `model_params` → 7B (footprint estimate only); reward → `expected_quality`
> spread over the competence axes with risk/latency/cost low. Adjust or reject
> these in review — the op is isolated and easy to retune or drop.

### Added — gateway best-of-N: a read-only `deliberate` op (2026-06-09)

The gateway exposed only the single-pass `tick`; the cortex's premium decision
mode — best-of-N `deliberate` (fork one branch per candidate, return the
winner + every assessment + the branch tree) — was unreachable. Added a
`deliberate` op whose inputs are all **explicit client choices** (no
product-default guessing): the shared `request`, the candidate `RewardVector`s
(the N), and the compute `tier` (`reflex` … `experimental`, the fanout dial).

- NDJSON `{"op":"deliberate","request":{…},"candidates":[…],"tier":"…"}` →
  `{"kind":"deliberation",…}`; HTTP `POST /v1/deliberate` with the same body.
- **Read-only** like `explain`: it decides but does not learn or touch the
  ledger (verified the ledger stays 0 after a deliberation), with the same
  `force_local` Privacy policy. Verified live over HTTP (best-of-3 → winner
  committed, `candidates_considered=3`).
- +4 tests (lib + http: best-of-N, read-only, bad body → 400, GET → 405). 29
  unit + 9 integration tests pass; `fmt` + `clippy -D warnings` clean on 1.88.0.

### Added — `sovereign-chat` is runnable: multi-turn conversation with bounded history (2026-06-09)

`sovereign-chat` composes `sovereign-llm` into a stateful chat session (record
the turn → render the role-tagged history → generate → append) with **bounded
history** for endless dialogue, but was lib-only. Added a `[[bin]]` + demo (the
workspace's 8th runnable binary) that runs a session on a small real
`SovereignLlm` and shows the distinct behaviour — the history grows to the cap
(system + 4 non-system messages) then **stays bounded** as the dialogue
continues, the earliest turns dropped while the system message is always kept.

The 6 model crates moved from dev-dependencies to dependencies (no new
workspace crates; Cargo.lock unchanged). `--help` supported. `fmt` +
`clippy -D warnings` clean on pinned 1.88.0; the 8 lib tests still pass. This
completes the runnable set of the four distinct decision/execution paths over
the runtime: routing (`gatewayd`), cost (`serve`), agent (`agent-runtime`),
conversation (`chat`).

### Added — `sovereign-agent-runtime` is runnable: a tool-using ReAct agent on the real engine (2026-06-09)

`sovereign-agent-runtime` bridges the real quantized inference engine
(`sovereign-llm`) into the ReAct loop (`sovereign-agent-loop`) but was lib-only.
Added a `[[bin]]` + demo (the workspace's 7th runnable binary) that drives the
agent two ways:

- **Real runtime** — a small `SovereignLlm` drives the loop end-to-end, proving
  the inference stack + agentic layer compose into one running agent. (Random
  weights → no tool call, one-step gibberish answer; the point is the real
  engine drives the control flow.)
- **Scripted ReAct** — a deterministic responder emits `[[tool:upper|sovereign]]`,
  so the run shows the full loop: generate → dispatch the tool → feed the
  observation back → final answer (`upper("sovereign") = "SOVEREIGN"`).

The 7 model crates the binary needs to build a `SovereignLlm` moved from
dev-dependencies to dependencies (no new workspace crates; Cargo.lock
unchanged). `--help` supported. `fmt` + `clippy -D warnings` clean on pinned
1.88.0; the 4 lib tests still pass.

### Added — `sovereign-serve` is runnable: the $0-aware serving assembly runs end-to-end (2026-06-09)

`sovereign-serve` composed the cache / complexity / token-meter crates into one
`serve()` call but was lib-only — the assembly never ran. Added a `[[bin]]` +
demo session (the workspace's 6th runnable binary) that drives requests through
it, showing the cost-aware behaviour the crates exist for:

- a repeated request is a **cache hit** — `$0`, the model never runs (`in=0 out=0`);
- each request's **complexity tier** is estimated for routing;
- a request that would blow the **token budget** is **refused before generating**
  (`16 + 50 > 40`), not run and charged.

The generator is a deterministic model stand-in (the point is the orchestration,
not the text), mirroring the cortex binary's demo mode. `--help` supported.
With no args it runs the demo; given `PROMPT [PROMPT…]` it serves each on an
unlimited budget (a repeated prompt resolving as a `$0` cache hit) — an actually
usable cost-aware serving tool, not just a fixed demo. `fmt` +
`clippy -D warnings` clean on pinned 1.88.0; the 6 lib tests still pass.

### Added — the World-Model prior now acts: a surprise engages deeper reasoning (2026-06-09)

The M030 prior was observe-only; now it influences compute — conservatively.
When a **confident, well-observed** prior contradicts the live verdict
(`confidence ≥ 0.75`, `observations ≥ 3`), the decision is a "surprise" (the
task is resolving against history) and the cortex engages a bounded HRM
recurrent pass (M080) — the same deeper-reasoning mechanism an uncertain verdict
already triggers.

Crucially, this **never changes the verdict** — it only adds a recurrent pass
(and the speculative control-word flag) for extra scrutiny before the Auditor
sees the branch, so it can never cause a wrong commit. Thresholds are named
constants (`WORLD_MODEL_SURPRISE_CONFIDENCE` / `_MIN_OBS`). Locked by a test:
seed a confident Prune history, then a committing request engages reasoning
while keeping its Commit verdict. Cortex suite now 56 tests; `fmt` +
`clippy -D warnings` clean on pinned 1.88.0.

### Added — cortex composes the World-Model plane (M030): learned routing-outcome priors (2026-06-09)

The cortex assembly gains a ninth real engine. `sovereign-cortex` now owns a
`sovereign-world-model` (M030) that learns `(task-topic, routing-role) →
outcome` dynamics across requests — distinct from the symbolic planner's fixed
effects (this learns from data, Dreamer-style):

- **`Cortex::learn`** observes the transition on **every** outcome (commit,
  prune, expand, need-more-compute), not just commits, so the model can predict
  prunes too. Separate from the commit-gated Memory-OS admission.
- **`Cortex::tick`** consults the model for a learned prior and annotates the
  decision with `Option<WorldModelPrediction>` — `expected_action`, `confidence`
  (modal probability), `observations` (history depth), and `agrees_with_verdict`
  (a mismatch flags a task resolving differently than history). Honest `None`
  for a cold pair — no fabrication.
- New `WorldModel::pair_observations(state, action)` (additive) backs the
  history-depth field.
- The prior is read-only in `tick` and learned only in `learn`, so there's no
  intra-request leakage: a cold pair predicts `None`, and the prediction only
  becomes informative once the pair has resolved before.
- Locked by a cortex test (cold → None; after one observation → agreeing
  prediction at confidence 1.0) + a world-model test. All 53 existing cortex
  tests still pass; `fmt` + `clippy -D warnings` clean on pinned 1.88.0; the
  gateway (which serializes `CortexDecision`) passes unchanged — the new field
  is additive.

### Added — `sovereign-gatewayd` deployable: systemd unit + Makefile install + e2e transport tests (2026-06-09)

Turns the gateway daemon from a buildable binary into a deployable managed
service:

- **`systemd/system/sovereign-gatewayd.service`** — runs `sovereign-gatewayd
  --http`, loopback-by-default (`SOVEREIGN_GATEWAY_ADDR`, with the documented
  `.d/bind.conf` override pattern), `Restart=on-failure`. Carries the full R171
  defense-in-depth posture; since the daemon is pure in-memory (reads/writes no
  files) it runs cleanly under `ProtectSystem=strict`. Passes all 245
  systemd-hardening lint assertions + the fleet/posture/timer gates.
- **Makefile `bins`** now builds + installs `sovereign-gatewayd` to
  `PREFIX/bin` alongside `sovereign-telemetry` / `sovereign-resource-control`,
  matching the `ExecStart` path.
- **End-to-end transport tests** (`tests/transports.rs`): spin the real binary
  on an ephemeral port and exercise both transports over actual sockets — NDJSON
  TCP (infer→ledger across one connection; malformed line → error, not drop) and
  HTTP (health 200, `POST /v1/messages` runs the engine, `/metrics` reflects it,
  404/400). Locks the socket plumbing the unit tests can't reach. 25 tests total.

### Added — `sovereign-gatewayd` HTTP/1.1 surface: real clients reach the engine (2026-06-09)

The gateway daemon spoke only a custom NDJSON line protocol; now it also serves
the bind paths the M048 manifest advertises over plain HTTP, so curl / an MCP
bridge / the cockpit can hit the engine directly:

- New `--http` transport (pure-std HTTP/1.1, thread-per-connection,
  `Connection: close`; request line + headers + `Content-Length` body parsed by
  hand — no async runtime, no new deps, honors `unsafe_code = forbid`).
- Routes: `GET /health`, `GET /manifest`, `GET /admin/ledger` (the CostRouteLedger
  bind path), `GET /metrics`, and `POST /v1/messages` (Anthropic surface) /
  `POST /v1/infer` / `POST /mcp` taking one JSON `CortexRequest` → the tagged
  decision. Wrong verb on a known route → 405; unknown → 404; malformed body →
  400; engine refusal → 422.
- **`GET /metrics`** renders the live ledger + health as Prometheus
  text-exposition (`sovereign_gateway_requests_total`, `…_route_total{role}`,
  `…_decisions_total{disposition}`, `…_cloud_spills_total`,
  `…_never_cloud_spill_holds`, `…_live_surfaces`, and — once the engine learns —
  `…_prediction_total` / `…_prediction_agreements_total`) so the existing
  node_exporter→Grafana cockpit can chart the daemon with no new pipeline —
  the operator-visible surface the SHIPPED bar requires. Verified live via curl.
- **Request-size caps (DoS hardening).** A `Content-Length` over 1 MiB → `413`
  *before* any buffer is allocated; an over-8 KiB request line or header line,
  or more than 100 headers → `431`; an over-1 MiB NDJSON line → error + close.
  Each is read through a fresh `take`, so a client can't exhaust the daemon's
  memory with a huge or unterminated request on either transport. Cortex
  requests are a few KB. Verified live (4 GiB body → 413; 9 KB header → 431).
- **Connection cap (flood back-pressure).** Both accept loops (now DRY'd into
  one `serve()`) bound concurrent handler threads (default 256, override
  `SOVEREIGN_GATEWAY_MAX_CONN`); over the cap a connection is accepted and
  closed immediately rather than spawning unbounded threads. Matters once the
  daemon is exposed past its loopback default. Tested with the cap at 2.
- **Survives a failed handler-spawn.** The accept loop uses
  `Thread::Builder::spawn` and, if a handler thread can't start under resource
  pressure, drops that one connection and keeps serving rather than panicking
  the accept loop and taking the whole daemon down. The `ConnGuard` drops on the
  failure path, so the active-connection counter stays correct.
- The HTTP routing (`http::respond`) is pure and routes through the same
  `GatewayServer::handle` as the line protocol, so the two transports can never
  diverge. Verified live (curl + raw-socket): `GET /health` 200,
  `POST /v1/messages` 200 with a real decision, ledger advancing, no cloud spill.
- +9 unit tests (19 total in the crate). `cargo fmt`/`clippy -D warnings` clean
  on the pinned 1.88.0 CI toolchain. The full Anthropic content-block schema
  remains a later layer; this v1 carries the typed cortex request/decision.

### Fixed — `cargo workspace` CI job green: the `sovereign-telemetry` orphan repaired (2026-06-09)

The `cargo workspace` check was RED **on `main` too** (pre-existing, not a
regression): `sovereign-telemetry`'s binary and `sovereign-pressure-reactions`'
test fixtures were written against an OLD API of three model crates
(`sovereign-pressure-sensors`, `sovereign-hardware-load-sample`,
`sovereign-observability-fabric`) that was later slimmed to pure
canonical-constructor snapshots — deleting `PressureSnapshot::{from_psi,
from_readings}`, `AxisReading::new`, `LoadSnapshot::{update_target, update_gpu}`,
`ObservabilityFabric::update_source`, and the free parsers (`parse_proc_stat_cpu`,
`parse_gpu_csv`, `parse_psi_some_avg10`, `parse_thermal_zone_temp`,
`cpu_util_pct`, `GpuTelemetry`). The two consumers were never updated.

Repaired **without touching the model crates** (they stay pure typed snapshots):
- The deleted OS-parsing helpers now live **in the `sovereign-telemetry` binary**
  — where reading `/proc`, `/sys`, and `nvidia-smi` belongs — and feed the model
  types through their public fields. The deleted mutator methods become direct
  public-field assignment on the canonical snapshots. The binary builds, runs as
  a real probe on a dev host (live PSI / `/proc/stat` CPU / thermal verdicts /
  adaptive reactions), and emits both JSON and Prometheus surfaces.
- `sovereign-pressure-reactions`' test fixtures rebuilt the same way
  (`free_canonical` + field set; a `set_util` helper for load fixtures).

`cargo check --workspace --all-targets` now exits 0; affected crates' tests green;
`cargo fmt` clean.

### Added — `sovereign-gatewayd`: the first persistent runnable service (2026-06-09)

Promotes the one-shot `sovereign-cortex` engine (PR #17) into a long-lived
**daemon** behind the M048 Module 4 `sovereign-gateway` contract — closing the
audit's "engine catalogued + assembled but nothing runs as a service" gap. New
`sovereign-gatewayd` binary crate, pure-std (no async runtime; honors the
workspace `unsafe_code = forbid`):

- **Stateful, learning engine.** The daemon owns one process-wide `Cortex`;
  every committed decision is admitted back into Memory-OS via `act_and_learn`
  (M016 learning without retraining), so recall grows across requests — verified
  live (recall 2 → 3 on a replayed request) and across *separate* TCP
  connections (a second client observes the first's accumulated ledger +
  learned memory). A CLI cannot do this.
- **NDJSON serving core** (`GatewayServer::handle_line`) shared by three
  transports in `main`: TCP (thread-per-connection, default `127.0.0.1:8787`),
  `--stdio` (MCP/Claude-Code shape), and `--selftest`. Ops: `infer` / `manifest`
  / `health` / `ledger`.
- **Gateway responsibilities made real, not decorative:** `force_local` policy
  forces `allow_cloud = false` before the router (Privacy + Routing on the
  client's behalf, per the provider-inversion doctrine); a live cost/route
  `Ledger` (surface 6: route distribution + committed/refused/learned counts);
  the **never-cloud-spill** invariant tracked as a process-level tripwire and
  asserted to HOLD across the full demo session. 4 of the 6 canonical surfaces
  marked `Live`.
- Locked by 10 unit tests (malformed input, every op, force-local override,
  cross-request learning, invariant) + an `examples/demo_request.rs` client
  payload generator. `cargo clippy` clean, `cargo fmt` clean.

### Added — MS048 scheduler observability + cross-repo consumer (Solution 1 ← Solution 2) (2026-06-05)

The runtime side of the selfdef MS048 Goldilocks Scheduler — sovereign-os
renders the scheduler READ-ONLY (boundary discipline: the decision lives in
selfdef) and now also CONSUMES it:

- **Decision observability**: 3 Grafana panels (route distribution + hibernate
  + ring-window size) + the `SelfdefSchedulerHighHibernateRate` alert (>50%
  deferral 15m) on the new `selfdef_scheduler_decisions_*` metrics; the cockpit
  `scheduler-status.py` card (40) parses + surfaces decision metrics; the 8
  scheduler alert `runbook_url`s repointed to the real selfdef runbook (were
  dangling).
- **Cross-repo consumer bridge** (`scripts/inference/scheduler-bridge.py`):
  the runtime gateway consults `selfdef-scheduler-decide` (read-only subprocess)
  per the integration contract — builds a task descriptor, parses the Decision,
  maps route → backend tier (blackwell→oracle / rtx4090→scout / cpu→cortex /
  hibernate→defer), honoring **honor-Hibernate · map-route→tier · read-only**.
  Graceful-offline: binary absent/errored → `scheduler_available=False` so the
  gateway falls back to its own SDD-011 routing (never crashes, never fabricates
  a route). Maps route → runtime service (blackwell→Oracle Core / rtx4090→Logic
  Engine / cpu→Pulse). Locked by `tests/unit/test_scheduler_bridge.py` (10
  cases, fake binary). Registered in the inference INDEX.
- **Router opt-in advisory** (`router.py`): when `SOVEREIGN_OS_CONSULT_SCHEDULER=1`
  (default OFF — routing then unchanged), the router surfaces the scheduler's
  hardware-tier advisory as the `X-Sovereign-Scheduler-Advisory` response header
  **without changing the routed tier** (the runtime's `classify()` stays
  authoritative). Fail-safe — a missing/broken scheduler never affects routing.
  Locked by `tests/unit/test_router_scheduler_advisory.py` (5 cases). Making the
  advisory authoritative remains a separate explicit operator step.

### Added — D-09 hardware-pressure cockpit dashboard driven to PRODUCTION (full 8-surface stack) (2026-05-27)

The M060 D-09 dashboard existed only as an HTML shell fetching `/api/hardware/pressure`,
`/api/hardware/zfs/datasets`, `/api/hardware/stream` — **dead endpoints, no backend** (the
"reached the shell but not prod" gap). Built the full §1g 8-surface stack, sovereign-os-native
(zero selfdef-boundary — pure runtime hardware signals), stdlib-only (sovereignty: zero deps):
- **core** `scripts/hardware/hardware-pressure.py` — unified pressure aggregator: Linux PSI
  (`/proc/pressure/{cpu,memory,io}` some/full × 10s/60s/300s, reusing the memory-pressure.py
  parser), dual-CCD topology (M070, per-core busy% from `/proc/stat`), GPU via `nvidia-smi`
  CSV, ZFS pool latency + per-dataset sync via `zpool`/`zfs`, scheduler backpressure (M058).
  Every probe degrades gracefully to `null` when a kernel iface/tool/device is absent — NEVER
  crashes (verified on this GPU-less/ZFS-less/PSI-less dev host). CLI: `status`/`psi`/`zfs --json`.
- **cli** `sovereign-osctl hardware-pressure <verb>` dispatch.
- **api** `scripts/operator/hardware-pressure-api.py` — read-only HTTP (stdlib http.server,
  loopback-default) serving the exact dashboard contract + an SSE `/api/hardware/stream` +
  hosting the webapp; mutation verbs → 405 (pressure is observed, not set).
- **webapp** the D-09 dashboard, now served by + wired to its real API.
- **service** `sovereign-hardware-pressure-api.service` (R171 defense-in-depth hardened).
- registered in the master-dashboard aggregator route table (port 8097, `/hardware-pressure/`).
- **tests** `tests/lint/test_hardware_pressure_api_contract.py` — 11 cases locking the full
  stack live (daemon spawn + the 3 dashboard endpoints + webapp serve + read-only 405 + osctl
  dispatch + R171 hardening), all green.

Verified end-to-end via live curl. SDD-040's stale D-09 row updated MISSING → shipped. This is
the first cockpit dashboard taken catalog→shell→**production** through every layer; the other
d-01…d-20 shells follow the same template.

### Fixed — repo-wide `cargo clippy` green (rust CI job no longer blocked at the clippy step) (2026-05-27)

`cargo clippy --workspace --all-targets -- -D warnings` (the rust CI job's step after
fmt) was RED with **424 findings across 124 crates** — the generated crate set was never
run through clippy (same root as the fmt gap). Resolved with clippy 0.1.88 (exact CI
toolchain): two `cargo clippy --fix` passes + one `--unsafe-fixes` pass auto-resolved the
bulk (collapsible_if ×67, manual_*/unnecessary_*/doc_* …), then the residual was fixed by
hand — 11 intentional inherent methods (`next()` widget-advance + a 10-arg / 8-arg
constructor) got targeted `#[allow]`s, `ItemPin` gained the `is_empty()` clippy expects,
three `.get(k).is_none()` → `contains_key`, an index loop → slice iterator, a
`.max().min()` → `.clamp()`, two nested `format!` flattened, two `if`-with-identical-blocks
collapsed (behaviour-preserving — verified non-bugs), and ten rustdoc list-formatting
lints fixed. One `clippy --fix` over-reach was caught + corrected: it dropped a
`cfg(test)`-only `Modifiers` import from `shortcut-cheatsheet` (correct for the lib target,
but the test used it) — re-imported inside the test module. Final state: clippy exits 0,
`cargo fmt --check` clean. 126 source files; all changes behaviour-preserving (no real
bugs surfaced — the catalog crates were correct, just un-linted).

### Fixed — repo-wide `cargo fmt` unblocks the rust CI job (2026-05-27)

`cargo fmt --all --check` (the rust job's first step in `test.yml`) was RED across
the crate set (469 source files) — crates written/generated with non-canonical
formatting that rustfmt reflows. Since `cargo fmt --check` is the first step of
the rust job, its failure blocked clippy/test/build from even running. Ran
`cargo fmt --all` (toolchain 1.88.0's rustfmt — identical to CI; no `rustfmt.toml`,
defaults match), making `--check` exit 0. Purely formatting (rustfmt preserves all
tokens/semantics; verified idempotent via the `--check` round-trip), as one
standalone style commit. Parallels the same-day selfdef fmt fix.

### Fixed — main CI green: 8 pre-existing lint failures resolved (2026-05-27)

`pytest tests/lint` had 8 failures on main (they predate this session). Root-caused
and fixed, all values determined from repo content (no fabrication):
- **SDD-040** (cockpit-dashboard bridge, authored 2026-05-19) was never catalog-wired.
  Added its `docs/sdd/INDEX.md` row (transcribed from its own header), a
  `> Closes findings: none (...)` cross-link line (same pattern as SDD-038/039), and
  a reference in the operator mandate (the dashboard-content surface note on E11.M2) —
  clearing `test_sdd_index_consistency`, `test_sdd_cross_links`, and both
  `test_sdd_reachability` tests.
- **E11.M2/M5/M6/M7/M8/M9/M10/M12** rows in the mandate's §1g decomposition lacked a
  status keyword. Appended an accurate `Status:` to each: `✓ shipped (R<n>)` for the
  six whose operator/* module file was verified present (371–857-line scripts + contract
  tests), `in-flight` for the never-ending-PR row (E11.M12). The §1g FLAGGED-UNDONE axis
  is preserved alongside — clearing `test_epic_e11_cross_repo_coverage`.
- **sovereign-hugepages-sizer.service** declared no `ProtectSystem=` and lacked
  `ProtectKernelTunables` (the author documented the intent in comments but never encoded
  the directives). Added `ProtectSystem=full` (safe: it locks /usr+/boot+/etc but not
  /proc/sys, with /etc/sysctl.d re-opened via the existing `ReadWritePaths`) +
  `ProtectKernelTunables=false` + a `# HARDENING-WAIVER:` documenting the one justified
  opt-out (the sizer must write /proc/sys/vm/nr_hugepages) — clearing both
  `test_systemd_*hardening*` tests.

The 8th failure (`test_round_refs::test_recent_rounds_in_commit_history`) was a
shallow-clone artifact, not a repo defect: R350–R475 are real commits below this clone's
shallow horizon; the test self-skips in CI's depth-1 checkout (HEAD carries no R-number),
and passes once the clone has full history. No repo change needed. Full suite:
2820 lint+schema tests pass.

### Added — repo-wide JSON parse + duplicate-key lint (2026-05-27)

The 19 Grafana cockpit dashboards under `docs/observability/dashboards/`
(plus `.mcp.json` and the env template) are imported verbatim into
Grafana, but nothing validated that the dashboard JSON parses, and
nothing guarded duplicate object keys. `json.load` silently keeps only
the LAST value for a repeated key — a duplicate panel `"id"` or a doubled
`"targets"`/`"title"` silently drops a panel or query, so the dashboard
imports fine but renders wrong with no syntax error. New
`tests/lint/test_all_json_parses_and_no_dup_keys.py` discovers every JSON
under the repo (skipping target/.git/build dirs) and asserts each parses
+ has no duplicate keys via an `object_pairs_hook` guard. Stdlib-only
(`json`); runs in the existing `pytest tests/lint` layer. All 21 files
pass; both checks negative-control-verified. Completes the
sh/py/yaml/json parse-gate matrix alongside the YAML lint added the same
day.

### Added — repo-wide YAML parse + duplicate-key lint (2026-05-27)

sovereign-os ships ~30 YAML documents (build/runtime profiles + mixins,
schema mirrors, cloud-init seeds, bootstrap phase/verify tables, the
whitelabel manifest, the model registry, GitHub workflows). A few had
content-specific lints, but most had NO gate ensuring they even parse,
and NONE guarded against duplicate mapping keys — which PyYAML accepts
silently, keeping only the last value (two `kernel:`/`runtime:` keys
quietly collapse to one). New `tests/lint/test_all_yaml_parses_and_no_dup_keys.py`
discovers every YAML under the repo (skipping target/.git/build dirs)
and asserts each parses + has no duplicate keys, via a strict PyYAML
`SafeLoader` subclass that raises on dup keys. Uses only `pyyaml` (CI
already installs it; runs in the existing `pytest tests/lint` layer). All
30 files pass; both checks negative-control-verified (injected syntax
error and duplicate key each land RED). Parallels the selfdef
`L1-yaml-parse-scan.sh` gate added the same day.

### Added — Cockpit dashboards + Rust runtime crates (2026-05-19)

Cross-repo cockpit-surface completion arc per M060 R10128 ("21 dashboards (D-00..D-20) satisfy operator '20+ dashboards and a main one' verbatim"):

- **11 new dashboards** authored under `webapp/` (D-03 model health, D-07 memory changes, D-08 rollback points, D-12 networking, D-13 filesystem grants, D-14 capability tokens, D-15 sandboxes, D-17 quarantine, D-18 trust scores, D-19 super-model manifest, D-20 peace machine health). D-12..D-18 consume selfdef MS007 mirror crates READ-ONLY per MS043 R10212; all mutation routes emit clipboard CLI for operator-signed `selfdefctl` invocation.
- **6 Rust runtime crates** (81 passing tests, cargo workspace bootstrapped):
  - `sovereign-nvfp4-runtime` (M077, arXiv 2509.25149 / 2505.19115 — E2M1 + E4M3 + 1×16 block quant + unbiased stochastic rounding ±2% verified)
  - `sovereign-holderpo` (M078, arXiv 2605.12058 — Hölder mean + GRPO + 4 anneal schedules)
  - `sovereign-hrm-runtime` (M080, arXiv 2506.21734 — 4th architectural class, 3 variants 27M/1.18B/7M)
  - `sovereign-intervention-class-mirror` (M079, arXiv 2604.09839 — WB↔BB protocol-separation invariant)
  - `sovereign-mirror-publisher` (typed manifest of the 9 selfdef-mirror HTTP/SSE endpoints with bound-lifecycle helpers)
  - `sovereign-dashboard-coverage` (verifies all 21 D-NN slots have on-disk coverage; one disk integration test against real repo tree)
- **CI extension** — new `cargo-workspace` job in `test.yml` runs fmt + clippy (-D warnings) + workspace test + release build across all 6 crates.


- 4 new SDDs (012-022): brand-identity placeholder · installer-experience
  · decommission-testing-scope · secure-boot posture · observability
  bindings · ZFS root layout · kernel choice · reproducibility target ·
  CI infrastructure · distro-base lock-in · disk-encryption posture.
- 3 new profiles + 2 new mixins: `minimal` (VM baseline) · `developer`
  (polyglot toolchain) · `headless` (bare-metal server); mixins
  `role-headless`, `role-developer`, `role-server`.
- Substrate-prepare adapter for live-build (was mkosi-only).
- `orchestrate.sh run --dry-run` / `preflight` / `rewind <step>` /
  `skip <step>` operational verbs.
- 4 new pre-install hooks: preflight-network · preflight-tpm ·
  preflight-storage (plus friction-audit-spec was already shipped).
- 2 new recurrent hooks: security-update-check · backup-snapshot.
- Substantive plymouth + GRUB whitelabel overlays — operator-verbatim
  motd ('quality over quantity · honesty over cheats and lies')
  surfaced at boot in 3 surfaces (`/etc/issue`, plymouth splash,
  GRUB menu bottom).
- `sovereign-osctl` 4 new subverbs: `audit provenance`, `inference
  health`, `inference route`, `doctor v2` (profile-conditioned
  multi-section).
- in-toto SLSA v1 build-provenance.json + sha256sums.txt emission
  at step 09; operator-side verification via `audit provenance`.
- SOURCE_DATE_EPOCH + DEBIAN_SNAPSHOT propagation through mkosi-emit;
  KBUILD_BUILD_TIMESTAMP recorded in kernel build.
- ZFS encryption (SDD-022): aes-256-gcm on tank/context + tank/agents;
  passphrase + TPM2 PCR-7+11 binding default for sain-01 + headless.
- 16 systemd service units, ALL with defense-in-depth sandboxing
  (ProtectSystem / NoNewPrivileges / PrivateTmp / narrow ReadWritePaths).
- 21 Layer-B Prometheus textfile-collector metrics emitted across
  pipeline + recurrent + inference + perimeter + log-rotation +
  ZFS-health + snapshot + security-updates + image-build + image-sign.
- 2 Grafana JSON dashboard templates (`docs/observability/dashboards/`).
- `scripts/setup.sh` — one-command fresh-clone bootstrap.
- `scripts/git-hooks/pre-commit` — operator-side L1 + profile + L3
  fast-sample gate before every commit.
- `tests/qemu/scaffold.sh` — Layer 4 QEMU integration scaffold (gated
  on KVM + qemu + built image; SKIPs gracefully when absent).

### Test coverage
- Layer 1 (schema + lint): ~25 + 6 lint suites (was 3).
  New: systemd-unit-hardening, dashboard-json-valid, dashboard-metrics-
  lockstep.
- Layer 2 (unit): ~51 (was 51); +10 provenance-manifest shape.
- Layer 3 (nspawn): 35 substantive test scripts (was 7). Coverage:
  every lifecycle stage + every operator-facing CLI verb + every
  build step's gate path + reproducibility chain + image-sign +
  whitelabel overlays + inference router + first-login-assistant +
  decommission gates + during-install gates + new recurrent hooks +
  e2e DRY-RUN smoke across all 5 profiles.
- Layer 4 (QEMU): scaffold ready; substantive run gated on
  KVM-equipped self-hosted runner (Q10-B per SDD-020).
- Layer 5 (hardware): operator-driven on real SAIN-01.

### Fixed (15 real wiring bugs caught by L1/L2/L3 discipline)
1. `whitelabel/default.yaml` template paths
2. `orchestrate.sh` cmd_help sed truncation
3. `state_step_status` empty-string default
4. `logging.sh` log_file parent dir auto-create
5. `sovereign-osctl profiles list` shell-var-vs-export propagation
6. `friction-audit-spec.sh` bash -c profile_field scope
7. `test_decisions_log_sequence.py` regex never matched its target
8. `first-login-assistant.sh` unconditional hostnamectl in containers
9. inference start scripts `${VAR:=…}` defaults not exported
10. `sovereign-osctl doctor` missing load_profile
11. `sovereign-osctl models remove` `${1:?word}` brace ambiguity (R62)
12. `sovereign-osctl` lib-path mismatch (`/usr/local/lib` vs `/usr/lib`) (R81)
13. `live-build-emit.sh` README embedded tmpdir basename → non-reproducible (R84)
14. `first-login-assistant.sh` shipped without Layer B coverage; gap closed
    + Layer 1 lint authored to prevent regression class (R86)

See `docs/src/tdd/bugs-caught.md` for the ledger + 3 distilled
cross-bug Learnings.

### Rounds 61-94 — operator-observability + Phase F + G arcs

**Phase F closer (Rounds 61-77)** — operator surface deepening:
- `sovereign-osctl models {size, remove, list, pull, verify}` complete
- `model-catalog-sync` substantive recurrent hook (replaced stub)
- `version --json` (7-key contract) + `status --json` (8-key contract)
- `whitelabel diff` operator preview verb
- `maintenance` surface expanded 2 → 8 subverbs
- `assistant` surface: full / status / reset / list
- 5-candidate lib-path detection (operator-actionable error on miss)
- Layer B parity across all during-install + post-install hooks
- 3rd Grafana dashboard: `sovereign-os-install.json`
- Root Makefile + `make install` / `make uninstall` (PREFIX/DESTDIR)
- Comprehensive dispatcher-surface L3 (33/33)

**Phase G — operator-observability arc (Rounds 78-94)**:
- Reproducibility self-test gate (`test_reproducibility_self_test.sh`):
  byte-identical mkosi + live-build emissions under pinned inputs
- 51-metric Layer B inventory (was 21) restructured into 7 labeled
  sections; two-way contract enforced (code ↔ inventory) by
  `test_metric_inventory_lockstep.py`
- Hook Layer-B coverage lint (`test_hook_layer_b_coverage.py`):
  every lifecycle hook calls `emit_metric` or carries a waiver
- `sovereign-osctl metrics {list, show, tail, health}` — read .prom
  files without third-party tooling (20-assertion L3)
- `sovereign-osctl alerts [--json]` — 6-rule in-tree engine over .prom
  files; ALERT/WARN with remediation hints (13-assertion L3)
- `sovereign-osctl journal {list, show, tail, errors}` — Layer A
  JSONL surface symmetrical with metrics (21-assertion L3)
- `alerts-check.sh` recurrent hook + `sovereign-alerts-check.timer`
  (hourly); meta-counters back into Layer B (15-assertion L3)
- SDD-023 codifies the alerts contract (6 rules, 2 levels, 5
  tunables, 4 surfaces, 5 test gates, 4 open Q23-X)
- Handoff 003 — operator-observability cold-start signpost
- Install-runbook §5b — Layer A/B/C walkthrough with sovereignty
  posture restated

### Rounds 95-114 — Phase H: contracts + hardening + audit surfaces

**Closing arcs**:
- Rounds 95-103 — closer for the observability arc: CHANGELOG R61-94
  catchup · headless hardening IaC (5 drop-ins) · SDD-024 server
  hardening posture · Handoff 003 trajectory
- Rounds 104-105 — workstation hardening parallel (sain-01 + old-workstation
  get 4 drop-ins, share auditd/pwquality/unattended with server, get
  workstation-tuned sshd, deliberately NO fail2ban) + D-017 + SDD-024
  extended
- Round 106 — in-toto verifier `--deep` mode closes the SDD-019
  triangle (manifest ↔ sums ↔ on-disk)
- Round 107 — `sovereign-osctl history` verb (per-run summary derived
  from JSONL); fourth observability-family verb completing symmetry
- Round 108 — 15th bug caught by L2 contract test: alerts engine
  reacted to `sovereign_os_meta_*` metrics → self-reinforcing loop;
  fix + 9-assertion L2 schema gate codifying SDD-023 Q23-A
- Round 109 — SDD-007 strategy 7 (must-not-touch) implementation;
  7/7 strategies now covered
- Round 110 — Handoff 003 refresh through R109
- Round 111 — `sovereign-osctl audit drift` verb: compares deployed
  hardening drop-ins vs config/{server,workstation} sources; --json mode
- Round 112 — SDD-024 Q24-C resolved: sshd Banner → /etc/issue.net
  (standard pre-auth convention); /etc/issue.net extended with
  "Authorized use only" legal-language line
- Round 113 — SDD-025 codifies the observability CLI architecture
  (4-verb shape + dir resolution + exit codes + --json contract)
- Round 114 — L2 schema test for audit drift --json (parallels alerts
  schema test)

**Operator-facing additions** (Rounds 95-114):
- 6 hardening drop-ins (5 server + 1 workstation-specific sshd)
  totaling ~250 lines of opinionated IaC with invariants pinned in
  Layer 1 lint
- 2 apply hooks (server + workstation) with DEST_PREFIX support for
  chroot/image-build flows + idempotency + drift detection
- 4 new sovereign-osctl verbs: `history` + `audit drift` + (carried
  from R88-91) `metrics`/`alerts`/`journal`
- `audit provenance --deep` flag completing the in-toto verifier
- 3 new SDDs: SDD-023 (alerts contract) · SDD-024 (server + workstation
  hardening posture) · SDD-025 (observability CLI architecture)
- 3 new decision-log entries: D-015 (alerts) · D-016 (server hardening) ·
  D-017 (workstation hardening parallel)
- 2 new L2 schema contract tests (alerts JSON + drift JSON)
- ~115 lint assertions (was ~92); ~70 unit tests (was ~62); ~55 L3
  nspawn tests (was ~52)

**Bug ledger**: now at 15 real wiring bugs caught (was 14 at start of
Phase H). #15 — alerts engine reacted to its own meta-metrics — caught
by L2 schema test within minutes of being authored, locked by an
explicit code guard + permanent test gate.

### Question closures (every PR-1-seed Q-X resolved/partial)
| Q | Status | Resolution |
|---|---|---|
| Q-001 | resolved | SDD-003 (substrate survey — mkosi primary) |
| Q-002 | resolved | SDD-004 (profile schema + mixins; merge rules pinned; fork/overlay are operator-side workflows) |
| Q-003 | deferred-with-criteria | SDD-012 (brand identity placeholder) |
| Q-004 | resolved | SDD-007 (legal scope) |
| Q-005 | resolved | SDD-017 (ZFS root layout) |
| Q-006 | resolved | SDD-015 (secure-boot 3-level posture) |
| Q-007 | resolved | SDD-018 (kernel choice — dual strategy) |
| Q-008 | resolved | SDD-013 (installer experience — image-only) |
| Q-009 | operator-side | hardware procurement |
| Q-010 | resolved | SDD-020 (CI infrastructure — GHA only) |
| Q-011 | resolved | SDD-001 (cross-repo boundaries) |
| Q-012 | resolved | minimal + developer + headless profiles landed |
| Q-013 | resolved | SDD-016 (observability bindings) |
| Q-014 | resolved | SDD-014 (decommission testing scope) |
| Q-015 | resolved | SDD-019 (reproducibility target) |
| Q-016 | resolved | SDD-021 (distro-base — Debian 13) |
| Q-017 | resolved | SDD-011 (inference backend stack) |
| Q-018 | resolved | first-login-assistant + cloud-init pre-add path + sovereign-osctl assistant surface (R67) + Layer B (R86) |
| Q-019 | resolved | sovereign-osctl 15 verb groups + 30+ subverbs + SDD-025 CLI architecture; 37-assertion dispatch L3 gate |

Plus Stage-2+ sub-questions: Q15-B (SDD-022) + Q18-A (Round 30
short-circuit) resolved; Q15-A/C, Q16-A..D, Q18-B..C, Q22-A..C tracked.

## Pre-history

Foundation-phase PRs 1–10 landed:
- PR 1 — charter + decisions log + INDEX files
- PR 2 — cross-repo boundaries (SDD-001)
- PR 3 — documentation pipeline (SDD-002) + mdbook
- PR 4 — substrate survey (SDD-003 → Gate 2)
- PR 5 — profile schema (SDD-004 → Gate 3)
- PR 6 — initial profile stubs (SDD-005)
- PR 7 — Debian surface audit (SDD-006)
- PR 8 — whitelabel mechanism (SDD-007 → Gate 4)
- PR 9 — TDD harness spec (SDD-008)
- PR 10 — TDD harness bootstrap (SDD-009 → Gate 5)

See `docs/decisions.md` § D-001..D-003 for the pre-PR-4 charter
decisions.
