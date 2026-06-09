//! `sovereign-significance` — is A *really* better than B, or just noise?
//!
//! A single evaluation number ("system A scored 0.71, B scored 0.69") says
//! nothing about whether the gap would survive a different test set. This crate
//! adds the statistical backing.
//!
//! **Bootstrap confidence interval** ([`bootstrap_ci`]) resamples the per-example
//! scores with replacement many times and reports the percentile interval of the
//! mean — a distribution-free way to say "the metric is 0.71 ± …" without
//! assuming normality.
//!
//! **Paired bootstrap test** ([`paired_bootstrap_pvalue`]) is the right tool when
//! both systems were measured on the *same* examples: it resamples the per-example
//! *differences* and reports the fraction of resamples in which B is at least as
//! good as A — a one-sided p-value for "A beats B". Pairing cancels per-example
//! difficulty, so it detects smaller true differences than comparing two
//! independent means.
//!
//! **McNemar's test** ([`mcnemar`]) compares two classifiers by their *discordant*
//! pairs — cases one got right and the other wrong — which is exactly the evidence
//! that distinguishes them; it returns the chi-square statistic with continuity
//! correction.
//!
//! Randomness is a seeded **splitmix64** generator, so every result is
//! reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the significance surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A bootstrap confidence interval for a mean.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ConfidenceInterval {
    /// The point estimate (mean of the original sample).
    pub estimate: f64,
    /// Lower percentile bound.
    pub lower: f64,
    /// Upper percentile bound.
    pub upper: f64,
    /// The confidence level used (e.g. 0.95).
    pub level: f64,
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }
}

fn mean(xs: &[f64]) -> f64 {
    if xs.is_empty() {
        0.0
    } else {
        xs.iter().sum::<f64>() / xs.len() as f64
    }
}

/// Percentile bootstrap confidence interval for the mean of `samples` at the
/// given `confidence` level (e.g. 0.95), using `iters` resamples seeded by `seed`.
///
/// # Panics
/// Panics if `samples` is empty, `iters == 0`, or `confidence` is not in `(0, 1)`.
pub fn bootstrap_ci(
    samples: &[f64],
    confidence: f64,
    iters: usize,
    seed: u64,
) -> ConfidenceInterval {
    assert!(!samples.is_empty(), "need at least one sample");
    assert!(iters > 0, "need at least one iteration");
    assert!(confidence > 0.0 && confidence < 1.0, "confidence in (0,1)");

    let mut rng = Rng(seed | 1);
    let n = samples.len();
    let mut means: Vec<f64> = Vec::with_capacity(iters);
    for _ in 0..iters {
        let mut acc = 0.0;
        for _ in 0..n {
            acc += samples[rng.below(n)];
        }
        means.push(acc / n as f64);
    }
    means.sort_by(|a, b| a.total_cmp(b));
    let alpha = 1.0 - confidence;
    let lo_idx = ((alpha / 2.0) * iters as f64).floor() as usize;
    let hi_idx = (((1.0 - alpha / 2.0) * iters as f64).ceil() as usize)
        .min(iters)
        .saturating_sub(1);
    ConfidenceInterval {
        estimate: mean(samples),
        lower: means[lo_idx.min(iters - 1)],
        upper: means[hi_idx],
        level: confidence,
    }
}

/// One-sided paired bootstrap p-value for the hypothesis that `a` scores higher
/// than `b` on the same examples (`a[i]` and `b[i]` are the two systems' scores on
/// example `i`). Returns the fraction of resamples in which the mean difference
/// `a − b` is `<= 0` — small means strong evidence that A really beats B.
///
/// # Panics
/// Panics if the slices differ in length, are empty, or `iters == 0`.
pub fn paired_bootstrap_pvalue(a: &[f64], b: &[f64], iters: usize, seed: u64) -> f64 {
    assert_eq!(a.len(), b.len(), "paired inputs must match in length");
    assert!(!a.is_empty(), "need at least one pair");
    assert!(iters > 0, "need at least one iteration");

    let diffs: Vec<f64> = a.iter().zip(b.iter()).map(|(&x, &y)| x - y).collect();
    let observed = mean(&diffs);
    if observed <= 0.0 {
        // A is not ahead on the full sample → no evidence it beats B.
        return 1.0;
    }
    let mut rng = Rng(seed | 1);
    let n = diffs.len();
    let mut not_better = 0usize;
    for _ in 0..iters {
        let mut acc = 0.0;
        for _ in 0..n {
            acc += diffs[rng.below(n)];
        }
        if acc / n as f64 <= 0.0 {
            not_better += 1;
        }
    }
    not_better as f64 / iters as f64
}

