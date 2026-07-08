//! Ternary weight type and BitNet b1.58 absmean quantization.

use serde::{Deserialize, Serialize};

/// A single ternary weight drawn from the set `{-1, 0, +1}` (F06039).
///
/// The discriminants are the 2-bit wire codes used by
/// [`crate::pack::Packing::TwoBit`]; the base-3 packer uses the same
/// `0/1/2` ordinal via [`Trit::to_base3`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[repr(u8)]
pub enum Trit {
    /// `0` — bypassed entirely; contributes nothing (F06045).
    Zero = 0,
    /// `+1` — activation added to the accumulator (F06043).
    Plus = 1,
    /// `-1` — activation subtracted from the accumulator (F06044).
    Minus = 2,
}

impl Trit {
    /// The signed integer value of this trit (`-1`, `0`, or `+1`).
    #[inline]
    pub const fn value(self) -> i8 {
        match self {
            Trit::Zero => 0,
            Trit::Plus => 1,
            Trit::Minus => -1,
        }
    }

    /// Base-3 digit (`0`, `1`, `2`) used by the dense base-3 packer.
    #[inline]
    pub const fn to_base3(self) -> u8 {
        self as u8
    }

    /// Reconstruct a trit from its base-3 digit. Digits `>= 3` saturate
    /// to [`Trit::Zero`] (defensive; a valid packed byte never produces one).
    #[inline]
    pub const fn from_base3(d: u8) -> Trit {
        match d {
            1 => Trit::Plus,
            2 => Trit::Minus,
            _ => Trit::Zero,
        }
    }
}

/// Quantize a real-valued weight tensor to ternary using the BitNet
/// b1.58 *absmean* rule (F06038, F06051):
///
/// ```text
/// γ        = mean(|W|)                       (per-tensor scale)
/// W_ternary = clamp(round(W / γ), -1, +1)    (the ternary set)
/// ```
///
/// Returns the ternary weights paired with the scale `γ`. De-quantizing
/// is `γ * W_ternary` — but note the forward path never does that
/// element-wise; it folds `γ` into the single per-row output scale.
///
/// An all-zero tensor yields scale `0.0` and all-[`Trit::Zero`] weights
/// (rather than dividing by zero).
pub fn quantize_absmean(weights: &[f32]) -> (Vec<Trit>, f32) {
    if weights.is_empty() {
        return (Vec::new(), 0.0);
    }
    let abs_sum: f64 = weights.iter().map(|w| (*w as f64).abs()).sum();
    let scale = (abs_sum / weights.len() as f64) as f32;
    if scale == 0.0 {
        return (vec![Trit::Zero; weights.len()], 0.0);
    }
    let trits = weights
        .iter()
        .map(|&w| {
            let r = (w / scale).round();
            if r >= 1.0 {
                Trit::Plus
            } else if r <= -1.0 {
                Trit::Minus
            } else {
                Trit::Zero
            }
        })
        .collect();
    (trits, scale)
}

/// Relative reconstruction error of absmean ternary quantization:
/// `‖W − Ŵ‖_F / ‖W‖_F`, where `Ŵ[i] = γ · value(quantize(W[i]))`.
///
/// This is the standard quality metric for whether a weight matrix is
/// *ternary-friendly*: `0.0` means the 1.58-bit approximation is lossless
/// for this tensor (every weight already sits at `−γ`, `0`, or `+γ`);
/// values approaching `1.0` mean most of the tensor's energy is lost to the
/// approximation. Use it to decide per-layer whether ternary is safe or a
/// higher precision (NVFP4 / FP16) is warranted.
///
/// An all-zero (or empty) tensor reconstructs exactly and returns `0.0`.
pub fn ternary_reconstruction_error(weights: &[f32]) -> f64 {
    let (trits, scale) = quantize_absmean(weights);
    let mut num = 0.0f64;
    let mut den = 0.0f64;
    for (&w, t) in weights.iter().zip(&trits) {
        let recon = scale as f64 * t.value() as f64;
        let diff = w as f64 - recon;
        num += diff * diff;
        den += (w as f64) * (w as f64);
    }
    if den == 0.0 { 0.0 } else { (num / den).sqrt() }
}

