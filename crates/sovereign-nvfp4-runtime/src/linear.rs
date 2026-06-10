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

use crate::{BLOCK_SIZE, E2m1, QuantBlock, dequantize_block, quantize_block_rne};
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

    /// Quantize a row-major `output_dim × input_dim` matrix with
    /// **stochastic** element rounding (the training-path recipe) — same
    /// layout as [`QuantMatrix::from_f32`], but each element is rounded
    /// stochastically so the quantization is unbiased in expectation.
    pub fn from_f32_stochastic<R: rand::Rng>(
        rng: &mut R,
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
                blocks.push(crate::quantize_block_stochastic(rng, &chunk));
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

    /// Reconstruct the full row-major f32 weight matrix from the quantized
    /// blocks (the de-quantized view, padding trimmed back to `input_dim`).
    pub fn dequantized_weights(&self) -> Vec<f32> {
        let mut out = vec![0.0f32; self.output_dim * self.input_dim];
        for (o, blocks) in self.rows.iter().enumerate() {
            for (b, block) in blocks.iter().enumerate() {
                let w = dequantize_block(block);
                for (j, &wj) in w.iter().enumerate() {
                    let idx = b * BLOCK_SIZE + j;
                    if idx < self.input_dim {
                        out[o * self.input_dim + idx] = wj;
                    }
                }
            }
        }
        out
    }

    /// Stored size in bytes: 16 elements (4 bits each = 8 bytes) + 1 scale
    /// byte per block.
    pub fn quantized_bytes(&self) -> usize {
        let blocks: usize = self.rows.iter().map(|r| r.len()).sum();
        blocks * (BLOCK_SIZE / 2 + 1)
    }
}

/// Relative reconstruction error `‖W − Ŵ‖_F / ‖W‖_F` between an original
/// f32 weight tensor and a quantizer's de-quantized view — the NVFP4
/// quant-quality metric (parallel to `sovereign-bitlinear-core`'s
/// `ternary_reconstruction_error`). `0.0` = lossless; a higher value means
/// more energy lost to 4-bit microscaling, so a loader can decide whether to
/// reach for RHT / 2D / selective-HP on that layer. Zero/empty tensors
/// return `0.0`.
pub fn relative_frobenius_error(original: &[f32], reconstructed: &[f32]) -> f64 {
    let mut num = 0.0f64;
    let mut den = 0.0f64;
    for (a, b) in original.iter().zip(reconstructed) {
        let d = *a as f64 - *b as f64;
        num += d * d;
        den += (*a as f64) * (*a as f64);
    }
    if den == 0.0 { 0.0 } else { (num / den).sqrt() }
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

/// A weight matrix under **two-dimensional** NVFP4 quantization (M077,
/// F06388-F06390): a per-row scale `r` *and* a per-column scale `c`, so the
/// factorization `W[o,j] ≈ r[o] · q[o,j] · c[j]` gives consistent
/// representations whether the matrix is read row-wise (the forward pass
/// `W·x`) or column-wise (the backward pass `Wᵀ·g`). Plain 1D NVFP4
/// ([`QuantMatrix`]) carries only the per-row block scale, so a column with
/// systematically small magnitudes rounds toward zero everywhere; the
/// per-column scale `c` restores it.
///
/// `q[o,j]` is the 4-bit E2M1 core (the residual after both scales divide
/// out). Forward: `y[o] = r[o] · Σ_j q[o,j] · (c[j]·x[j])` — scale `x` by the
/// columns, 4-bit matvec, scale the output by the rows.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TwoDQuantMatrix {
    /// Output rows.
    pub output_dim: usize,
    /// Input columns.
    pub input_dim: usize,
    /// Per-row scales (`output_dim`).
    pub row_scales: Vec<f32>,
    /// Per-column scales (`input_dim`).
    pub col_scales: Vec<f32>,
    /// The 4-bit E2M1 core, row-major `output_dim × input_dim`.
    pub core: Vec<E2m1>,
}

