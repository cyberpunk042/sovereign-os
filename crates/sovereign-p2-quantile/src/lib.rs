//! `sovereign-p2-quantile` — a percentile over a stream, in five numbers.
//!
//! Reporting p95 latency exactly means keeping every sample and sorting — `O(n)`
//! memory you don't have on a hot path. The **P² algorithm** (Jain & Chlamtac,
//! 1985) estimates a chosen quantile in *constant* memory: it keeps just five
//! "markers" that approximate the minimum, the `p/2`, `p`, `(1+p)/2`, and maximum
//! positions of the distribution seen so far. Each new sample shifts the marker
//! positions; when a marker drifts too far from its ideal position the algorithm
//! nudges its height using **parabolic interpolation** (falling back to linear
//! when the parabola would be non-monotonic). The middle marker's height is the
//! running estimate of the `p`-quantile, updated in `O(1)` per sample with no
//! allocation.
//!
//! [`P2Quantile::new`] picks the quantile; [`P2Quantile::observe`] feeds a value;
//! [`P2Quantile::quantile`] reads the current estimate. For the first five
//! samples it returns the exact order statistic; thereafter the P² estimate,
//! which is accurate to a fraction of a percent on smooth distributions.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the p2-quantile surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// An online estimator for a single quantile via the P² algorithm.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct P2Quantile {
    p: f64,
    count: usize,
    /// marker heights q[0..5] (the estimated values).
    q: [f64; 5],
    /// marker positions n[0..5] (1-based ranks).
    n: [f64; 5],
    /// desired marker positions np[0..5].
    np: [f64; 5],
    /// increments dn[0..5] of the desired positions per sample.
    dn: [f64; 5],
    /// the first five samples, collected before the estimator initializes.
    init: Vec<f64>,
}

impl P2Quantile {
    /// An estimator for the `p`-quantile, `p` in `(0, 1)` (e.g. `0.95` for p95).
    ///
    /// # Panics
    /// Panics if `p` is not strictly between 0 and 1.
    pub fn new(p: f64) -> Self {
        assert!(p > 0.0 && p < 1.0, "quantile p must be in (0, 1)");
        Self {
            p,
            count: 0,
            q: [0.0; 5],
            n: [0.0; 5],
            np: [0.0; 5],
            dn: [0.0; 5],
            init: Vec::with_capacity(5),
        }
    }

    /// The quantile being estimated.
    pub fn p(&self) -> f64 {
        self.p
    }

    /// Number of samples observed.
    pub fn count(&self) -> usize {
        self.count
    }

    /// Feed one sample.
    pub fn observe(&mut self, x: f64) {
        self.count += 1;
        if self.count <= 5 {
            self.init.push(x);
            if self.count == 5 {
                self.initialize();
            }
            return;
        }
        self.update(x);
    }

    /// Initialize the five markers from the first five (sorted) samples.
    fn initialize(&mut self) {
        self.init.sort_by(|a, b| a.total_cmp(b));
        for i in 0..5 {
            self.q[i] = self.init[i];
            self.n[i] = (i + 1) as f64;
        }
        let p = self.p;
        self.np = [1.0, 1.0 + 2.0 * p, 1.0 + 4.0 * p, 3.0 + 2.0 * p, 5.0];
        self.dn = [0.0, p / 2.0, p, (1.0 + p) / 2.0, 1.0];
    }

    /// Process one sample after initialization.
    fn update(&mut self, x: f64) {
        // 1. find cell k and adjust extreme markers.
        let k = if x < self.q[0] {
            self.q[0] = x;
            0
        } else if x < self.q[1] {
            0
        } else if x < self.q[2] {
            1
        } else if x < self.q[3] {
            2
        } else if x <= self.q[4] {
            3
        } else {
            self.q[4] = x;
            3
        };

        // 2. increment positions of markers above k.
        for i in (k + 1)..5 {
            self.n[i] += 1.0;
        }
        // 3. update desired positions.
        for i in 0..5 {
            self.np[i] += self.dn[i];
        }
        // 4. adjust interior markers 1..=3 if needed.
        for i in 1..4 {
            let d = self.np[i] - self.n[i];
            let can_up = self.n[i + 1] - self.n[i] > 1.0;
            let can_down = self.n[i - 1] - self.n[i] < -1.0;
            if (d >= 1.0 && can_up) || (d <= -1.0 && can_down) {
                let sign = if d >= 0.0 { 1.0 } else { -1.0 };
                let qi = self.parabolic(i, sign);
                if self.q[i - 1] < qi && qi < self.q[i + 1] {
                    self.q[i] = qi;
                } else {
                    self.q[i] = self.linear(i, sign);
                }
                self.n[i] += sign;
            }
        }
    }

    /// Parabolic prediction for marker `i` moving by `sign` (±1).
    fn parabolic(&self, i: usize, sign: f64) -> f64 {
        let n = &self.n;
        let q = &self.q;
        q[i] + sign / (n[i + 1] - n[i - 1])
            * ((n[i] - n[i - 1] + sign) * (q[i + 1] - q[i]) / (n[i + 1] - n[i])
                + (n[i + 1] - n[i] - sign) * (q[i] - q[i - 1]) / (n[i] - n[i - 1]))
    }

