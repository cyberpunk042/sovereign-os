//! NVFP4 quantized linear (matvec) — the Logic-engine compute kernel.
//!
//! `lib.rs` defines the NVFP4 codec (E2M1 element, E4M3 per-block scale,
//! 16-value blocks, [`quantize_block_rne`] / [`dequantize_block`]). This
//! module builds the actual linear projection on top: a weight matrix is
//! stored as rows of quantized blocks, and `matvec` runs the forward pass
//! block-wise — dequantize a block, multiply-accumulate against the
//! matching activations, advance. This is the NVFP4 analogue of the
//! BitLinear GEMM (the Conductor's kernel is multiplication-free ternary;
//! the Logic engine's kernel is 4-bit microscaled).
//!
//! Rows are zero-padded up to a 16-multiple so any `input_dim` is allowed;
//! padding quantizes to zero and contributes nothing.

use crate::{BLOCK_SIZE, QuantBlock, dequantize_block, quantize_block_rne};
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from the NVFP4 linear kernel.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum LinearError {
    /// Weight element count did not equal `output_dim * input_dim`.
    #[error("weight count {got} does not match output_dim*input_dim = {expected}")]
    ShapeMismatch {
        /// Supplied weight count.
        got: usize,
        /// Required count.
        expected: usize,
    },
    /// Activation length did not equal `input_dim`.
    #[error("activation length {got} does not match input_dim {expected}")]
    InputMismatch {
        /// Supplied activation length.
        got: usize,
        /// Expected `input_dim`.
        expected: usize,
    },
    /// The random Hadamard transform requires a power-of-two `input_dim`.
    #[error("RHT requires a power-of-two input_dim, got {0}")]
    RhtInputNotPowerOfTwo(usize),
}

/// A weight matrix quantized to NVFP4, row-major, each row a run of
/// 16-element [`QuantBlock`]s.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct QuantMatrix {
    /// Number of output rows.
    pub output_dim: usize,
    /// Number of input columns (before padding).
    pub input_dim: usize,
    /// `output_dim` rows, each `blocks_per_row()` blocks.
    pub rows: Vec<Vec<QuantBlock>>,
}

impl QuantMatrix {
    /// Blocks per row = `ceil(input_dim / 16)`.
    pub fn blocks_per_row(&self) -> usize {
        self.input_dim.div_ceil(BLOCK_SIZE)
    }

    /// Quantize a row-major `output_dim × input_dim` f32 weight matrix.
    pub fn from_f32(
        weights: &[f32],
        output_dim: usize,
        input_dim: usize,
    ) -> Result<Self, LinearError> {
        let expected = output_dim * input_dim;
        if weights.len() != expected {
            return Err(LinearError::ShapeMismatch {
                got: weights.len(),
                expected,
            });
        }
        let bpr = input_dim.div_ceil(BLOCK_SIZE);
        let mut rows = Vec::with_capacity(output_dim);
        for o in 0..output_dim {
            let row = &weights[o * input_dim..(o + 1) * input_dim];
            let mut blocks = Vec::with_capacity(bpr);
            for b in 0..bpr {
                let mut chunk = [0.0f32; BLOCK_SIZE];
                for (j, slot) in chunk.iter_mut().enumerate() {
                    let idx = b * BLOCK_SIZE + j;
                    if idx < input_dim {
                        *slot = row[idx];
                    }
                }
                blocks.push(quantize_block_rne(&chunk));
            }
            rows.push(blocks);
        }
        Ok(Self {
            output_dim,
            input_dim,
            rows,
        })
    }

    /// Forward pass `y = W·x`, computed block-wise on the dequantized
    /// NVFP4 weights. `x.len()` must equal `input_dim`.
    pub fn matvec(&self, x: &[f32]) -> Result<Vec<f32>, LinearError> {
        if x.len() != self.input_dim {
            return Err(LinearError::InputMismatch {
                got: x.len(),
                expected: self.input_dim,
            });
        }
        let mut y = vec![0.0f32; self.output_dim];
        for (o, blocks) in self.rows.iter().enumerate() {
            let mut acc = 0.0f32;
            for (b, block) in blocks.iter().enumerate() {
                let w = dequantize_block(block);
                for (j, wj) in w.iter().enumerate() {
                    let idx = b * BLOCK_SIZE + j;
                    if idx < self.input_dim {
                        acc += wj * x[idx];
                    }
                }
            }
            y[o] = acc;
        }
        Ok(y)
    }

    /// Effective bits per parameter: `(16·4 + 8) / 16 = 4.5`.
    pub fn bits_per_param(&self) -> f64 {
        (BLOCK_SIZE as f64 * 4.0 + 8.0) / BLOCK_SIZE as f64
    }

    /// Stored size in bytes: 16 elements (4 bits each = 8 bytes) + 1 scale
    /// byte per block.
    pub fn quantized_bytes(&self) -> usize {
        let blocks: usize = self.rows.iter().map(|r| r.len()).sum();
        blocks * (BLOCK_SIZE / 2 + 1)
    }
}

