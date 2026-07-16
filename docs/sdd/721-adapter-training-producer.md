# SDD-721 — the adapter training producer (unsloth on the unpacked base) (IMPLEMENTATION)

> Status: **active — planner shipped** (the GPU training run is SAIN-01-side, deferred like all hardware-gated work)
> Owner: operator-directed 2026-07-16 (verbatim): *"what about custom training, doesn't it take unsloth ? … did we
> handle that already ? like a real support for it and LoRA management and observability and operability ?"*;
> then *"ready"* → build the training-planner slice with recommended defaults (unsloth · unpacked base · QLoRA).
> Addresses: the M046 training producer the foundry deferred to "Stage 4" (`adapter-decide.py`: *"real
> gate-advancing producer (M046 training + eval/oracle/human) is Stage 4"*). Closes the last gap in the loop.
> Mandate module: **E11.M721**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## The gap this closes

LoRA **management + observability + operability** were already built — `adapter-foundry.py` (inventory → D-11
dashboard), `adapter-gate.py` (MS041 triple-gate → D-10 eval-history), `adapter-decide.py` (promote/demote/
rollback + `register`), `adapter-transport.py` (SDD-716, ship + ZFS), `--lora` serving (SDD-715) — and the
**toolchains registry already catalogs unsloth + TRL** (`scripts/models/toolchains.py`). But nothing actually
**trains**: `register` only mints a *pending* adapter (metadata, empty gates); no trainer is invoked. This adds
the producer, so the loop is whole:

    traces → dataset → **TRAIN (this)** → register → MS041 gate → transport (SDD-716) → serve `--lora` (SDD-715)
                                                                                              → rollback

## What this delivers

- **NEW `scripts/inference/adapter-train.py`** — a **planner** (the `adapter-transport` pattern): `plan <id>
  --base <unpacked> --dataset <path> [--method qlora|lora] [--trainer unsloth|trl] [--epochs N]` prints the exact
  commands — an `adapter-decide register` step (mint the pending adapter) + the trainer invocation + the output
  layout `/var/lib/sovereign-os/adapters/<id>/train/` — **DRY-RUN by default**, `--apply` runs them. QLoRA
  defaults (r=16, α=32, lr=2e-4, 4-bit) are operator-overridable. Trainer metadata (install/detect/hardware-fit)
  is read from the existing `toolchains.py` registry — not reinvented. Stdlib-only (no trainer imported at load).
- **The ternary caveat is enforced, not just documented.** A packed ternary/GGUF `--base` **warns**: you cannot
  LoRA-train a 1.58-bit base — train the FP16 LoRA on the **unpacked** safetensors (`prism-ml/Ternary-Bonsai-*-
  unpacked`), base frozen, then serve the adapter over the ternary GGUF (SDD-715). The planner also warns that a
  CUDA trainer belongs on **SAIN-01** (E0446: "4090 → train small LoRAs / QLoRA"), not the serving box.
- **NEW contract lint** `tests/lint/test_adapter_train_contract.py`: present/executable/stdlib; reuses
  toolchains + adapter-decide; plan shape `[register, train]` with base/dataset/output/hyperparams; the ternary
  warning fires; QLoRA=4-bit vs LoRA≠4-bit; DRY-RUN default.

## Why a planner, not the trainer itself

GPU training (unsloth/TRL on the 4090/Blackwell) can't run in CI — no GPUs, no weights — which is exactly why
M046 deferred it. So the deliverable is the **plan** (the exact `register` + trainer commands + the output/
next-step layout, argv-tested) plus the correctness rails (unpacked-base + SAIN-01 warnings). The GPU-side
trainer entry point (`scripts/inference/train/<trainer>-lora.py`) is the operator-supplied Stage-4 piece the
plan invokes; this SDD wires everything up to it and hands off cleanly to the already-built gate → transport →
serve chain.

## On the operator's question directly

- **"does it take unsloth?"** — unsloth is the recommended trainer (2-5× faster QLoRA on consumer GPUs; already
  in `toolchains.py`, Qwen-based archs supported → the unpacked Bonsai). TRL is the alternative (`--trainer trl`).
- **"real support + LoRA management + observability + operability?"** — management/observability/operability:
  **yes, already shipped** (foundry + gate + decide + transport + D-10/D-11 + registry). Training: **this SDD**
  adds the producer/planner; the GPU run is the remaining SAIN-01-side step.

## Verification

- `pytest tests/lint/test_adapter_train_contract.py` — 7 passed; functional: `plan` on an unpacked base emits
  the register+train commands + SAIN-01 warning; a `.gguf` base emits the ternary caveat; QLoRA→4-bit / LoRA→not.
- Full `tests/` + ruff green; `context.md` sdd count bumped.
- **Not GPU-verified** (no CUDA/weights in CI): a real training run producing adapter weights. The plan
  construction, the correctness warnings, and the registry/handoff wiring are proven.

## Non-goals (follow-ups)

- The **GPU-side trainer script** (`train/unsloth-lora.py`) — Stage-4, operator-supplied; needs the SAIN-01 GPUs.
- **Dataset curation from traces** (the E0444 "trace → success/failure examples → curated dataset" pipeline) —
  its own producer.
- **Real gate-producers** (eval numbers feeding the MS041 gate) — `adapter-gate` scores today are operator/stub.
- **`sovereign-osctl adapter-train` verb + api + dashboard** (the §1g ladder) — the core planner lands first.
