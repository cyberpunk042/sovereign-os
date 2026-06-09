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
//! - [`intersect`] — `VP2INTERSECT`: for two id lists, the membership masks
//!   (which elements of each appear in the other).
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
}
