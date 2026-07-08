# M086 — AVX-512 scalar-reference → real-SIMD lift plan (per flag)

**Parent**: sovereign-os runtime — the SIMD-acceleration layer beneath M085's three-tier instruction references. M085 shipped **semantically-exact portable scalar references** for the operator's note; M086 is the plan to turn each into an actual `std::arch` hardware kernel, gated by detected capability.
**Source**: operator review request 2026-07-02 ("i wanna see all the CPU/kernel flag and all the work needed") + "fix everything". The flag inventory below is the authoritative CPU-feature map for the note's instructions.
**Codified so far**: `scripts/hardware/avx512-advisor.py` (`tiers` verb — flag/Zen5/host/engine map; `VP2INTERSECT` added) · `crates/sovereign-precision-profile/` (`Tiers::detect()` + `PrecisionProfile::gated_by` — capability gate) · `crates/sovereign-linear/` (`Precision::Bf16` — T1 BF16 now a wired precision).

## The flag inventory (8 core + VPOPCNT-as-two)

Every crate is `#![forbid(unsafe_code)]` today → all nine are **scalar references**, not SIMD. `avx512_vp2intersect` is the one flag with **no hardware on Zen 5** (Intel Tiger-Lake-only, since removed; AMD never implemented) — it stays scalar-only forever on the SAIN-01 baseline.

| # | flag (`/proc/cpuinfo`) | note instruction | tier | Zen 5 | engine status | SIMD-lift work |
|---|---|---|---|---|---|---|
| 1 | `avx512f` | VPTERNLOGD/Q | T2 | ✅ | scalar-ref (`bitops::vpternlog`) | intrinsic `_mm512_ternarylogic_epi64`; consumer = attention-mask fusion |
| 2 | `avx512bw` | (prereq for byte permute/compress) | — | ✅ | — | enables #5/#6 byte-granular paths |
| 3 | `avx512_vnni` | VPDPBUSD | T1 | ✅ | **wired** (`Precision::Int8`) | intrinsic `_mm512_dpbusd_epi32`; drop-in behind the existing `MatI8::matvec` |
| 4 | `avx512_bf16` | VDPBF16PS (`VPDOTBF16PLUS`) | T1 | ✅ | **wired** (`Precision::Bf16`) | intrinsic `_mm512_dpbf16_ps`; drop-in behind `MatBf16::matvec` |
| 5 | `avx512_vbmi` | VPERMB | T3 | ✅ | scalar-ref (`bitops::vpermb`) | intrinsic `_mm512_permutexvar_epi8`; consumer = token/KV shuffle |
| 6 | `avx512_vbmi2` | VPSHLDVQ, VPCOMPRESSB/VPEXPANDB | T3 | ✅ | scalar-ref (`bitops::vpshldv`/`compress`/`expand`) | `_mm512_shldv_epi64`, `_mm512_mask_compress_epi8`/`_mm512_mask_expand_epi8`; consumer = KV-cache compaction |
| 7 | `avx512_vp2intersect` | VP2INTERSECTD/Q | T2 | ❌ **absent** | scalar-ref (`bitops::intersect`) | **none** — no Zen 5 hardware; scalar is the permanent path |
| 8 | `avx512_vpopcntdq` | VPOPCNTD/Q | margin | ✅ | scalar-ref (`bitops::popcount`) | `_mm512_popcnt_epi64`; consumer = ternary BitLinear dot |
| 9 | `avx512_bitalg` | VPOPCNTB/W | margin | ✅ | scalar-ref | `_mm512_popcnt_epi8`; byte-mask popcount |

## The 5-step lift (identical shape per flag)

1. **Intrinsic kernel** — `std::arch::x86_64` behind `#[cfg(target_feature = "…")]`. This is `unsafe`, so it lives in a NEW sibling `-simd` crate (or a relaxed `unsafe` module), never in the `#![forbid(unsafe_code)]` reference crates.
2. **Runtime dispatch** — `std::arch::is_x86_feature_detected!` chooses SIMD vs scalar per call so one binary runs everywhere. (`Tiers::detect()` already does this detection at tier granularity.)
3. **Build flags** — release build with `-C target-cpu=znver5` / `+avx512vnni,+avx512_bf16,+avx512vbmi2,…`. (The build side already does this for `bitnet.cpp`; the Rust engine build does not yet.)
4. **Differential tests** — the existing scalar unit tests become the oracle: SIMD output must equal scalar bit-for-bit. (Already have the scalar tests for all nine.)
5. **Capability + profile gate** — `avx512-advisor` detected caps + `PrecisionProfile.Tiers` opt-in decide whether the SIMD path is used. **This wiring exists** (`Tiers::detect` + `gated_by`); the dispatcher (#2) is the missing link.

## Epics (E0817–E0821)

| epic | name | status |
|---|---|---|
| E0817 | Flag inventory + `avx512-advisor tiers` verb (instruction → flag → Zen5 → host → engine) | **done** (2026-07-02) |
| E0818 | `Precision::Bf16` — T1 BF16 becomes a wired precision (VDPBF16PS reference active in the model path) | **done** (2026-07-02) |
| E0819 | Capability gate — `Tiers::detect()` + `PrecisionProfile::gated_by`; demo reports host caps + gated tiers | **done** (2026-07-02) |
| E0820 | SIMD dispatcher — sibling `-simd` crate with `is_x86_feature_detected!` dispatch, VNNI + BF16 intrinsics first (the two wired precisions), scalar as differential oracle | **open** |
| E0821 | Engine build flags — `-C target-cpu=znver5` release profile for the Rust engine (currently portable-only) | **open** |

## Runtime status

- **Done**: the flag map is authoritative and probeable (`avx512-advisor tiers`); T1 is fully wired at both precisions (INT8 + BF16); the capability gate is live and demonstrated.
- **Open**: no `std::arch` SIMD path exists yet (E0820) — the engine is correct-everywhere scalar; and the Rust release build isn't `znver5`-tuned (E0821). VP2INTERSECT is intentionally excluded from SIMD work (no hardware).
