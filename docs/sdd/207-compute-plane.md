# SDD-207 — The Sovereign Compute Plane (Phase 1: VRAM-fit job placement)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-12
> Closes findings: operator directive 2026-07-12 — Background Tasks "massive" pass: *"my rtx4090 jobs I guess or a secondary model in general … lets discuss and plan."* Discussed; plan approved: **one compute plane** placing BOTH background models and GPU jobs across the host PRO 6000 + the VFIO-passed 4090/3090 by live VRAM/priority. This SDD is **Phase 1** (the plane core).
> Derived from / extends: the M075 SRP scheduler (`crates/sovereign-srp-scheduler` — roles + VRAM-fit `place()`), SDD-204 (the jobs runtime), the M075 device topology.

## Mission

Give the box a **compute plane**: one scheduler that owns every compute claim
across every device and places by **live free VRAM**, so long-running GPU work
never OOMs the box. It extends the M075 SRP doctrine (Conductor=CPU/ternary,
Logic=RTX 4090 24 GB/quantized, Oracle=Blackwell PRO 6000 96 GB/fp16; fit by
precision + VRAM) from *static* capacities to *live* availability.

The full vision is four phases; this is Phase 1.

| Phase | Delivers |
|---|---|
| **1 — plane core (this SDD)** | host device inventory + live free-VRAM placement; jobs place-or-wait; observable |
| 2 — secondary-model hosting | the gateway multi-model registry; residents placed by the plane |
| 3 — the 4090-VM as a device | wire the guest agent live; the plane spans host + guest |
| 4 — observatory + policy | a plane pane; priorities, eviction, notifications |

## What Phase 1 ships

- NEW `scripts/operator/lib/compute_plane.py` — the plane. Probes host GPUs via
  `nvidia-smi` (live free VRAM) + the CPU, maps each to an SRP role, tracks
  **claims** (a device + VRAM held for a job's life), and `place(need_gb,
  role_pref)` returns a device whose *effective* free VRAM (live free − claims)
  covers the need — preferring the role, else `None` (the caller waits). A
  no-VRAM job places on the CPU (Conductor). Degrade-safe: no `nvidia-smi` →
  CPU-only, and a GPU job honestly waits.
- `jobs-api` (SDD-204) integration: a job with `meta.vram_gb > 0` is **placed
  before it runs** — it waits (state `queued`, "waiting for N GB free VRAM…")
  until a device fits, claims it, runs, and **releases** on completion. So a GPU
  job never OOMs the box; concurrent GPU jobs serialise by VRAM. `GET /plane.json`
  exposes the plane state (devices · live free · claims).
- `sovereign-osctl plane` — read-only: the devices with live free VRAM + the
  outstanding claims. feature-coverage maps `plane → code-console`.
- `tests/lint/test_jobs_runtime_contract.py` extended: placement fits by live
  VRAM (a 40 GB model excludes the 24 GB Logic; a claim removes headroom → queue),
  the CPU-only degrade, and jobs-api **queues (never OOMs)** a job when VRAM is
  exhausted + it stays cancellable while waiting.

## Doctrine + honest gating

- The canonical placement rule is the Rust `sovereign-srp-scheduler::place()`;
  the Python plane is the host-side runtime the jobs daemon consults, mirroring
  the same fit rule. Phase 2 wires the Rust gateway to `place()` for model
  residents.
- **The 4090 tension:** SRP maps the 4090→Logic, but it is VFIO-isolated in a
  guest VM — so in Phase 1 the plane sees only host devices (the PRO 6000 + CPU);
  a `logic`-preferred job with no host 4090 falls back to Oracle or waits. Phase 3
  wires the guest agent so the VM's 4090/3090 appear as devices.
- Phase 1's admission holds a worker thread while a job waits for VRAM (fine at
  the box's concurrency); a dedicated admission scheduler is a Phase-4 refinement.
