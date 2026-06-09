//! `sovereign-vnni` — AVX-512 VNNI (VPDPBUSD) INT8 fusion (M074).
//!
//! The AVX++ dump calls out **VPDPBUSD** — the single-cycle AVX-512 VNNI
//! instruction that fuses four `u8 × i8` byte products into one `i32`
//! accumulator lane — as the INT8 hot path. This crate is the portable
//! scalar reference for that operation plus an INT8 `matvec` built on it,
//! sitting beside the ternary ([`sovereign-bitlinear-core`]) and 4-bit
//! ([`sovereign-nvfp4-runtime`]) compute kernels.
//!
//! VPDPBUSD does **not** saturate its accumulation (that is `VPDPBUSDS`), so
//! the reference uses wrapping `i32` adds to match the hardware exactly.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the VNNI surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Bytes fused per VPDPBUSD accumulator lane.
pub const LANE_WIDTH: usize = 4;

/// Errors from the VNNI kernel.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum VnniError {
    /// `a` and `b` operand lengths differ.
    #[error("operand length mismatch: a={a}, b={b}")]
    LengthMismatch {
        /// Length of `a`.
        a: usize,
        /// Length of `b`.
        b: usize,
    },
    /// `a`/`b` length is not `4 × acc.len()` for the vectorized op.
    #[error("operands of length {operands} do not match {lanes} lanes × 4")]
    LaneMismatch {
        /// Operand length supplied.
        operands: usize,
        /// Accumulator (lane) count.
        lanes: usize,
    },
    /// Weight count did not equal `output_dim × input_dim`.
    #[error("weight count {got} does not match output_dim*input_dim = {expected}")]
    ShapeMismatch {
        /// Supplied weight count.
        got: usize,
        /// Required count.
        expected: usize,
    },
}

/// One VPDPBUSD lane: `acc + Σ_{j<4} a[j](u8) · b[j](i8)`, into `i32`,
/// wrapping (non-saturating) like the hardware instruction.
#[inline]
pub fn vpdpbusd_lane(acc: i32, a: [u8; LANE_WIDTH], b: [i8; LANE_WIDTH]) -> i32 {
    let mut s = acc;
    for j in 0..LANE_WIDTH {
        s = s.wrapping_add(a[j] as i32 * b[j] as i32);
    }
    s
}

/// Vectorized VPDPBUSD: `acc[lane] += 4-way dot of the matching a/b chunk`.
/// `a` and `b` must be exactly `4 × acc.len()` long.
pub fn vpdpbusd(acc: &mut [i32], a: &[u8], b: &[i8]) -> Result<(), VnniError> {
    if a.len() != b.len() {
        return Err(VnniError::LengthMismatch {
            a: a.len(),
            b: b.len(),
        });
    }
    if a.len() != acc.len() * LANE_WIDTH {
        return Err(VnniError::LaneMismatch {
            operands: a.len(),
            lanes: acc.len(),
        });
    }
    for (lane, acc_i) in acc.iter_mut().enumerate() {
        let base = lane * LANE_WIDTH;
        let av = [a[base], a[base + 1], a[base + 2], a[base + 3]];
        let bv = [b[base], b[base + 1], b[base + 2], b[base + 3]];
        *acc_i = vpdpbusd_lane(*acc_i, av, bv);
    }
    Ok(())
}

/// Full INT8 dot product `Σ a[i](u8) · b[i](i8)` via VNNI-style accumulation
/// (one `i32` accumulator over all positions). Any length is allowed.
pub fn dot_i8(a: &[u8], b: &[i8]) -> Result<i32, VnniError> {
    if a.len() != b.len() {
        return Err(VnniError::LengthMismatch {
            a: a.len(),
            b: b.len(),
        });
    }
    let mut acc = 0i32;
    for (x, y) in a.iter().zip(b) {
        acc = acc.wrapping_add(*x as i32 * *y as i32);
    }
    Ok(acc)
}

/// An INT8 weight matrix (`output_dim × input_dim`, row-major, `i8`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MatI8 {
    /// Output rows.
    pub output_dim: usize,
    /// Input columns.
    pub input_dim: usize,
    /// Weights, row-major.
    pub weights: Vec<i8>,
}

