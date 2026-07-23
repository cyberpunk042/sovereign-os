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

// ── M00122 bloom / sketch — popcount overlap ──

/// M00122 — the overlap sketch `popcount(query & memory)` over a bitset of `w`
/// u64 words. This is the "is this seen before" cheap-check: a high overlap
/// means the query's set bits are already in memory. Dispatches to AVX-512's
/// `VPOPCNTQ` when the host has `avx512vpopcntdq`, else the scalar
/// `u64::count_ones` (which lowers to `POPCNT` on any modern x86). Bit-identical.
#[must_use]
pub fn bloom_overlap(query: &[u64], memory: &[u64]) -> u32 {
    let n = query.len().min(memory.len());
    #[cfg(target_arch = "x86_64")]
    {
        if std::is_x86_feature_detected!("avx512vpopcntdq")
            && std::is_x86_feature_detected!("avx512f")
        {
            // SAFETY: gated by the runtime feature checks immediately above.
            return unsafe { bloom_overlap_avx512(&query[..n], &memory[..n]) };
        }
    }
    bloom_overlap_scalar(&query[..n], &memory[..n])
}

/// Scalar reference for [`bloom_overlap`] — the source of truth.
#[must_use]
pub fn bloom_overlap_scalar(query: &[u64], memory: &[u64]) -> u32 {
    query
        .iter()
        .zip(memory)
        .map(|(&q, &m)| (q & m).count_ones())
        .sum()
}

/// # Safety
/// Caller must ensure the host supports `avx512vpopcntdq` + `avx512f`.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512vpopcntdq,avx512f")]
unsafe fn bloom_overlap_avx512(query: &[u64], memory: &[u64]) -> u32 {
    use std::arch::x86_64::*;
    let mut total = 0u32;
    let chunks = query.len() / 8;
    // SAFETY: AVX-512F + VPOPCNTDQ intrinsics enabled by target_feature + caller
    // gate; each load reads 8 contiguous u64 within bounds.
    unsafe {
        for c in 0..chunks {
            let q = _mm512_loadu_si512(query.as_ptr().add(c * 8) as *const __m512i);
            let m = _mm512_loadu_si512(memory.as_ptr().add(c * 8) as *const __m512i);
            let pc = _mm512_popcnt_epi64(_mm512_and_si512(q, m));
            total += _mm512_reduce_add_epi64(pc) as u32;
        }
    }
    // tail — scalar, same predicate.
    for (&q, &m) in query
        .iter()
        .skip(chunks * 8)
        .zip(memory.iter().skip(chunks * 8))
    {
        total += (q & m).count_ones();
    }
    total
}

// ── M00117 token-law bitset combination ──

/// How the token-law planes combine (F00619).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LawCombine {
    /// A token is allowed only if **every** law allows it (grammar ∧ schema ∧ …).
    And,
    /// A token is allowed if **any** law allows it.
    Or,
}

/// M00117 — combine the token-law planes (grammar / schema / tool / safety /
/// route), each a vocab bitset of `w` u64 words, into one allowed-token mask
/// (F00625). `And` is the safe default: a token survives only if all laws pass.
/// Returns a bitset the same width as the inputs.
///
/// Dispatches to a real AVX-512F kernel (`_mm512_and_si512` / `_mm512_or_si512`,
/// 8×u64 = 512 allow-bits fused per instruction) when the host supports it, else
/// the scalar reference — bit-identical results, proven by the parity test.
#[must_use]
pub fn token_law_combine(laws: &[&[u64]], combine: LawCombine) -> Vec<u64> {
    let width = laws.iter().map(|l| l.len()).max().unwrap_or(0);
    if laws.is_empty() {
        return vec![0u64; width];
    }
    #[cfg(target_arch = "x86_64")]
    {
        if crate::has_avx512f() {
            // SAFETY: gated by runtime is_x86_feature_detected!("avx512f").
            return unsafe { token_law_combine_avx512(laws, combine, width) };
        }
    }
    token_law_combine_scalar(laws, combine, width)
}

