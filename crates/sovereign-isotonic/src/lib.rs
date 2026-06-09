//! `sovereign-isotonic` — fit the best monotonic curve, assuming nothing about its shape.
//!
//! Temperature scaling calibrates a model's probabilities by fitting *one* number;
//! it works when miscalibration is a uniform squashing, but not when the distortion
//! has a more complex shape. **Isotonic regression** is the non-parametric
//! alternative: it finds the monotonic (non-decreasing) function closest to the data
//! in weighted least squares, assuming only that higher scores should map to
//! higher probabilities — and lets the data decide everything else.
//!
//! It is computed by **pool adjacent violators** (PAV). Walk the points in order
//! and keep a stack of blocks, each a pooled average; whenever a new block's average
//! would dip below the block before it — a violation of monotonicity — merge the two
//! into one block with their combined weighted mean, and keep merging backwards
//! until order is restored. After one pass the block averages are the unique optimal
//! fit, in linear time after the sort.
//!
//! [`IsotonicRegression::fit`] fits non-decreasing (or, with `increasing = false`,
//! non-increasing) values to `(x, y)` points; [`IsotonicRegression::fit_weighted`]
//! takes per-point weights. [`IsotonicRegression::predict`] evaluates the fitted
//! curve at any `x`, linearly interpolating between fitted points and clamping
//! beyond the ends. Use it to turn raw scores into calibrated probabilities, or to
//! enforce any known monotonic relationship.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the isotonic surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A fitted isotonic (monotonic) regression as a set of `(x, y)` breakpoints.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IsotonicRegression {
    /// Strictly increasing x breakpoints.
    xs: Vec<f64>,
    /// Fitted monotonic y values at each breakpoint.
    ys: Vec<f64>,
    /// Whether the fit is non-decreasing (`true`) or non-increasing (`false`).
    increasing: bool,
}

/// One pooled block during the PAV sweep.
#[derive(Clone, Copy)]
struct Block {
    sum_wy: f64,
    sum_w: f64,
}
impl Block {
    fn mean(&self) -> f64 {
        self.sum_wy / self.sum_w
    }
    fn merge(&mut self, o: &Block) {
        self.sum_wy += o.sum_wy;
        self.sum_w += o.sum_w;
    }
}

impl IsotonicRegression {
    /// Fit a monotonic curve to `(x, y)` points with unit weights.
    pub fn fit(points: &[(f64, f64)], increasing: bool) -> Self {
        let weighted: Vec<(f64, f64, f64)> = points.iter().map(|&(x, y)| (x, y, 1.0)).collect();
        Self::fit_weighted(&weighted, increasing)
    }

    /// Fit a monotonic curve to `(x, y, weight)` points.
    pub fn fit_weighted(points: &[(f64, f64, f64)], increasing: bool) -> Self {
        // keep finite, positive-weight points; sort by x.
        let mut pts: Vec<(f64, f64, f64)> = points
            .iter()
            .copied()
            .filter(|&(x, y, w)| x.is_finite() && y.is_finite() && w.is_finite() && w > 0.0)
            .collect();
        pts.sort_by(|a, b| a.0.total_cmp(&b.0));
        if pts.is_empty() {
            return Self {
                xs: Vec::new(),
                ys: Vec::new(),
                increasing,
            };
        }

        // for a non-increasing fit, negate y, fit increasing, negate back.
        let sign = if increasing { 1.0 } else { -1.0 };

        // PAV in one pass, tracking each block's element count alongside its sums.
        let mut blocks: Vec<(Block, usize)> = Vec::with_capacity(pts.len());
        for &(_, y, w) in &pts {
            let mut b = Block {
                sum_wy: w * y * sign,
                sum_w: w,
            };
            let mut count = 1usize;
            // pool while the new block violates monotonicity with the previous.
            while let Some((prev, pc)) = blocks.last() {
                if prev.mean() <= b.mean() {
                    break;
                }
                b.merge(prev);
                count += pc;
                blocks.pop();
            }
            blocks.push((b, count));
        }

        // expand blocks to per-x breakpoints (each pooled x gets the block mean),
        // keeping xs strictly increasing so prediction interpolates correctly.
        let mut xs = Vec::new();
        let mut ys = Vec::new();
        let mut covered = 0usize;
        for (b, count) in &blocks {
            let mean = b.mean() * sign;
            for _ in 0..*count {
                let (x, _, _) = pts[covered];
                if xs.last().map(|&lx| x > lx).unwrap_or(true) {
                    xs.push(x);
                    ys.push(mean);
                } else if let Some(last) = ys.last_mut() {
                    *last = mean; // same x within/across a block: identical value
                }
                covered += 1;
            }
        }

        Self { xs, ys, increasing }
    }

