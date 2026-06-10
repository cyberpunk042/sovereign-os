//! `sovereign-rope` — rotary position embeddings (RoPE).
//!
//! Attention's dot product is position-blind: `q·k` is the same wherever the
//! two tokens sit. RoPE fixes that *before* the dot product by rotating each
//! adjacent pair `(x₂ᵢ, x₂ᵢ₊₁)` of a query/key vector by an angle
//! `pos · θᵢ`, where `θᵢ = base^(−2i/head_dim)` runs from fast (high-freq)
//! to slow (low-freq) across the pairs. Because a 2-D rotation is
//! orthogonal, this injects *absolute* position without changing any vector's
//! norm — and, crucially, the attention score between a query at position `m`
//! and a key at position `n` ends up depending only on the **relative**
//! offset `m − n`:
//!
//! ```text
//! ⟨R_m q, R_n k⟩ = ⟨q, R_{n−m} k⟩
//! ```
//!
//! That identity (a direct consequence of `R(mθ)ᵀ R(nθ) = R((n−m)θ)`) is the
//! whole point of RoPE, and it is pinned as a test here. This crate is the
//! position-encoding stage that feeds [`sovereign-attention`]: rotate the
//! queries and keys by their positions, then attend.
//!
//! [`sovereign-attention`]: https://docs.rs/sovereign-attention
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the RoPE surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The conventional RoPE frequency base (`θ` denominator).
pub const DEFAULT_THETA_BASE: f32 = 10_000.0;

/// Things that can go wrong applying RoPE.
#[derive(Debug, Error, PartialEq)]
pub enum RopeError {
    /// A vector's length did not match the configured head dimension.
    #[error("dimension mismatch: expected head_dim {expected}, got {got}")]
    DimMismatch {
        /// Configured head dimension.
        expected: usize,
        /// Observed vector length.
        got: usize,
    },
}

fn unit_scale() -> f32 {
    1.0
}

/// A RoPE configuration for one attention head.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Rope {
    /// Head dimension (must be even — RoPE rotates adjacent pairs).
    pub head_dim: usize,
    /// Frequency base `θ` (typically [`DEFAULT_THETA_BASE`]).
    pub theta_base: f32,
    /// Linear **position-interpolation** factor (Chen et al.): every position
    /// is multiplied by this before rotation, so `1.0` is standard RoPE and
    /// `< 1.0` compresses positions back into the trained range to extend
    /// context. Defaults to `1.0` for backward-compatible deserialization.
    #[serde(default = "unit_scale")]
    pub position_scale: f32,
}

/// The NTK-aware frequency base for extending context by `factor`× without
/// retraining (Peng et al. / "NTK-aware scaling"): scale the base so the
/// slowest-rotating pair gains the full `factor` of range while the fastest is
/// barely touched. Feed the result to [`Rope::with_base`].
///
/// # Panics
/// Panics if `head_dim < 2`, `head_dim` is odd, or `factor <= 0`.
pub fn ntk_aware_base(head_dim: usize, theta_base: f32, factor: f32) -> f32 {
    assert!(
        head_dim >= 2 && head_dim % 2 == 0,
        "head_dim must be even ≥ 2"
    );
    assert!(factor > 0.0, "factor must be > 0");
    let exponent = head_dim as f32 / (head_dim as f32 - 2.0);
    theta_base * factor.powf(exponent)
}

impl Rope {
    /// A RoPE head with the conventional base of 10000.
    ///
    /// # Panics
    /// Panics if `head_dim` is zero or odd — RoPE rotates pairs.
    pub fn new(head_dim: usize) -> Self {
        Self::with_base(head_dim, DEFAULT_THETA_BASE)
    }

    /// A RoPE head with an explicit frequency base.
    ///
    /// # Panics
    /// Panics if `head_dim` is zero or odd.
    pub fn with_base(head_dim: usize, theta_base: f32) -> Self {
        assert!(head_dim > 0, "head_dim must be > 0");
        assert!(
            head_dim % 2 == 0,
            "head_dim must be even (RoPE rotates pairs)"
        );
        assert!(theta_base > 0.0, "theta_base must be > 0");
        Self {
            head_dim,
            theta_base,
            position_scale: 1.0,
        }
    }