impl TwoDQuantMatrix {
    /// Quantize with per-row + per-column scales. The scales are extracted
    /// in two passes (rows, then columns of the row-normalized matrix); the
    /// residual is rounded to E2M1.
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
        // Pass 1: per-row scale = max|row| / 3 (E2M1's largest magnitude).
        let mut row_scales = vec![1.0f32; output_dim];
        for (o, rs) in row_scales.iter_mut().enumerate() {
            let row = &weights[o * input_dim..(o + 1) * input_dim];
            let m = row.iter().copied().map(f32::abs).fold(0.0f32, f32::max);
            *rs = if m > 0.0 { m / 3.0 } else { 1.0 };
        }
        // Pass 2: per-column scale from the row-normalized matrix.
        let mut col_scales = vec![1.0f32; input_dim];
        for (j, cs) in col_scales.iter_mut().enumerate() {
            let mut m = 0.0f32;
            for o in 0..output_dim {
                let v = (weights[o * input_dim + j] / row_scales[o]).abs();
                m = m.max(v);
            }
            *cs = if m > 0.0 { m / 3.0 } else { 1.0 };
        }
        // Core: round the doubly-normalized residual to E2M1.
        let mut core = vec![E2m1::default(); expected];
        for o in 0..output_dim {
            for j in 0..input_dim {
                let idx = o * input_dim + j;
                let norm = weights[idx] / (row_scales[o] * col_scales[j]);
                core[idx] = E2m1::from_f32_rne(norm);
            }
        }
        Ok(Self {
            output_dim,
            input_dim,
            row_scales,
            col_scales,
            core,
        })
    }

    /// Forward `y = W·x` on the 2D-quantized weights: scale `x` by the
    /// columns, 4-bit accumulate, scale the output by the rows.
    pub fn matvec(&self, x: &[f32]) -> Result<Vec<f32>, LinearError> {
        if x.len() != self.input_dim {
            return Err(LinearError::InputMismatch {
                got: x.len(),
                expected: self.input_dim,
            });
        }
        let xc: Vec<f32> = x
            .iter()
            .zip(&self.col_scales)
            .map(|(xi, c)| xi * c)
            .collect();
        let mut y = vec![0.0f32; self.output_dim];
        for (o, yo) in y.iter_mut().enumerate() {
            let mut acc = 0.0f32;
            for j in 0..self.input_dim {
                acc += self.core[o * self.input_dim + j].to_f32() * xc[j];
            }
            *yo = self.row_scales[o] * acc;
        }
        Ok(y)
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
    fn nvfp4_reconstruction_error_is_bounded_and_lossless_when_uniform() {
        // Uniform-magnitude weights quantize losslessly under NVFP4.
        let uniform = vec![1.5f32; 32];
        let q = QuantMatrix::from_f32(&uniform, 2, 16).unwrap();
        let e0 = relative_frobenius_error(&uniform, &q.dequantized_weights());
        assert!(e0 < 1e-6, "uniform weights should be ~lossless: {e0}");

        // A spread of magnitudes loses some energy, but stays bounded.
        let spread = rng_seq(2 * 16, 0x4242);
        let qs = QuantMatrix::from_f32(&spread, 2, 16).unwrap();
        let e = relative_frobenius_error(&spread, &qs.dequantized_weights());
        assert!(e > 0.0 && e < 0.5, "spread error out of range: {e}");
    }

    #[test]
    fn two_d_reconstructs_column_structure_better_than_1d() {
        // The metric-level analogue of the matvec test: 2D's per-column
        // scale recovers a systematically-tiny column that 1D rounds to ~0.
        let (output_dim, input_dim) = (6, 16);
        let mut weights = vec![1.0f32; output_dim * input_dim];
        for o in 0..output_dim {
            weights[o * input_dim + 5] = 0.012;
        }
        let one_d = QuantMatrix::from_f32(&weights, output_dim, input_dim).unwrap();
        let two_d = TwoDQuantMatrix::from_f32(&weights, output_dim, input_dim).unwrap();
        // Reconstruct just the small column from each and compare its error.
        let e1 = relative_frobenius_error(&weights, &one_d.dequantized_weights());
        // 2D stores per-column scale, so the tiny column survives → lower error.
        // (TwoDQuantMatrix has no dequantized_weights; compare via its matvec
        // reconstruction of the small column using a one-hot probe.)
        let mut probe = vec![0.0f32; input_dim];
        probe[5] = 1.0;
        let col_ref: Vec<f32> = (0..output_dim)
            .map(|o| weights[o * input_dim + 5])
            .collect();
        let col_2d = two_d.matvec(&probe).unwrap();
        let col_1d = one_d.matvec(&probe).unwrap();
        let e_col_2d = relative_frobenius_error(&col_ref, &col_2d);
        let e_col_1d = relative_frobenius_error(&col_ref, &col_1d);
        assert!(
            e_col_2d < e_col_1d,
            "2D did not recover the small column better: 1d {e_col_1d} vs 2d {e_col_2d}"
        );
        assert!(e1 > 0.0); // 1D loses the small column → nonzero overall error
    }

    #[test]
    fn two_d_matvec_approximates_f32_reference() {
        let (output_dim, input_dim) = (5, 24);
        let weights = rng_seq(output_dim * input_dim, 0x77AA);
        let x = rng_seq(input_dim, 0x33BB);
        let q = TwoDQuantMatrix::from_f32(&weights, output_dim, input_dim).unwrap();
        let y_q = q.matvec(&x).unwrap();
        let y_ref = dense_f32_matvec(&weights, input_dim, &x);
        let diff: Vec<f32> = y_q.iter().zip(&y_ref).map(|(a, b)| a - b).collect();
        let rel = l2(&diff) / l2(&y_ref).max(1e-6);
        assert!(rel < 0.25, "2D relative error too high: {rel}");
    }

    #[test]
    fn two_d_beats_1d_on_column_structured_weights() {
        // Most entries ~1.0, but one column is systematically tiny. 1D's
        // per-row scale rounds that column to ~0 everywhere; the per-column
        // scale in 2D restores it.
        let (output_dim, input_dim) = (6, 16);
        let small_col = 5usize;
        let mut weights = vec![1.0f32; output_dim * input_dim];
        for o in 0..output_dim {
            weights[o * input_dim + small_col] = 0.012;
        }
        let x = vec![1.0f32; input_dim];
        let y_ref = dense_f32_matvec(&weights, input_dim, &x);

        let one_d = QuantMatrix::from_f32(&weights, output_dim, input_dim).unwrap();
        let two_d = TwoDQuantMatrix::from_f32(&weights, output_dim, input_dim).unwrap();
        let err = |y: &[f32]| {
            let d: Vec<f32> = y.iter().zip(&y_ref).map(|(a, b)| a - b).collect();
            l2(&d) / l2(&y_ref).max(1e-6)
        };
        let (e1, e2) = (
            err(&one_d.matvec(&x).unwrap()),
            err(&two_d.matvec(&x).unwrap()),
        );
        assert!(
            e2 < e1,
            "2D did not beat 1D on column structure: 1d {e1} vs 2d {e2}"
        );
    }

    #[test]
    fn stochastic_matrix_is_a_valid_approximation() {
        use rand::SeedableRng;
        use rand_chacha::ChaCha20Rng;
        let (output_dim, input_dim) = (5, 37);
        let weights = rng_seq(output_dim * input_dim, 0x2468);
        let x = rng_seq(input_dim, 0x1111);
        let mut rng = ChaCha20Rng::seed_from_u64(0xBEEF);
        let q =
            QuantMatrix::from_f32_stochastic(&mut rng, &weights, output_dim, input_dim).unwrap();
        let y_q = q.matvec(&x).unwrap();
        let y_ref = dense_f32_matvec(&weights, input_dim, &x);
        let diff: Vec<f32> = y_q.iter().zip(&y_ref).map(|(a, b)| a - b).collect();
        let rel = l2(&diff) / l2(&y_ref).max(1e-6);
        // A single stochastic draw is noisier than RNE but still a valid
        // low-bit approximation.
        assert!(
            rel < 0.4,
            "stochastic matvec relative error too high: {rel}"
        );
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