    /// Number of breakpoints in the fitted curve.
    pub fn len(&self) -> usize {
        self.xs.len()
    }
    /// Whether the fit is empty (no data).
    pub fn is_empty(&self) -> bool {
        self.xs.is_empty()
    }
    /// The fitted breakpoints as `(x, y)` pairs.
    pub fn breakpoints(&self) -> Vec<(f64, f64)> {
        self.xs
            .iter()
            .copied()
            .zip(self.ys.iter().copied())
            .collect()
    }

    /// Evaluate the fitted curve at `x`, linearly interpolating between breakpoints
    /// and clamping to the end values outside the fitted range. Returns `None` only
    /// for an empty fit.
    pub fn predict(&self, x: f64) -> Option<f64> {
        if self.xs.is_empty() {
            return None;
        }
        if x <= self.xs[0] {
            return Some(self.ys[0]);
        }
        let last = self.xs.len() - 1;
        if x >= self.xs[last] {
            return Some(self.ys[last]);
        }
        // binary search for the bracketing breakpoint.
        let mut lo = 0usize;
        let mut hi = last;
        while hi - lo > 1 {
            let mid = (lo + hi) / 2;
            if self.xs[mid] <= x {
                lo = mid;
            } else {
                hi = mid;
            }
        }
        let (x0, y0) = (self.xs[lo], self.ys[lo]);
        let (x1, y1) = (self.xs[hi], self.ys[hi]);
        let t = if x1 > x0 { (x - x0) / (x1 - x0) } else { 0.0 };
        Some(y0 + t * (y1 - y0))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    /// Is a sequence non-decreasing?
    fn non_decreasing(v: &[f64]) -> bool {
        v.windows(2).all(|w| w[0] <= w[1] + 1e-12)
    }

    #[test]
    fn already_monotonic_unchanged() {
        let pts = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 5.0)];
        let iso = IsotonicRegression::fit(&pts, true);
        for &(x, y) in &pts {
            assert!(approx(iso.predict(x).unwrap(), y), "x={x}");
        }
    }

    #[test]
    fn pools_violators() {
        // y = [1, 3, 2, 4] at x = 0,1,2,3. The 3 then 2 violate; pool to 2.5 each.
        let pts = [(0.0, 1.0), (1.0, 3.0), (2.0, 2.0), (3.0, 4.0)];
        let iso = IsotonicRegression::fit(&pts, true);
        assert!(approx(iso.predict(0.0).unwrap(), 1.0));
        assert!(approx(iso.predict(1.0).unwrap(), 2.5));
        assert!(approx(iso.predict(2.0).unwrap(), 2.5));
        assert!(approx(iso.predict(3.0).unwrap(), 4.0));
    }

    #[test]
    fn output_is_monotonic() {
        let mut s = 0x1357u64;
        let mut rng = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            (s >> 40) as f64 / (1u64 << 24) as f64
        };
        let pts: Vec<(f64, f64)> = (0..200).map(|i| (i as f64, rng())).collect();
        let iso = IsotonicRegression::fit(&pts, true);
        let fitted: Vec<f64> = pts.iter().map(|&(x, _)| iso.predict(x).unwrap()).collect();
        assert!(non_decreasing(&fitted));
    }

    #[test]
    fn minimizes_sse_vs_constant() {
        // the isotonic fit should have <= SSE of the best constant (the mean), since
        // constant is a feasible monotonic fit.
        let pts = [(0.0, 1.0), (1.0, 4.0), (2.0, 2.0), (3.0, 5.0), (4.0, 3.0)];
        let mean = pts.iter().map(|p| p.1).sum::<f64>() / pts.len() as f64;
        let iso = IsotonicRegression::fit(&pts, true);
        let sse_iso: f64 = pts
            .iter()
            .map(|&(x, y)| (y - iso.predict(x).unwrap()).powi(2))
            .sum();
        let sse_const: f64 = pts.iter().map(|&(_, y)| (y - mean).powi(2)).sum();
        assert!(
            sse_iso <= sse_const + 1e-9,
            "iso {sse_iso} const {sse_const}"
        );
    }

    #[test]
    fn decreasing_fit() {
        // data trending down with noise; non-increasing fit.
        let pts = [(0.0, 5.0), (1.0, 3.0), (2.0, 4.0), (3.0, 1.0)];
        let iso = IsotonicRegression::fit(&pts, false);
        let fitted: Vec<f64> = pts.iter().map(|&(x, _)| iso.predict(x).unwrap()).collect();
        assert!(
            fitted.windows(2).all(|w| w[0] >= w[1] - 1e-12),
            "{fitted:?}"
        );
    }

    #[test]
    fn weighted_pulls_toward_heavy_points() {
        // a heavily-weighted violator dominates the pooled mean.
        let light = IsotonicRegression::fit_weighted(
            &[(0.0, 0.0, 1.0), (1.0, 10.0, 1.0), (2.0, 0.0, 1.0)],
            true,
        );
        let heavy = IsotonicRegression::fit_weighted(
            &[(0.0, 0.0, 1.0), (1.0, 10.0, 1.0), (2.0, 0.0, 100.0)],
            true,
        );
        // with a heavy low point at x=2, the pooled plateau is lower.
        assert!(heavy.predict(1.0).unwrap() < light.predict(1.0).unwrap());
    }

    #[test]
    fn predict_interpolates_and_clamps() {
        let pts = [(0.0, 0.0), (10.0, 10.0)];
        let iso = IsotonicRegression::fit(&pts, true);
        assert!(approx(iso.predict(5.0).unwrap(), 5.0)); // midpoint interpolation
        assert!(approx(iso.predict(-3.0).unwrap(), 0.0)); // clamp low
        assert!(approx(iso.predict(99.0).unwrap(), 10.0)); // clamp high
    }

    #[test]
    fn calibration_use_case() {
        // raw scores vs correctness; isotonic gives a monotonic score->prob map.
        let data = [
            (0.1, 0.0),
            (0.2, 0.0),
            (0.3, 1.0),
            (0.4, 0.0),
            (0.6, 1.0),
            (0.7, 1.0),
            (0.9, 1.0),
        ];
        let iso = IsotonicRegression::fit(&data, true);
        // calibrated probability is monotonic and within [0,1].
        let p_low = iso.predict(0.15).unwrap();
        let p_high = iso.predict(0.8).unwrap();
        assert!(p_low <= p_high);
        assert!((0.0..=1.0).contains(&p_low) && (0.0..=1.0).contains(&p_high));
    }

    #[test]
    fn empty_and_single() {
        let e = IsotonicRegression::fit(&[], true);
        assert!(e.is_empty());
        assert!(e.predict(1.0).is_none());
        let s = IsotonicRegression::fit(&[(5.0, 3.0)], true);
        assert!(approx(s.predict(0.0).unwrap(), 3.0));
        assert!(approx(s.predict(100.0).unwrap(), 3.0));
    }

    #[test]
    fn serde_round_trip() {
        let iso = IsotonicRegression::fit(&[(0.0, 1.0), (1.0, 3.0), (2.0, 2.0)], true);
        let j = serde_json::to_string(&iso).unwrap();
        let back: IsotonicRegression = serde_json::from_str(&j).unwrap();
        assert_eq!(iso, back);
        assert_eq!(iso.predict(1.0), back.predict(1.0));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
