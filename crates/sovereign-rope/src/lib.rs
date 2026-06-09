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

/// A RoPE configuration for one attention head.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Rope {
    /// Head dimension (must be even — RoPE rotates adjacent pairs).
    pub head_dim: usize,
    /// Frequency base `θ` (typically [`DEFAULT_THETA_BASE`]).
    pub theta_base: f32,
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
        }
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
            let angle = pos as f32 * self.freq(i);
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
