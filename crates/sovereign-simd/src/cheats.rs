//! M008 bit-level cheats — AVX-512 instructions as AI control infrastructure.
//!
//! The dump's thesis: AVX-512 isn't just math, it's *law enforcement* — one
//! instruction fuses a policy decision across 8 branches. This module makes the
//! named cheats real kernels (a subset of the 13; each with a scalar reference
//! that is the source of truth, proven bit-identical to the AVX-512 path by the
//! tests, and exercised on the AVX-512 CI host):
//!
//! - **M00114 VPTERNLOG** — fuse three policy planes into one mask in a single
//!   instruction. `ternlog` (scalar) covers all 256 truth tables (F00606);
//!   `fuse_policy` is the real `_mm512_ternarylogic_epi64::<0x80>` AND-of-3.
//! - **M00115 k-mask routing** — cmpeq → k-mask, one routing plane per query
//!   (k1..k7 as decision vectors).
//! - **M00116 VPCOMPRESS** — pack the alive branches dense, order preserved
//!   (F00617), via `_mm512_maskz_compress_epi64`.
//! - **M00120 speculative accept** — `accept = oracle & grammar & tool & budget
//!   & memory`, short-circuiting (F00641).
//! - **M00123 SIMD FSM** — 8 branches step one FSM transition at once.
//! - **M00125 filter cascade** — cheapest-first predicate ordering.
//!
//! Standing rule: We do not minimize anything.

// ── M00114 VPTERNLOG — fuse three policy planes ──

/// M00114 — the ternary-logic truth table `imm8` applied bitwise across 8 lanes.
/// For each output bit, the (a,b,c) bits form a 3-bit index into `imm8`:
/// `out = (imm8 >> (a<<2 | b<<1 | c)) & 1`. This scalar reference covers **all
/// 256** truth tables (F00606) and is the source of truth for [`fuse_policy`].
#[must_use]
pub fn ternlog(a: &[u64; 8], b: &[u64; 8], c: &[u64; 8], imm8: u8) -> [u64; 8] {
    let mut out = [0u64; 8];
    for lane in 0..8 {
        let (av, bv, cv) = (a[lane], b[lane], c[lane]);
        let mut r = 0u64;
        for bit in 0..64 {
            let idx = (((av >> bit) & 1) << 2) | (((bv >> bit) & 1) << 1) | ((cv >> bit) & 1);
            r |= ((imm8 as u64 >> idx) & 1) << bit;
        }
        out[lane] = r;
    }
    out
}

/// M00114 — fuse three policy planes `model_wants ∧ policy_allows ∧
/// oracle_verified` into one accept mask. This is `imm8 = 0x80` (the AND of all
/// three inputs) and dispatches to the real `_mm512_ternarylogic_epi64` when the
/// host has AVX-512F — one instruction for all 8 branches. Bit-identical to
/// `ternlog(.., 0x80)`.
#[must_use]
pub fn fuse_policy(
    model_wants: &[u64; 8],
    policy_allows: &[u64; 8],
    oracle_verified: &[u64; 8],
) -> [u64; 8] {
    #[cfg(target_arch = "x86_64")]
    {
        if crate::has_avx512f() {
            // SAFETY: gated by runtime is_x86_feature_detected!("avx512f").
            return unsafe { ternlog_avx512::<0x80>(model_wants, policy_allows, oracle_verified) };
        }
    }
    ternlog(model_wants, policy_allows, oracle_verified, 0x80)
}

/// # Safety
/// Caller must ensure the host supports `avx512f`. `IMM8` is the const truth
/// table encoded into the instruction.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
unsafe fn ternlog_avx512<const IMM8: i32>(a: &[u64; 8], b: &[u64; 8], c: &[u64; 8]) -> [u64; 8] {
    use std::arch::x86_64::*;
    let mut out = [0u64; 8];
    // SAFETY: AVX-512F intrinsics enabled by target_feature + caller gate; each
    // load/store touches exactly one 8×u64 ZMM, in-bounds.
    unsafe {
        let va = _mm512_loadu_si512(a.as_ptr() as *const __m512i);
        let vb = _mm512_loadu_si512(b.as_ptr() as *const __m512i);
        let vc = _mm512_loadu_si512(c.as_ptr() as *const __m512i);
        let r = _mm512_ternarylogic_epi64::<IMM8>(va, vb, vc);
        _mm512_storeu_si512(out.as_mut_ptr() as *mut __m512i, r);
    }
    out
}