    /// A RoPE head with an explicit linear position-interpolation scale (and
    /// the conventional base). `position_scale = train_ctx / target_ctx`
    /// compresses an extended context back into the trained range.
    ///
    /// # Panics
    /// Panics if `head_dim` is zero/odd or `position_scale <= 0`.
    pub fn with_position_scale(head_dim: usize, position_scale: f32) -> Self {
        assert!(position_scale > 0.0, "position_scale must be > 0");
        let mut r = Self::new(head_dim);
        r.position_scale = position_scale;
        r
    }

    /// A RoPE head configured to extend context from `train_ctx` to
    /// `target_ctx` by linear position interpolation: positions are scaled by
    /// `train_ctx / target_ctx` so a sequence up to `target_ctx` stays within
    /// the rotation range the model saw at `train_ctx`.
    ///
    /// # Panics
    /// Panics if `head_dim` is zero/odd or either context is zero.
    pub fn for_context_extension(head_dim: usize, train_ctx: usize, target_ctx: usize) -> Self {
        assert!(train_ctx > 0 && target_ctx > 0, "contexts must be > 0");
        Self::with_position_scale(head_dim, train_ctx as f32 / target_ctx as f32)
    }

    /// Number of rotated pairs (`head_dim / 2`).
    pub fn pairs(&self) -> usize {
        self.head_dim / 2
    }

    /// Angular frequency `θᵢ` of pair `i` (0-based). Pair 0 is the fastest.
    ///
    /// # Panics
    /// Panics if `pair >= self.pairs()`.
    pub fn freq(&self, pair: usize) -> f32 {
        assert!(pair < self.pairs(), "pair out of range");
        let exponent = (2 * pair) as f32 / self.head_dim as f32;
        self.theta_base.powf(-exponent)
    }

    fn check(&self, v: &[f32]) -> Result<(), RopeError> {
        if v.len() != self.head_dim {
            return Err(RopeError::DimMismatch {
                expected: self.head_dim,
                got: v.len(),
            });
        }
        Ok(())
    }

    /// Rotate `v` in place by `pos`: pair `i` turns by `pos · θᵢ`.
    pub fn rotate_in_place(&self, v: &mut [f32], pos: usize) -> Result<(), RopeError> {
        self.check(v)?;
        for i in 0..self.pairs() {
            let angle = pos as f32 * self.position_scale * self.freq(i);
            let (sin, cos) = angle.sin_cos();
            let a = v[2 * i];
            let b = v[2 * i + 1];
            v[2 * i] = a * cos - b * sin;
            v[2 * i + 1] = a * sin + b * cos;
        }
        Ok(())
    }

    /// Rotate a copy of `v` by `pos`.
    pub fn rotate(&self, v: &[f32], pos: usize) -> Result<Vec<f32>, RopeError> {
        let mut out = v.to_vec();
        self.rotate_in_place(&mut out, pos)?;
        Ok(out)
    }

