//! `sovereign-running-stats` — online statistics for runtime telemetry.
//!
//! A runtime wants to know its latency, throughput, and acceptance rates, but
//! storing every sample to compute them is wasteful and unbounded. This crate
//! computes them *online* — one pass, constant memory. [`RunningStats`] uses
//! **Welford's algorithm**, the numerically-stable way to maintain a streaming
//! mean and variance (the naive "sum of squares minus square of sum" loses
//! precision and can go negative); it also tracks count, min, and max.
//! [`Ema`] keeps an exponential moving average for "recent" trends that fade
//! old samples out.
//!
//! Both are deterministic and dependency-free, so the telemetry is reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the running-stats surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Streaming mean/variance via Welford's algorithm, plus count/min/max.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct RunningStats {
    count: u64,
    mean: f64,
    m2: f64,
    min: f64,
    max: f64,
}

impl Default for RunningStats {
    fn default() -> Self {
        Self {
            count: 0,
            mean: 0.0,
            m2: 0.0,
            min: f64::INFINITY,
            max: f64::NEG_INFINITY,
        }
    }
}

impl RunningStats {
    /// An empty accumulator.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a sample.
    pub fn push(&mut self, x: f64) {
        self.count += 1;
        let delta = x - self.mean;
        self.mean += delta / self.count as f64;
        let delta2 = x - self.mean;
        self.m2 += delta * delta2;
        if x < self.min {
            self.min = x;
        }
        if x > self.max {
            self.max = x;
        }
    }

    /// Number of samples.
    pub fn count(&self) -> u64 {
        self.count
    }

    /// The running mean (`0.0` if no samples).
    pub fn mean(&self) -> f64 {
        if self.count == 0 { 0.0 } else { self.mean }
    }

    /// Population variance `m2 / n` (`0.0` if no samples).
    pub fn variance(&self) -> f64 {
        if self.count == 0 {
            0.0
        } else {
            self.m2 / self.count as f64
        }
    }

    /// Sample variance `m2 / (n - 1)` (`0.0` if fewer than two samples).
    pub fn sample_variance(&self) -> f64 {
        if self.count < 2 {
            0.0
        } else {
            self.m2 / (self.count - 1) as f64
        }
    }

    /// Population standard deviation.
    pub fn std_dev(&self) -> f64 {
        self.variance().sqrt()
    }

    /// Minimum sample (`None` if empty).
    pub fn min(&self) -> Option<f64> {
        (self.count > 0).then_some(self.min)
    }

    /// Maximum sample (`None` if empty).
    pub fn max(&self) -> Option<f64> {
        (self.count > 0).then_some(self.max)
    }
}

/// An exponential moving average: `v ← α·x + (1−α)·v`.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Ema {
    alpha: f64,
    value: Option<f64>,
}

impl Ema {
    /// An EMA with smoothing factor `alpha` in `(0, 1]` (higher = more reactive).
    ///
    /// # Panics
    /// Panics if `alpha` is not in `(0, 1]`.
    pub fn new(alpha: f64) -> Self {
        assert!(alpha > 0.0 && alpha <= 1.0, "alpha must be in (0, 1]");
        Self { alpha, value: None }
    }

    /// Add a sample; the first sample seeds the average.
    pub fn push(&mut self, x: f64) {
        self.value = Some(match self.value {
            None => x,
            Some(v) => self.alpha * x + (1.0 - self.alpha) * v,
        });
    }

    /// The current average (`None` before any sample).
    pub fn value(&self) -> Option<f64> {
        self.value
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn empty_stats_are_zero() {
        let s = RunningStats::new();
        assert_eq!(s.count(), 0);
        assert_eq!(s.mean(), 0.0);
        assert_eq!(s.variance(), 0.0);
        assert_eq!(s.min(), None);
        assert_eq!(s.max(), None);
    }

    #[test]
    fn known_mean_and_variance() {
        // data: 2,4,4,4,5,5,7,9 → mean 5, population variance 4, std 2
        let mut s = RunningStats::new();
        for &x in &[2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0] {
            s.push(x);
        }
        assert_eq!(s.count(), 8);
        assert!(approx(s.mean(), 5.0));
        assert!(approx(s.variance(), 4.0));
        assert!(approx(s.std_dev(), 2.0));
        assert_eq!(s.min(), Some(2.0));
        assert_eq!(s.max(), Some(9.0));
    }

    #[test]
    fn single_sample() {
        let mut s = RunningStats::new();
        s.push(7.5);
        assert!(approx(s.mean(), 7.5));
        assert_eq!(s.variance(), 0.0);
        assert_eq!(s.sample_variance(), 0.0); // n<2
        assert_eq!(s.min(), Some(7.5));
        assert_eq!(s.max(), Some(7.5));
    }

    #[test]
    fn sample_variance_uses_n_minus_one() {
        let mut s = RunningStats::new();
        for &x in &[1.0, 2.0, 3.0] {
            s.push(x);
        }
        // population variance = 2/3; sample variance = (sum sq dev)/(n-1) = 2/2 = 1
        assert!(approx(s.sample_variance(), 1.0));
        assert!(approx(s.variance(), 2.0 / 3.0));
    }

    #[test]
    fn numerically_stable_for_large_offsets() {
        // naive sum-of-squares would lose precision; Welford stays accurate
        let mut s = RunningStats::new();
        for &x in &[1e9 + 1.0, 1e9 + 2.0, 1e9 + 3.0] {
            s.push(x);
        }
        assert!(approx(s.mean(), 1e9 + 2.0));
        assert!(approx(s.variance(), 2.0 / 3.0));
    }

    #[test]
    fn ema_seeds_then_smooths() {
        let mut e = Ema::new(0.5);
        assert_eq!(e.value(), None);
        e.push(10.0);
        assert_eq!(e.value(), Some(10.0)); // first sample seeds
        e.push(20.0);
        // 0.5*20 + 0.5*10 = 15
        assert!(approx(e.value().unwrap(), 15.0));
        e.push(0.0);
        // 0.5*0 + 0.5*15 = 7.5
        assert!(approx(e.value().unwrap(), 7.5));
    }

    #[test]
    fn ema_alpha_one_tracks_latest() {
        let mut e = Ema::new(1.0);
        e.push(5.0);
        e.push(9.0);
        assert_eq!(e.value(), Some(9.0)); // fully reactive
    }

    #[test]
    fn serde_round_trip() {
        let mut s = RunningStats::new();
        s.push(1.0);
        s.push(2.0);
        let j = serde_json::to_string(&s).unwrap();
        let back: RunningStats = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
