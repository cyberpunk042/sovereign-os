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