    /// Linear prediction fallback for marker `i`.
    fn linear(&self, i: usize, sign: f64) -> f64 {
        let s = sign as isize;
        let j = (i as isize + s) as usize;
        self.q[i] + sign * (self.q[j] - self.q[i]) / (self.n[j] - self.n[i])
    }

    /// The current quantile estimate, or `None` before any sample.
    ///
    /// With fewer than five samples it returns the exact order statistic for the
    /// requested quantile; afterwards the P² estimate (marker 2).
    pub fn quantile(&self) -> Option<f64> {
        if self.count == 0 {
            return None;
        }
        if self.count < 5 {
            let mut s = self.init.clone();
            s.sort_by(|a, b| a.total_cmp(b));
            let idx = ((self.p * (s.len() as f64 - 1.0)).round() as usize).min(s.len() - 1);
            return Some(s[idx]);
        }
        Some(self.q[2])
    }

    /// The running minimum and maximum seen (marker extremes), if initialized.
    pub fn min_max(&self) -> Option<(f64, f64)> {
        if self.count >= 5 {
            Some((self.q[0], self.q[4]))
        } else if self.count > 0 {
            let mut s = self.init.clone();
            s.sort_by(|a, b| a.total_cmp(b));
            Some((s[0], s[s.len() - 1]))
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Exact quantile of a slice (nearest-rank) for comparison.
    fn exact_quantile(data: &[f64], p: f64) -> f64 {
        let mut s = data.to_vec();
        s.sort_by(|a, b| a.total_cmp(b));
        let idx = ((p * (s.len() as f64 - 1.0)).round() as usize).min(s.len() - 1);
        s[idx]
    }

    #[test]
    fn estimates_median_of_uniform_stream() {
        let mut q = P2Quantile::new(0.5);
        let data: Vec<f64> = (1..=1000).map(|i| i as f64).collect();
        for &x in &data {
            q.observe(x);
        }
        let est = q.quantile().unwrap();
        let exact = exact_quantile(&data, 0.5);
        // within 2% of the true median
        assert!(
            (est - exact).abs() / exact < 0.02,
            "est {est} exact {exact}"
        );
    }

    #[test]
    fn estimates_p95_within_tolerance() {
        let mut q = P2Quantile::new(0.95);
        // a skewed stream (latencies): mostly small, occasional large.
        let mut rng = 0x1234u64;
        let mut next = || {
            rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
            ((rng >> 33) as f64) / (1u64 << 31) as f64
        };
        let data: Vec<f64> = (0..20000)
            .map(|_| {
                let u: f64 = next();
                // exponential-ish via -ln(1-u)
                -(1.0 - u).ln() * 100.0
            })
            .collect();
        for &x in &data {
            q.observe(x);
        }
        let est = q.quantile().unwrap();
        let exact = exact_quantile(&data, 0.95);
        assert!(
            (est - exact).abs() / exact < 0.05,
            "p95 est {est} exact {exact}"
        );
    }

    #[test]
    fn exact_for_small_samples() {
        let mut q = P2Quantile::new(0.5);
        q.observe(3.0);
        q.observe(1.0);
        q.observe(2.0);
        // median of {1,2,3} = 2
        assert_eq!(q.quantile(), Some(2.0));
    }

    #[test]
    fn min_max_tracks_extremes() {
        let mut q = P2Quantile::new(0.5);
        for x in [5.0, 1.0, 9.0, 3.0, 7.0, 2.0, 8.0] {
            q.observe(x);
        }
        let (lo, hi) = q.min_max().unwrap();
        assert_eq!(lo, 1.0);
        assert_eq!(hi, 9.0);
    }

    #[test]
    fn empty_returns_none() {
        let q = P2Quantile::new(0.9);
        assert_eq!(q.quantile(), None);
        assert_eq!(q.min_max(), None);
        assert_eq!(q.count(), 0);
    }

    #[test]
    fn p99_on_constant_stream() {
        // all-equal stream → quantile equals that value
        let mut q = P2Quantile::new(0.99);
        for _ in 0..1000 {
            q.observe(42.0);
        }
        assert!((q.quantile().unwrap() - 42.0).abs() < 1e-9);
    }

    #[test]
    fn serde_round_trip() {
        let mut q = P2Quantile::new(0.9);
        for i in 0..100 {
            q.observe(i as f64);
        }
        let j = serde_json::to_string(&q).unwrap();
        let back: P2Quantile = serde_json::from_str(&j).unwrap();
        // f64 markers may shift a ULP through JSON; compare behaviour.
        assert_eq!(q.count(), back.count());
        let (a, b) = (q.quantile().unwrap(), back.quantile().unwrap());
        assert!((a - b).abs() < 1e-9);
    }
}
