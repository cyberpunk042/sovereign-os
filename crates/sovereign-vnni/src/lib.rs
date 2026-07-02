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

    /// The `i32` sum of each weight row (`Σ_j W[r][j]`). This is the
    /// zero-point correction term an asymmetric-activation INT8 scheme needs:
    /// with `q = round(x/s_x) + zp`, the true dot is
    /// `s_w · s_x · (Σ q·w − zp · Σ w)` — the second factor is this row sum.
    pub fn row_sums(&self) -> Vec<i32> {
        (0..self.output_dim)
            .map(|o| {
                self.weights[o * self.input_dim..(o + 1) * self.input_dim]
                    .iter()
                    .map(|&w| w as i32)
                    .sum()
            })
            .collect()
    }
}

/// BF16 pairs fused per VDPBF16PS accumulator lane.
pub const BF16_LANE_WIDTH: usize = 2;

/// Convert an `f32` to BF16 bits (`u16`) with round-to-nearest-even — the
/// conversion `VCVTNE2PS2BF16` performs. BF16 is the top 16 bits of the f32
/// layout (1 sign, 8 exponent, 7 mantissa), so range matches f32 and only
/// mantissa precision is dropped. NaN is canonicalized (quiet bit forced).
pub fn f32_to_bf16(x: f32) -> u16 {
    let bits = x.to_bits();
    if x.is_nan() {
        // preserve NaN, force the mantissa MSB so truncation can't yield Inf.
        return ((bits >> 16) as u16) | 0x0040;
    }
    // round-to-nearest-even on the truncated half.
    let round_bias = 0x7fff + ((bits >> 16) & 1);
    ((bits + round_bias) >> 16) as u16
}

/// Convert BF16 bits (`u16`) back to `f32` — exact (BF16 ⊂ f32).
pub fn bf16_to_f32(b: u16) -> f32 {
    f32::from_bits((b as u32) << 16)
}

/// One VDPBF16PS lane: `acc + a[0]·b[0] + a[1]·b[1]` where `a`/`b` are BF16
/// bit patterns — the AVX-512 BF16 instruction that fuses two BF16 products
/// into one `f32` accumulator lane (the dump note's T1 "multiplication floues
/// BF16" beside VPDPBUSD's INT8 path). Products are computed in f32, exactly
/// as the hardware promotes each BF16 operand before the FMA.
#[inline]
pub fn vdpbf16ps_lane(acc: f32, a: [u16; BF16_LANE_WIDTH], b: [u16; BF16_LANE_WIDTH]) -> f32 {
    let mut s = acc;
    for j in 0..BF16_LANE_WIDTH {
        s += bf16_to_f32(a[j]) * bf16_to_f32(b[j]);
    }
    s
}

/// Full BF16 dot product `Σ a[i]·b[i]` (operands as BF16 bits) accumulated in
/// `f32` — VDPBF16PS-style. Any length is allowed.
pub fn dot_bf16(a: &[u16], b: &[u16]) -> Result<f32, VnniError> {
    if a.len() != b.len() {
        return Err(VnniError::LengthMismatch {
            a: a.len(),
            b: b.len(),
        });
    }
    let mut acc = 0.0f32;
    for (x, y) in a.iter().zip(b) {
        acc += bf16_to_f32(*x) * bf16_to_f32(*y);
    }
    Ok(acc)
}

/// A BF16 weight matrix (`output_dim × input_dim`, row-major, BF16 bits) —
/// the VDPBF16PS analogue of [`MatI8`]: halve weight memory versus f32 while
/// keeping f32 range, accumulating exactly in f32.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MatBf16 {
    /// Output rows.
    pub output_dim: usize,
    /// Input columns.
    pub input_dim: usize,
    /// Weights, row-major, BF16 bit patterns.
    pub weights: Vec<u16>,
}