/// Whether absmean ternary quantization is safe for this tensor at a given
/// relative-error tolerance — the actionable, operator-facing per-layer
/// decision (R12201/R12228: exempt layers that quantize poorly from the
/// ternary requirement). Returns `true` when
/// [`ternary_reconstruction_error`] is at or below `max_relative_error`.
///
/// A lossless tensor (all magnitudes equal, or all-zero) is ternary-friendly
/// at any non-negative tolerance.
pub fn is_ternary_friendly(weights: &[f32], max_relative_error: f64) -> bool {
    ternary_reconstruction_error(weights) <= max_relative_error
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ternary_friendly_accepts_lossless_and_rejects_lossy() {
        // Lossless (equal magnitudes) → friendly at any tolerance, incl. 0.
        assert!(is_ternary_friendly(&[2.0f32, -2.0, 2.0], 0.0));
        // A spread tensor has positive error; a zero tolerance rejects it,
        // a generous tolerance accepts it.
        let spread = [0.1f32, 0.9, -0.2, 3.0, -1.5, 0.05];
        assert!(!is_ternary_friendly(&spread, 0.0));
        assert!(is_ternary_friendly(&spread, 1.0));
    }

    #[test]
    fn reconstruction_error_lossless_for_equal_magnitudes() {
        // All |w| equal → absmean scale = |w|, each weight maps to ±1·scale
        // exactly → zero reconstruction error.
        let w = [2.0f32, -2.0, 2.0, -2.0];
        assert_eq!(ternary_reconstruction_error(&w), 0.0);
    }

    #[test]
    fn reconstruction_error_zero_tensor_is_zero() {
        assert_eq!(ternary_reconstruction_error(&[0.0f32; 8]), 0.0);
        assert_eq!(ternary_reconstruction_error(&[]), 0.0);
    }

    #[test]
    fn reconstruction_error_bounded_and_positive_for_spread_weights() {
        // A spread of magnitudes loses information to the ternary clamp/round.
        let w = [0.1f32, 0.9, -0.2, 3.0, -1.5, 0.05];
        let e = ternary_reconstruction_error(&w);
        assert!(e > 0.0 && e < 1.0, "error out of (0,1): {e}");
    }

    #[test]
    fn trit_values() {
        assert_eq!(Trit::Minus.value(), -1);
        assert_eq!(Trit::Zero.value(), 0);
        assert_eq!(Trit::Plus.value(), 1);
    }

    #[test]
    fn base3_round_trip() {
        for t in [Trit::Zero, Trit::Plus, Trit::Minus] {
            assert_eq!(Trit::from_base3(t.to_base3()), t);
        }
    }

    #[test]
    fn absmean_scale_is_mean_abs() {
        let w = [2.0, -2.0, 4.0, -4.0];
        let (_, scale) = quantize_absmean(&w);
        // mean(|w|) = (2+2+4+4)/4 = 3.0
        assert!((scale - 3.0).abs() < 1e-6);
    }

    #[test]
    fn absmean_assigns_ternary_set() {
        // Around scale 3.0: |w| well above 1.5*scale -> ±1, near 0 -> 0.
        let w = [6.0, -6.0, 0.1, -0.1, 0.0];
        let (trits, _) = quantize_absmean(&w);
        assert_eq!(trits[0], Trit::Plus);
        assert_eq!(trits[1], Trit::Minus);
        assert_eq!(trits[2], Trit::Zero);
        assert_eq!(trits[3], Trit::Zero);
        assert_eq!(trits[4], Trit::Zero);
    }

    #[test]
    fn all_zero_tensor_is_safe() {
        let (trits, scale) = quantize_absmean(&[0.0, 0.0, 0.0]);
        assert_eq!(scale, 0.0);
        assert!(trits.iter().all(|&t| t == Trit::Zero));
    }

    #[test]
    fn empty_tensor() {
        let (trits, scale) = quantize_absmean(&[]);
        assert!(trits.is_empty());
        assert_eq!(scale, 0.0);
    }
}
