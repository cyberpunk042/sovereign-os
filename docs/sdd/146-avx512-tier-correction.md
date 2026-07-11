# SDD-146 — AVX-512 AI-workload tier correction (D-21 Features-CPU: popcount is T4 margin, not T3)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the D-21 lm-orchestration panel's Features-CPU tier grouping disagreed with the canonical M085 note / config/hardware/m086 / scripts/hardware/avx512-advisor.py — it filed `avx512_vpopcntdq` (popcount) under "T3 · Bit manipulation" and VNNI/VBMI under "T2 · AI acceleration". Operator (2026-07-11, verbatim): "i saw popcount as t3 somewhere and thats wrong, that would be T4, we can clearly see what t3 is here" + "the task is simple we want to exploit everything and properly". Recover band (SDD-146 / E11.M146 per SDD-100).
> Derived from / extends: SDD-111 (which shipped the original D-21 Features-CPU tier scaffold); the canonical M085 three-tier note (2026-07-02). §1g.

## Mission

Make the D-21 Features-CPU panel agree with the canonical AVX-512 AI-workload tiering, exploiting every instruction family properly and never mislabelling popcount as a structural tier.

## Problem

The panel authored an ad-hoc grouping (`CPU_TIERS`) over the real `/proc/cpuinfo` flags that diverged from the canonical spec on three counts:

| Flag | Panel said (wrong) | Canonical (M085/m086/avx512-advisor) |
|---|---|---|
| `avx512_vnni` (VPDPBUSD) | T2 · AI acceleration | **T1** — Quantisation & dot-product (VNNI) |
| `avx512vbmi` (VPERMB) | T2 · AI acceleration | **T3** — Structure, prune & KV-cache (VBMI/CD) |
| `avx512_vpopcntdq` (VPOPCNTDQ) | **T3** · Bit manipulation | **T4 / margin** — Pop-count (ternary/mask) |

The operator's handwritten note (the authority) defines: **T1** = Quantisation & Dot Product (VNNI: VPDPBUSD INT8, VPDOTBF16PLUS/VDPBF16PS BF16); **T2** = Bitwise Logic & Attention (VPTERNLOGD/Q LUT, VP2INTERSECTD/Q token corr.); **T3** = Structuration, Élagage & KV-Cache (VBMI/CD: VPERMB/VPSHLDV, VPCOMPRESSB/VPEXPANDB); popcount sits in a separate **T4 margin** (VPOPCNTDQ + BITALG). The in-repo canonical surfaces (m085/m086/avx512-advisor) already encode exactly this; only the D-21 panel drifted.

## Fix (presentation-only)

- **`webapp/d-21-lm-orchestration/index.html`** — `CPU_TIERS` re-grouped to mirror `avx512-advisor.py` `TIER_INSTRUCTIONS` (flag→tier) exactly:
  - `Foundation floor · vector width (prerequisites)` — `avx512vl`, `avx512bw`, `avx512dq`
  - `T1 · Quantisation & dot-product (VNNI · VPDPBUSD/VDPBF16PS)` — `avx512_vnni`, `avx512_bf16`
  - `T2 · Bitwise logic & attention (VPTERNLOG LUT · VP2INTERSECT)` — `avx512f`, `avx512_vp2intersect`
  - `T3 · Structure, prune & KV-cache (VBMI/CD · VPERMB/VPCOMPRESSB)` — `avx512vbmi`, `avx512_vbmi2`
  - `T4 · Pop-count margin (ternary/mask · VPOPCNTDQ/BITALG)` — `avx512_vpopcntdq`, `avx512_bitalg`
  - Flags the daemon does not probe (`avx512_bf16`/`avx512_vbmi2`/`avx512_vp2intersect`/`avx512_bitalg`) render an honest `—` (never a fabricated ✓ — SB-077); VP2INTERSECT is Zen-5-absent by design. The Rowhammer honest-deferred row is untouched.
- **`tests/lint/test_cpu_features_build_binding.py`** — the stale tier comment (`# T2 vector popcount + intersect`, `# T1 foundation + T2 compute + T3 byte/permute`) corrected to the canonical tier labels; the asserted RUSTFLAGS tuple is unchanged (comment-only).

## R10212 / SB-077 preserved

Read-only presentation only — the panel still consumes `/api/lm-orchestration/features` and never mutates (R10212); unprobed flags stay honest `—` (SB-077). No behaviour/data/API change; the live ✓ resolution for every real daemon flag is preserved.

## Verification

- `tests/lint/test_d21_lm_orchestration_webapp_contract.py` + `tests/lint/test_cpu_features_build_binding.py` green (27 passed) — the D-21 contract still finds the `T1 ·`/`T2 ·`/`T3 ·` tiers + the honest-deferred Rowhammer row.
- Full lint suite: 5904 passed, 39 skipped; the only 2 failures (`test_oracle_blackwell_nvfp4.py` NVFP4 dry-run path) are **pre-existing** and unrelated (verified: they fail identically with these edits stashed).

## On completion

The D-21 Features-CPU panel matches the canonical M085 tiering: popcount is the T4 margin, T3 is the VBMI/CD structuration/prune/KV-cache tier, T1 is VNNI quant/dot. Every instruction family is exploited and labelled per the operator's note.

## Cross-references

- `config/hardware/m085-zen5-three-tier-instructions.yaml` (the tier contract); `config/hardware/m086-avx512-simd-lift-plan.yaml` (per-flag `tier:`); `scripts/hardware/avx512-advisor.py` `TIER_INSTRUCTIONS`. SDD-111 (original D-21 tier scaffold); SDD-100 — band scheme.
