//! `sovereign-alias-sampler` — O(1) categorical sampling via the alias method.
//!
//! Drawing a category from fixed weights `[w_0, …, w_{n-1}]` by walking the
//! cumulative distribution costs `O(n)` per sample. When you draw from the *same*
//! distribution many times — Monte-Carlo self-consistency, sampling sequences
//! from a statistical model, bootstrap resampling — the **Walker-Vose alias
//! method** is far better: an `O(n)` preprocessing step builds two tables, after
//! which every sample is `O(1)`.
//!
//! The idea is to chop the distribution into `n` equal-probability "columns",
//! each holding at most two categories: a primary and an *alias*. Scale each
//! probability by `n`; categories with scaled mass below 1 are "small", those
//! above are "large". Repeatedly pair a small column `s` with a large one `l`:
//! `s` keeps its own mass and donates the rest of its column to `l`, whose mass
//! is reduced accordingly and re-classified. To sample, pick a column uniformly,
//! then flip a biased coin: with probability `prob[col]` take the column's
//! primary category, otherwise its alias.
//!
//! Randomness is a seeded **splitmix64** generator, so a given seed and weight
//! vector always produce the same draw sequence — reproducible for replay and
//! testing. A stateless [`AliasTable::sample_with`] is also exposed so callers
//! can supply their own randomness.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the alias-sampler surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors building an alias table.
#[derive(Debug, Clone, PartialEq, Error)]
pub enum AliasError {
    /// No weights were given.
    #[error("weights must be non-empty")]
    Empty,
    /// A weight was negative, NaN, or infinite.
    #[error("weight at index {index} is not a finite non-negative number: {value}")]
    BadWeight {
        /// Offending index.
        index: usize,
        /// Offending value.
        value: f64,
    },
    /// All weights were zero, so there is no distribution to sample.
    #[error("weights sum to zero")]
    ZeroSum,
}

/// A precomputed alias table over `n` categories.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AliasTable {
    /// `prob[i]` is the probability of taking category `i` (vs its alias) when
    /// column `i` is selected.
    prob: Vec<f64>,
    /// `alias[i]` is the fallback category for column `i`.
    alias: Vec<usize>,
    /// The original normalized probabilities, kept for inspection/validation.
    weights: Vec<f64>,
    rng: u64,
}

impl AliasTable {
    /// Build the table from non-negative weights, seeded with `seed`.
    pub fn from_weights(weights: &[f64], seed: u64) -> Result<Self, AliasError> {
        if weights.is_empty() {
            return Err(AliasError::Empty);
        }
        let mut sum = 0.0;
        for (i, &w) in weights.iter().enumerate() {
            if !w.is_finite() || w < 0.0 {
                return Err(AliasError::BadWeight { index: i, value: w });
            }
            sum += w;
        }
        if sum == 0.0 {
            return Err(AliasError::ZeroSum);
        }

        let n = weights.len();
        let normalized: Vec<f64> = weights.iter().map(|&w| w / sum).collect();
        // scaled[i] = p_i * n; mean is 1.
        let mut scaled: Vec<f64> = normalized.iter().map(|&p| p * n as f64).collect();

        let mut prob = vec![0.0f64; n];
        let mut alias = vec![0usize; n];

        let mut small: Vec<usize> = Vec::new();
        let mut large: Vec<usize> = Vec::new();
        for (i, &s) in scaled.iter().enumerate() {
            if s < 1.0 {
                small.push(i);
            } else {
                large.push(i);
            }
        }

        // NB: pop inside the loop, not in the condition — evaluating
        // `(small.pop(), large.pop())` in a `while let` would pop from BOTH even
        // when one is empty, silently discarding an element.
        while !small.is_empty() && !large.is_empty() {
            let s = small.pop().unwrap();
            let l = large.pop().unwrap();
            prob[s] = scaled[s];
            alias[s] = l;
            // l absorbs the remaining mass of column s.
            scaled[l] = (scaled[l] + scaled[s]) - 1.0;
            if scaled[l] < 1.0 {
                small.push(l);
            } else {
                large.push(l);
            }
        }
        // Leftovers (from floating-point drift) are certain outcomes.
        for i in large.into_iter().chain(small.into_iter()) {
            prob[i] = 1.0;
            alias[i] = i;
        }

        Ok(Self {
            prob,
            alias,
            weights: normalized,
            rng: seed,
        })
    }

    /// The number of categories.
    pub fn len(&self) -> usize {
        self.prob.len()
    }

    /// Whether the table has no categories (never true after a successful build).
    pub fn is_empty(&self) -> bool {
        self.prob.is_empty()
    }

    /// The normalized probability of category `i` (the distribution being
    /// sampled).
    pub fn probability(&self, i: usize) -> f64 {
        self.weights[i]
    }

