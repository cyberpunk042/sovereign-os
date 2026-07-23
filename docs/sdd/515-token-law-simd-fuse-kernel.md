# SDD-515 — The fused-mask AND-kernel goes SIMD: one AVX-512 instruction fuses 512 allow-bits (M00155 DEEPEN)

> Status: active · Mandate: **E11.M515** (control-bits band 500–599)
>
> Cross-link: the **third and final Deepen slice** (`backlog/milestones/M010-deterministic-data-plane.md`) over the M00117 engine — the second perf half, closing the Deepen perf roadmap. The fourteenth SDD in the control-bits band, after the Expose arc (SDD-507/510/511), the Connect fork (SDD-512), the entropy plane (SDD-513), and the incremental fusion (SDD-514).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"let continue"* → the remaining unblocked Deepen perf work). SDD-513 and SDD-514 both named the SIMD-of-the-AND as the last open perf item; SDD-514 removed the O(n²) whole-prefix re-walk, making this the remaining Deepen perf item — the per-step plane fusion itself.

## Mission

Once each plane reports its allow-bitset for a step, `token_law_combine` fuses them into one mask: for `And` (the safe default) a token survives only if **every** plane allows it. That fusion was a scalar word-by-word AND/OR over the whole vocabulary bitset (`⌈V/64⌉` words — ~500 u64 for a 32k vocab) per plane per step. This SDD makes it a real AVX-512F kernel: `_mm512_and_si512` / `_mm512_or_si512` fuse **8 u64 = 512 allow-bits per instruction**, exactly the M008 thesis this crate already realizes for VPTERNLOG / VPCOMPRESS / field-query — with the scalar path retained as the source of truth and a proven bit-for-bit parity invariant. This is the one place in the token-law hot path that is pure vocab-width vector work; SDD-514 removed the quadratic re-walk, so the remaining per-step cost is this fuse, and this is the item both prior Deepen SDDs deferred as "SIMD-of-the-AND".

## The parity invariant (load-bearing)

Same discipline as the rest of `sovereign-simd`: **the scalar reference (`token_law_combine_scalar`) is the source of truth, and the AVX-512 kernel (`token_law_combine_avx512`) is proven bit-identical to it for every input.** The public `token_law_combine` dispatches to the AVX-512 path only behind the runtime `has_avx512f()` gate (identical to `fuse_policy` / `compress_survivors` / `field_query_mask`), falling back to the scalar reference on any other host — so results never depend on the host. A parity test walks widths that span full 8-word chunks, ragged non-8-multiple tails, and **ragged law widths** (a short law: its missing high words are implicitly `0`, so `And` clears them and `Or` leaves them — the one subtlety the vector loop must preserve), for both `And` and `Or`, asserting `avx == scalar` on an AVX-512 host. Because equality is proven, the dispatch is a pure performance change: every existing `token_law_combine` caller (the whole `fused_mask` / `FuseSession` fusion tail, `TokenLawPlanes::combine_with_dynamics`) is untouched and behavior-identical.

## Design

### The kernel — `token_law_combine` (in `sovereign-simd::cheats`)

`token_law_combine(laws, combine)` keeps its signature and semantics; internally it now:
- computes `width = max law len`, early-returns `vec![0; width]` for an empty law set (unchanged),
- on an `avx512f` host, dispatches to `token_law_combine_avx512`,
- otherwise runs `token_law_combine_scalar` (the extracted original body, the source of truth).

`token_law_combine_avx512` seeds the accumulator (`And` → all-ones, `Or` → all-zeros) and, per law, fuses it into the accumulator: an 8-u64-chunk vector loop (`_mm512_loadu_si512` × 2 → `_mm512_and_si512` / `_mm512_or_si512` → `_mm512_storeu_si512`), a scalar tail for the non-8-multiple remainder, and — for `And` — a zero-fill of the words past a short law's width (implicit-`0` semantics; a no-op for `Or`). It mirrors the crate's existing variable-width kernel (`field_query_mask_avx512`): `#[cfg(target_arch = "x86_64")]` + `#[target_feature(enable = "avx512f")]`, `unsafe` gated by the caller's runtime `is_x86_feature_detected!`, per-access SAFETY notes.

### What does NOT change

The scalar semantics, the public signature, and every consumer. `allowed_token_count` (the popcount) already had its AVX-512 story via the crate's `VPOPCNTQ` precedent and is left as-is — the named Deepen item is the AND-of-the-planes, which this delivers. No new crate, no osctl verb, no webapp surface.

## What shipped

- **`sovereign-simd`** — `token_law_combine` dispatches to a real AVX-512F kernel (`_mm512_and_si512` / `_mm512_or_si512`, 8×u64/instr) behind `has_avx512f()`; `token_law_combine_scalar` extracted as the source of truth; `token_law_combine_avx512` added; +2 tests (a host-agnostic wide/ragged correctness test; the AVX-512-gated `token_law_combine_avx_matches_scalar` parity test).
- Registration: SDD-515 + INDEX row 515 + mandate E11.M515 + catalog regen + context `sdd files` 225→226 + `tests/lint/test_token_law_simd_fuse_kernel_contract.py`.

## Non-goals / roadmap

- **The route plane as a real source** — still the one open Deepen piece, still blocked on a semantics decision (the 7-axis router outputs an `SrpRole` model choice, not a vocab subset; there is no defined `SrpRole → allow-bitset` mapping). Operator decision required before it can be built. With this SDD the Deepen **perf** roadmap is closed; only the route-plane **source** item remains, and it is design-gated, not build-gated.
- **A SIMD popcount for `allowed_token_count`** — the crate already has a `VPOPCNTQ` precedent (`bloom_overlap_avx512`); not the named AND-kernel item, left scalar.

## References

- Milestone: `backlog/milestones/M010-deterministic-data-plane.md` (M00155 Deepen).
- The "SIMD-of-the-AND" call-outs: `docs/sdd/513-token-law-entropy-plane.md` + `docs/sdd/514-token-law-incremental-fusion.md` (Non-goals).
- Kernel: `crates/sovereign-simd/src/cheats.rs` (`token_law_combine`, `token_law_combine_scalar`, `token_law_combine_avx512`).
- The crate's variable-width AVX-512 precedent: `crates/sovereign-simd/src/lib.rs` (`field_query_mask_avx512`).
- The fusion consumer: `crates/sovereign-token-law-mask/src/lib.rs` (`TokenLawPlanes::combine_with_dynamics`) → `crates/sovereign-token-law-fuse/src/lib.rs` (`compose`).