/// Scalar reference for [`token_law_combine`] — the source of truth the AVX-512
/// path is proven bit-identical to. A law shorter than `width` is treated as `0`
/// in the missing high words (so `And` clears them, `Or` leaves them).
#[must_use]
fn token_law_combine_scalar(laws: &[&[u64]], combine: LawCombine, width: usize) -> Vec<u64> {
    let mut out = match combine {
        LawCombine::And => vec![u64::MAX; width],
        LawCombine::Or => vec![0u64; width],
    };
    for law in laws {
        for (i, slot) in out.iter_mut().enumerate() {
            let bits = law.get(i).copied().unwrap_or(0);
            match combine {
                LawCombine::And => *slot &= bits,
                LawCombine::Or => *slot |= bits,
            }
        }
    }
    out
}

/// # Safety
/// Caller must ensure the host supports `avx512f`. Bit-identical to
/// [`token_law_combine_scalar`] for every input.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
unsafe fn token_law_combine_avx512(laws: &[&[u64]], combine: LawCombine, width: usize) -> Vec<u64> {
    use std::arch::x86_64::*;
    let mut out = match combine {
        LawCombine::And => vec![u64::MAX; width],
        LawCombine::Or => vec![0u64; width],
    };
    for law in laws {
        let n = law.len().min(width);
        let chunks = n / 8;
        // SAFETY: the AVX-512F loads/stores are enabled by the fn's
        // `#[target_feature]` + the caller's runtime `is_x86_feature_detected!`
        // gate; each 8×u64 access reads/writes `c*8 + 8 <= chunks*8 <= n`
        // contiguous words, in-bounds of both `out` (len `width >= n`) and `law`.
        unsafe {
            for c in 0..chunks {
                let off = c * 8;
                let vo = _mm512_loadu_si512(out.as_ptr().add(off) as *const __m512i);
                let vl = _mm512_loadu_si512(law.as_ptr().add(off) as *const __m512i);
                let r = match combine {
                    LawCombine::And => _mm512_and_si512(vo, vl),
                    LawCombine::Or => _mm512_or_si512(vo, vl),
                };
                _mm512_storeu_si512(out.as_mut_ptr().add(off) as *mut __m512i, r);
            }
        }
        // tail of this law (n not a multiple of 8) — scalar, same op.
        for i in (chunks * 8)..n {
            match combine {
                LawCombine::And => out[i] &= law[i],
                LawCombine::Or => out[i] |= law[i],
            }
        }
        // words past this law are implicitly 0: And clears them, Or is a no-op.
        if matches!(combine, LawCombine::And) {
            for slot in out[n..].iter_mut() {
                *slot = 0;
            }
        }
    }
    out
}

