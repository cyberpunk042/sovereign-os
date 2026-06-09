//! `sovereign-gumbel` — sample categories straight from logits via Gumbel noise.
//!
//! A language model emits unnormalised scores (logits); sampling the next token
//! usually means exponentiating them into a softmax distribution and drawing from
//! its cumulative sum. The **Gumbel-max trick** skips the normalization entirely:
//! add one i.i.d. sample of the Gumbel distribution to each logit and take the
//! `argmax`. The index that wins is distributed *exactly* as `softmax(logits)` —
//! a clean, branch-free way to sample from logits, and the basis of the
//! "reparameterization" used in differentiable sampling.
//!
//! The same perturbed scores give more for free. Taking the **top-k** of
//! `logit_i + gumbel_i` instead of just the max draws `k` *distinct* categories
//! **without replacement**, each with the correct marginal — the Gumbel-top-k
//! trick (Vieira; Kool et al.) — which is how you get diverse parallel samples or
//! a sampled-without-replacement beam.
//!
//! A Gumbel sample is `−ln(−ln(u))` for `u` uniform in `(0, 1)`; randomness comes
//! from a seeded **splitmix64** generator, so a given seed and logit vector always
//! yield the same draw. Logits may be any finite values; `−∞` is treated as a
//! forbidden category that can never be chosen.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the gumbel surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A seeded Gumbel sampler over logits.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GumbelSampler {
    rng: u64,
}

impl GumbelSampler {
    /// A sampler seeded with `seed`.
    pub fn new(seed: u64) -> Self {
        Self { rng: seed }
    }

