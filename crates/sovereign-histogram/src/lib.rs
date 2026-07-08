//! `sovereign-histogram` — bucketed distributions and percentiles.
//!
//! The mean hides the tail, and the tail is where SLOs live: a p99 latency of
//! two seconds matters even when the average is fine. `running-stats` gives you
//! the mean and variance; this gives you the *shape*. A [`Histogram`] records
//! values into a fixed set of buckets — constant memory, no per-sample storage
//! — and answers [`percentile`](Histogram::percentile) queries (p50, p95, p99)
//! plus per-bucket and cumulative counts.
//!
//! The estimate is bucket-resolution: a percentile is reported as the upper
//! bound of the bucket the cumulative count lands in (the standard for
//! bucketed histograms), so finer buckets give finer answers. Deterministic
//! and dependency-free.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the histogram surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A fixed-bucket histogram. `bounds` are the inclusive upper edges of all but
/// the last (overflow) bucket; `counts` has `bounds.len() + 1` entries.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Histogram {
    bounds: Vec<f64>,
    counts: Vec<u64>,
    total: u64,
}

impl Histogram {
    /// A histogram with the given bucket upper-bounds. They are sorted; the
    /// final implicit bucket catches everything above the last bound.
    ///
    /// # Panics
    /// Panics if `bounds` is empty.
    pub fn new(mut bounds: Vec<f64>) -> Self {
        assert!(!bounds.is_empty(), "need at least one bound");
        bounds.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let n = bounds.len() + 1;
        Self {
            bounds,
            counts: vec![0; n],
            total: 0,
        }
    }

    /// Build with evenly-spaced bounds from `lo` to `hi` in `n` steps.
    ///
    /// # Panics
    /// Panics if `n == 0` or `hi <= lo`.
    pub fn linear(lo: f64, hi: f64, n: usize) -> Self {
        assert!(n > 0 && hi > lo, "need n > 0 and hi > lo");
        let step = (hi - lo) / n as f64;
        let bounds = (1..=n).map(|i| lo + step * i as f64).collect();
        Self::new(bounds)
    }

    /// Which bucket `x` falls into (0..=bounds.len()).
    fn bucket(&self, x: f64) -> usize {
        // first bucket whose upper bound is >= x
        self.bounds.partition_point(|&b| b < x)
    }

    /// Record a value.
    pub fn record(&mut self, x: f64) {
        let b = self.bucket(x);
        self.counts[b] += 1;
        self.total += 1;
    }

    /// Total recorded.
    pub fn total(&self) -> u64 {
        self.total
    }

    /// Per-bucket counts (one more than the number of bounds).
    pub fn counts(&self) -> &[u64] {
        &self.counts
    }

    /// Count of values at or below `x`.
    pub fn count_le(&self, x: f64) -> u64 {
        let b = self.bucket(x);
        self.counts[..=b].iter().sum()
    }

    /// The `p`-quantile (`p` in `[0, 1]`), reported as the upper bound of the
    /// bucket the cumulative count reaches. Returns `f64::INFINITY` if it lands
    /// in the overflow bucket, and `None` if no values were recorded.
    pub fn percentile(&self, p: f64) -> Option<f64> {
        if self.total == 0 {
            return None;
        }
        let p = p.clamp(0.0, 1.0);
        let target = ((p * self.total as f64).ceil() as u64).max(1);
        let mut cum = 0u64;
        for (i, &c) in self.counts.iter().enumerate() {
            cum += c;
            if cum >= target {
                return Some(if i < self.bounds.len() {
                    self.bounds[i]
                } else {
                    f64::INFINITY
                });
            }
        }
        Some(f64::INFINITY)
    }

    /// Convenience: the median (`p50`).
    pub fn median(&self) -> Option<f64> {
        self.percentile(0.5)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn filled() -> Histogram {
        // bounds 10,20,30,40 → buckets: ≤10, (10,20], (20,30], (30,40], >40
        let mut h = Histogram::new(vec![10.0, 20.0, 30.0, 40.0]);
        for &x in &[5.0, 15.0, 15.0, 25.0, 35.0] {
            h.record(x);
        }
        h
    }

    #[test]
    fn buckets_and_total() {
        let h = filled();
        assert_eq!(h.total(), 5);
        // 5→bucket0, 15→bucket1 (x2), 25→bucket2, 35→bucket3
        assert_eq!(h.counts(), &[1, 2, 1, 1, 0]);
    }

    #[test]
    fn percentiles() {
        let h = filled();
        // total 5; p50 target=ceil(2.5)=3 → cum 1,3 at bucket1 → bound 20
        assert_eq!(h.median(), Some(20.0));
        // p20 target=ceil(1)=1 → bucket0 → bound 10
        assert_eq!(h.percentile(0.2), Some(10.0));
        // p100 target=5 → cum 1,3,4,5 at bucket3 → bound 40
        assert_eq!(h.percentile(1.0), Some(40.0));
    }

    #[test]
    fn overflow_bucket_reports_infinity() {
        let mut h = Histogram::new(vec![10.0]);
        h.record(5.0); // bucket 0
        h.record(100.0); // overflow
        // p100 lands in overflow → infinity
        assert_eq!(h.percentile(1.0), Some(f64::INFINITY));
        assert_eq!(h.counts(), &[1, 1]);
    }

    #[test]
    fn count_le() {
        let h = filled();
        assert_eq!(h.count_le(10.0), 1); // just the 5
        assert_eq!(h.count_le(20.0), 3); // 5,15,15
        assert_eq!(h.count_le(100.0), 5); // all
    }

    #[test]
    fn empty_has_no_percentile() {
        let h = Histogram::new(vec![1.0, 2.0]);
        assert_eq!(h.percentile(0.5), None);
        assert_eq!(h.total(), 0);
    }

    #[test]
    fn linear_bounds() {
        let h = Histogram::linear(0.0, 100.0, 10);
        // bounds 10,20,...,100 → 10 bounds, 11 buckets
        assert_eq!(h.counts().len(), 11);
    }

    #[test]
    fn unsorted_bounds_are_sorted() {
        let mut h = Histogram::new(vec![30.0, 10.0, 20.0]);
        h.record(15.0);
        // 15 → bucket1 (10,20]
        assert_eq!(h.counts(), &[0, 1, 0, 0]);
    }

    #[test]
    fn p95_on_a_skewed_distribution() {
        let mut h = Histogram::linear(0.0, 10.0, 10); // bounds 1..=10
        // 95 fast (≈1) + 5 slow (≈9) → p95 should land near the slow tail
        for _ in 0..95 {
            h.record(0.5);
        }
        for _ in 0..5 {
            h.record(9.5);
        }
        let p95 = h.percentile(0.95).unwrap();
        assert!(p95 <= 1.0, "p95 {p95} should be in the fast bucket");
        let p99 = h.percentile(0.99).unwrap();
        assert!(p99 >= 9.0, "p99 {p99} should reach the slow tail");
    }

    #[test]
    fn serde_round_trip() {
        let h = filled();
        let j = serde_json::to_string(&h).unwrap();
        let back: Histogram = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