/// An NVFP4 weight matrix quantized **after** a random Hadamard rotation —
/// the accuracy recipe the dump's NVFP4 work (M077) calls for.
///
/// 4-bit microscaling quantizes each 16-element block against a single
/// shared scale, so one outlier weight inflates the scale and rounds the
/// rest of the block toward zero. The random Hadamard transform `R`
/// (orthonormal: `RᵀR = I`) *spreads* each block's outliers across all
/// dimensions before quantization, so no element dominates the block scale.
///
/// Because `R` preserves inner products, rotating both the weight rows and
/// the activations leaves the result unchanged in exact arithmetic
/// (`(R·wₒ)·(R·x) = wₒ·x`); only the *quantization error* is reduced. The
/// rotation is the same on both sides, recovered from the stored `signs`.
///
/// `input_dim` must be a power of two (the fast Walsh-Hadamard constraint).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RhtQuantMatrix {
    /// NVFP4-quantized **rotated** weights (`W·Rᵀ`, row-major).
    pub quant: QuantMatrix,
    /// The RHT sign vector (length `input_dim`); defines the rotation `R`.
    pub signs: Vec<i8>,
}

impl RhtQuantMatrix {
    /// Quantize a row-major `output_dim × input_dim` matrix after rotating
    /// each row by `R = rht_forward(·, signs)`, with `signs` drawn from
    /// `seed`. `input_dim` must be a power of two.
    pub fn from_f32(
        weights: &[f32],
        output_dim: usize,
        input_dim: usize,
        seed: u64,
    ) -> Result<Self, LinearError> {
        let expected = output_dim * input_dim;
        if weights.len() != expected {
            return Err(LinearError::ShapeMismatch {
                got: weights.len(),
                expected,
            });
        }
        if !input_dim.is_power_of_two() {
            return Err(LinearError::RhtInputNotPowerOfTwo(input_dim));
        }
        let signs = crate::random_signs(input_dim, seed);
        let mut rotated = Vec::with_capacity(expected);
        for o in 0..output_dim {
            let row = &weights[o * input_dim..(o + 1) * input_dim];
            let r = crate::rht_forward(row, &signs)
                .map_err(|_| LinearError::RhtInputNotPowerOfTwo(input_dim))?;
            rotated.extend(r);
        }
        let quant = QuantMatrix::from_f32(&rotated, output_dim, input_dim)?;
        Ok(Self { quant, signs })
    }

    /// Forward `y = W·x`: rotate `x` by the same `R`, then matvec on the
    /// rotated quantized weights. Equal to `W·x` up to NVFP4 quantization
    /// error — lower than plain [`QuantMatrix::matvec`] for outlier-heavy
    /// weights, identical (within tolerance) for benign ones.
    pub fn matvec(&self, x: &[f32]) -> Result<Vec<f32>, LinearError> {
        if x.len() != self.quant.input_dim {
            return Err(LinearError::InputMismatch {
                got: x.len(),
                expected: self.quant.input_dim,
            });
        }
        let xr = crate::rht_forward(x, &self.signs)
            .map_err(|_| LinearError::RhtInputNotPowerOfTwo(self.quant.input_dim))?;
        self.quant.matvec(&xr)
    }

    /// Effective bits per parameter — the underlying NVFP4 cost (the sign
    /// vector is a per-tensor seed, amortized to ~0 per weight).
    pub fn bits_per_param(&self) -> f64 {
        self.quant.bits_per_param()
    }
}

/// Dense f32 reference `y = W·x` (multiply-based), for accuracy checks.
pub fn dense_f32_matvec(weights: &[f32], input_dim: usize, x: &[f32]) -> Vec<f32> {
    let output_dim = weights.len() / input_dim;
    let mut y = vec![0.0f32; output_dim];
    for (o, yo) in y.iter_mut().enumerate() {
        let row = &weights[o * input_dim..(o + 1) * input_dim];
        *yo = row.iter().zip(x).map(|(w, xi)| w * xi).sum();
    }
    y
}

#[cfg(test)]
mod tests {
    use super::*;

    // deterministic finite pseudo-randoms in [-2, 2)
    fn rng_seq(n: usize, seed: u64) -> Vec<f32> {
        let mut s = seed;
        (0..n)
            .map(|_| {
                s ^= s << 13;
                s ^= s >> 7;
                s ^= s << 17;
                ((s >> 40) as f32 / 0x10_0000 as f32) * 4.0 - 2.0
            })
            .collect()
    }

    fn l2(v: &[f32]) -> f32 {
        v.iter().map(|x| x * x).sum::<f32>().sqrt()
    }

    #[test]
    fn matvec_approximates_f32_reference() {
        let (output_dim, input_dim) = (5, 37); // non-multiple of 16 → padding path
        let weights = rng_seq(output_dim * input_dim, 0xABCD);
        let x = rng_seq(input_dim, 0x1234);

        let q = QuantMatrix::from_f32(&weights, output_dim, input_dim).unwrap();
        let y_q = q.matvec(&x).unwrap();
        let y_ref = dense_f32_matvec(&weights, input_dim, &x);

        // NVFP4 is lossy; require the relative L2 error to be modest.
        let mut diff = vec![0.0f32; output_dim];
        for i in 0..output_dim {
            diff[i] = y_q[i] - y_ref[i];
        }
        let rel = l2(&diff) / l2(&y_ref).max(1e-6);
        assert!(rel < 0.25, "relative error too high: {rel}");
    }