    /// Rotate a sequence of vectors, applying position `start_pos + i` to the
    /// `i`-th vector. Returns the rotated sequence.
    pub fn rotate_sequence(
        &self,
        seq: &[Vec<f32>],
        start_pos: usize,
    ) -> Result<Vec<Vec<f32>>, RopeError> {
        seq.iter()
            .enumerate()
            .map(|(i, v)| self.rotate(v, start_pos + i))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn norm(v: &[f32]) -> f32 {
        v.iter().map(|x| x * x).sum::<f32>().sqrt()
    }

    fn dot(a: &[f32], b: &[f32]) -> f32 {
        a.iter().zip(b).map(|(x, y)| x * y).sum()
    }

    fn approx(a: &[f32], b: &[f32], eps: f32) -> bool {
        a.len() == b.len() && a.iter().zip(b).all(|(x, y)| (x - y).abs() <= eps)
    }

    #[test]
    fn position_zero_is_identity() {
        let rope = Rope::new(8);
        let v = vec![1.0, -2.0, 0.5, 3.0, -1.0, 0.25, 4.0, -0.5];
        assert!(approx(&rope.rotate(&v, 0).unwrap(), &v, 1e-6));
    }

    #[test]
    fn default_position_scale_is_one() {
        assert_eq!(Rope::new(8).position_scale, 1.0);
        // Default-scaled rotation equals plain rotation.
        let v = vec![1.0, -2.0, 0.5, 3.0, -1.0, 0.25, 4.0, -0.5];
        let a = Rope::new(8).rotate(&v, 7).unwrap();
        let b = Rope::with_position_scale(8, 1.0).rotate(&v, 7).unwrap();
        assert!(approx(&a, &b, 1e-6));
    }

    #[test]
    fn position_interpolation_halves_the_angle() {
        // scale 0.5 at position 2k rotates by the same angle as standard RoPE
        // at position k — positions are linearly compressed.
        let v = vec![1.0, -2.0, 0.5, 3.0, -1.0, 0.25, 4.0, -0.5];
        let scaled = Rope::with_position_scale(8, 0.5);
        let plain = Rope::new(8);
        assert!(approx(
            &scaled.rotate(&v, 6).unwrap(),
            &plain.rotate(&v, 3).unwrap(),
            1e-5
        ));
    }

    #[test]
    fn context_extension_sets_the_ratio_and_stays_in_range() {
        // Extend 2048 → 8192 → scale 0.25; the last extended position rotates
        // by the same angle the model saw at its trained max.
        let rope = Rope::for_context_extension(8, 2048, 8192);
        assert!((rope.position_scale - 0.25).abs() < 1e-6);
        let v = vec![1.0, -2.0, 0.5, 3.0, -1.0, 0.25, 4.0, -0.5];
        let extended = rope.rotate(&v, 8192).unwrap();
        let trained = Rope::new(8).rotate(&v, 2048).unwrap();
        assert!(approx(&extended, &trained, 1e-3));
    }

    #[test]
    fn ntk_aware_base_grows_with_factor() {
        let base = ntk_aware_base(8, DEFAULT_THETA_BASE, 4.0);
        assert!(base > DEFAULT_THETA_BASE, "NTK base should grow");
        // factor 1 leaves the base unchanged.
        assert!((ntk_aware_base(8, DEFAULT_THETA_BASE, 1.0) - DEFAULT_THETA_BASE).abs() < 1e-3);
        // A larger base slows the rotation of every pair (extends range).
        let slow = Rope::with_base(8, base);
        let fast = Rope::new(8);
        assert!(slow.freq(1) < fast.freq(1));
    }

    #[test]
    fn position_scale_deserializes_with_default() {
        // Legacy JSON without position_scale → defaults to 1.0.
        let legacy = r#"{"head_dim":8,"theta_base":10000.0}"#;
        let rope: Rope = serde_json::from_str(legacy).unwrap();
        assert_eq!(rope.position_scale, 1.0);
        // Round-trip with the field present.
        let r2 = Rope::with_position_scale(8, 0.5);
        let j = serde_json::to_string(&r2).unwrap();
        assert_eq!(serde_json::from_str::<Rope>(&j).unwrap(), r2);
    }

    #[test]
    fn rotation_preserves_norm() {
        let rope = Rope::new(8);
        let v = vec![1.0, -2.0, 0.5, 3.0, -1.0, 0.25, 4.0, -0.5];
        let before = norm(&v);
        for pos in [1usize, 5, 17, 100, 4096] {
            let after = norm(&rope.rotate(&v, pos).unwrap());
            assert!(
                (before - after).abs() < 1e-4,
                "pos {pos}: {before} vs {after}"
            );
        }
    }

    #[test]
    fn known_single_pair_rotation() {
        // head_dim 2 → one pair, freq = base^0 = 1. Rotate [1,0] by pos 1:
        // angle = 1 rad → [cos 1, sin 1].
        let rope = Rope::with_base(2, 10_000.0);
        assert_eq!(rope.pairs(), 1);
        assert!((rope.freq(0) - 1.0).abs() < 1e-6);
        let out = rope.rotate(&[1.0, 0.0], 1).unwrap();
        assert!(approx(&out, &[1.0f32.cos(), 1.0f32.sin()], 1e-6));
    }

    #[test]
    fn rotations_compose_additively() {
        // R_m then R_n == R_{m+n}, because angles add.
        let rope = Rope::new(8);
        let v = vec![1.0, -2.0, 0.5, 3.0, -1.0, 0.25, 4.0, -0.5];
        let two_step = rope.rotate(&rope.rotate(&v, 3).unwrap(), 5).unwrap();
        let one_step = rope.rotate(&v, 8).unwrap();
        assert!(approx(&two_step, &one_step, 1e-4));
    }

    #[test]
    fn relative_position_invariant() {
        // The defining RoPE property: ⟨R_m q, R_n k⟩ = ⟨q, R_{n-m} k⟩, so the
        // score depends only on the offset n-m. Hold n-m fixed, slide m.
        let rope = Rope::new(16);
        let q: Vec<f32> = (0..16).map(|i| (i as f32 * 0.1).sin()).collect();
        let k: Vec<f32> = (0..16).map(|i| (i as f32 * 0.2).cos()).collect();

        let offset = 4usize;
        let baseline = dot(
            &rope.rotate(&q, offset).unwrap(),
            &rope.rotate(&k, 0).unwrap(),
        );
        for m in [1usize, 7, 20, 63] {
            let n = m + offset;
            let score = dot(&rope.rotate(&q, n).unwrap(), &rope.rotate(&k, m).unwrap());
            assert!(
                (score - baseline).abs() < 1e-3,
                "m={m}: score {score} vs baseline {baseline}"
            );
        }
    }

    #[test]
    fn different_offsets_give_different_scores() {
        // Sanity: the invariant isn't trivial — distinct offsets differ.
        let rope = Rope::new(16);
        let q: Vec<f32> = (0..16).map(|i| (i as f32 * 0.1).sin()).collect();
        let k = q.clone();
        let s0 = dot(&rope.rotate(&q, 0).unwrap(), &rope.rotate(&k, 0).unwrap());
        let s5 = dot(&rope.rotate(&q, 5).unwrap(), &rope.rotate(&k, 0).unwrap());
        assert!((s0 - s5).abs() > 1e-3, "offset 0 and 5 should differ");
    }

    #[test]
    fn freqs_descend_from_one() {
        let rope = Rope::new(8);
        // pair 0 is the fastest (freq 1.0), later pairs are slower.
        assert!((rope.freq(0) - 1.0).abs() < 1e-6);
        assert!(rope.freq(0) > rope.freq(1));
        assert!(rope.freq(1) > rope.freq(2));
        assert!(rope.freq(3) < 0.1); // base^(-6/8) for base 1e4 is small
    }

    #[test]
    fn rotate_sequence_applies_increasing_positions() {
        let rope = Rope::new(4);
        let seq = vec![vec![1.0, 0.0, 1.0, 0.0]; 3];
        let rotated = rope.rotate_sequence(&seq, 10).unwrap();
        // position 10, 11, 12 → equals individual rotates
        assert!(approx(
            &rotated[0],
            &rope.rotate(&seq[0], 10).unwrap(),
            1e-6
        ));
        assert!(approx(
            &rotated[1],
            &rope.rotate(&seq[1], 11).unwrap(),
            1e-6
        ));
        assert!(approx(
            &rotated[2],
            &rope.rotate(&seq[2], 12).unwrap(),
            1e-6
        ));
    }

    #[test]
    fn dim_mismatch_is_caught() {
        let rope = Rope::new(8);
        assert_eq!(
            rope.rotate(&[1.0, 2.0], 1).unwrap_err(),
            RopeError::DimMismatch {
                expected: 8,
                got: 2
            }
        );
    }

    #[test]
    #[should_panic(expected = "even")]
    fn odd_head_dim_panics() {
        let _ = Rope::new(7);
    }

    #[test]
    fn serde_round_trip() {
        let rope = Rope::with_base(64, 500_000.0);
        let j = serde_json::to_string(&rope).unwrap();
        let back: Rope = serde_json::from_str(&j).unwrap();
        assert_eq!(rope, back);
    }
}
