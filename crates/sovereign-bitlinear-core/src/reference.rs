//! Multiply-based reference forward pass.
//!
//! This is the "honest" GEMM the BitLinear path replaces: it de-quantizes
//! the ternary weights to `scale * value` and does ordinary
//! multiply-accumulate. The BitLinear forward must match this bit-for-bit
//! (see `linear::tests::forward_matches_dense_reference`) — that is the
//! proof that eliminating the multiplies does not change the answer.

use crate::ternary::Trit;

/// Row-major dense forward: `y[o] = scale * Σ_i value(W[o,i]) * x[i]`.
///
/// `weights` is `output_dim × input_dim` in row-major order. Computed
/// with the multiplies *present*, exactly the cost BitLinear avoids.
pub fn dense_forward(weights: &[Trit], scale: f32, input_dim: usize, x: &[f32]) -> Vec<f32> {
    let output_dim = weights.len() / input_dim;
    let mut y = vec![0.0f32; output_dim];
    for o in 0..output_dim {
        let row = &weights[o * input_dim..(o + 1) * input_dim];
        let mut acc = 0.0f32;
        for (w, &xi) in row.iter().zip(x.iter()) {
            acc += (w.value() as f32) * xi;
        }
        y[o] = scale * acc;
    }
    y
}

/// Number of floating-point multiplies a dense GEMM of this shape costs.
/// The BitLinear path reduces this to just `output_dim` (the per-row
/// scale), eliminating `output_dim × input_dim` inner-product multiplies.
pub const fn dense_mul_count(output_dim: usize, input_dim: usize) -> usize {
    output_dim * input_dim + output_dim
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dense_forward_small() {
        // 2x3 weights, scale 2.0.
        let w = [
            Trit::Plus,
            Trit::Zero,
            Trit::Minus, // row 0
            Trit::Minus,
            Trit::Plus,
            Trit::Plus, // row 1
        ];
        let x = [1.0, 10.0, 100.0];
        let y = dense_forward(&w, 2.0, 3, &x);
        // row0: (+1*1 + 0*10 + -1*100) = -99 -> *2 = -198
        // row1: (-1*1 + +1*10 + +1*100) = 109 -> *2 = 218
        assert_eq!(y, vec![-198.0, 218.0]);
    }

    #[test]
    fn mul_count_formula() {
        assert_eq!(dense_mul_count(4, 8), 36);
    }
}