    #[test]
    fn rht_matvec_approximates_f32_reference() {
        let (output_dim, input_dim) = (4, 32); // power of two
        let weights = rng_seq(output_dim * input_dim, 0x5151);
        let x = rng_seq(input_dim, 0x9999);

        let q = RhtQuantMatrix::from_f32(&weights, output_dim, input_dim, 0xC0FFEE).unwrap();
        let y_q = q.matvec(&x).unwrap();
        let y_ref = dense_f32_matvec(&weights, input_dim, &x);

        let diff: Vec<f32> = y_q.iter().zip(&y_ref).map(|(a, b)| a - b).collect();
        let rel = l2(&diff) / l2(&y_ref).max(1e-6);
        assert!(rel < 0.25, "RHT relative error too high: {rel}");
    }

    #[test]
    fn rht_reduces_error_on_outlier_weights() {
        // Each 16-wide row: one big outlier + 15 small values. Plain NVFP4
        // lets the outlier dominate the block scale and rounds the smalls to
        // ~0; RHT spreads the outlier so the block quantizes more uniformly.
        let (output_dim, input_dim) = (4, 16);
        let mut weights = vec![0.0f32; output_dim * input_dim];
        for o in 0..output_dim {
            weights[o * input_dim] = 12.0; // the outlier
            for j in 1..input_dim {
                weights[o * input_dim + j] = 0.15;
            }
        }
        let x = vec![1.0f32; input_dim];
        let y_ref = dense_f32_matvec(&weights, input_dim, &x);

        let plain = QuantMatrix::from_f32(&weights, output_dim, input_dim).unwrap();
        let rht = RhtQuantMatrix::from_f32(&weights, output_dim, input_dim, 0x1357).unwrap();
        let y_plain = plain.matvec(&x).unwrap();
        let y_rht = rht.matvec(&x).unwrap();

        let err = |y: &[f32]| {
            let d: Vec<f32> = y.iter().zip(&y_ref).map(|(a, b)| a - b).collect();
            l2(&d) / l2(&y_ref).max(1e-6)
        };
        let (e_plain, e_rht) = (err(&y_plain), err(&y_rht));
        assert!(
            e_rht < e_plain,
            "RHT did not reduce outlier error: plain {e_plain} vs rht {e_rht}"
        );
    }

    #[test]
    fn rht_rejects_non_power_of_two() {
        let err = RhtQuantMatrix::from_f32(&[0.0; 20], 1, 20, 7).unwrap_err();
        assert_eq!(err, LinearError::RhtInputNotPowerOfTwo(20));
    }

    #[test]
    fn padding_path_blocks_per_row() {
        let q = QuantMatrix::from_f32(&[0.0; 20], 1, 20).unwrap();
        assert_eq!(q.blocks_per_row(), 2); // ceil(20/16)
        assert_eq!(q.rows[0].len(), 2);
    }

    #[test]
    fn zero_weights_give_zero_output() {
        let q = QuantMatrix::from_f32(&[0.0; 3 * 16], 3, 16).unwrap();
        let y = q.matvec(&[1.0; 16]).unwrap();
        assert_eq!(y, vec![0.0, 0.0, 0.0]);
    }

    #[test]
    fn bits_per_param_is_4_5() {
        let q = QuantMatrix::from_f32(&[0.0; 16], 1, 16).unwrap();
        assert!((q.bits_per_param() - 4.5).abs() < 1e-9);
    }

    #[test]
    fn quantized_bytes_accounts_blocks() {
        // 2x16 = 2 blocks → 2 * (8 + 1) = 18 bytes
        let q = QuantMatrix::from_f32(&[0.0; 2 * 16], 2, 16).unwrap();
        assert_eq!(q.quantized_bytes(), 18);
    }

    #[test]
    fn shape_mismatch_rejected() {
        let err = QuantMatrix::from_f32(&[1.0, 2.0], 2, 2).unwrap_err();
        assert!(matches!(err, LinearError::ShapeMismatch { .. }));
    }

    #[test]
    fn input_mismatch_rejected() {
        let q = QuantMatrix::from_f32(&[0.0; 6], 2, 3).unwrap();
        let err = q.matvec(&[1.0, 2.0]).unwrap_err();
        assert!(matches!(err, LinearError::InputMismatch { .. }));
    }

    #[test]
    fn serde_round_trip() {
        let q = QuantMatrix::from_f32(&rng_seq(32, 7), 2, 16).unwrap();
        let j = serde_json::to_string(&q).unwrap();
        let back: QuantMatrix = serde_json::from_str(&j).unwrap();
        assert_eq!(q, back);
    }
}
