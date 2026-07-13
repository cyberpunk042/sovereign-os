# Exotic tool domains

> Six `scripts/<domain>/` trees each hold a lone specialist entry point — real
> operator capabilities that had **no doc, no `--help` discoverability page, no index**
> (each traces to a mandate row or the master spec, but you had to already know it
> existed). This page surfaces them: role, how to invoke, and what already wraps them.
> Enforced complete by `tests/lint/test_exotic_tools_doc.py` — a new script in any of
> these domains can't ship undiscoverable.

Most run standalone as `python3 scripts/<domain>/<name>.py` (each takes `--help`).
Where a domain already has an operator API / osctl surface, it's noted.

## science — GPU-as-scientific-instrument (NVIDIA Warp)

| Script | Role | Invoke |
|---|---|---|
| `scripts/science/science.py` | The operator-facing science catalog CLI (DNA / protein / particle tools). The front door. | `python3 scripts/science/science.py --help` |
| `scripts/science/warp-runner.py` | R558 (SDD-070) — the one Warp-importing backend that runs the differentiable particle sim on GPU (`--device auto/cuda/cpu`), emits metrics (`--emit-metrics`, `--json`). Driven by `science.py` / `scripts/operator/science-api.py`, not run by hand normally. | `python3 scripts/science/warp-runner.py --help` |

**Already surfaced:** `scripts/operator/science-api.py` (loopback API) + the science catalog card. This page documents the backend so the pair is discoverable.

## research — hardware-exploit research loop

| Script | Role | Invoke |
|---|---|---|
| `scripts/research/loop.py` | R287 (E1.M19) — operator-named *"hardware-exploit-to-the-max research loop (continuously evolving SDD + TDD as new BitNet / … land)"*. `--config PATH`, `--json`/`--human`. | `python3 scripts/research/loop.py --help` |

## insights — filesystem / log insight synthesis

| Script | Role | Invoke |
|---|---|---|
| `scripts/insights/synthesize.py` | R234 (SDD-026 Z-10) — operator-named log + filesystem-usage insight synthesizer (`usage` global + per-source views). | `python3 scripts/insights/synthesize.py --help` |

## history — cross-surface history aggregation

| Script | Role | Invoke |
|---|---|---|
| `scripts/history/aggregate.py` | R246 (SDD-026 Z-16) — operator-named aggregator across OS / Services / Modules / Tools / Dashboards / Configurations / Options history (`--source`, `--since` ISO-8601, `--limit`). | `python3 scripts/history/aggregate.py --help` |

## weaver — atomic state-fabric transitions

| Script | Role | Invoke |
|---|---|---|
| `scripts/weaver/atomic-state.py` | Master spec §21 (The Weaver Execution) — the Atomic State Transition Protocol over the 4 operator-named state files (`--from-stdin` / `--from-file`; catalog of the 4 state-fabric targets). | `python3 scripts/weaver/atomic-state.py --help` |

**Already surfaced:** a `scripts/operator/weaver-*.py` API backs the state fabric; this page documents the atomic-transition primitive.

## pulse — 1-bit (ternary) runtime build pipeline

| Script | Role | Invoke |
|---|---|---|
| `scripts/pulse/build-bitnet.sh` | Master spec §15–17 — builds the Pulse runtime (bitnet.cpp) from Microsoft's upstream with the AVX-512 fusion path. | `bash scripts/pulse/build-bitnet.sh` |
| `scripts/pulse/wasm-aot.sh` | Master spec §20 — the Wasm→AVX-512 Ahead-Of-Time compilation pipeline (avoids JIT bloat for low-bit matrix logic). | `bash scripts/pulse/wasm-aot.sh` |

`scripts/pulse/lib/` + `scripts/pulse/sample/` are the build helpers + sample inputs these two drive.

## Why these were "hidden"

Each is the sole entry point of its domain, born from a specific mandate row / master-spec section, but with no cross-cutting index they read as orphans on a directory listing. The reserved SDD band 300–399 ("science-tools") is their eventual structured home; until an owning session picks that up, this page is the discoverability surface, and the lint keeps it complete.