/// The number of allowed tokens in a combined mask (F00624
/// `sovereign_os_token_law_allowed_tokens`).
#[must_use]
pub fn allowed_token_count(mask: &[u64]) -> u32 {
    mask.iter().map(|w| w.count_ones()).sum()
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
    fn bloom_overlap_counts_shared_bits() {
        // popcount(query & memory) — the seen-before sketch.
        let query = [0xFFFF_0000_FFFF_0000u64, 0x00FF_00FF_00FF_00FF];
        let memory = [0xF0F0_0000_FFFF_0000u64, 0x000F_00FF_0000_00FF];
        assert_eq!(
            bloom_overlap(&query, &memory),
            bloom_overlap_scalar(&query, &memory)
        );
        // no overlap → 0; full overlap → total set bits
        assert_eq!(bloom_overlap(&[0xFF, 0], &[0x00, 0xFF]), 0);
        let all = [u64::MAX; 8];
        assert_eq!(bloom_overlap(&all, &all), 8 * 64);
        // mismatched lengths use the shorter
        assert_eq!(bloom_overlap(&[u64::MAX; 3], &[u64::MAX; 1]), 64);
    }

    #[test]
    fn token_law_combines_all_planes() {
        // F00625 — grammar ∧ schema ∧ tool ∧ safety ∧ route.
        let grammar = [0b1111_1111u64];
        let schema = [0b0111_1111u64];
        let tool = [0b1111_1110u64];
        let safety = [0b1011_1111u64];
        let route = [0b1111_1100u64];
        let laws: [&[u64]; 5] = [&grammar, &schema, &tool, &safety, &route];
        let allowed = token_law_combine(&laws, LawCombine::And);
        // AND of all five = 0b0011_1100
        assert_eq!(allowed, vec![0b0011_1100u64]);
        assert_eq!(allowed_token_count(&allowed), 4);
        // OR admits more
        let any = token_law_combine(&laws, LawCombine::Or);
        assert_eq!(any, vec![0b1111_1111u64]);
        // empty law set → nothing allowed
        assert_eq!(token_law_combine(&[], LawCombine::And), Vec::<u64>::new());
    }

    #[test]
    fn token_law_combine_handles_wide_and_ragged_masks() {
        // Wider than one AVX-512 chunk (8 u64) with a non-8-multiple tail, plus a
        // SHORT law: high words past a short law are 0 under And, unchanged under Or.
        let full_a: Vec<u64> = (0..20u64)
            .map(|i| 0xFFFF_FFFF_FFFF_FFFF ^ (1 << (i % 64)))
            .collect();
        let full_b: Vec<u64> = (0..20u64)
            .map(|i| 0xFFFF_FFFF_FFFF_FFFF ^ (1 << ((i * 7) % 64)))
            .collect();
        let short: Vec<u64> = vec![0xF0F0_F0F0_F0F0_F0F0; 12]; // narrower than width 20
        let laws: [&[u64]; 3] = [&full_a, &full_b, &short];
        // Reference by hand (the scalar path is the source of truth).
        let expect = token_law_combine_scalar(&laws, LawCombine::And, 20);
        assert_eq!(token_law_combine(&laws, LawCombine::And), expect);
        assert_eq!(expect.len(), 20);
        // And past the short law's width 12 must be all-zero.
        assert!(
            expect[12..].iter().all(|&w| w == 0),
            "And clears words past a short law"
        );
        // Or keeps the wide words.
        let or = token_law_combine(&laws, LawCombine::Or);
        assert_eq!(or, token_law_combine_scalar(&laws, LawCombine::Or, 20));
    }

    #[test]
    fn token_law_combine_avx_matches_scalar() {
        // The load-bearing parity invariant: on an AVX-512 host the vectorized
        // kernel is bit-identical to the scalar reference across widths that span
        // full chunks, ragged tails, and ragged law widths — for And and Or.
        #[cfg(target_arch = "x86_64")]
        if crate::has_avx512f() {
            for width in [1usize, 7, 8, 9, 16, 17, 20, 33] {
                let a: Vec<u64> = (0..width as u64)
                    .map(|i| i.wrapping_mul(0x9E37_79B9_7F4A_7C15))
                    .collect();
                let b: Vec<u64> = (0..width as u64)
                    .map(|i| !(i.wrapping_mul(0xD1B5)))
                    .collect();
                for cut in [width, width / 2, 0] {
                    let short = &a[..cut];
                    let laws: [&[u64]; 3] = [&a, &b, short];
                    for combine in [LawCombine::And, LawCombine::Or] {
                        let scalar = token_law_combine_scalar(&laws, combine, width);
                        // SAFETY: guarded by `has_avx512f()` returning true.
                        let avx = unsafe { token_law_combine_avx512(&laws, combine, width) };
                        assert_eq!(avx, scalar, "width={width} cut={cut} combine={combine:?}");
                    }
                }
            }
        }
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