impl MatI8 {
    /// Build from a row-major `i8` weight slice.
    pub fn from_i8(weights: &[i8], output_dim: usize, input_dim: usize) -> Result<Self, VnniError> {
        let expected = output_dim * input_dim;
        if weights.len() != expected {
            return Err(VnniError::ShapeMismatch {
                got: weights.len(),
                expected,
            });
        }
        Ok(Self {
            output_dim,
            input_dim,
            weights: weights.to_vec(),
        })
    }

    /// INT8 forward `y = W·x` with `u8` activations, into `i32` outputs —
    /// one VNNI dot per row.
    pub fn matvec(&self, x: &[u8]) -> Result<Vec<i32>, VnniError> {
        if x.len() != self.input_dim {
            return Err(VnniError::LengthMismatch {
                a: x.len(),
                b: self.input_dim,
            });
        }
        let mut y = vec![0i32; self.output_dim];
        for (o, yo) in y.iter_mut().enumerate() {
            let row = &self.weights[o * self.input_dim..(o + 1) * self.input_dim];
            *yo = dot_i8(x, row)?;
        }
        Ok(y)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lane_accumulates_four_products() {
        // 1*1 + 2*1 + 3*1 + 4*1 = 10
        assert_eq!(vpdpbusd_lane(0, [1, 2, 3, 4], [1, 1, 1, 1]), 10);
        // with a non-zero starting acc
        assert_eq!(vpdpbusd_lane(5, [1, 2, 3, 4], [1, 1, 1, 1]), 15);
    }

    #[test]
    fn lane_handles_signed_weights() {
        // 10*(-2) + 20*1 + 0*5 + 255*(-1) = -20 + 20 + 0 - 255 = -255
        assert_eq!(vpdpbusd_lane(0, [10, 20, 0, 255], [-2, 1, 5, -1]), -255);
    }

    #[test]
    fn vectorized_two_lanes() {
        let mut acc = [0i32, 100];
        // lane0: 1+2+3+4 = 10 ; lane1: 1*1+1*1+1*1+1*1 = 4 → 104
        vpdpbusd(
            &mut acc,
            &[1, 2, 3, 4, 1, 1, 1, 1],
            &[1, 1, 1, 1, 1, 1, 1, 1],
        )
        .unwrap();
        assert_eq!(acc, [10, 104]);
    }

    #[test]
    fn vectorized_lane_mismatch_rejected() {
        let mut acc = [0i32; 2];
        // 6 operands ≠ 2 lanes × 4
        let err = vpdpbusd(&mut acc, &[1, 2, 3, 4, 5, 6], &[1, 1, 1, 1, 1, 1]).unwrap_err();
        assert!(matches!(err, VnniError::LaneMismatch { .. }));
    }

    #[test]
    fn dot_matches_naive_reference() {
        let a: [u8; 6] = [1, 2, 3, 4, 5, 6];
        let b: [i8; 6] = [-1, 2, -3, 4, -5, 6];
        let naive: i32 = a
            .iter()
            .zip(b.iter())
            .map(|(x, y)| *x as i32 * *y as i32)
            .sum();
        assert_eq!(dot_i8(&a, &b).unwrap(), naive);
    }

    #[test]
    fn dot_length_mismatch_rejected() {
        let err = dot_i8(&[1, 2, 3], &[1, 2]).unwrap_err();
        assert!(matches!(err, VnniError::LengthMismatch { .. }));
    }

    #[test]
    fn matvec_matches_naive_gemm() {
        // 2x3 i8 weights, u8 activations
        let w: [i8; 6] = [1, -2, 3, -1, 2, -3];
        let m = MatI8::from_i8(&w, 2, 3).unwrap();
        let x: [u8; 3] = [4, 5, 6];
        // row0: 1*4 + -2*5 + 3*6 = 4 -10 +18 = 12
        // row1: -1*4 + 2*5 + -3*6 = -4 +10 -18 = -12
        assert_eq!(m.matvec(&x).unwrap(), vec![12, -12]);
    }

    #[test]
    fn matvec_shape_and_input_guards() {
        assert!(matches!(
            MatI8::from_i8(&[1, 2], 2, 2).unwrap_err(),
            VnniError::ShapeMismatch { .. }
        ));
        let m = MatI8::from_i8(&[1, 2, 3, 4, 5, 6], 2, 3).unwrap();
        assert!(matches!(
            m.matvec(&[1, 2]).unwrap_err(),
            VnniError::LengthMismatch { .. }
        ));
    }

    #[test]
    fn matvec_serde_round_trip() {
        let m = MatI8::from_i8(&[1, -1, 2, -2], 2, 2).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: MatI8 = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
