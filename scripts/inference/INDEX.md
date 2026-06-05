# Inference stack

Direct-stack architecture per SDD-011 (Q-017 resolution path).

## Per-tier mapping (sain-01 default)

| Tier | Backend | Hardware | Start script |
|---|---|---|---|
| **Pulse** | `bitnet.cpp` | CCD 0 cores 0-5 (CPU) | [`start-pulse.sh`](start-pulse.sh) |
| **Logic Engine** | `vLLM` (primary) + `llama.cpp` (fallback) | RTX 3090 24 GB (VFIO-bound) | [`start-logic-engine.sh`](start-logic-engine.sh) |
| **Oracle Core** | `vLLM` + DFlash drafts | RTX PRO 6000 Blackwell 96 GB | [`start-oracle-core.sh`](start-oracle-core.sh) |

## Router

[`router.py`](router.py) — thin OpenAI-compatible HTTP front for clients that want a single endpoint. Deterministic routing by model-id + request shape; no black-box dispatch.

## Scheduler bridge (cross-repo, MS048)

[`scheduler-bridge.py`](scheduler-bridge.py) — READ-ONLY consumer of the selfdef IPS-side Goldilocks Scheduler (Solution 2). Builds a task descriptor (profile + 4 model-estimated axes), invokes the `selfdef-scheduler-decide` producer binary, and maps the returned route → backend tier (`blackwell`→oracle / `rtx3090`→scout / `cpu`→cortex / `hybrid` / `hibernate`→defer), honoring the integration contract (`cyberpunk042/selfdef/docs/operator/ms048-scheduler-integration-contract.md`): **honor Hibernate · map route→tier · read-only**. Graceful-offline — binary absent/errored → `scheduler_available=False` so the gateway falls back to its own SDD-011 routing; never crashes, never fabricates a route. Binary path via `SELFDEF_SCHEDULER_DECIDE_BIN`. Usable standalone (`scheduler-bridge.py --profile careful --risk 0.2 --json`) or importable (`consult(task) -> verdict`). Maps route → runtime service (blackwell→Oracle Core / rtx3090→Logic Engine / cpu→Pulse). Tests: `tests/unit/test_scheduler_bridge.py` (10 cases).

**Router integration (opt-in, MS048):** `router.py` consults the bridge when `SOVEREIGN_OS_CONSULT_SCHEDULER=1` (default OFF — routing then completely unchanged) and surfaces the scheduler's hardware-tier advisory as the `X-Sovereign-Scheduler-Advisory` response header **without changing the routed tier** (the runtime's `classify()` stays authoritative). Profile via `SOVEREIGN_OS_SCHEDULER_PROFILE` (default `production`). Fail-safe — a missing/broken scheduler never affects routing. Tests: `tests/unit/test_router_scheduler_advisory.py` (5 cases). Making the advisory **authoritative** (router defers routing to the scheduler) remains a separate, explicit operator step.

## Backends

[`backends/bitnet.py`](backends/bitnet.py) · [`backends/vllm.py`](backends/vllm.py) · [`backends/llama_cpp.py`](backends/llama_cpp.py)

Each implements a small adapter contract (`lib/backend.py`).

## Why no unifying abstraction (vs LocalAI)

Per SDD-011: SAIN-01's value is per-tier hardware exploitation. The router speaks OpenAI but routes deterministically; backends remain operator-readable + observable.

## Per-profile differences

- `sain-01`: full Trinity (Pulse + Logic + Oracle).
- `old-workstation`: only `llama.cpp` (single 8 GB GPU). LocalAI acceptable as alternative.
- `minimal` / `headless`: inference disabled.
- `developer` (reserved): `llama.cpp` or operator-installed Ollama.