/// McNemar's chi-square statistic (with Edwards' continuity correction) for two
/// classifiers compared on the same examples. `b` is the number of examples the
/// first classifier got right and the second wrong; `c` the reverse. Larger means
/// the two differ more significantly; `0` when `b == c`. (The concordant counts
/// are irrelevant and not needed.)
///
/// The statistic is `(|b − c| − 1)² / (b + c)`, compared against a chi-square
/// distribution with 1 degree of freedom (≈ 3.84 at p = 0.05).
pub fn mcnemar(b: u64, c: u64) -> f64 {
    if b + c == 0 {
        return 0.0;
    }
    let diff = (b as f64 - c as f64).abs();
    let corrected = (diff - 1.0).max(0.0);
    corrected * corrected / (b + c) as f64
}

/// Whether a McNemar statistic is significant at p ≈ 0.05 (χ² with 1 df > 3.841).
pub fn mcnemar_significant_05(statistic: f64) -> bool {
    statistic > 3.841
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64, tol: f64) -> bool {
        (a - b).abs() < tol
    }

    #[test]
    fn ci_brackets_the_mean() {
        let samples: Vec<f64> = (0..200).map(|i| (i % 10) as f64).collect(); // mean 4.5
        let ci = bootstrap_ci(&samples, 0.95, 2000, 42);
        assert!(approx(ci.estimate, 4.5, 1e-9));
        assert!(ci.lower < ci.estimate && ci.estimate < ci.upper);
        // a large tight sample → reasonably narrow interval
        assert!(ci.upper - ci.lower < 1.5, "width {}", ci.upper - ci.lower);
    }

    #[test]
    fn ci_widens_with_variance() {
        let tight: Vec<f64> = vec![5.0; 100];
        let wide: Vec<f64> = (0..100)
            .map(|i| if i % 2 == 0 { 0.0 } else { 10.0 })
            .collect();
        let ct = bootstrap_ci(&tight, 0.95, 1000, 1);
        let cw = bootstrap_ci(&wide, 0.95, 1000, 1);
        // identical values → zero-width interval
        assert!(approx(ct.upper - ct.lower, 0.0, 1e-9));
        assert!(cw.upper - cw.lower > 1.0);
    }

    #[test]
    fn paired_test_detects_consistent_improvement() {
        // A beats B by a small but consistent margin on every example.
        let a: Vec<f64> = (0..100).map(|i| 0.7 + (i % 5) as f64 * 0.01).collect();
        let b: Vec<f64> = a.iter().map(|&x| x - 0.05).collect();
        let p = paired_bootstrap_pvalue(&a, &b, 2000, 7);
        assert!(
            p < 0.01,
            "consistent improvement should be significant, p={p}"
        );
    }

    #[test]
    fn paired_test_no_evidence_when_equal() {
        let a: Vec<f64> = (0..100).map(|i| (i % 7) as f64).collect();
        let b = a.clone();
        let p = paired_bootstrap_pvalue(&a, &b, 1000, 3);
        assert!(approx(p, 1.0, 1e-9), "equal systems → p=1, got {p}");
    }

    #[test]
    fn paired_test_high_p_for_noisy_tiny_difference() {
        // A is barely ahead on average but noisy → not significant
        let a: Vec<f64> = (0..50)
            .map(|i| if i % 2 == 0 { 1.0 } else { 0.0 })
            .collect();
        let b: Vec<f64> = (0..50)
            .map(|i| if i % 2 == 0 { 0.0 } else { 1.0 })
            .collect();
        // means equal here → p = 1
        let p = paired_bootstrap_pvalue(&a, &b, 1000, 5);
        assert!(p > 0.5, "p={p}");
    }

    #[test]
    fn mcnemar_basic() {
        // strongly discordant: 30 vs 5 → significant
        let stat = mcnemar(30, 5);
        assert!(mcnemar_significant_05(stat), "stat {stat}");
        // balanced discordance → not significant
        assert!(!mcnemar_significant_05(mcnemar(10, 10)));
        assert_eq!(mcnemar(0, 0), 0.0);
    }

    #[test]
    fn mcnemar_matches_formula() {
        // (|25-10|-1)^2 / 35 = 14^2/35 = 196/35 = 5.6
        let stat = mcnemar(25, 10);
        assert!(approx(stat, 196.0 / 35.0, 1e-9), "stat {stat}");
    }

    #[test]
    fn deterministic_for_seed() {
        let s: Vec<f64> = (0..50).map(|i| i as f64).collect();
        let a = bootstrap_ci(&s, 0.9, 500, 123);
        let b = bootstrap_ci(&s, 0.9, 500, 123);
        assert_eq!((a.lower, a.upper), (b.lower, b.upper));
    }
}
