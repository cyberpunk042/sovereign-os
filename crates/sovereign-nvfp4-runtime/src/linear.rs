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
