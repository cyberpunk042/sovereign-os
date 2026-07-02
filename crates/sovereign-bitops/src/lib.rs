//! `sovereign-bitops` — M008 AVX-512 bit-level cheats (portable references).
//!
//! The dump leans on a handful of AVX-512 bit instructions as "cheats". This
//! crate is their exact scalar reference, so the rest of the system can use
//! the same semantics on any target:
//!
//! - [`vpternlog`] — `VPTERNLOG`: an arbitrary 3-input bitwise boolean
//!   selected by an 8-bit truth table (the immediate). One instruction
//!   computes *any* function of three bit-vectors.
//! - [`popcount`] — `VPOPCNTDQ`: set-bit count.
//! - [`compress`] — `VPCOMPRESS`: gather mask-selected lanes into a
//!   contiguous result.
//! - [`expand`] — `VPEXPAND`: the inverse — scatter a contiguous run back to
//!   mask-selected lanes (T3 "compactage dynamique" round trip).
//! - [`intersect`] — `VP2INTERSECT`: for two id lists, the membership masks
//!   (which elements of each appear in the other).
//! - [`vpermb`] — `VPERMB` (VBMI): full 64-byte table permute — the T3 token
//!   alignment / shuffling primitive.
//! - [`vpshldv`] — `VPSHLDVQ` (VBMI2): concatenated variable shift-left,
//!   funnel-shifting bits in from a second operand.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::HashSet;

/// Schema version of the bitops surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// `VPTERNLOG`: arbitrary 3-input bitwise boolean. For every bit position,
/// the three input bits `(a, b, c)` form an index `0..8`, and the result bit
/// is `imm8`'s bit at that index. Computed as the OR of the selected
/// minterms — exact and branch-free over the 8 cases.
///
/// Examples: `imm8 = 0x80` → `a & b & c`; `0x96` → `a ^ b ^ c`; `0xFE` →
/// `a | b | c`; `0xF0` → `a`.
pub fn vpternlog(a: u64, b: u64, c: u64, imm8: u8) -> u64 {
    let mut r = 0u64;
    for i in 0..8u8 {
        if imm8 & (1 << i) != 0 {
            let fa = if i & 0b100 != 0 { a } else { !a };
            let fb = if i & 0b010 != 0 { b } else { !b };
            let fc = if i & 0b001 != 0 { c } else { !c };
            r |= fa & fb & fc;
        }
    }
    r
}

/// `VPOPCNTDQ`: number of set bits.
pub fn popcount(x: u64) -> u32 {
    x.count_ones()
}

/// `VPCOMPRESS`: gather the elements of `values` whose corresponding `mask`
/// bit (bit `i` for `values[i]`) is set, into a contiguous vector preserving
/// order. Only the low `values.len()` mask bits are consulted.
pub fn compress<T: Copy>(values: &[T], mask: u64) -> Vec<T> {
    values
        .iter()
        .enumerate()
        .filter(|(i, _)| *i < 64 && mask & (1u64 << i) != 0)
        .map(|(_, &v)| v)
        .collect()
}

/// `VPEXPAND`: the inverse of [`compress`] — scatter the contiguous `packed`
/// elements back out to the positions whose `mask` bit is set, filling the
/// cleared positions with `fill` (the hardware's zero-masking form). The
/// result has `width` lanes; set bits beyond the packed supply keep `fill`.
/// Together with `compress` this is the note's T3 "compactage dynamique":
/// compact live tokens/KV slots down, expand them back into place.
pub fn expand<T: Copy>(packed: &[T], mask: u64, width: usize, fill: T) -> Vec<T> {
    let mut out = vec![fill; width];
    let mut next = 0usize;
    for (i, slot) in out.iter_mut().enumerate().take(width.min(64)) {
        if mask & (1u64 << i) != 0 {
            if let Some(&v) = packed.get(next) {
                *slot = v;
                next += 1;
            }
        }
    }
    out
}

