//! `sovereign-rmsnorm` — root-mean-square normalization.
//!
//! Every Llama-style transformer block normalizes its activations *before*
//! attention and *before* the FFN. RMSNorm is the normalizer those models
//! use: instead of LayerNorm's mean-subtract-then-divide-by-stddev, it simply
//! divides by the root-mean-square of the vector and applies a learned
//! per-channel gain `γ`:
//!
//! ```text
//! rms(x) = sqrt( mean(xᵢ²) + ε )
//! y_i    = (x_i / rms(x)) · γ_i
//! ```
//!
//! Dropping the mean-subtraction makes it cheaper and, with unit gain, makes
//! the output's RMS equal to 1 — so it is **scale-invariant**: feeding `c·x`
//! for any positive `c` yields the same result. Both properties are pinned as
//! tests. This is the normalization stage that wraps the attention and
//! feed-forward engines in a transformer block.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the RMSNorm surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The conventional numerical-stability epsilon.
pub const DEFAULT_EPS: f32 = 1e-6;

/// Things that can go wrong applying RMSNorm.
#[derive(Debug, Error, PartialEq)]
pub enum RmsNormError {
    /// The input length did not match the configured dimension.
    #[error("dimension mismatch: expected {expected}, got {got}")]
    DimMismatch {
        /// Configured dimension (gain length).
        expected: usize,
        /// Observed input length.
        got: usize,
    },
}

/// An RMS normalizer with a learned per-channel gain.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RmsNorm {
    /// Activation dimension.
    pub dim: usize,
    /// Numerical-stability epsilon added under the square root.
    pub eps: f32,
    /// Per-channel gain `γ` (length `dim`).
    pub gain: Vec<f32>,
}

impl RmsNorm {
    /// An RMSNorm with unit gain and [`DEFAULT_EPS`].
    ///
    /// # Panics
    /// Panics if `dim == 0`.
    pub fn new(dim: usize) -> Self {
        assert!(dim > 0, "dim must be > 0");
        Self {
            dim,
            eps: DEFAULT_EPS,
            gain: vec![1.0; dim],
        }
    }

    /// An RMSNorm with an explicit gain vector and epsilon.
    ///
    /// # Panics
    /// Panics if `gain` is empty.
    pub fn with_gain(gain: Vec<f32>, eps: f32) -> Self {
        assert!(!gain.is_empty(), "gain must be non-empty");
        Self {
            dim: gain.len(),
            eps,
            gain,
        }
    }

    /// Normalize `x`: divide by its RMS, then apply the per-channel gain.
    pub fn normalize(&self, x: &[f32]) -> Result<Vec<f32>, RmsNormError> {
        if x.len() != self.dim {
            return Err(RmsNormError::DimMismatch {
                expected: self.dim,
                got: x.len(),
            });
        }
        let mean_sq = x.iter().map(|v| v * v).sum::<f32>() / self.dim as f32;
        let inv_rms = 1.0 / (mean_sq + self.eps).sqrt();
        Ok(x.iter()
            .zip(&self.gain)
            .map(|(v, g)| v * inv_rms * g)
            .collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rms(v: &[f32]) -> f32 {
        (v.iter().map(|x| x * x).sum::<f32>() / v.len() as f32).sqrt()
    }

    fn approx(a: &[f32], b: &[f32], eps: f32) -> bool {
        a.len() == b.len() && a.iter().zip(b).all(|(x, y)| (x - y).abs() <= eps)
    }

    #[test]
    fn unit_gain_output_has_rms_one() {
        let norm = RmsNorm::new(4);
        let y = norm.normalize(&[1.0, 2.0, 3.0, 4.0]).unwrap();
        // eps is tiny, so output RMS is essentially 1.
        assert!((rms(&y) - 1.0).abs() < 1e-3, "rms {}", rms(&y));
    }

    #[test]
    fn positive_scale_invariance() {
        let norm = RmsNorm::new(5);
        let x = vec![0.5, -1.0, 2.0, 3.0, -0.25];
        let base = norm.normalize(&x).unwrap();
        for c in [2.0f32, 10.0, 0.1, 1000.0] {
            let scaled: Vec<f32> = x.iter().map(|v| v * c).collect();
            let y = norm.normalize(&scaled).unwrap();
            assert!(approx(&y, &base, 1e-3), "c={c}: {y:?} vs {base:?}");
        }
    }

    #[test]
    fn negation_flips_sign() {
        let norm = RmsNorm::new(3);
        let x = vec![1.0, -2.0, 0.5];
        let y = norm.normalize(&x).unwrap();
        let neg: Vec<f32> = x.iter().map(|v| -v).collect();
        let yn = norm.normalize(&neg).unwrap();
        let flip: Vec<f32> = y.iter().map(|v| -v).collect();
        assert!(approx(&yn, &flip, 1e-5));
    }

    #[test]
    fn gain_scales_each_channel() {
        let gain = vec![2.0, 0.5, 1.0, -1.0];
        let norm = RmsNorm::with_gain(gain.clone(), DEFAULT_EPS);
        let unit = RmsNorm::new(4);
        let x = vec![1.0, 2.0, 3.0, 4.0];
        let base = unit.normalize(&x).unwrap();
        let y = norm.normalize(&x).unwrap();
        for i in 0..4 {
            assert!((y[i] - base[i] * gain[i]).abs() < 1e-5, "channel {i}");
        }
    }

    #[test]
    fn zero_vector_stays_finite_and_zero() {
        let norm = RmsNorm::new(4);
        let y = norm.normalize(&[0.0; 4]).unwrap();
        assert!(y.iter().all(|v| v.is_finite()));
        assert_eq!(y, vec![0.0; 4]);
    }

    #[test]
    fn known_value() {
        // x = [3,4], mean_sq = (9+16)/2 = 12.5, rms ≈ 3.5355 (eps negligible)
        // y = [3/3.5355, 4/3.5355] ≈ [0.8485, 1.1314]
        let norm = RmsNorm::with_gain(vec![1.0, 1.0], 0.0);
        let y = norm.normalize(&[3.0, 4.0]).unwrap();
        assert!(approx(&y, &[0.848528, 1.131371], 1e-4), "{y:?}");
    }

    #[test]
    fn dim_mismatch_is_caught() {
        let norm = RmsNorm::new(4);
        assert_eq!(
            norm.normalize(&[1.0, 2.0]).unwrap_err(),
            RmsNormError::DimMismatch {
                expected: 4,
                got: 2
            }
        );
    }

    #[test]
    fn serde_round_trip() {
        let norm = RmsNorm::with_gain(vec![1.0, 2.0, 3.0], 1e-5);
        let j = serde_json::to_string(&norm).unwrap();
        let back: RmsNorm = serde_json::from_str(&j).unwrap();
        assert_eq!(norm, back);
    }
}
