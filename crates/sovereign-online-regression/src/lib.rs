//! `sovereign-online-regression` — a least-squares line that updates as data arrives.
//!
//! Is latency climbing with load? Is throughput drifting down? Those are slopes, and
//! you want them *live*, from a stream of `(x, y)` samples, without buffering the
//! history. This crate fits a simple linear regression incrementally: each point
//! folds into a handful of running sums, and at any moment you can read the slope,
//! intercept, correlation, and the `R²` goodness-of-fit — all in constant memory.
//!
//! It uses **West's weighted incremental algorithm** for the means and the co-moment
//! `Σ w (x−x̄)(y−ȳ)`, which is numerically stable (no catastrophic cancellation from
//! subtracting large sums) and naturally supports per-sample **weights**. Because the
//! update is reversible, [`OnlineRegression::remove`] subtracts a point back out —
//! handy for a sliding window where old samples should expire.
//!
//! [`OnlineRegression::push`] adds a sample; [`OnlineRegression::slope`] and
//! [`OnlineRegression::intercept`] give the fitted line (both `None` until at least
//! two points with differing `x` exist); [`OnlineRegression::predict`] extrapolates;
//! and [`OnlineRegression::r_squared`] / [`OnlineRegression::correlation`] say how
//! well the line explains the data. When all `x` are identical the slope is
//! genuinely undefined and reported as `None` rather than a divide-by-zero.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the online-regression surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// An incrementally-fitted simple linear regression `y ≈ slope·x + intercept`.
#[derive(Debug, Clone, Copy, PartialEq, Default, Serialize, Deserialize)]
pub struct OnlineRegression {
    /// Number of samples currently included.
    count: u64,
    /// Total weight.
    sum_w: f64,
    mean_x: f64,
    mean_y: f64,
    /// Weighted sum of squared deviations in x.
    m2x: f64,
    /// Weighted sum of squared deviations in y.
    m2y: f64,
    /// Weighted co-moment `Σ w (x-x̄)(y-ȳ)`.
    cxy: f64,
}

impl OnlineRegression {
    /// An empty regression.
    pub fn new() -> Self {
        Self::default()
    }

    /// Number of samples included.
    pub fn count(&self) -> u64 {
        self.count
    }
    /// Whether no samples are included.
    pub fn is_empty(&self) -> bool {
        self.count == 0
    }
    /// The mean of x (`None` if empty).
    pub fn mean_x(&self) -> Option<f64> {
        (self.sum_w != 0.0).then_some(self.mean_x)
    }
    /// The mean of y (`None` if empty).
    pub fn mean_y(&self) -> Option<f64> {
        (self.sum_w != 0.0).then_some(self.mean_y)
    }

    /// Add a sample with unit weight.
    pub fn push(&mut self, x: f64, y: f64) {
        self.push_weighted(x, y, 1.0);
    }

    /// Add a sample with a given weight (West's incremental update).
    pub fn push_weighted(&mut self, x: f64, y: f64, weight: f64) {
        if !x.is_finite() || !y.is_finite() || !weight.is_finite() || weight == 0.0 {
            return;
        }
        self.apply(x, y, weight);
        self.count += 1;
    }

    /// Remove a previously-added unit-weight sample (reverses the update). No-op if
    /// empty.
    pub fn remove(&mut self, x: f64, y: f64) {
        self.remove_weighted(x, y, 1.0);
    }

    /// Remove a previously-added weighted sample.
    pub fn remove_weighted(&mut self, x: f64, y: f64, weight: f64) {
        if self.count == 0
            || !x.is_finite()
            || !y.is_finite()
            || !weight.is_finite()
            || weight == 0.0
        {
            return;
        }
        self.apply(x, y, -weight);
        self.count -= 1;
        if self.count == 0 {
            *self = Self::new(); // reset to pristine zero state
        }
    }

    /// The core weighted co-moment update; `weight` may be negative (removal).
    fn apply(&mut self, x: f64, y: f64, weight: f64) {
        let new_sum_w = self.sum_w + weight;
        if new_sum_w == 0.0 {
            // removing the last mass: reset cleanly.
            self.sum_w = 0.0;
            self.mean_x = 0.0;
            self.mean_y = 0.0;
            self.m2x = 0.0;
            self.m2y = 0.0;
            self.cxy = 0.0;
            return;
        }
        let dx_old = x - self.mean_x;
        let dy_old = y - self.mean_y;
        self.mean_x += weight * dx_old / new_sum_w;
        self.mean_y += weight * dy_old / new_sum_w;
        let dx_new = x - self.mean_x;
        let dy_new = y - self.mean_y;
        self.m2x += weight * dx_old * dx_new;
        self.m2y += weight * dy_old * dy_new;
        self.cxy += weight * dx_old * dy_new;
        self.sum_w = new_sum_w;
    }

    /// The fitted slope, or `None` if there is no spread in x (fewer than two
    /// distinct x values).
    pub fn slope(&self) -> Option<f64> {
        if self.count < 2 || self.m2x <= 0.0 {
            None
        } else {
            Some(self.cxy / self.m2x)
        }
    }

    /// The fitted intercept, or `None` if the slope is undefined.
    pub fn intercept(&self) -> Option<f64> {
        self.slope().map(|m| self.mean_y - m * self.mean_x)
    }

    /// Predict `y` at `x` from the fitted line, or `None` if the line is undefined.
    pub fn predict(&self, x: f64) -> Option<f64> {
        let m = self.slope()?;
        Some(self.mean_y + m * (x - self.mean_x))
    }

