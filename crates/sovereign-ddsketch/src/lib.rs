//! `sovereign-ddsketch` — quantiles with a guaranteed relative error.
//!
//! Tail latency is a distribution problem: a p99 of two seconds is the number that
//! breaks an SLO, and you need it accurate from a stream too large to store. A
//! fixed-bucket [histogram][crate] spends its resolution evenly and is coarse in
//! the tail; [P-squared][crate] tracks a handful of preset quantiles and cannot be
//! merged across machines. **DDSketch** (Masson, Rim & Lee, 2019) solves both: it
//! answers *any* quantile with a guaranteed **relative** error and merges exactly.
//!
//! The idea is logarithmic bucketing. With accuracy `alpha`, set `gamma =
//! (1+alpha)/(1-alpha)` and file a value `v` into bucket `ceil(log_gamma v)`.
//! Every value in a bucket is within a factor `gamma` of the others, so reporting
//! the bucket's representative value `2·gamma^k/(gamma+1)` is correct to within
//! `alpha` *relative* to the true value — tight where it matters, in the tail,
//! because the buckets get geometrically wider as values grow. Memory is one
//! counter per occupied bucket: bounded by the ratio of largest to smallest value,
//! independent of how many samples arrive.
//!
//! Negative values are handled by a mirrored store, near-zero values by an exact
//! zero count. Because two sketches with the same `alpha` share a bucket layout,
//! [`DDSketch::merge`] is just per-bucket addition — collect from a fleet, merge,
//! query once. [`DDSketch::quantile`] returns the estimate, [`DDSketch::add`]
//! records a value, and exact [`DDSketch::min`]/[`DDSketch::max`]/[`DDSketch::sum`]
//! are tracked alongside.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Schema version of the DDSketch surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Values with magnitude below this are treated as zero (keeps bucket keys finite).
const MIN_VALUE: f64 = 1e-9;

/// A relative-error quantile sketch.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DDSketch {
    /// Relative-accuracy parameter in `(0, 1)`.
    alpha: f64,
    /// Positive-value buckets: `key -> count`.
    positive: BTreeMap<i32, u64>,
    /// Negative-value buckets (keyed by magnitude): `key -> count`.
    negative: BTreeMap<i32, u64>,
    /// Count of values treated as zero.
    zero_count: u64,
    /// Total values recorded.
    count: u64,
    /// Exact running sum, min, max (for reporting alongside the sketch).
    sum: f64,
    min: f64,
    max: f64,
}

/// Error constructing a sketch.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DDSketchError {
    /// `alpha` was not in the open interval `(0, 1)`.
    BadAlpha,
    /// Tried to merge sketches built with different `alpha`.
    AlphaMismatch,
}

impl std::fmt::Display for DDSketchError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DDSketchError::BadAlpha => write!(f, "alpha must be in (0, 1)"),
            DDSketchError::AlphaMismatch => write!(f, "cannot merge sketches with different alpha"),
        }
    }
}
impl std::error::Error for DDSketchError {}

impl DDSketch {
    /// A new sketch with relative accuracy `alpha` (e.g. `0.01` for 1% error).
    pub fn new(alpha: f64) -> Result<Self, DDSketchError> {
        if !(alpha > 0.0 && alpha < 1.0) {
            return Err(DDSketchError::BadAlpha);
        }
        Ok(Self {
            alpha,
            positive: BTreeMap::new(),
            negative: BTreeMap::new(),
            zero_count: 0,
            count: 0,
            sum: 0.0,
            min: f64::INFINITY,
            max: f64::NEG_INFINITY,
        })
    }

    fn gamma(&self) -> f64 {
        (1.0 + self.alpha) / (1.0 - self.alpha)
    }
    fn ln_gamma(&self) -> f64 {
        self.gamma().ln()
    }

    /// Bucket key for a positive magnitude.
    fn key(&self, magnitude: f64) -> i32 {
        (magnitude.ln() / self.ln_gamma()).ceil() as i32
    }