impl MatBf16 {
    /// Build by converting a row-major f32 weight slice to BF16 (RNE).
    pub fn from_f32(
        weights: &[f32],
        output_dim: usize,
        input_dim: usize,
    ) -> Result<Self, VnniError> {
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
            weights: weights.iter().map(|&w| f32_to_bf16(w)).collect(),
        })
    }

    /// BF16 forward `y = W·x`: the f32 activations are converted to BF16 (as
    /// the hardware ingests them) and each row is a VDPBF16PS-style dot,
    /// accumulated in f32.
    pub fn matvec(&self, x: &[f32]) -> Result<Vec<f32>, VnniError> {
        if x.len() != self.input_dim {
            return Err(VnniError::LengthMismatch {
                a: x.len(),
                b: self.input_dim,
            });
        }
        let xb: Vec<u16> = x.iter().map(|&v| f32_to_bf16(v)).collect();
        let mut y = vec![0.0f32; self.output_dim];
        for (o, yo) in y.iter_mut().enumerate() {
            let row = &self.weights[o * self.input_dim..(o + 1) * self.input_dim];
            *yo = dot_bf16(&xb, row)?;
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

    #[test]
    fn row_sums_match_naive() {
        let m = MatI8::from_i8(&[1, -2, 3, -1, 2, -3], 2, 3).unwrap();
        assert_eq!(m.row_sums(), vec![2, -2]);
    }

    #[test]
    fn bf16_conversion_round_trips_representable_values() {
        // powers of two and small integers are exactly representable in BF16.
        for v in [0.0f32, 1.0, -2.0, 0.5, 96.0, -0.25] {
            assert_eq!(bf16_to_f32(f32_to_bf16(v)), v, "{v}");
        }
        // NaN stays NaN; infinity stays infinite.
        assert!(bf16_to_f32(f32_to_bf16(f32::NAN)).is_nan());
        assert_eq!(bf16_to_f32(f32_to_bf16(f32::INFINITY)), f32::INFINITY);
    }

    #[test]
    fn bf16_conversion_rounds_to_nearest_even() {
        // 1.0 + 2^-8 sits exactly halfway between BF16 neighbours 1.0 and
        // 1.0078125; RNE picks the even mantissa (1.0).
        let half_way = f32::from_bits(0x3F80_8000);
        assert_eq!(bf16_to_f32(f32_to_bf16(half_way)), 1.0);
        // just above the halfway point rounds up.
        let above = f32::from_bits(0x3F80_8001);
        assert_eq!(bf16_to_f32(f32_to_bf16(above)), 1.007_812_5);
    }

    #[test]
    fn bf16_lane_accumulates_two_products() {
        let a = [f32_to_bf16(1.5), f32_to_bf16(2.0)];
        let b = [f32_to_bf16(2.0), f32_to_bf16(-0.5)];
        // 0.25 + 1.5*2.0 + 2.0*(-0.5) = 0.25 + 3.0 - 1.0 = 2.25
        assert_eq!(vdpbf16ps_lane(0.25, a, b), 2.25);
    }

    #[test]
    fn bf16_dot_matches_f32_on_representable_values() {
        let af = [1.0f32, -2.0, 0.5, 4.0];
        let bf = [2.0f32, 1.0, -8.0, 0.25];
        let a: Vec<u16> = af.iter().map(|&v| f32_to_bf16(v)).collect();
        let b: Vec<u16> = bf.iter().map(|&v| f32_to_bf16(v)).collect();
        let exact: f32 = af.iter().zip(&bf).map(|(x, y)| x * y).sum();
        assert_eq!(dot_bf16(&a, &b).unwrap(), exact);
        assert!(matches!(
            dot_bf16(&a[..2], &b).unwrap_err(),
            VnniError::LengthMismatch { .. }
        ));
    }

    #[test]
    fn bf16_matvec_matches_f32_on_representable_weights() {
        // weights/activations exactly representable in BF16 → matvec is exact.
        let w = [1.0f32, -2.0, 3.0, -1.0, 2.0, -3.0];
        let m = MatBf16::from_f32(&w, 2, 3).unwrap();
        let y = m.matvec(&[4.0, 5.0, 6.0]).unwrap();
        assert_eq!(y, vec![12.0, -12.0]);
    }

    #[test]
    fn bf16_matvec_is_close_on_general_weights() {
        // BF16 keeps ~7 mantissa bits → relative error per product ≤ ~2^-8.
        let w: Vec<f32> = (0..12).map(|i| ((i as f32) * 0.37).sin()).collect();
        let x: Vec<f32> = (0..4).map(|i| ((i as f32) * 0.71).cos()).collect();
        let m = MatBf16::from_f32(&w, 3, 4).unwrap();
        let y = m.matvec(&x).unwrap();
        for (r, yr) in y.iter().enumerate() {
            let exact: f32 = w[r * 4..(r + 1) * 4]
                .iter()
                .zip(&x)
                .map(|(a, b)| a * b)
                .sum();
            assert!((yr - exact).abs() < 0.05, "row {r}: {yr} vs {exact}");
        }
    }

    #[test]
    fn bf16_matvec_shape_guards_and_serde() {
        assert!(matches!(
            MatBf16::from_f32(&[1.0, 2.0], 2, 2).unwrap_err(),
            VnniError::ShapeMismatch { .. }
        ));
        let m = MatBf16::from_f32(&[1.0; 6], 2, 3).unwrap();
        assert!(matches!(
            m.matvec(&[1.0, 2.0]).unwrap_err(),
            VnniError::LengthMismatch { .. }
        ));
        let j = serde_json::to_string(&m).unwrap();
        let back: MatBf16 = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
