# SDD-062 — functional D-22 live chat (the M058 inference producer: real single-prompt inference + a loopback chat proxy + live telemetry)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: none (the deferred M058 inference producer behind D-22's render-only chat composer)
> Derived from: operator directive 2026-07-09 ("the full deal, no minimizing" — chose functional web-chat over the render-only compromise, after SDD-061's adapter gate-producers merged in PR #39); M058 inference producer; D-22 LM status & operability (M060); R10212.

## Mission

Make the D-22 chat composer **actually chat from the panel** — real single-prompt
inference, streaming tokens into the log, plus live inference telemetry on the device
grid. Operator directive: **"the full deal, no minimizing."** Three pieces:

1. **`inference prompt <text>`** — the real single-prompt inference CLI verb (routes a
   prompt through the loopback router → tier backend, streams tokens to stdout).
2. **`POST /api/lm-status/chat`** on the D-22 daemon — a bounded, **loopback-only**
   inference-query proxy → the router's `/v1/chat/completions`, SSE-streaming tokens
   into `#chat-log`. This is the sanctioned, narrow R10212 relaxation (below).
3. **A live-telemetry producer** — records the **real measured** tokens/sec + latency
   from each completion to `/run/sovereign-os/model-state.json` (preserving `loaded`)
   + `model-latency.json`, so D-22's existing SSE device grid shows live inference
   stats (the "live streaming is wired when a producer publishes model-state.json"
   note the panel already carries).

## Problem

- The D-22 chat composer is **render-only**: `chat-send` copies `sovereign-osctl
  inference status # … live chat pending the M058 inference producer` (a real verb,
  no phantom) — there is **no single-prompt inference verb** (`inference` is only
  `{status,start,stop,restart,route,health,logs}`; `route` classifies a prompt's tier
  but never runs it).
- Nothing publishes live inference telemetry — `model-state.json` carries only the
  `loaded` set (SDD-049 load actuation), never `tokens_per_sec`.

## The R10212 posture decision (sanctioned)

The D-22 daemon is currently hard read-only (405 on all POST; the read-only contract
test asserts the *only* mutating POST allowed is `/api/control/execute`). The operator
sanctioned relaxing this **narrowly** ("the full deal, no minimizing"):

- The D-22 daemon gains **one** POST — a bounded, **loopback-only** inference-query
  proxy. A chat completion is a **non-mutating read-compute** on a local model: no
  file/config/model-state change, no shell, no new host process, selfdef/perimeter
  untouched. It is NOT a host/state mutation.
- **All actual mutations stay 405 + exec-rail-only** on the D-22 daemon — model
  load/unload, tier start/stop/restart, adapter promote, etc. The `/api/control/execute`
  rail remains the sole *state-mutating* web path.
- This preserves the **spirit** of R10212 ("web never *arbitrarily mutates* state")
  while enabling a functional chat (a query, not a mutation). Distinct from `sessions
  start` (SDD-058, CLI-only) which runs arbitrary **host code**; a chat prompt runs
  **text through an already-running loopback model**.

**Bounds on the chat endpoint** (defence for the relaxation): forwards only to
`SOVEREIGN_OS_ROUTER_URL` (default `http://127.0.0.1:8080` — loopback, never external);
a max prompt length + a request timeout; no persistence of prompt text beyond the
completion + the derived numeric telemetry; honest error when the router/backend is
unreachable (hardware-gated — never fabricated). SB-077: telemetry is the **real
measured** rate/latency from actual completions, empty when no backend answered.

## Required coverage

### `scripts/inference/prompt.py` — the shared inference-prompt engine

- `run(text, *, stream, timeout)`: POST `{messages:[{role:user,content:text}],
  stream:true}` to `SOVEREIGN_OS_ROUTER_URL/v1/chat/completions` (the router proxies +
  streams the tier's response body — `router.py:445-468`). Yields token deltas;
  measures elapsed + token count → `tokens_per_sec`. Router unreachable → structured
  honest error. Used by BOTH the CLI verb and the web proxy (single source).
- `publish_telemetry(tier, tokens_per_sec, latency_ms)`: read-modify-write
  `model-state.json` — set `tokens_per_sec[role]` (tier→role: pulse→conductor /
  logic→logic / oracle→oracle) + `updated_ts`, **preserving `loaded`** (the SDD-049
  contract `test_models_load` pins) — atomic `os.replace`; append a per-model latency
  record to `model-latency.json` `models`. Never fabricates (only real measurements).
- CLI: `prompt.py "<text>"` streams to stdout; osctl `inference prompt <text>` routes to it.

### `scripts/operator/lm-status-operability-api.py` — the chat proxy

- `POST /api/lm-status/chat` `{prompt, ...}` → the prompt engine → SSE token stream
  back to the browser (loopback-only, bounded, records telemetry). The one sanctioned
  POST; every other POST/PUT/DELETE stays 405. GET surfaces unchanged.

### `webapp/d-22-lm-status-operability/index.html` — the functional composer

- `chat-send` → `fetch('/api/lm-status/chat', {method:'POST', ...})`, render the SSE
  token stream into `#chat-log` (drop the clipboard-copy path). The device grid keeps
  consuming `/api/lm-status/stream` (now fed real `tokens_per_sec`).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-062-A | Chat architecture — render-only vs functional web-chat. | **answered (operator, 2026-07-09): "the full deal, no minimizing" — functional web-chat.** |
| Q-062-B | R10212 framing for the chat POST. | **answered: a chat completion is a non-mutating read-compute to the loopback router; the one narrow POST; all state mutations stay 405 + exec-rail-only.** |
| Q-062-C | Telemetry source. | **answered: real measured tokens/sec + latency from actual completions; honest-empty without a backend (SB-077).** |
| Q-062-D | Which tier serves a chat prompt. | **proposed: the router's `classify()` per prompt (as `/v1/chat/completions` already does); default endpoint the router :8080.** |
| Q-062-E | Multi-turn conversation history. | **proposed: single-turn now; conversation context/history is Stage N.** |

## Goals

- A real, testable single-prompt inference engine reused by both the CLI verb and the
  web chat; a bounded loopback-only chat proxy; a live-telemetry producer that
  preserves the SDD-049 `model-state.json` `loaded` contract.
- Functional chat from the panel (the standing /goal) with the R10212 relaxation kept
  as narrow as possible.

## Non-goals (Stage N)

- Multi-turn conversation history / context windows; a persistent chat log.
- Per-device model targeting beyond the router's `classify()`.
- Auth on the chat endpoint (loopback-only stands in for now).
- The heavy per-tier metrics scraper (telemetry is derived from live completions).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX + mandate E11.M29.
- **Stage 1:** `scripts/inference/prompt.py` (engine + telemetry) + the osctl
  `inference prompt` verb + `tests/unit/test_inference_prompt.py`.
- **Stage 2:** the D-22 `POST /api/lm-status/chat` proxy + the contract-test update
  (permit the one inference-query POST) + the webapp chat wiring.
- **Stage N:** multi-turn history; per-device targeting; the metrics scraper.

## Safety invariants

The chat endpoint is loopback-only + bounded (max prompt length + timeout) + a
non-mutating read-compute — never a host/state mutation; ALL state mutations stay 405
+ exec-rail-only on the D-22 daemon; the exec rail (`/api/control/execute`) is
unchanged; telemetry is real-measured (SB-077 — honest-empty without a backend) and
the writer PRESERVES the `model-state.json` `loaded` set (SDD-049 contract); no prompt
persistence beyond the completion; selfdef/perimeter untouched; router forwarded to
loopback only (never external); MS003 signing unaffected (no signed mutation here).

## Cross-references

- `scripts/inference/router.py` (`classify` + the streaming `/v1/chat/completions`
  proxy, :445-468) — the loopback endpoint the engine POSTs to.
- `scripts/inference/model-health.py` — the telemetry READER (`snapshot()` consumes
  `model-state.json {loaded, tokens_per_sec}` + `model-latency.json {models,kvcache}`).
- `scripts/models/load.py` (SDD-049) — the other `model-state.json` writer (the
  `loaded` set the telemetry writer must preserve; `test_models_load` pins it).
- `scripts/operator/lm-status-operability-api.py` — the D-22 daemon (gains the one POST).
- `tests/lint/test_d22_lm_status_operability_webapp_contract.py` — the read-only
  contract (updated to permit the one inference-query POST). SDD-058 (`sessions start`
  CLI-only precedent), M058 inference producer, R10212.