// ── M00115 k-mask routing planes ──

/// A routing query: a control-word field predicate `field(word) == value`.
#[derive(Debug, Clone, Copy)]
pub struct RoutingQuery {
    /// Field bit offset.
    pub shift: u32,
    /// Field bit width.
    pub width: u32,
    /// The value that routes a branch onto this plane.
    pub value: u16,
}

/// M00115 — evaluate up to 7 routing planes (k1..k7) over 8 branch control
/// words. Each plane yields an 8-bit k-mask: bit `i` set ⇔ branch `i` matches
/// that plane's query. This is the AVX-512 `VPCMPEQQ → k` idiom used as a
/// *decision vector*, one k-register per plane. Scalar-computed here (the mask
/// is 8 bits); the underlying comparison is [`crate::field_query_mask`]'s kernel.
#[must_use]
pub fn routing_planes(words: &[u64; 8], planes: &[RoutingQuery]) -> Vec<u8> {
    planes
        .iter()
        .take(7)
        .map(|q| crate::field_query_mask(words, q.shift, q.width, q.value) as u8)
        .collect()
}

// ── M00116 VPCOMPRESS — pack alive branches dense ──

/// M00116 — pack the *alive* branches (those whose `alive` k-mask bit is set)
/// into the low lanes, order preserved (first-fit, F00617). Returns the packed
/// array (dead tail left as the original values are dropped → zero-filled) and
/// the survivor count. Dispatches to `_mm512_maskz_compress_epi64` when the host
/// has AVX-512F. Bit-identical to the scalar reference.
#[must_use]
pub fn compress_survivors(v: &[u64; 8], alive: u8) -> ([u64; 8], u32) {
    #[cfg(target_arch = "x86_64")]
    {
        if crate::has_avx512f() {
            // SAFETY: gated by runtime is_x86_feature_detected!("avx512f").
            return unsafe { compress_survivors_avx512(v, alive) };
        }
    }
    compress_survivors_scalar(v, alive)
}

/// Scalar reference for [`compress_survivors`] — the source of truth.
#[must_use]
pub fn compress_survivors_scalar(v: &[u64; 8], alive: u8) -> ([u64; 8], u32) {
    let mut out = [0u64; 8];
    let mut n = 0usize;
    for (i, &val) in v.iter().enumerate() {
        if alive & (1 << i) != 0 {
            out[n] = val;
            n += 1;
        }
    }
    (out, n as u32)
}

/// # Safety
/// Caller must ensure the host supports `avx512f`.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
unsafe fn compress_survivors_avx512(v: &[u64; 8], alive: u8) -> ([u64; 8], u32) {
    use std::arch::x86_64::*;
    let mut out = [0u64; 8];
    // SAFETY: AVX-512F intrinsics enabled by target_feature + caller gate; the
    // load/store touch one 8×u64 ZMM; maskz_compress zero-fills the dead tail.
    unsafe {
        let vv = _mm512_loadu_si512(v.as_ptr() as *const __m512i);
        let packed = _mm512_maskz_compress_epi64(alive, vv);
        _mm512_storeu_si512(out.as_mut_ptr() as *mut __m512i, packed);
    }
    (out, alive.count_ones())
}

// ── M00120 speculative acceptance ──

/// M00120 — `accept = oracle & grammar & tool & budget & memory`, short-circuit.
/// Each predicate is an 8-bit branch mask; a branch is accepted only if it
/// passes **every** predicate. Short-circuits: the moment the running mask is 0,
/// no branch can survive, so the remaining predicates are skipped. Returns the
/// accept mask and how many predicates were actually evaluated (the short-circuit
/// depth).
#[must_use]
pub fn speculative_accept(predicates: &[u8]) -> (u8, usize) {
    let mut acc = 0xFFu8;
    let mut evaluated = 0usize;
    for &p in predicates {
        acc &= p;
        evaluated += 1;
        if acc == 0 {
            break; // short-circuit: no branch can be accepted
        }
    }
    (acc, evaluated)
}