    /// Representative value of a positive bucket key.
    fn value_of(&self, key: i32) -> f64 {
        let g = self.gamma();
        (key as f64 * self.ln_gamma()).exp() * 2.0 / (g + 1.0)
    }

    /// Record a value.
    pub fn add(&mut self, v: f64) {
        if !v.is_finite() {
            return;
        }
        self.count += 1;
        self.sum += v;
        if v < self.min {
            self.min = v;
        }
        if v > self.max {
            self.max = v;
        }
        if v.abs() < MIN_VALUE {
            self.zero_count += 1;
        } else if v > 0.0 {
            *self.positive.entry(self.key(v)).or_insert(0) += 1;
        } else {
            *self.negative.entry(self.key(-v)).or_insert(0) += 1;
        }
    }

    /// Record a value `n` times (weighted insert).
    pub fn add_many(&mut self, v: f64, n: u64) {
        if n == 0 || !v.is_finite() {
            return;
        }
        self.count += n;
        self.sum += v * n as f64;
        if v < self.min {
            self.min = v;
        }
        if v > self.max {
            self.max = v;
        }
        if v.abs() < MIN_VALUE {
            self.zero_count += n;
        } else if v > 0.0 {
            *self.positive.entry(self.key(v)).or_insert(0) += n;
        } else {
            *self.negative.entry(self.key(-v)).or_insert(0) += n;
        }
    }

    /// Number of recorded values.
    pub fn count(&self) -> u64 {
        self.count
    }
    /// Whether no values have been recorded.
    pub fn is_empty(&self) -> bool {
        self.count == 0
    }
    /// Exact sum of recorded values.
    pub fn sum(&self) -> f64 {
        self.sum
    }
    /// Exact minimum (`None` if empty).
    pub fn min(&self) -> Option<f64> {
        if self.is_empty() {
            None
        } else {
            Some(self.min)
        }
    }
    /// Exact maximum (`None` if empty).
    pub fn max(&self) -> Option<f64> {
        if self.is_empty() {
            None
        } else {
            Some(self.max)
        }
    }
    /// Exact mean (`None` if empty).
    pub fn mean(&self) -> Option<f64> {
        if self.is_empty() {
            None
        } else {
            Some(self.sum / self.count as f64)
        }
    }
    /// The configured relative accuracy.
    pub fn alpha(&self) -> f64 {
        self.alpha
    }

    /// Estimate the value at quantile `q` in `[0, 1]`. The result is within a
    /// factor `1 ± alpha` of the true quantile value. `None` if empty.
    pub fn quantile(&self, q: f64) -> Option<f64> {
        if self.is_empty() {
            return None;
        }
        let q = q.clamp(0.0, 1.0);
        // 0-based element rank we are seeking.
        let target = q * (self.count - 1) as f64;

        let mut cum: u64 = 0;
        // ascending value order: most-negative first (largest magnitude key),
        // then zeros, then positives ascending.
        for (&key, &c) in self.negative.iter().rev() {
            cum += c;
            if (cum as f64) > target {
                return Some(-self.value_of(key));
            }
        }
        if self.zero_count > 0 {
            cum += self.zero_count;
            if (cum as f64) > target {
                return Some(0.0);
            }
        }
        for (&key, &c) in self.positive.iter() {
            cum += c;
            if (cum as f64) > target {
                return Some(self.value_of(key));
            }
        }
        // floating rounding fallback: the very last value.
        self.max()
    }

    /// Merge another sketch (same `alpha`) into this one.
    pub fn merge(&mut self, other: &DDSketch) -> Result<(), DDSketchError> {
        if (self.alpha - other.alpha).abs() > 1e-12 {
            return Err(DDSketchError::AlphaMismatch);
        }
        for (&k, &c) in &other.positive {
            *self.positive.entry(k).or_insert(0) += c;
        }
        for (&k, &c) in &other.negative {
            *self.negative.entry(k).or_insert(0) += c;
        }
        self.zero_count += other.zero_count;
        self.count += other.count;
        self.sum += other.sum;
        if other.count > 0 {
            if other.min < self.min {
                self.min = other.min;
            }
            if other.max > self.max {
                self.max = other.max;
            }
        }
        Ok(())
    }