    /// The Pearson correlation coefficient in `[-1, 1]`, or `None` if either
    /// variable has no spread.
    pub fn correlation(&self) -> Option<f64> {
        if self.count < 2 || self.m2x <= 0.0 || self.m2y <= 0.0 {
            None
        } else {
            Some((self.cxy / (self.m2x * self.m2y).sqrt()).clamp(-1.0, 1.0))
        }
    }

    /// The coefficient of determination `R²` in `[0, 1]`, or `None` if undefined.
    pub fn r_squared(&self) -> Option<f64> {
        self.correlation().map(|r| r * r)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-6
    }

    #[test]
    fn fits_a_perfect_line() {
        // y = 2x + 3
        let mut r = OnlineRegression::new();
        for x in 0..10 {
            let x = x as f64;
            r.push(x, 2.0 * x + 3.0);
        }
        assert!(approx(r.slope().unwrap(), 2.0));
        assert!(approx(r.intercept().unwrap(), 3.0));
        assert!(approx(r.r_squared().unwrap(), 1.0));
        assert!(approx(r.predict(100.0).unwrap(), 203.0));
    }

    #[test]
    fn negative_slope_and_correlation() {
        let mut r = OnlineRegression::new();
        for x in 0..10 {
            let x = x as f64;
            r.push(x, -1.5 * x + 10.0);
        }
        assert!(approx(r.slope().unwrap(), -1.5));
        assert!(r.correlation().unwrap() < 0.0);
        assert!(approx(r.correlation().unwrap(), -1.0));
    }

    #[test]
    fn noisy_line_recovers_trend() {
        let mut s = 0xBEEFu64;
        let mut noise = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            ((s >> 40) as f64 / (1u64 << 24) as f64) - 0.5
        };
        let mut r = OnlineRegression::new();
        for i in 0..1000 {
            let x = i as f64 * 0.1;
            r.push(x, 0.7 * x + 5.0 + noise());
        }
        assert!(
            (r.slope().unwrap() - 0.7).abs() < 0.05,
            "slope {}",
            r.slope().unwrap()
        );
        assert!(r.r_squared().unwrap() > 0.9);
    }

    #[test]
    fn no_relationship_low_r2() {
        // y alternates independent of x.
        let mut r = OnlineRegression::new();
        for i in 0..100 {
            let y = if i % 2 == 0 { 1.0 } else { -1.0 };
            r.push(i as f64, y);
        }
        assert!(
            r.r_squared().unwrap() < 0.05,
            "r2 {}",
            r.r_squared().unwrap()
        );
    }

    #[test]
    fn remove_reverses_push() {
        // a regression of {p1,p2} should equal {p1,p2,p3} with p3 removed.
        let p1 = (1.0, 2.0);
        let p2 = (2.0, 5.0);
        let p3 = (3.0, 1.0);
        let mut base = OnlineRegression::new();
        base.push(p1.0, p1.1);
        base.push(p2.0, p2.1);

        let mut full = OnlineRegression::new();
        full.push(p1.0, p1.1);
        full.push(p2.0, p2.1);
        full.push(p3.0, p3.1);
        full.remove(p3.0, p3.1);

        assert_eq!(base.count(), full.count());
        assert!(approx(base.slope().unwrap(), full.slope().unwrap()));
        assert!(approx(base.intercept().unwrap(), full.intercept().unwrap()));
    }

    #[test]
    fn sliding_window_via_remove() {
        // keep the last 3 points; the slope should reflect only those.
        let mut r = OnlineRegression::new();
        let pts = [
            (0.0, 0.0),
            (1.0, 1.0),
            (2.0, 2.0),
            (3.0, 30.0),
            (4.0, 40.0),
            (5.0, 50.0),
        ];
        for (i, &(x, y)) in pts.iter().enumerate() {
            r.push(x, y);
            if i >= 3 {
                let (ox, oy) = pts[i - 3];
                r.remove(ox, oy);
            }
        }
        // last three are (3,30),(4,40),(5,50): slope 10.
        assert!(
            approx(r.slope().unwrap(), 10.0),
            "slope {}",
            r.slope().unwrap()
        );
        assert_eq!(r.count(), 3);
    }

    #[test]
    fn weighted_samples() {
        // a heavily-weighted point pulls the fit.
        let mut r = OnlineRegression::new();
        r.push_weighted(0.0, 0.0, 1.0);
        r.push_weighted(1.0, 1.0, 1.0);
        r.push_weighted(2.0, 100.0, 100.0); // dominant
        // the line bends strongly toward the heavy point.
        assert!(r.slope().unwrap() > 10.0);
    }

    #[test]
    fn degenerate_no_x_spread() {
        let mut r = OnlineRegression::new();
        r.push(5.0, 1.0);
        r.push(5.0, 2.0);
        r.push(5.0, 3.0);
        assert!(r.slope().is_none()); // all x identical
        assert!(r.correlation().is_none());
        assert!(r.predict(0.0).is_none());
    }

    #[test]
    fn empty_and_single() {
        let mut r = OnlineRegression::new();
        assert!(r.slope().is_none());
        assert!(r.mean_x().is_none());
        r.push(1.0, 2.0);
        assert!(r.slope().is_none()); // need >= 2 points
        assert!(approx(r.mean_x().unwrap(), 1.0));
    }

    #[test]
    fn deterministic() {
        let build = || {
            let mut r = OnlineRegression::new();
            for i in 0..50 {
                r.push(i as f64, (i as f64) * 1.3 + 2.0);
            }
            r.slope().unwrap()
        };
        assert_eq!(build(), build());
    }

    #[test]
    fn serde_round_trip() {
        let mut r = OnlineRegression::new();
        for i in 0..10 {
            r.push(i as f64, 2.0 * i as f64 + 1.0);
        }
        let j = serde_json::to_string(&r).unwrap();
        let back: OnlineRegression = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
        assert_eq!(r.slope(), back.slope());
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