/// `VPERMB` (AVX-512 VBMI): full-width byte permute. Each output byte `i` is
/// `table[idx[i] & 63]` — the index's low 6 bits select one of the 64 table
/// bytes, exactly like the hardware ignores the upper index bits. This is the
/// note's T3 "alignement & shuffling de tokens" primitive: one instruction
/// arbitrarily rearranges a 64-byte tile (token ids, KV bytes, mask lanes).
pub fn vpermb(table: &[u8; 64], idx: &[u8]) -> Vec<u8> {
    idx.iter().map(|&i| table[(i & 63) as usize]).collect()
}

/// `VPSHLDVQ` (AVX-512 VBMI2): concatenated variable shift-left. Conceptually
/// `a:b` (128 bits, `a` high) is shifted left by `count & 63` and the high 64
/// bits are returned — so bits vacated at `a`'s bottom are funnel-filled from
/// `b`'s top. `count = 0` returns `a` unchanged. The T3 building block for
/// re-aligning bit-packed token streams without a shift+or dance.
pub fn vpshldv(a: u64, b: u64, count: u64) -> u64 {
    let c = (count & 63) as u32;
    if c == 0 {
        a
    } else {
        (a << c) | (b >> (64 - c))
    }
}

/// `VP2INTERSECT`: returns `(mask_a, mask_b)` where bit `i` of `mask_a` is
/// set iff `a[i]` appears in `b`, and bit `j` of `mask_b` is set iff `b[j]`
/// appears in `a`. Lists longer than 64 only set bits for their first 64.
pub fn intersect(a: &[u32], b: &[u32]) -> (u64, u64) {
    let set_a: HashSet<u32> = a.iter().copied().collect();
    let set_b: HashSet<u32> = b.iter().copied().collect();
    let mut mask_a = 0u64;
    let mut mask_b = 0u64;
    for (i, x) in a.iter().enumerate().take(64) {
        if set_b.contains(x) {
            mask_a |= 1u64 << i;
        }
    }
    for (j, y) in b.iter().enumerate().take(64) {
        if set_a.contains(y) {
            mask_b |= 1u64 << j;
        }
    }
    (mask_a, mask_b)
}

#[cfg(test)]
mod tests {
    use super::*;

    const A: u64 = 0b1100;
    const B: u64 = 0b1010;
    const C: u64 = 0b0110;

    #[test]
    fn ternlog_known_truth_tables() {
        assert_eq!(vpternlog(A, B, C, 0x80), A & B & C); // AND3
        assert_eq!(vpternlog(A, B, C, 0x96), A ^ B ^ C); // XOR3
        assert_eq!(vpternlog(A, B, C, 0xFE), A | B | C); // OR3
        assert_eq!(vpternlog(A, B, C, 0xF0), A); // passthrough a
        assert_eq!(vpternlog(A, B, C, 0xCC), B); // passthrough b
        assert_eq!(vpternlog(A, B, C, 0xAA), C); // passthrough c
    }

    #[test]
    fn ternlog_all_ones_and_zeros() {
        assert_eq!(vpternlog(A, B, C, 0xFF), !0u64);
        assert_eq!(vpternlog(A, B, C, 0x00), 0u64);
    }

    #[test]
    fn ternlog_matches_per_bit_definition() {
        // brute-force check against the bit-by-bit definition on small inputs
        for imm in [0x01u8, 0x17, 0x5A, 0xE8, 0xFD] {
            let r = vpternlog(A, B, C, imm);
            let mut expect = 0u64;
            for bit in 0..64 {
                let ai = (A >> bit) & 1;
                let bi = (B >> bit) & 1;
                let ci = (C >> bit) & 1;
                let idx = (ai << 2 | bi << 1 | ci) as u8;
                if imm & (1 << idx) != 0 {
                    expect |= 1u64 << bit;
                }
            }
            assert_eq!(r, expect, "imm {imm:#x}");
        }
    }

