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

## Features (F07211–F07295)

| feature | name | source |
|---|---|---|
| F07211 | Doctrinal — 9 core flags + VPOPCNT-as-two | flag inventory |
| F07212 | Doctrinal — all nine are scalar references (no SIMD yet) | flag inventory |
| F07213 | Doctrinal — avx512_vp2intersect has no hardware on Zen 5 | flag inventory |
| F07214 | Doctrinal — scalar-only forever on SAIN-01 baseline | flag inventory |
| F07215 | Epic E0817 — Flag inventory + avx512-advisor tiers verb | epics |
| F07216 | Epic E0818 — Precision::Bf16 wired precision | epics |
| F07217 | Epic E0819 — Capability gate (Tiers::detect + PrecisionProfile::gated_by) | epics |
| F07218 | Epic E0820 — SIMD dispatcher (sibling -simd crate) | epics |
| F07219 | Epic E0821 — Engine build flags (-C target-cpu=znver5) | epics |
| F07220 | Flag 1 — avx512f → VPTERNLOGD/Q | flag inventory |
| F07221 | Flag 2 — avx512bw (prereq for byte permute/compress) | flag inventory |
| F07222 | Flag 3 — avx512_vnni → VPDPBUSD (wired) | flag inventory |
| F07223 | Flag 4 — avx512_bf16 → VDPBF16PS (wired) | flag inventory |
| F07224 | Flag 5 — avx512_vbmi → VPERMB | flag inventory |
| F07225 | Flag 6 — avx512_vbmi2 → VPSHLDV/VPCOMPRESSB/VPEXPANDB | flag inventory |
| F07226 | Flag 7 — avx512_vp2intersect → VP2INTERSECTD/Q (no Zen 5 hardware) | flag inventory |
| F07227 | Flag 8 — avx512_vpopcntdq → VPOPCNTD/Q | flag inventory |
| F07228 | Flag 9 — avx512_bitalg → VPOPCNTB/W | flag inventory |
| F07229 | 5-step lift — Step 1: Intrinsic kernel (std::arch::x86_64) | five_step_lift |
| F07230 | 5-step lift — Step 2: Runtime dispatch (is_x86_feature_detected!) | five_step_lift |
| F07231 | 5-step lift — Step 3: Build flags (-C target-cpu=znver5) | five_step_lift |
| F07232 | 5-step lift — Step 4: Differential tests (scalar = SIMD bit-for-bit) | five_step_lift |
| F07233 | 5-step lift — Step 5: Capability + profile gate | five_step_lift |
| F07234 | Runtime status — E0817 done (flag inventory + avx512-advisor tiers) | runtime status |
| F07235 | Runtime status — E0818 done (Precision::Bf16 wired) | runtime status |
| F07236 | Runtime status — E0819 done (capability gate live) | runtime status |
| F07237 | Runtime status — E0820 open (no std::arch SIMD yet) | runtime status |
| F07238 | Runtime status — E0821 open (Rust release not znver5-tuned) | runtime status |
| F07239 | Codified — avx512-advisor.py tiers verb | codified |
| F07240 | Codified — PrecisionProfile::gated_by | codified |
| F07241 | Codified — Tiers::detect() | codified |
| F07242 | Codified — sovereign-precision-profile crate | codified |
| F07243 | Safety — #![forbid(unsafe_code)] in reference crates | safety |
| F07244 | Safety — SIMD lives in NEW sibling -simd crate (or relaxed unsafe module) | safety |
| F07245 | Safety — runtime dispatch chooses SIMD vs scalar per call | safety |
| F07246 | Safety — one binary runs everywhere | safety |
| F07247 | Cross-ref — M085 Zen5 three-tier instruction references | cross-ref |
| F07248 | Cross-ref — M073 one-bit-ternary-logic-bitlinear-core | cross-ref |
| F07249 | Cross-ref — M074 avx-512-vnni-hardware-fusion | cross-ref |
| F07250 | Cross-ref — M077 nvfp4-pretraining-and-inference-pipeline | cross-ref |
| F07251 | Cross-ref — M038 avx512-cortex-hot-path | cross-ref |
| F07252 | Cross-ref — M058 hardware-aware-scheduling-goldilocks | cross-ref |
| F07253 | Operator review — "i wanna see all the CPU/kernel flag and all the work needed" | operator review |
| F07254 | Operator review — "fix everything" | operator review |
| F07255 | Intrinsic — _mm512_ternarylogic_epi64 (VPTERNLOG) | intrinsics |
| F07256 | Intrinsic — _mm512_dpbusd_epi32 (VNNI) | intrinsics |
| F07257 | Intrinsic — _mm512_dpbf16_ps (BF16) | intrinsics |
| F07258 | Intrinsic — _mm512_permutexvar_epi8 (VPERMB) | intrinsics |
| F07259 | Intrinsic — _mm512_shldv_epi64 (VPSHLDV) | intrinsics |
| F07260 | Intrinsic — _mm512_mask_compress_epi8 (VPCOMPRESSB) | intrinsics |
| F07261 | Intrinsic — _mm512_mask_expand_epi8 (VPEXPANDB) | intrinsics |
| F07262 | Intrinsic — none for VP2INTERSECT (no Zen 5 hardware) | intrinsics |
| F07263 | Intrinsic — _mm512_popcnt_epi64 (VPOPCNTD/Q) | intrinsics |
| F07264 | Intrinsic — _mm512_popcnt_epi8 (VPOPCNTB/W) | intrinsics |
| F07265 | Consumer — attention-mask fusion (VPTERNLOG) | consumers |
| F07266 | Consumer — token/KV shuffle (VPERMB) | consumers |
| F07267 | Consumer — KV-cache compaction (VPCOMPRESSB/VPEXPANDB) | consumers |
| F07268 | Consumer — ternary BitLinear dot (VPOPCNT) | consumers |
| F07269 | Build — -C target-cpu=znver5 release profile | build |
| F07270 | Build — +avx512vnni,+avx512_bf16,+avx512vbmi2,… | build |
| F07271 | Build — bitnet.cpp already uses these flags | build |
| F07272 | Build — Rust engine build does not yet (E0821) | build |
| F07273 | Test — existing scalar unit tests become oracle | test |
| F07274 | Test — SIMD output must equal scalar bit-for-bit | test |
| F07275 | Test — all nine flags have scalar tests already | test |
| F07276 | Dispatcher — std::arch::is_x86_feature_detected! per call | dispatcher |
| F07277 | Dispatcher — Tiers::detect() already does tier-granularity detection | dispatcher |
| F07278 | Dispatcher — PrecisionProfile.Tiers opt-in decides SIMD vs scalar | dispatcher |
| F07279 | Gate — avx512-advisor detected caps | gate |
| F07280 | Gate — PrecisionProfile::gated_by | gate |
| F07281 | Gate — demo reports host caps + gated tiers | gate |
| F07282 | Project boundary — SIMD-acceleration layer beneath M085 | boundary |
| F07283 | Project boundary — M085 shipped semantically-exact portable scalar references | boundary |
| F07284 | Source — operator review request 2026-07-02 | source |
| F07285 | Source — "fix everything" operator directive | source |
| F07286 | avx512-advisor — instruction → flag → Zen5 → host → engine map | codified |
| F07287 | avx512-advisor — VP2INTERSECT added to tiers verb | codified |
| F07288 | avx512-advisor — flag inventory is authoritative CPU-feature map | codified |
| F07289 | avx512-advisor — probeable (tiers verb) | codified |
| F07290 | Precision::Bf16 — T1 BF16 becomes wired precision | codified |
| F07291 | Precision::Bf16 — VDPBF16PS reference active in model path | codified |
| F07292 | Capability gate — Tiers::detect() + PrecisionProfile::gated_by | codified |
| F07293 | Capability gate — demo reports host caps + gated tiers | codified |
| F07294 | Engine — correct-everywhere scalar (no SIMD yet) | runtime status |
| F07295 | Engine — VP2INTERSECT intentionally excluded from SIMD work | runtime status |