    /// Number of occupied buckets (the sketch's memory footprint).
    pub fn num_buckets(&self) -> usize {
        self.positive.len() + self.negative.len() + usize::from(self.zero_count > 0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Exact quantile of a sorted-able sample, using the same rank convention as
    /// the sketch (cumulative count `> q·(n-1)`) so the comparison isolates the
    /// bucketing error alone.
    fn exact_quantile(data: &[f64], q: f64) -> f64 {
        let mut v = data.to_vec();
        v.sort_by(|a, b| a.total_cmp(b));
        let target = q * (v.len() - 1) as f64;
        for (i, &x) in v.iter().enumerate() {
            if (i + 1) as f64 > target {
                return x;
            }
        }
        *v.last().unwrap()
    }

    #[test]
    fn bad_alpha_rejected() {
        assert_eq!(DDSketch::new(0.0), Err(DDSketchError::BadAlpha));
        assert_eq!(DDSketch::new(1.0), Err(DDSketchError::BadAlpha));
        assert!(DDSketch::new(0.01).is_ok());
    }

    #[test]
    fn empty_returns_none() {
        let s = DDSketch::new(0.01).unwrap();
        assert!(s.quantile(0.5).is_none());
        assert!(s.min().is_none());
        assert!(s.is_empty());
    }

    #[test]
    fn relative_error_bound_holds() {
        let alpha = 0.01;
        let mut s = DDSketch::new(alpha).unwrap();
        let data: Vec<f64> = (1..=10_000).map(|i| i as f64).collect();
        for &v in &data {
            s.add(v);
        }
        for &q in &[0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999] {
            let est = s.quantile(q).unwrap();
            let truth = exact_quantile(&data, q);
            let rel = (est - truth).abs() / truth;
            assert!(
                rel <= alpha + 1e-9,
                "q={q} est={est} truth={truth} rel={rel}"
            );
        }
    }

    #[test]
    fn median_of_uniform() {
        let mut s = DDSketch::new(0.02).unwrap();
        for i in 1..=1000 {
            s.add(i as f64);
        }
        let m = s.quantile(0.5).unwrap();
        // true median ~500; within 2% relative.
        assert!((m - 500.0).abs() / 500.0 <= 0.02, "median {m}");
    }

    #[test]
    fn tail_accuracy_p99() {
        let alpha = 0.01;
        let mut s = DDSketch::new(alpha).unwrap();
        // a skewed distribution: most small, a few large.
        let mut data = Vec::new();
        for i in 1..=9900 {
            data.push((i % 100) as f64 + 1.0);
        }
        for i in 0..100 {
            data.push(1000.0 + i as f64);
        }
        for &v in &data {
            s.add(v);
        }
        let est = s.quantile(0.99).unwrap();
        let truth = exact_quantile(&data, 0.99);
        let rel = (est - truth).abs() / truth;
        assert!(rel <= alpha + 1e-9, "p99 est={est} truth={truth} rel={rel}");
    }

    #[test]
    fn negative_values() {
        let alpha = 0.01;
        let mut s = DDSketch::new(alpha).unwrap();
        let data: Vec<f64> = (-5000..=5000).map(|i| i as f64).collect();
        for &v in &data {
            s.add(v);
        }
        // median should be ~0.
        let m = s.quantile(0.5).unwrap();
        assert!(m.abs() < 1.0, "median {m}");
        // a low quantile is strongly negative within relative error.
        let p10 = s.quantile(0.1).unwrap();
        let truth = exact_quantile(&data, 0.1);
        assert!(p10 < 0.0);
        let rel = (p10 - truth).abs() / truth.abs();
        assert!(rel <= alpha + 1e-9, "p10 est={p10} truth={truth}");
    }

    #[test]
    fn zeros_and_mixed_signs() {
        let mut s = DDSketch::new(0.01).unwrap();
        for _ in 0..100 {
            s.add(0.0);
        }
        for i in 1..=100 {
            s.add(i as f64);
            s.add(-(i as f64));
        }
        assert_eq!(s.count(), 300);
        // median of {-100..-1, 0×100, 1..100} is 0.
        assert_eq!(s.quantile(0.5).unwrap(), 0.0);
    }

    #[test]
    fn min_max_sum_mean_exact() {
        let mut s = DDSketch::new(0.01).unwrap();
        for v in [3.0, 1.0, 4.0, 1.5, 9.0, 2.0] {
            s.add(v);
        }
        assert_eq!(s.min().unwrap(), 1.0);
        assert_eq!(s.max().unwrap(), 9.0);
        assert!((s.sum() - 20.5).abs() < 1e-9);
        assert!((s.mean().unwrap() - 20.5 / 6.0).abs() < 1e-9);
    }

    #[test]
    fn merge_equals_combined() {
        let alpha = 0.01;
        let mut a = DDSketch::new(alpha).unwrap();
        let mut b = DDSketch::new(alpha).unwrap();
        let mut combined = DDSketch::new(alpha).unwrap();
        for i in 1..=5000 {
            a.add(i as f64);
            combined.add(i as f64);
        }
        for i in 5001..=10000 {
            b.add(i as f64);
            combined.add(i as f64);
        }
        a.merge(&b).unwrap();
        assert_eq!(a.count(), combined.count());
        for &q in &[0.1, 0.5, 0.9, 0.99] {
            assert_eq!(a.quantile(q), combined.quantile(q), "q={q}");
        }
    }

    #[test]
    fn merge_alpha_mismatch_rejected() {
        let mut a = DDSketch::new(0.01).unwrap();
        let b = DDSketch::new(0.02).unwrap();
        assert_eq!(a.merge(&b), Err(DDSketchError::AlphaMismatch));
    }

    #[test]
    fn add_many_matches_repeated_add() {
        let alpha = 0.01;
        let mut a = DDSketch::new(alpha).unwrap();
        let mut b = DDSketch::new(alpha).unwrap();
        a.add_many(42.0, 1000);
        for _ in 0..1000 {
            b.add(42.0);
        }
        assert_eq!(a.count(), b.count());
        assert_eq!(a.quantile(0.5), b.quantile(0.5));
    }

    #[test]
    fn bounded_memory() {
        // a million inserts over a modest value range → few buckets.
        let mut s = DDSketch::new(0.01).unwrap();
        for i in 0..1_000_000u64 {
            s.add((i % 1000) as f64 + 1.0);
        }
        assert_eq!(s.count(), 1_000_000);
        // values 1..1000 with gamma~1.02 → on the order of a few hundred buckets,
        // nowhere near a million.
        assert!(s.num_buckets() < 1000, "buckets {}", s.num_buckets());
    }

    #[test]
    fn quantile_endpoints() {
        let mut s = DDSketch::new(0.01).unwrap();
        for i in 1..=100 {
            s.add(i as f64);
        }
        let q0 = s.quantile(0.0).unwrap();
        let q1 = s.quantile(1.0).unwrap();
        // within relative error of true min(1) and max(100).
        assert!((q0 - 1.0).abs() / 1.0 <= 0.01 + 1e-9, "q0 {q0}");
        assert!((q1 - 100.0).abs() / 100.0 <= 0.01 + 1e-9, "q1 {q1}");
    }

    #[test]
    fn serde_round_trip() {
        let mut s = DDSketch::new(0.01).unwrap();
        for i in 1..=500 {
            s.add(i as f64);
        }
        let j = serde_json::to_string(&s).unwrap();
        let back: DDSketch = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
        assert_eq!(s.quantile(0.9), back.quantile(0.9));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
