//! Bit-packing for ternary weights.
//!
//! Two schemes, both real:
//!
//! - [`Packing::Base3`] — 5 trits packed per byte via base-3 positional
//!   encoding (`d0 + 3·d1 + 9·d2 + 27·d3 + 81·d4`, max `242 < 256`). This
//!   is **1.6 bits/parameter** (F06054 intent + F06040 bound), the
//!   practical floor above `log2(3) ≈ 1.585` for byte-addressable storage.
//! - [`Packing::TwoBit`] — 4 trits per byte, 2 bits each. **2.0
//!   bits/parameter**, byte-simple to unpack on the AVX-512 path; this is
//!   the literal "2 bits per parameter, aligns with byte boundaries"
//!   reading of F06054/F06055.

use crate::{BitLinearError, ternary::Trit};
use serde::{Deserialize, Serialize};

/// Ternary packing scheme.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Packing {
    /// 5 trits/byte, base-3 positional. 1.6 bits/param.
    Base3,
    /// 4 trits/byte, 2 bits each. 2.0 bits/param.
    TwoBit,
}

impl Packing {
    /// Trits stored in a single byte under this scheme.
    #[inline]
    pub const fn trits_per_byte(self) -> usize {
        match self {
            Packing::Base3 => 5,
            Packing::TwoBit => 4,
        }
    }

    /// Bytes required to hold `n` trits under this scheme.
    #[inline]
    pub const fn bytes_for(self, n: usize) -> usize {
        n.div_ceil(self.trits_per_byte())
    }
}

/// Effective bits per parameter for `n` trits under `packing`, measured
/// from the actually-allocated byte buffer (so trailing-byte padding is
/// honestly accounted for).
pub fn bits_per_param(packing: Packing, n: usize) -> f64 {
    if n == 0 {
        return 0.0;
    }
    (packing.bytes_for(n) * 8) as f64 / n as f64
}

/// Pack ternary weights into a byte buffer.
pub fn pack(trits: &[Trit], packing: Packing) -> Vec<u8> {
    match packing {
        Packing::Base3 => pack_base3(trits),
        Packing::TwoBit => pack_two_bit(trits),
    }
}

/// Unpack exactly `n` trits from `bytes`. Errors if the buffer is too
/// small to hold `n` trits under `packing`.
pub fn unpack(bytes: &[u8], n: usize, packing: Packing) -> Result<Vec<Trit>, BitLinearError> {
    if bytes.len() < packing.bytes_for(n) {
        return Err(BitLinearError::TruncatedBuffer {
            got: bytes.len(),
            trits: n,
            packing,
        });
    }
    Ok(match packing {
        Packing::Base3 => unpack_base3(bytes, n),
        Packing::TwoBit => unpack_two_bit(bytes, n),
    })
}

fn pack_base3(trits: &[Trit]) -> Vec<u8> {
    let mut out = Vec::with_capacity(Packing::Base3.bytes_for(trits.len()));
    for chunk in trits.chunks(5) {
        let mut byte = 0u16;
        let mut place = 1u16;
        for t in chunk {
            byte += place * t.to_base3() as u16;
            place *= 3;
        }
        out.push(byte as u8);
    }
    out
}

fn unpack_base3(bytes: &[u8], n: usize) -> Vec<Trit> {
    let mut out = Vec::with_capacity(n);
    'outer: for &b in bytes {
        let mut v = b;
        for _ in 0..5 {
            if out.len() == n {
                break 'outer;
            }
            out.push(Trit::from_base3(v % 3));
            v /= 3;
        }
    }
    out
}

fn pack_two_bit(trits: &[Trit]) -> Vec<u8> {
    let mut out = Vec::with_capacity(Packing::TwoBit.bytes_for(trits.len()));
    for chunk in trits.chunks(4) {
        let mut byte = 0u8;
        for (i, t) in chunk.iter().enumerate() {
            byte |= (t.to_base3() & 0b11) << (i * 2);
        }
        out.push(byte);
    }
    out
}

fn unpack_two_bit(bytes: &[u8], n: usize) -> Vec<Trit> {
    let mut out = Vec::with_capacity(n);
    'outer: for &b in bytes {
        for i in 0..4 {
            if out.len() == n {
                break 'outer;
            }
            out.push(Trit::from_base3((b >> (i * 2)) & 0b11));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<Trit> {
        // 13 trits — exercises partial trailing chunks under both schemes.
        vec![
            Trit::Plus,
            Trit::Minus,
            Trit::Zero,
            Trit::Plus,
            Trit::Plus,
            Trit::Minus,
            Trit::Zero,
            Trit::Zero,
            Trit::Plus,
            Trit::Minus,
            Trit::Minus,
            Trit::Zero,
            Trit::Plus,
        ]
    }

    #[test]
    fn base3_round_trip() {
        let t = sample();
        let packed = pack(&t, Packing::Base3);
        assert_eq!(packed.len(), 3); // ceil(13/5)
        let back = unpack(&packed, t.len(), Packing::Base3).unwrap();
        assert_eq!(t, back);
    }

    #[test]
    fn two_bit_round_trip() {
        let t = sample();
        let packed = pack(&t, Packing::TwoBit);
        assert_eq!(packed.len(), 4); // ceil(13/4)
        let back = unpack(&packed, t.len(), Packing::TwoBit).unwrap();
        assert_eq!(t, back);
    }

    #[test]
    fn base3_byte_never_overflows() {
        // The densest possible 5-trit chunk is all Minus (digit 2):
        // 2*(1+3+9+27+81) = 242, which fits in a u8.
        let all_minus = vec![Trit::Minus; 5];
        let packed = pack(&all_minus, Packing::Base3);
        assert_eq!(packed, vec![242u8]);
    }

    #[test]
    fn base3_is_1_point_6_bits() {
        // 1000 trits -> 200 bytes -> 1.6 bits/param exactly.
        let bpp = bits_per_param(Packing::Base3, 1000);
        assert!((bpp - 1.6).abs() < 1e-9, "got {bpp}");
        // ...and it sits above the log2(3) information bound.
        assert!(bpp >= crate::TERNARY_ENTROPY_BITS);
    }

    #[test]
    fn two_bit_is_2_bits() {
        let bpp = bits_per_param(Packing::TwoBit, 1000);
        assert!((bpp - 2.0).abs() < 1e-9, "got {bpp}");
    }

    #[test]
    fn truncated_buffer_is_rejected() {
        let err = unpack(&[0u8], 10, Packing::Base3).unwrap_err();
        assert!(matches!(err, BitLinearError::TruncatedBuffer { .. }));
    }
}
