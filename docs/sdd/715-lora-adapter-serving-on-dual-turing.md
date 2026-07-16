# SDD-715 — LoRA-adapter serving on the dual-Turing node (IMPLEMENTATION)

> Status: draft (implementation — Slice 2 of the personal-workstation LoRA plan: the *serving* half)
> Owner: operator-directed 2026-07-16 (verbatim): *"go"* (start Slice 2 — the adapter loop, after SDD-714 merged).
> Addresses: closes the serving gap in the M046 LoRA foundry — adapters were inventoried/gated/promoted but
> could not actually be *loaded*. No finding re-opens; new operator-scoped work on **M046** (E0441–E0444).
> Mandate module: **E11.M715**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## The gap this closes

The M046 LoRA foundry is **already built** on the inventory/governance side: `scripts/inference/adapter-foundry.py`
(catalog `class: lora-adapter` + `/var/lib/sovereign-os/adapters/registry.json` promotion state), `adapter-gate.py`
/ `adapter-decide.py` (MS041 triple-gate), the `sovereign-osctl adapters` verb, and the D-11 dashboard. But the
**serving** side was missing: `LlamaCppBackend` had no `--lora`, so a promoted adapter had nowhere to load. And
no adapter was bound to the dual-Turing serving node (SDD-714) with a Bonsai base. Slice 2 lands exactly that —
the E0442 "LoRA-as-profiles" overlay made real on the operator's box.

## What this delivers

- **llama.cpp backend LoRA overlay** (`scripts/inference/backends/llama_cpp.py`): `lora_path` / `lora_scale`
  params → `--lora <path>` (or `--lora-scaled <path> <scale>`), plumbed through `for_dual_turing()`. The base
  stays the shared frozen ternary GGUF; the adapter is a hot-swappable **behavioral overlay, unmerged**
  (E0443 "Do Not Merge Too Early"). This is the exact analogue of SDD-714's `--tensor-split` — the concrete
  argv-layer capability the runtime needs.
- **Two real E0442 candidate adapters** in `models/catalog.yaml` (`class: lora-adapter`, `engine: llama.cpp`),
  bound to `dual-turing-serving`:
  - `sovereign-os-admin-lora` — base `Ternary-Bonsai-27B` (oracle tier), the E0442 "sovereign-os/admin LoRA".
  - `coding-style-lora` — base `Prism-Ternary-Bonsai-8B` (scout tier), the E0442 "coding-style LoRA".
  Both `status: operator-must-confirm` (real weights are operator-supplied and must pass the MS041 triple-gate;
  `adapter-foundry.py list` now inventories all three adapters automatically — no foundry change needed).
- **A serving-coherence lint** (`tests/lint/test_lora_adapter_serving_coherence.py`): every lora-adapter's
  `base_model` must resolve to a real catalog model (stronger than the existing presence-only check); a bound
  runtime profile must actually **serve** that base (E0442 — no overlay-on-unserved-base; `tier_intent`-only
  profiles are skipped as runtime-resolved); and the llama.cpp adapter must expose `--lora`.

## How the loop reads now (with Slice 1)

Train on SAIN-01 (E0446 4090/Blackwell) → promote through the foundry (adapter-gate/decide, MS041 triple-gate,
registry.json) → the adapter is a catalogued `lora-adapter` bound to `dual-turing-serving` → `llama-server
--lora` overlays it on the frozen Bonsai base on the 2×2080. The base is shared; switching adapters is an
overlay swap, not a reload — E0442 "profiles decide overlays", E0443 "don't merge too early".

## Verification

- `python3 -m pytest` on the touched contracts — the new serving-coherence lint, backend-adapters verbatim
  (with the new `--lora` pin), catalog schema + content — all green.
- Functional: `LlamaCppBackend.for_dual_turing(..., lora_path=…)` emits `--lora`; with `lora_scale` →
  `--lora-scaled <path> <scale>`; non-LoRA constructors emit neither. `adapter-foundry.py list` inventories the
  two new adapters (`sovereign-os-admin-lora`, `coding-style-lora`) as `pending` (honest pre-promotion state).
- Full `tests/` + 5 profiles + ruff green; `context.md` sdd count 197→198.
- **Not hardware-verified** (no Turing GPUs / no real adapter weights in CI): a real GGUF LoRA loading on a
  2080 + serving a behavior. The argv, catalog graph, and inventory are proven; the load is a runtime step.

## Scope / posture

- **Serve-only.** No training code here — training stays on SAIN-01 (operator-chosen, SDD-714).
- **bf16 adapters** are recorded as trained; Turing (no native BF16) serves the **F16** conversion — a runtime
  conversion step, noted on each entry.
- **M046 spec (E0441–E0447) untouched** — the serving role lives in the backend + catalog + a lint, not in the
  verbatim/sacrosanct spec YAML.

## Non-goals (Slice 2b + Slice 3)

- **Slice 2b — the transport + ZFS half**: shipping a promoted adapter from SAIN-01 to the box and the E0446
  ZFS "adapter versions + rollback" lineage. This is runtime/ops across two boxes + ZFS — not CI-verifiable
  here; its own SDD when the hardware exists.
- **Multi-adapter-in-one-batch** (S-LoRA / Punica, E0441 M00771–M00772) — slice-1 loads one adapter per served
  base; the batched-multi-adapter path is a later increment.
- **Slice 3** — vision (`mmproj`) + `dspark` speculative-decode draft (BF16→F16 on Turing). Own SDDs.