    /// splitmix64 next value.
    fn next_u64(&mut self) -> u64 {
        self.rng = self.rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.rng;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// A uniform `f64` in the open interval `(0, 1)`.
    fn next_open_unit(&mut self) -> f64 {
        // 53-bit mantissa in [0, 1); nudge into (0, 1) so the logs are finite.
        let bits = self.next_u64() >> 11;
        (bits as f64 + 0.5) / (1u64 << 53) as f64
    }

    /// One sample of the standard Gumbel distribution: `−ln(−ln(u))`.
    pub fn gumbel(&mut self) -> f64 {
        let u = self.next_open_unit();
        -(-(u.ln())).ln()
    }

    /// Draw one category from `logits`, distributed as `softmax(logits)`.
    /// `−∞` logits are never selected. Returns `None` if `logits` is empty or
    /// every logit is `−∞`.
    pub fn sample(&mut self, logits: &[f64]) -> Option<usize> {
        let mut best = None;
        let mut best_score = f64::NEG_INFINITY;
        for (i, &l) in logits.iter().enumerate() {
            if l == f64::NEG_INFINITY {
                // perturbing -inf keeps it -inf: forbidden category.
                let _ = self.gumbel(); // still consume randomness for determinism
                continue;
            }
            let score = l + self.gumbel();
            if score > best_score {
                best_score = score;
                best = Some(i);
            }
        }
        best
    }

    /// Draw up to `k` *distinct* categories from `logits` without replacement,
    /// via the Gumbel-top-k trick: the indices of the `k` largest perturbed
    /// scores, returned best-first. Fewer than `k` are returned only if fewer
    /// than `k` categories have finite logits.
    pub fn sample_k(&mut self, logits: &[f64], k: usize) -> Vec<usize> {
        let mut perturbed: Vec<(usize, f64)> = Vec::with_capacity(logits.len());
        for (i, &l) in logits.iter().enumerate() {
            if l == f64::NEG_INFINITY {
                let _ = self.gumbel();
                continue;
            }
            perturbed.push((i, l + self.gumbel()));
        }
        // sort by perturbed score descending (ties by index for determinism)
        perturbed.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
        perturbed.truncate(k);
        perturbed.into_iter().map(|(i, _)| i).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn softmax(logits: &[f64]) -> Vec<f64> {
        let max = logits.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let exps: Vec<f64> = logits
            .iter()
            .map(|&l| {
                if l == f64::NEG_INFINITY {
                    0.0
                } else {
                    (l - max).exp()
                }
            })
            .collect();
        let sum: f64 = exps.iter().sum();
        exps.iter().map(|&e| e / sum).collect()
    }

    #[test]
    fn empirical_distribution_matches_softmax() {
        let logits = [2.0, 1.0, 0.0, -1.0];
        let probs = softmax(&logits);
        let mut g = GumbelSampler::new(0xC0FFEE);
        let trials = 200_000;
        let mut counts = [0usize; 4];
        for _ in 0..trials {
            counts[g.sample(&logits).unwrap()] += 1;
        }
        for i in 0..4 {
            let freq = counts[i] as f64 / trials as f64;
            assert!(
                (freq - probs[i]).abs() < 0.01,
                "cat {i}: freq {freq} vs softmax {}",
                probs[i]
            );
        }
    }

    #[test]
    fn argmax_dominates_with_a_sharp_logit() {
        // a logit far above the rest should be sampled almost always
        let logits = [10.0, 0.0, 0.0];
        let mut g = GumbelSampler::new(7);
        let mut hits = 0;
        for _ in 0..10_000 {
            if g.sample(&logits) == Some(0) {
                hits += 1;
            }
        }
        assert!(hits > 9_900, "sharp logit chosen {hits}/10000");
    }

    #[test]
    fn forbidden_logits_are_never_chosen() {
        let logits = [0.0, f64::NEG_INFINITY, 0.0, f64::NEG_INFINITY];
        let mut g = GumbelSampler::new(123);
        for _ in 0..10_000 {
            let s = g.sample(&logits).unwrap();
            assert!(s == 0 || s == 2, "chose forbidden {s}");
        }
    }

    #[test]
    fn sample_k_returns_distinct_indices() {
        let logits = [1.0, 2.0, 3.0, 4.0, 5.0];
        let mut g = GumbelSampler::new(42);
        let picks = g.sample_k(&logits, 3);
        assert_eq!(picks.len(), 3);
        let mut sorted = picks.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(sorted.len(), 3, "indices must be distinct: {picks:?}");
    }

    #[test]
    fn sample_k_skips_forbidden_and_caps_at_available() {
        let logits = [0.0, f64::NEG_INFINITY, 1.0]; // only 2 finite categories
        let mut g = GumbelSampler::new(9);
        let picks = g.sample_k(&logits, 5);
        assert_eq!(picks.len(), 2);
        assert!(!picks.contains(&1));
    }

    #[test]
    fn sample_k_favors_high_logits_on_average() {
        // over many runs the top logit should appear in the top-1 most often
        let logits = [5.0, 3.0, 1.0, 0.0];
        let mut top1_is_best = 0;
        for seed in 0..2000u64 {
            let mut g = GumbelSampler::new(seed.wrapping_mul(0x9E37_79B9) + 1);
            if g.sample_k(&logits, 1) == vec![0] {
                top1_is_best += 1;
            }
        }
        // softmax([5,3,1,0])[0] ≈ 0.84
        let freq = top1_is_best as f64 / 2000.0;
        assert!(freq > 0.78, "top-1 picked best {freq}");
    }

    #[test]
    fn deterministic_for_a_seed() {
        let logits = [0.5, 1.5, 2.5, 0.1];
        let mut a = GumbelSampler::new(2024);
        let mut b = GumbelSampler::new(2024);
        let sa: Vec<usize> = (0..50).map(|_| a.sample(&logits).unwrap()).collect();
        let sb: Vec<usize> = (0..50).map(|_| b.sample(&logits).unwrap()).collect();
        assert_eq!(sa, sb);
    }

    #[test]
    fn empty_or_all_forbidden_is_none() {
        let mut g = GumbelSampler::new(1);
        assert_eq!(g.sample(&[]), None);
        assert_eq!(g.sample(&[f64::NEG_INFINITY, f64::NEG_INFINITY]), None);
        assert!(g.sample_k(&[], 3).is_empty());
    }

    #[test]
    fn serde_round_trip() {
        let g = GumbelSampler::new(99);
        let j = serde_json::to_string(&g).unwrap();
        let back: GumbelSampler = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
