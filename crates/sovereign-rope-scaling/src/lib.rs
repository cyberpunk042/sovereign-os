//! `sovereign-rope-scaling` — run a rotary model past its trained context.
//!
//! Rotary position embeddings rotate each query/key pair by `pos · θᵢ`, with
//! `θᵢ = base^(−2i/d)`. A model trained to context length `L` has never seen
//! positions beyond `L`, so feeding it longer sequences extrapolates the rotations
//! into territory it cannot interpret — quality collapses. The fix is to *scale*
//! the position encoding so length `s·L` maps back into the trained range. This
//! crate implements the three standard methods.
//!
//! - **Linear position interpolation** (Chen et al.): divide every position by the
//!   scale factor `s`, compressing `s·L` positions into `[0, L)`. Simple and
//!   robust, but squeezes the high-frequency dimensions that encode local order.
//! - **NTK-aware scaling** (bloc97): instead of scaling positions, raise the
//!   frequency `base` by `s^(d/(d−2))`, which stretches the *low* frequencies
//!   (long-range) while barely touching the high ones — preserving local
//!   resolution. No position rescale needed.
//! - **Dynamic NTK**: apply NTK scaling only once the current sequence exceeds the
//!   original context, and scale by exactly how far past it you are — so short
//!   sequences are untouched and long ones get just enough stretch.
//!
//! [`ScalingMethod`] selects the method; [`effective_position`] gives the position
//! to feed the rotation, and [`inverse_frequencies`] the per-pair `θᵢ` to use.
//! [`effective_max_context`] reports how far the method extends the window.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the rope-scaling surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The conventional RoPE frequency base.
pub const DEFAULT_THETA_BASE: f64 = 10_000.0;

/// A context-scaling method.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum ScalingMethod {
    /// No scaling (the model's native behavior).
    None,
    /// Linear position interpolation by `factor` (`> 1` extends the window).
    Linear {
        /// The scale factor `s`.
        factor: f64,
    },
    /// NTK-aware base scaling by `factor`.
    Ntk {
        /// The scale factor `s`.
        factor: f64,
    },
    /// Dynamic NTK: scale only when `current_len > original_max`, by the ratio.
    DynamicNtk {
        /// The model's original trained context length.
        original_max: usize,
        /// The current sequence length.
        current_len: usize,
    },
}

impl ScalingMethod {
    /// The effective scale factor this method is currently applying (`1.0` = none).
    pub fn factor(&self) -> f64 {
        match *self {
            ScalingMethod::None => 1.0,
            ScalingMethod::Linear { factor } | ScalingMethod::Ntk { factor } => factor.max(1.0),
            ScalingMethod::DynamicNtk {
                original_max,
                current_len,
            } => {
                if original_max == 0 || current_len <= original_max {
                    1.0
                } else {
                    current_len as f64 / original_max as f64
                }
            }
        }
    }
}

/// The position to feed the rotary rotation for raw `position` under `method`.
/// Linear interpolation divides the position; the NTK methods leave it unchanged
/// (they scale the frequencies instead).
pub fn effective_position(position: usize, method: ScalingMethod) -> f64 {
    match method {
        ScalingMethod::Linear { factor } => position as f64 / factor.max(1.0),
        _ => position as f64,
    }
}

/// The NTK-scaled frequency base for `method` given `head_dim` (the NTK methods
/// raise the base; the others return `base` unchanged).
pub fn scaled_base(base: f64, head_dim: usize, method: ScalingMethod) -> f64 {
    let s = match method {
        ScalingMethod::Ntk { .. } | ScalingMethod::DynamicNtk { .. } => method.factor(),
        _ => 1.0,
    };
    if s <= 1.0 || head_dim <= 2 {
        return base;
    }
    // NTK-aware: base' = base * s^(d/(d-2))
    let d = head_dim as f64;
    base * s.powf(d / (d - 2.0))
}

/// The per-pair inverse frequencies `θᵢ = base'^(−2i/d)` under `method`. The
/// returned vector has `head_dim / 2` entries, pair 0 fastest.
///
/// # Panics
/// Panics if `head_dim` is zero or odd.
pub fn inverse_frequencies(head_dim: usize, base: f64, method: ScalingMethod) -> Vec<f64> {
    assert!(
        head_dim > 0 && head_dim % 2 == 0,
        "head_dim must be positive and even"
    );
    let b = scaled_base(base, head_dim, method);
    let d = head_dim as f64;
    (0..head_dim / 2)
        .map(|i| b.powf(-2.0 * i as f64 / d))
        .collect()
}

