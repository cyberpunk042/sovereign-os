//! Information-theory validator (F06074, F06075).
//!
//! Confirms a ternary encoding sits near the `log2(3) ≈ 1.585` bit floor
//! and *rejects* any encoding that spends more than 2 bits per parameter —
//! such an encoding is not exploiting ternary structure and should never
//! claim to be a BitLinear model.

use crate::{BitLinearError, MAX_TERNARY_BITS_PER_PARAM, TERNARY_ENTROPY_BITS, pack::Packing};
use serde::{Deserialize, Serialize};

/// Result of validating a packing against the ternary information bounds.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct InfoTheoryReport {
    /// Bits per parameter the encoding actually spends.
    pub bits_per_param: f64,
    /// `log2(3)` floor.
    pub entropy_floor: f64,
    /// Overhead above the floor, in bits per parameter.
    pub overhead_bits: f64,
    /// Whether the encoding is within the ternary ceiling.
    pub within_ceiling: bool,
}

/// Validate that storing `n` ternary parameters under `packing` respects
/// the ternary bit budget. Returns a report on success, or
/// [`BitLinearError::NotTernary`] if it exceeds [`MAX_TERNARY_BITS_PER_PARAM`].
pub fn validate_bits_per_param(
    packing: Packing,
    n: usize,
) -> Result<InfoTheoryReport, BitLinearError> {
    let bpp = crate::pack::bits_per_param(packing, n);
    if bpp > MAX_TERNARY_BITS_PER_PARAM {
        return Err(BitLinearError::NotTernary {
            bits_per_param: bpp,
            ceiling: MAX_TERNARY_BITS_PER_PARAM,
        });
    }
    Ok(InfoTheoryReport {
        bits_per_param: bpp,
        entropy_floor: TERNARY_ENTROPY_BITS,
        overhead_bits: (bpp - TERNARY_ENTROPY_BITS).max(0.0),
        within_ceiling: true,
    })
}

/// Validate a raw bits-per-parameter figure (e.g. for a competing encoding
/// not described by a [`Packing`], such as "one `i8` per weight" = 8 bits).
pub fn validate_raw_bits_per_param(bpp: f64) -> Result<InfoTheoryReport, BitLinearError> {
    if bpp > MAX_TERNARY_BITS_PER_PARAM {
        return Err(BitLinearError::NotTernary {
            bits_per_param: bpp,
            ceiling: MAX_TERNARY_BITS_PER_PARAM,
        });
    }
    Ok(InfoTheoryReport {
        bits_per_param: bpp,
        entropy_floor: TERNARY_ENTROPY_BITS,
        overhead_bits: (bpp - TERNARY_ENTROPY_BITS).max(0.0),
        within_ceiling: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base3_passes_and_is_near_floor() {
        let r = validate_bits_per_param(Packing::Base3, 100_000).unwrap();
        assert!((r.bits_per_param - 1.6).abs() < 1e-6);
        // Overhead above log2(3) is small (~0.015 bits).
        assert!(r.overhead_bits < 0.02, "overhead {}", r.overhead_bits);
        assert!(r.within_ceiling);
    }

    #[test]
    fn two_bit_passes_at_the_ceiling() {
        let r = validate_bits_per_param(Packing::TwoBit, 100_000).unwrap();
        assert!((r.bits_per_param - 2.0).abs() < 1e-6);
    }

    #[test]
    fn one_byte_per_weight_is_rejected() {
        // The classic "store each weight as an i8" — 8 bits/param — must
        // be rejected as not-ternary (F06075).
        let err = validate_raw_bits_per_param(8.0).unwrap_err();
        assert_eq!(
            err,
            BitLinearError::NotTernary {
                bits_per_param: 8.0,
                ceiling: 2.0
            }
        );
    }

    #[test]
    fn just_over_ceiling_is_rejected() {
        assert!(validate_raw_bits_per_param(2.0001).is_err());
        assert!(validate_raw_bits_per_param(2.0).is_ok());
    }
}