    #[test]
    fn popcount_counts_bits() {
        assert_eq!(popcount(0), 0);
        assert_eq!(popcount(0b1011), 3);
        assert_eq!(popcount(!0u64), 64);
    }

    #[test]
    fn compress_gathers_masked_lanes() {
        let v = [10u32, 20, 30, 40];
        assert_eq!(compress(&v, 0b1010), vec![20, 40]); // bits 1,3
        assert_eq!(compress(&v, 0b1111), vec![10, 20, 30, 40]);
        assert_eq!(compress(&v, 0), Vec::<u32>::new());
    }

    #[test]
    fn intersect_membership_masks() {
        let a = [1u32, 2, 3, 4];
        let b = [3u32, 4, 5];
        let (ma, mb) = intersect(&a, &b);
        // a[2]=3, a[3]=4 in b → bits 2,3
        assert_eq!(ma, 0b1100);
        // b[0]=3, b[1]=4 in a → bits 0,1
        assert_eq!(mb, 0b0011);
    }

    #[test]
    fn intersect_disjoint_is_zero() {
        let (ma, mb) = intersect(&[1, 2], &[3, 4]);
        assert_eq!(ma, 0);
        assert_eq!(mb, 0);
    }

    #[test]
    fn expand_scatters_to_masked_lanes() {
        // packed [20, 40] back to bits 1,3 of a 4-lane vector, fill 0.
        assert_eq!(expand(&[20u32, 40], 0b1010, 4, 0), vec![0, 20, 0, 40]);
        // more set bits than packed values → extras keep the fill.
        assert_eq!(expand(&[7u32], 0b0111, 4, 9), vec![7, 9, 9, 9]);
        // no mask bits → all fill.
        assert_eq!(expand(&[1u32, 2], 0, 3, 5), vec![5, 5, 5]);
    }

    #[test]
    fn expand_round_trips_compress() {
        // compress then expand reconstructs the kept positions exactly.
        let v = [10u32, 20, 30, 40, 50];
        let mask = 0b10110u64;
        let packed = compress(&v, mask);
        let back = expand(&packed, mask, v.len(), 0);
        for i in 0..v.len() {
            if mask & (1 << i) != 0 {
                assert_eq!(back[i], v[i], "kept lane {i}");
            } else {
                assert_eq!(back[i], 0, "cleared lane {i}");
            }
        }
    }

    #[test]
    fn vpermb_permutes_bytes_by_low_six_index_bits() {
        let mut table = [0u8; 64];
        for (i, t) in table.iter_mut().enumerate() {
            *t = (i as u8) * 2;
        }
        // straight lookup
        assert_eq!(vpermb(&table, &[0, 1, 63]), vec![0, 2, 126]);
        // reversal shuffle of the first 4 table bytes
        assert_eq!(vpermb(&table, &[3, 2, 1, 0]), vec![6, 4, 2, 0]);
        // upper index bits are ignored (hardware masks to 6 bits): 64→0, 65→1
        assert_eq!(vpermb(&table, &[64, 65, 255]), vec![0, 2, 126]);
    }

    #[test]
    fn vpshldv_funnel_shifts_from_the_second_operand() {
        // shift 8: a's low byte vacated, filled from b's top byte.
        assert_eq!(
            vpshldv(0x0011_2233_4455_6677, 0xAABB_0000_0000_0000, 8),
            0x1122_3344_5566_77AA
        );
        // count 0 → a unchanged; count masked to 6 bits (64 ≡ 0).
        assert_eq!(vpshldv(0xDEAD, 0xBEEF, 0), 0xDEAD);
        assert_eq!(vpshldv(0xDEAD, 0xBEEF, 64), 0xDEAD);
        // full funnel: shift 63 keeps a's LSB at the top, b's top 63 bits below.
        assert_eq!(vpshldv(0b1, u64::MAX, 63), (1u64 << 63) | (u64::MAX >> 1));
    }
}