/// How far the method extends the usable context from `original_max`.
pub fn effective_max_context(original_max: usize, method: ScalingMethod) -> usize {
    (original_max as f64 * method.factor()).round() as usize
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn none_is_identity() {
        assert!(approx(effective_position(100, ScalingMethod::None), 100.0));
        let f = inverse_frequencies(8, DEFAULT_THETA_BASE, ScalingMethod::None);
        // pair 0 = base^0 = 1
        assert!(approx(f[0], 1.0));
        assert_eq!(effective_max_context(2048, ScalingMethod::None), 2048);
    }

    #[test]
    fn linear_compresses_positions() {
        let m = ScalingMethod::Linear { factor: 4.0 };
        assert!(approx(effective_position(400, m), 100.0));
        // linear does NOT change the base/frequencies
        let f_none = inverse_frequencies(8, DEFAULT_THETA_BASE, ScalingMethod::None);
        let f_lin = inverse_frequencies(8, DEFAULT_THETA_BASE, m);
        assert_eq!(f_none, f_lin);
        // and it quadruples the usable context
        assert_eq!(effective_max_context(2048, m), 8192);
    }

    #[test]
    fn ntk_raises_the_base_and_keeps_positions() {
        let m = ScalingMethod::Ntk { factor: 4.0 };
        // NTK leaves positions alone
        assert!(approx(effective_position(400, m), 400.0));
        // base is raised
        let b = scaled_base(DEFAULT_THETA_BASE, 128, m);
        assert!(b > DEFAULT_THETA_BASE, "ntk base {b}");
        // high-frequency pair 0 stays ~1 (local resolution preserved)
        let f = inverse_frequencies(128, DEFAULT_THETA_BASE, m);
        assert!(approx(f[0], 1.0));
        // but the slowest pair is lower than unscaled (long-range stretched)
        let f_none = inverse_frequencies(128, DEFAULT_THETA_BASE, ScalingMethod::None);
        let last = f.len() - 1;
        assert!(f[last] < f_none[last], "ntk should lower slow freqs");
    }

    #[test]
    fn ntk_base_formula() {
        // base' = base * s^(d/(d-2))
        let s = 2.0f64;
        let d = 64.0f64;
        let expected = DEFAULT_THETA_BASE * s.powf(d / (d - 2.0));
        let got = scaled_base(DEFAULT_THETA_BASE, 64, ScalingMethod::Ntk { factor: s });
        assert!(approx(got, expected), "got {got} expected {expected}");
    }

    #[test]
    fn dynamic_ntk_inactive_below_original() {
        let m = ScalingMethod::DynamicNtk {
            original_max: 4096,
            current_len: 2000,
        };
        // short sequence → no scaling
        assert!(approx(m.factor(), 1.0));
        assert!(approx(
            scaled_base(DEFAULT_THETA_BASE, 128, m),
            DEFAULT_THETA_BASE
        ));
    }

    #[test]
    fn dynamic_ntk_active_above_original() {
        let m = ScalingMethod::DynamicNtk {
            original_max: 4096,
            current_len: 8192,
        };
        assert!(approx(m.factor(), 2.0));
        assert!(scaled_base(DEFAULT_THETA_BASE, 128, m) > DEFAULT_THETA_BASE);
    }

    #[test]
    fn frequencies_are_monotonic_decreasing() {
        for method in [
            ScalingMethod::None,
            ScalingMethod::Linear { factor: 2.0 },
            ScalingMethod::Ntk { factor: 8.0 },
        ] {
            let f = inverse_frequencies(64, DEFAULT_THETA_BASE, method);
            assert!(
                f.windows(2).all(|w| w[0] >= w[1]),
                "not monotonic: {method:?}"
            );
        }
    }

    #[test]
    fn factor_below_one_is_clamped() {
        // a factor < 1 (would shrink context) is clamped to no-op
        let m = ScalingMethod::Linear { factor: 0.5 };
        assert!(approx(effective_position(100, m), 100.0));
        assert!(approx(m.factor(), 1.0));
    }

    #[test]
    fn serde_round_trip() {
        let m = ScalingMethod::DynamicNtk {
            original_max: 4096,
            current_len: 16384,
        };
        let j = serde_json::to_string(&m).unwrap();
        let back: ScalingMethod = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