// ── M00123 SIMD finite-state machine ──

/// M00123 — step 8 branches through one FSM transition at once. `state[i]` and
/// `input[i]` index the flattened transition `table[state * n_inputs + input]`.
/// Out-of-range indices hold the branch (identity). One host loop over 8 lanes =
/// the "8 branches at once" — a natural `VPGATHERQQ` on hardware.
#[must_use]
pub fn fsm_step(state: &[u8; 8], input: &[u8; 8], table: &[u8], n_inputs: usize) -> [u8; 8] {
    let mut next = *state;
    for i in 0..8 {
        let idx = state[i] as usize * n_inputs + input[i] as usize;
        if idx < table.len() {
            next[i] = table[idx];
        }
    }
    next
}

// ── M00125 filter cascade — cheapest-first ordering ──

/// A cascade filter: a branch mask + the (relative) cost to evaluate it.
#[derive(Debug, Clone, Copy)]
pub struct Filter {
    /// The branch mask this filter passes (bit i = branch i survives it).
    pub mask: u8,
    /// The relative cost of evaluating this filter.
    pub cost: u32,
}

/// M00125 — run a cheapest-first filter cascade: sort filters by ascending cost,
/// AND their masks with short-circuit. Cheap filters run first so an expensive
/// oracle is only reached by branches that already passed everything cheaper.
/// Returns the survivor mask, the evaluated-count, and the total cost paid.
#[must_use]
pub fn filter_cascade(filters: &[Filter]) -> (u8, usize, u32) {
    let mut order: Vec<&Filter> = filters.iter().collect();
    order.sort_by_key(|f| f.cost);
    let mut acc = 0xFFu8;
    let mut evaluated = 0usize;
    let mut cost = 0u32;
    for f in order {
        acc &= f.mask;
        evaluated += 1;
        cost += f.cost;
        if acc == 0 {
            break;
        }
    }
    (acc, evaluated, cost)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ternlog_covers_all_256_truth_tables() {
        // F00606 — for every imm8, the output bit equals the truth-table lookup.
        let a = [0xF0F0_F0F0_F0F0_F0F0u64; 8];
        let b = [0xCCCC_CCCC_CCCC_CCCCu64; 8];
        let c = [0xAAAA_AAAA_AAAA_AAAAu64; 8];
        // a/b/c chosen so (a,b,c) bit-triples enumerate all 8 combinations across
        // the low byte — the standard VPTERNLOG truth-table probe.
        for imm in 0u16..=255 {
            let out = ternlog(&a, &b, &c, imm as u8);
            // verify bit 0..8 against the table directly
            for bit in 0..8u32 {
                let idx =
                    (((a[0] >> bit) & 1) << 2) | (((b[0] >> bit) & 1) << 1) | ((c[0] >> bit) & 1);
                let expect = (imm as u64 >> idx) & 1;
                assert_eq!((out[0] >> bit) & 1, expect, "imm={imm:#x} bit={bit}");
            }
        }
    }

    #[test]
    fn fuse_policy_is_and3_and_matches_scalar() {
        let wants = [0b1111u64; 8];
        let allows = [0b1100u64; 8];
        let oracle = [0b1010u64; 8];
        // AND of all three = 0b1000
        let f = fuse_policy(&wants, &allows, &oracle);
        assert_eq!(f, [0b1000u64; 8]);
        assert_eq!(f, ternlog(&wants, &allows, &oracle, 0x80));
    }

    #[test]
    fn ternlog_avx_matches_scalar_for_key_tables() {
        // exercise the intrinsic path for a handful of const imm8 (AND3 / OR3 /
        // XOR3 / majority) when the host supports it.
        let a = [0xDEAD_BEEF_0000_FFFFu64; 8];
        let b = [0x0F0F_F0F0_1234_5678u64; 8];
        let c = [0xFFFF_0000_AAAA_5555u64; 8];
        if crate::has_avx512f() {
            #[cfg(target_arch = "x86_64")]
            unsafe {
                assert_eq!(
                    ternlog_avx512::<0x80>(&a, &b, &c),
                    ternlog(&a, &b, &c, 0x80)
                ); // AND3
                assert_eq!(
                    ternlog_avx512::<0xFE>(&a, &b, &c),
                    ternlog(&a, &b, &c, 0xFE)
                ); // OR3
                assert_eq!(
                    ternlog_avx512::<0x96>(&a, &b, &c),
                    ternlog(&a, &b, &c, 0x96)
                ); // XOR3
                assert_eq!(
                    ternlog_avx512::<0xE8>(&a, &b, &c),
                    ternlog(&a, &b, &c, 0xE8)
                ); // majority
            }
        }
    }

    #[test]
    fn compress_preserves_order_on_survivors() {
        // F00617 — survivors keep their relative order, packed low, dead → 0.
        let v = [10u64, 20, 30, 40, 50, 60, 70, 80];
        let alive = 0b1010_1101; // lanes 0,2,3,5,7
        let (packed, n) = compress_survivors(&v, alive);
        assert_eq!(n, 5);
        assert_eq!(&packed[..5], &[10, 30, 40, 60, 80]);
        assert_eq!(&packed[5..], &[0, 0, 0]);
        assert_eq!(
            compress_survivors(&v, alive),
            compress_survivors_scalar(&v, alive)
        );
        // none / all
        assert_eq!(compress_survivors(&v, 0).1, 0);
        assert_eq!(compress_survivors(&v, 0xFF), (v, 8));
    }

    #[test]
    fn speculative_accept_ands_and_short_circuits() {
        // F00641 — accept = AND of all predicates; short-circuit when it hits 0.
        let (acc, ev) = speculative_accept(&[0b1111, 0b1110, 0b1100, 0b1000]);
        assert_eq!(acc, 0b1000);
        assert_eq!(ev, 4);
        // a zero predicate early stops evaluation
        let (acc, ev) = speculative_accept(&[0b1111, 0b0000, 0b1010, 0b1111]);
        assert_eq!(acc, 0);
        assert_eq!(ev, 2, "must short-circuit at the zero predicate");
        // empty → accept all
        assert_eq!(speculative_accept(&[]), (0xFF, 0));
    }

    #[test]
    fn fsm_steps_eight_branches() {
        // a 2-state toggle FSM: state 0 --in1--> 1, state 1 --in1--> 0, in0 holds.
        // table[state*2 + input]
        let table = [
            0u8, 1, /*s0: in0->0 in1->1*/ 1, 0, /*s1: in0->1 in1->0*/
        ];
        let state = [0u8, 1, 0, 1, 0, 1, 0, 1];
        let input = [1u8, 1, 0, 0, 1, 1, 0, 0];
        let next = fsm_step(&state, &input, &table, 2);
        assert_eq!(next, [1, 0, 0, 1, 1, 0, 0, 1]);
        // out-of-range index holds the branch
        assert_eq!(fsm_step(&[9; 8], &[9; 8], &table, 2), [9; 8]);
    }

    #[test]
    fn filter_cascade_runs_cheapest_first() {
        // an expensive oracle (cost 100) is only reached if the cheap filters pass
        let filters = [
            Filter {
                mask: 0b1111_1110,
                cost: 100,
            }, // oracle (expensive)
            Filter {
                mask: 0b1111_1111,
                cost: 1,
            }, // cheap pass
            Filter {
                mask: 0b0000_0000,
                cost: 2,
            }, // duplicate check (kills all)
        ];
        // sorted cheapest-first: cost 1 (pass) → cost 2 (kills all → short-circuit)
        let (surv, ev, cost) = filter_cascade(&filters);
        assert_eq!(surv, 0, "the cheap kill runs before the oracle");
        assert_eq!(ev, 2, "short-circuit before the costly oracle");
        assert_eq!(cost, 3, "paid only cost 1 + 2, never the 100");
    }
}