## Requirements (R14421–R14590)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R14421 | Doctrinal — 9 core flags + VPOPCNT-as-two | flag inventory | F07211 | non-negotiable | false | 10 |
| R14422 | Doctrinal — every crate is #![forbid(unsafe_code)] today | flag inventory | F07212 | non-negotiable | false | 10 |
| R14423 | Doctrinal — all nine are scalar references, not SIMD | flag inventory | F07212 | non-negotiable | false | 10 |
| R14424 | Doctrinal — avx512_vp2intersect is the one flag with no hardware on Zen 5 | flag inventory | F07213 | non-negotiable | false | 10 |
| R14425 | Doctrinal — Intel Tiger-Lake-only, since removed; AMD never implemented | flag inventory | F07213 | non-negotiable | false | 10 |
| R14426 | Doctrinal — avx512_vp2intersect stays scalar-only forever on SAIN-01 | flag inventory | F07214 | non-negotiable | false | 10 |
| R14427 | Doctrinal — the 5-step lift is identical shape per flag | five_step_lift | F07229 | non-negotiable | false | 10 |
| R14428 | Doctrinal — one binary runs everywhere (runtime dispatch) | five_step_lift | F07230 | non-negotiable | false | 10 |
| R14429 | E0817 — Flag inventory + avx512-advisor tiers verb | epics | F07215 | non-negotiable | false | 10 |
| R14430 | E0817 — instruction → flag → Zen5 → host → engine map | epics | F07215 | non-negotiable | false | 10 |
| R14431 | E0817 — VP2INTERSECT added to tiers verb | epics | F07215 | non-negotiable | false | 10 |
| R14432 | E0817 — flag inventory is authoritative CPU-feature map | epics | F07215 | non-negotiable | false | 10 |
| R14433 | E0817 — probeable via avx512-advisor tiers | epics | F07215 | non-negotiable | false | 10 |
| R14434 | E0817 — done (2026-07-02) | epics | F07215 | non-negotiable | false | 10 |
| R14435 | E0817 — codified in scripts/hardware/avx512-advisor.py | epics | F07215 | non-negotiable | false | 10 |
| R14436 | E0817 — cross-ref M085 flag inventory | epics | F07215 | non-negotiable | false | 10 |
| R14437 | E0818 — Precision::Bf16 wired precision | epics | F07216 | non-negotiable | false | 10 |
| R14438 | E0818 — VDPBF16PS reference active in model path | epics | F07216 | non-negotiable | false | 10 |
| R14439 | E0818 — done (2026-07-02) | epics | F07216 | non-negotiable | false | 10 |
| R14440 | E0818 — codified in crates/sovereign-linear/ | epics | F07216 | non-negotiable | false | 10 |
| R14441 | E0818 — cross-ref M085 T1 BF16 engine | epics | F07216 | non-negotiable | false | 10 |
| R14442 | E0818 — cross-ref M086 flag 4 (avx512_bf16) | epics | F07216 | non-negotiable | false | 10 |
| R14443 | E0819 — Capability gate (Tiers::detect() + PrecisionProfile::gated_by) | epics | F07217 | non-negotiable | false | 10 |
| R14444 | E0819 — Tiers::detect() already detects at tier granularity | epics | F07217 | non-negotiable | false | 10 |
| R14445 | E0819 — PrecisionProfile::gated_by gates by capability | epics | F07217 | non-negotiable | false | 10 |
| R14446 | E0819 — demo reports host caps + gated tiers | epics | F07217 | non-negotiable | false | 10 |
| R14447 | E0819 — done (2026-07-02) | epics | F07217 | non-negotiable | false | 10 |
| R14448 | E0819 — codified in crates/sovereign-precision-profile/ | epics | F07217 | non-negotiable | false | 10 |
| R14449 | E0819 — cross-ref M085 precision-as-flexible-profile | epics | F07217 | non-negotiable | false | 10 |
| R14450 | E0819 — cross-ref M086 flag inventory runtime detection | epics | F07217 | non-negotiable | false | 10 |
| R14451 | E0820 — SIMD dispatcher (sibling -simd crate) | epics | F07218 | non-negotiable | false | 10 |
| R14452 | E0820 — std::arch::x86_64 behind #[cfg(target_feature = "...")] | epics | F07218 | non-negotiable | false | 10 |
| R14453 | E0820 — unsafe lives in NEW sibling -simd crate | epics | F07218 | non-negotiable | false | 10 |
| R14454 | E0820 — never in #![forbid(unsafe_code)] reference crates | epics | F07218 | non-negotiable | false | 10 |
| R14455 | E0820 — runtime dispatch chooses SIMD vs scalar per call | epics | F07218 | non-negotiable | false | 10 |
| R14456 | E0820 — is_x86_feature_detected! per call | epics | F07218 | non-negotiable | false | 10 |
| R14457 | E0820 — VNNI + BF16 intrinsics first (two wired precisions) | epics | F07218 | non-negotiable | false | 10 |
| R14458 | E0820 — scalar as differential oracle | epics | F07218 | non-negotiable | false | 10 |
| R14459 | E0820 — open (no std::arch SIMD path exists yet) | epics | F07218 | non-negotiable | false | 10 |
| R14460 | E0820 — cross-ref M085 drop-in SIMD paths | epics | F07218 | non-negotiable | false | 10 |
| R14461 | E0820 — cross-ref M086 flag 3 (avx512_vnni) | epics | F07218 | non-negotiable | false | 10 |
| R14462 | E0820 — cross-ref M086 flag 4 (avx512_bf16) | epics | F07218 | non-negotiable | false | 10 |
| R14463 | E0821 — Engine build flags (-C target-cpu=znver5) | epics | F07219 | non-negotiable | false | 10 |
| R14464 | E0821 — release profile with +avx512vnni,+avx512_bf16,+avx512vbmi2,… | epics | F07219 | non-negotiable | false | 10 |
| R14465 | E0821 — bitnet.cpp already uses these flags | epics | F07219 | non-negotiable | false | 10 |
| R14466 | E0821 — Rust engine build does not yet | epics | F07219 | non-negotiable | false | 10 |
| R14467 | E0821 — open (not znver5-tuned) | epics | F07219 | non-negotiable | false | 10 |
| R14468 | E0821 — cross-ref M085 build discipline | epics | F07219 | non-negotiable | false | 10 |
| R14469 | E0821 — one edit to release profile needed | epics | F07219 | non-negotiable | false | 10 |
| R14470 | E0821 — no new dependency | epics | F07219 | non-negotiable | false | 10 |
| R14471 | Flag 1 — avx512f → VPTERNLOGD/Q | flag inventory | F07220 | non-negotiable | false | 10 |
| R14472 | Flag 1 — T2 tier | flag inventory | F07220 | non-negotiable | false | 10 |
| R14473 | Flag 1 — Zen 5: ✅ | flag inventory | F07220 | non-negotiable | false | 10 |
| R14474 | Flag 1 — engine: scalar-ref (bitops::vpternlog) | flag inventory | F07220 | non-negotiable | false | 10 |
| R14475 | Flag 1 — SIMD-lift: _mm512_ternarylogic_epi64 | flag inventory | F07220 | non-negotiable | false | 10 |
| R14476 | Flag 1 — consumer: attention-mask fusion | flag inventory | F07220 | non-negotiable | false | 10 |
| R14477 | Flag 2 — avx512bw (prereq for byte permute/compress) | flag inventory | F07221 | non-negotiable | false | 10 |
| R14478 | Flag 2 — Zen 5: ✅ | flag inventory | F07221 | non-negotiable | false | 10 |
| R14479 | Flag 2 — enables #5/#6 byte-granular paths | flag inventory | F07221 | non-negotiable | false | 10 |
| R14480 | Flag 2 — no standalone instruction; prerequisite only | flag inventory | F07221 | non-negotiable | false | 10 |
| R14481 | Flag 3 — avx512_vnni → VPDPBUSD | flag inventory | F07222 | non-negotiable | false | 10 |
| R14482 | Flag 3 — T1 tier | flag inventory | F07222 | non-negotiable | false | 10 |
| R14483 | Flag 3 — Zen 5: ✅ | flag inventory | F07222 | non-negotiable | false | 10 |
| R14484 | Flag 3 — engine: wired (Precision::Int8) | flag inventory | F07222 | non-negotiable | false | 10 |
| R14485 | Flag 3 — SIMD-lift: _mm512_dpbusd_epi32 | flag inventory | F07222 | non-negotiable | false | 10 |
| R14486 | Flag 3 — drop-in behind MatI8::matvec | flag inventory | F07222 | non-negotiable | false | 10 |
| R14487 | Flag 3 — cross-ref M085 E0808 | flag inventory | F07222 | non-negotiable | false | 10 |
| R14488 | Flag 3 — cross-ref M086 E0820 VNNI intrinsics | flag inventory | F07222 | non-negotiable | false | 10 |
| R14489 | Flag 4 — avx512_bf16 → VDPBF16PS (VPDOTBF16PLUS) | flag inventory | F07223 | non-negotiable | false | 10 |
| R14490 | Flag 4 — T1 tier | flag inventory | F07223 | non-negotiable | false | 10 |
| R14491 | Flag 4 — Zen 5: ✅ | flag inventory | F07223 | non-negotiable | false | 10 |
| R14492 | Flag 4 — engine: wired (Precision::Bf16) | flag inventory | F07223 | non-negotiable | false | 10 |
| R14493 | Flag 4 — SIMD-lift: _mm512_dpbf16_ps | flag inventory | F07223 | non-negotiable | false | 10 |
| R14494 | Flag 4 — drop-in behind MatBf16::matvec | flag inventory | F07223 | non-negotiable | false | 10 |
| R14495 | Flag 4 — cross-ref M085 E0809 | flag inventory | F07223 | non-negotiable | false | 10 |
| R14496 | Flag 4 — cross-ref M086 E0820 BF16 intrinsics | flag inventory | F07223 | non-negotiable | false | 10 |
| R14497 | Flag 5 — avx512_vbmi → VPERMB | flag inventory | F07224 | non-negotiable | false | 10 |
| R14498 | Flag 5 — T3 tier | flag inventory | F07224 | non-negotiable | false | 10 |
| R14499 | Flag 5 — Zen 5: ✅ | flag inventory | F07224 | non-negotiable | false | 10 |
| R14500 | Flag 5 — engine: scalar-ref (bitops::vpermb) | flag inventory | F07224 | non-negotiable | false | 10 |
| R14501 | Flag 5 — SIMD-lift: _mm512_permutexvar_epi8 | flag inventory | F07224 | non-negotiable | false | 10 |
| R14502 | Flag 5 — consumer: token/KV shuffle | flag inventory | F07224 | non-negotiable | false | 10 |
| R14503 | Flag 6 — avx512_vbmi2 → VPSHLDV, VPCOMPRESSB/VPEXPANDB | flag inventory | F07225 | non-negotiable | false | 10 |
| R14504 | Flag 6 — T3 tier | flag inventory | F07225 | non-negotiable | false | 10 |
| R14505 | Flag 6 — Zen 5: ✅ | flag inventory | F07225 | non-negotiable | false | 10 |
| R14506 | Flag 6 — engine: scalar-ref (bitops::vpshldv/compress/expand) | flag inventory | F07225 | non-negotiable | false | 10 |
| R14507 | Flag 6 — SIMD-lift: _mm512_shldv_epi64 | flag inventory | F07225 | non-negotiable | false | 10 |
| R14508 | Flag 6 — SIMD-lift: _mm512_mask_compress_epi8 / _mm512_mask_expand_epi8 | flag inventory | F07225 | non-negotiable | false | 10 |
| R14509 | Flag 6 — consumer: KV-cache compaction | flag inventory | F07225 | non-negotiable | false | 10 |
| R14510 | Flag 6 — cross-ref M085 E0813 | flag inventory | F07225 | non-negotiable | false | 10 |
| R14511 | Flag 7 — avx512_vp2intersect → VP2INTERSECTD/Q | flag inventory | F07226 | non-negotiable | false | 10 |
| R14512 | Flag 7 — T2 tier | flag inventory | F07226 | non-negotiable | false | 10 |
| R14513 | Flag 7 — Zen 5: ❌ absent | flag inventory | F07226 | non-negotiable | false | 10 |
| R14514 | Flag 7 — Intel Tiger-Lake-only, since removed | flag inventory | F07226 | non-negotiable | false | 10 |
| R14515 | Flag 7 — AMD never implemented | flag inventory | F07226 | non-negotiable | false | 10 |
| R14516 | Flag 7 — scalar-only forever on SAIN-01 | flag inventory | F07226 | non-negotiable | false | 10 |
| R14517 | Flag 7 — SIMD-lift: none (no Zen 5 hardware) | flag inventory | F07226 | non-negotiable | false | 10 |
| R14518 | Flag 7 — cross-ref M085 E0811 | flag inventory | F07226 | non-negotiable | false | 10 |
| R14519 | Flag 8 — avx512_vpopcntdq → VPOPCNTD/Q | flag inventory | F07227 | non-negotiable | false | 10 |
| R14520 | Flag 8 — margin tier | flag inventory | F07227 | non-negotiable | false | 10 |
| R14521 | Flag 8 — Zen 5: ✅ | flag inventory | F07227 | non-negotiable | false | 10 |
| R14522 | Flag 8 — engine: scalar-ref (bitops::popcount) | flag inventory | F07227 | non-negotiable | false | 10 |
| R14523 | Flag 8 — SIMD-lift: _mm512_popcnt_epi64 | flag inventory | F07227 | non-negotiable | false | 10 |
| R14524 | Flag 8 — consumer: ternary BitLinear dot | flag inventory | F07227 | non-negotiable | false | 10 |
| R14525 | Flag 9 — avx512_bitalg → VPOPCNTB/W | flag inventory | F07228 | non-negotiable | false | 10 |
| R14526 | Flag 9 — margin tier | flag inventory | F07228 | non-negotiable | false | 10 |
| R14527 | Flag 9 — Zen 5: ✅ | flag inventory | F07228 | non-negotiable | false | 10 |
| R14528 | Flag 9 — engine: scalar-ref | flag inventory | F07228 | non-negotiable | false | 10 |
| R14529 | Flag 9 — SIMD-lift: _mm512_popcnt_epi8 | flag inventory | F07228 | non-negotiable | false | 10 |
| R14530 | Step 1 — Intrinsic kernel (std::arch::x86_64 behind #[cfg(target_feature = "...")]) | five_step_lift | F07229 | non-negotiable | false | 10 |
| R14531 | Step 1 — unsafe lives in NEW sibling -simd crate | five_step_lift | F07229 | non-negotiable | false | 10 |
| R14532 | Step 2 — Runtime dispatch (std::arch::is_x86_feature_detected!) | five_step_lift | F07230 | non-negotiable | false | 10 |
| R14533 | Step 2 — chooses SIMD vs scalar per call | five_step_lift | F07230 | non-negotiable | false | 10 |
| R14534 | Step 3 — Build flags (-C target-cpu=znver5) | five_step_lift | F07231 | non-negotiable | false | 10 |
| R14535 | Step 3 — +avx512vnni,+avx512_bf16,+avx512vbmi2,… | five_step_lift | F07231 | non-negotiable | false | 10 |
| R14536 | Step 4 — Differential tests (scalar output = SIMD bit-for-bit) | five_step_lift | F07232 | non-negotiable | false | 10 |
| R14537 | Step 4 — existing scalar unit tests become oracle | five_step_lift | F07232 | non-negotiable | false | 10 |
| R14538 | Step 5 — Capability + profile gate | five_step_lift | F07233 | non-negotiable | false | 10 |
| R14539 | Step 5 — avx512-advisor detected caps + PrecisionProfile.Tiers opt-in | five_step_lift | F07233 | non-negotiable | false | 10 |
| R14540 | Runtime — E0817 done (flag inventory + avx512-advisor tiers) | runtime status | F07234 | non-negotiable | false | 10 |
| R14541 | Runtime — E0818 done (Precision::Bf16 wired) | runtime status | F07235 | non-negotiable | false | 10 |
| R14542 | Runtime — E0819 done (capability gate live) | runtime status | F07236 | non-negotiable | false | 10 |
| R14543 | Runtime — E0820 open (no std::arch SIMD yet) | runtime status | F07237 | non-negotiable | false | 10 |
| R14544 | Runtime — E0821 open (Rust release not znver5-tuned) | runtime status | F07238 | non-negotiable | false | 10 |
| R14545 | Runtime — flag map is authoritative and probeable | runtime status | F07234 | non-negotiable | false | 10 |
| R14546 | Runtime — T1 is fully wired at both precisions (INT8 + BF16) | runtime status | F07234 | non-negotiable | false | 10 |
| R14547 | Runtime — capability gate is live and demonstrated | runtime status | F07236 | non-negotiable | false | 10 |
| R14548 | Codified — avx512-advisor.py tiers verb | codified | F07239 | non-negotiable | false | 10 |
| R14549 | Codified — PrecisionProfile::gated_by | codified | F07240 | non-negotiable | false | 10 |
| R14550 | Codified — Tiers::detect() | codified | F07241 | non-negotiable | false | 10 |
| R14551 | Codified — sovereign-precision-profile crate | codified | F07242 | non-negotiable | false | 10 |
| R14552 | Codified — avx512-advisor tiers verb added VP2INTERSECT | codified | F07239 | non-negotiable | false | 10 |
| R14553 | Codified — flag inventory is authoritative CPU-feature map | codified | F07239 | non-negotiable | false | 10 |
| R14554 | Safety — #![forbid(unsafe_code)] in reference crates | safety | F07243 | non-negotiable | false | 10 |
| R14555 | Safety — SIMD lives in NEW sibling -simd crate (or relaxed unsafe module) | safety | F07244 | non-negotiable | false | 10 |
| R14556 | Safety — runtime dispatch chooses SIMD vs scalar per call | safety | F07245 | non-negotiable | false | 10 |
| R14557 | Safety — one binary runs everywhere | safety | F07246 | non-negotiable | false | 10 |
| R14558 | Safety — scalar path is the permanent fallback | safety | F07243 | non-negotiable | false | 10 |
| R14559 | Cross-ref — M085 Zen5 three-tier instruction references | cross-ref | F07247 | non-negotiable | false | 10 |
| R14560 | Cross-ref — M073 one-bit-ternary-logic-bitlinear-core | cross-ref | F07248 | non-negotiable | false | 10 |
| R14561 | Cross-ref — M074 avx-512-vnni-hardware-fusion | cross-ref | F07249 | non-negotiable | false | 10 |
| R14562 | Cross-ref — M077 nvfp4-pretraining-and-inference-pipeline | cross-ref | F07250 | non-negotiable | false | 10 |
| R14563 | Cross-ref — M038 avx512-cortex-hot-path | cross-ref | F07251 | non-negotiable | false | 10 |
| R14564 | Cross-ref — M058 hardware-aware-scheduling-goldilocks | cross-ref | F07252 | non-negotiable | false | 10 |
| R14565 | Operator — "i wanna see all the CPU/kernel flag and all the work needed" | operator review | F07253 | non-negotiable | false | 10 |
| R14566 | Operator — "fix everything" | operator review | F07254 | non-negotiable | false | 10 |
| R14567 | Operator — review request 2026-07-02 | operator review | F07253 | non-negotiable | false | 10 |
| R14568 | Intrinsic — _mm512_ternarylogic_epi64 (VPTERNLOG) | intrinsics | F07255 | non-negotiable | false | 10 |
| R14569 | Intrinsic — _mm512_dpbusd_epi32 (VNNI) | intrinsics | F07256 | non-negotiable | false | 10 |
| R14570 | Intrinsic — _mm512_dpbf16_ps (BF16) | intrinsics | F07257 | non-negotiable | false | 10 |
| R14571 | Intrinsic — _mm512_permutexvar_epi8 (VPERMB) | intrinsics | F07258 | non-negotiable | false | 10 |
| R14572 | Intrinsic — _mm512_shldv_epi64 (VPSHLDV) | intrinsics | F07259 | non-negotiable | false | 10 |
| R14573 | Intrinsic — _mm512_mask_compress_epi8 (VPCOMPRESSB) | intrinsics | F07260 | non-negotiable | false | 10 |
| R14574 | Intrinsic — _mm512_mask_expand_epi8 (VPEXPANDB) | intrinsics | F07261 | non-negotiable | false | 10 |
| R14575 | Intrinsic — none for VP2INTERSECT (no Zen 5 hardware) | intrinsics | F07262 | non-negotiable | false | 10 |
| R14576 | Intrinsic — _mm512_popcnt_epi64 (VPOPCNTD/Q) | intrinsics | F07263 | non-negotiable | false | 10 |
| R14577 | Intrinsic — _mm512_popcnt_epi8 (VPOPCNTB/W) | intrinsics | F07264 | non-negotiable | false | 10 |
| R14578 | Consumer — attention-mask fusion (VPTERNLOG) | consumers | F07265 | non-negotiable | false | 10 |
| R14579 | Consumer — token/KV shuffle (VPERMB) | consumers | F07266 | non-negotiable | false | 10 |
| R14580 | Consumer — KV-cache compaction (VPCOMPRESSB/VPEXPANDB) | consumers | F07267 | non-negotiable | false | 10 |
| R14581 | Consumer — ternary BitLinear dot (VPOPCNT) | consumers | F07268 | non-negotiable | false | 10 |
| R14582 | Build — -C target-cpu=znver5 release profile | build | F07269 | non-negotiable | false | 10 |
| R14583 | Build — +avx512vnni,+avx512_bf16,+avx512vbmi2,… | build | F07270 | non-negotiable | false | 10 |
| R14584 | Build — bitnet.cpp already uses these flags | build | F07271 | non-negotiable | false | 10 |
| R14585 | Build — Rust engine build does not yet (E0821) | build | F07272 | non-negotiable | false | 10 |
| R14586 | Test — existing scalar unit tests become oracle | test | F07273 | non-negotiable | false | 10 |
| R14587 | Test — SIMD output must equal scalar bit-for-bit | test | F07274 | non-negotiable | false | 10 |
| R14588 | Test — all nine flags have scalar tests already | test | F07275 | non-negotiable | false | 10 |
| R14589 | Dispatcher — std::arch::is_x86_feature_detected! per call | dispatcher | F07276 | non-negotiable | false | 10 |
| R14590 | Dispatcher — Tiers::detect() already does tier-granularity detection | dispatcher | F07277 | non-negotiable | false | 10 |