    /// splitmix64 next value.
    fn next_u64(&mut self) -> u64 {
        self.rng = self.rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.rng;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Draw one category in `O(1)` using the internal RNG.
    pub fn sample(&mut self) -> usize {
        let n = self.len();
        let col = (self.next_u64() % n as u64) as usize;
        // uniform in [0, 1)
        let u = (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64;
        if u < self.prob[col] {
            col
        } else {
            self.alias[col]
        }
    }

    /// Draw `k` categories.
    pub fn sample_n(&mut self, k: usize) -> Vec<usize> {
        (0..k).map(|_| self.sample()).collect()
    }

    /// Stateless draw: pick a category from an externally chosen column index and
    /// a uniform `u ∈ [0, 1)`. Lets callers drive sampling with their own RNG.
    ///
    /// # Panics
    /// Panics if `col >= len()`.
    pub fn sample_with(&self, col: usize, u: f64) -> usize {
        assert!(col < self.len(), "column out of range");
        if u < self.prob[col] {
            col
        } else {
            self.alias[col]
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_bad_input() {
        assert_eq!(AliasTable::from_weights(&[], 1), Err(AliasError::Empty));
        assert_eq!(
            AliasTable::from_weights(&[0.0, 0.0], 1),
            Err(AliasError::ZeroSum)
        );
        assert!(matches!(
            AliasTable::from_weights(&[1.0, -2.0], 1),
            Err(AliasError::BadWeight { index: 1, .. })
        ));
        assert!(matches!(
            AliasTable::from_weights(&[1.0, f64::NAN], 1),
            Err(AliasError::BadWeight { index: 1, .. })
        ));
    }

    #[test]
    fn probabilities_are_normalized() {
        let t = AliasTable::from_weights(&[1.0, 3.0], 1).unwrap();
        assert!((t.probability(0) - 0.25).abs() < 1e-12);
        assert!((t.probability(1) - 0.75).abs() < 1e-12);
    }

    #[test]
    fn empirical_frequencies_match_weights() {
        let weights = [1.0, 2.0, 3.0, 4.0]; // probs .1 .2 .3 .4
        let mut t = AliasTable::from_weights(&weights, 0xABCDEF).unwrap();
        let n = 200_000;
        let mut counts = [0usize; 4];
        for _ in 0..n {
            counts[t.sample()] += 1;
        }
        let expected = [0.1, 0.2, 0.3, 0.4];
        for i in 0..4 {
            let freq = counts[i] as f64 / n as f64;
            assert!(
                (freq - expected[i]).abs() < 0.01,
                "cat {i}: freq {freq} vs {}",
                expected[i]
            );
        }
    }

    #[test]
    fn single_category_always_returns_zero() {
        let mut t = AliasTable::from_weights(&[5.0], 7).unwrap();
        for _ in 0..100 {
            assert_eq!(t.sample(), 0);
        }
    }

    #[test]
    fn zero_weight_category_is_never_drawn() {
        // category 1 has zero weight → must never be sampled
        let mut t = AliasTable::from_weights(&[3.0, 0.0, 2.0], 99).unwrap();
        for _ in 0..10_000 {
            assert_ne!(t.sample(), 1);
        }
    }

    #[test]
    fn deterministic_for_a_seed() {
        let mut a = AliasTable::from_weights(&[1.0, 1.0, 1.0], 42).unwrap();
        let mut b = AliasTable::from_weights(&[1.0, 1.0, 1.0], 42).unwrap();
        assert_eq!(a.sample_n(50), b.sample_n(50));
    }

    #[test]
    fn sample_with_is_consistent() {
        let t = AliasTable::from_weights(&[1.0, 1.0], 1).unwrap();
        // u below prob[col] keeps the column; u above takes the alias.
        for col in 0..t.len() {
            let keep = t.sample_with(col, 0.0);
            assert_eq!(keep, col);
            // a u of 1.0 (>= any prob) yields the alias (which may equal col)
            let aliased = t.sample_with(col, 1.0 - 1e-12);
            assert!(aliased == col || aliased == t.alias[col]);
        }
    }

    #[test]
    fn uniform_distribution_is_balanced() {
        let mut t = AliasTable::from_weights(&[1.0; 6], 123).unwrap();
        let n = 120_000;
        let mut counts = [0usize; 6];
        for _ in 0..n {
            counts[t.sample()] += 1;
        }
        for c in counts {
            let freq = c as f64 / n as f64;
            assert!((freq - 1.0 / 6.0).abs() < 0.01, "freq {freq}");
        }
    }

    #[test]
    fn serde_round_trip() {
        let t = AliasTable::from_weights(&[2.0, 5.0, 1.0], 8).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: AliasTable = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
