//! `sovereign-tdigest` — streaming quantiles that are sharpest at the extremes.
//!
//! [DDSketch][crate] guarantees a *relative* error everywhere; **t-digest**
//! (Dunning) makes a different bet that is often the one you want for latencies and
//! scores: spend resolution where the tail is. It clusters the stream into
//! **centroids** — a running mean and a weight — and caps each centroid's weight by
//! a **scale function** of its position in the distribution. Near the median the
//! cap is loose, so a few fat centroids cover the bulk cheaply; near `q = 0` and
//! `q = 1` the cap tightens to almost one point per centroid, so p1 and p999 stay
//! crisp. The result is rank-error-bounded quantiles over an *unbounded* value
//! range (no minimum-value floor), in a footprint of roughly `compression`
//! centroids regardless of how many samples arrive.
//!
//! Values are buffered and periodically **merged**: existing centroids and the
//! buffer are sorted by mean and swept once, greedily fusing adjacent centroids
//! while the scale function permits, which both compresses and keeps the structure
//! sorted. Quantiles interpolate between centroid means (anchored on the exact min
//! and max), giving smooth, monotone estimates. Because two digests with the same
//! `compression` are mergeable by the same sweep, [`TDigest::merge`] combines
//! shards — gather from a fleet, merge, query once.
//!
//! [`TDigest::add`] records a value, [`TDigest::quantile`] estimates one, and
//! [`TDigest::cdf`] inverts it (the rank of a value). Exact
//! [`TDigest::min`]/[`TDigest::max`]/[`TDigest::sum`] ride alongside.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::f64::consts::PI;

/// Schema version of the t-digest surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A single cluster: a weighted mean of nearby values.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
struct Centroid {
    mean: f64,
    weight: f64,
}

/// A t-digest streaming quantile estimator.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TDigest {
    /// Compression parameter: larger = more centroids = higher accuracy.
    compression: f64,
    /// Merged centroids, sorted ascending by mean.
    centroids: Vec<Centroid>,
    /// Unmerged buffered points (value, weight).
    buffer: Vec<Centroid>,
    /// Total weight (sample count for unit weights).
    count: f64,
    sum: f64,
    min: f64,
    max: f64,
}

impl TDigest {
    /// A new digest with the given `compression` (clamped to at least 20). A
    /// typical value is 100; higher trades memory for accuracy.
    pub fn new(compression: f64) -> Self {
        Self {
            compression: compression.max(20.0),
            centroids: Vec::new(),
            buffer: Vec::new(),
            count: 0.0,
            sum: 0.0,
            min: f64::INFINITY,
            max: f64::NEG_INFINITY,
        }
    }

    /// A digest with the default compression of 100.
    pub fn with_default() -> Self {
        Self::new(100.0)
    }

    /// The scale function `k(q)` mapping a quantile to "k-space".
    fn k(&self, q: f64) -> f64 {
        (self.compression / (2.0 * PI)) * (2.0 * q - 1.0).clamp(-1.0, 1.0).asin()
    }
    /// Inverse scale function `k_inv(k)`.
    fn k_inv(&self, k: f64) -> f64 {
        ((2.0 * PI * k / self.compression).sin() + 1.0) / 2.0
    }

    /// Record a value (unit weight).
    pub fn add(&mut self, v: f64) {
        self.add_weighted(v, 1.0);
    }

    /// Record a value with a given positive weight.
    pub fn add_weighted(&mut self, v: f64, weight: f64) {
        if !v.is_finite() || !weight.is_finite() || weight <= 0.0 {
            return;
        }
        self.count += weight;
        self.sum += v * weight;
        if v < self.min {
            self.min = v;
        }
        if v > self.max {
            self.max = v;
        }
        self.buffer.push(Centroid { mean: v, weight });
        // merge when the buffer grows large relative to the centroid budget.
        if self.buffer.len() as f64 > self.compression * 10.0 {
            self.compress();
        }
    }

    /// Fold buffered points into the sorted centroid set, enforcing the scale bound.
    fn compress(&mut self) {
        if self.buffer.is_empty() && self.centroids.len() <= 1 {
            self.buffer.clear();
            return;
        }
        let mut all: Vec<Centroid> = Vec::with_capacity(self.centroids.len() + self.buffer.len());
        all.append(&mut self.centroids);
        all.append(&mut self.buffer);
        all.sort_by(|a, b| a.mean.total_cmp(&b.mean));
        if all.is_empty() {
            return;
        }
        let total = self.count;

        let mut result: Vec<Centroid> = Vec::with_capacity(all.len());
        result.push(all[0]);
        let mut q0 = 0.0;
        let mut q_limit = self.k_inv(self.k(q0) + 1.0);

        for &c in &all[1..] {
            let last = result.last_mut().unwrap();
            let q = q0 + (last.weight + c.weight) / total;
            if q <= q_limit {
                // fuse c into the current centroid (weighted mean).
                let w = last.weight + c.weight;
                last.mean = (last.mean * last.weight + c.mean * c.weight) / w;
                last.weight = w;
            } else {
                q0 += last.weight / total;
                q_limit = self.k_inv(self.k(q0) + 1.0);
                result.push(c);
            }
        }
        self.centroids = result;
    }

    /// Total recorded weight (sample count).
    pub fn count(&self) -> f64 {
        self.count
    }
    /// Whether nothing has been recorded.
    pub fn is_empty(&self) -> bool {
        self.count == 0.0
    }
    /// Number of stored centroids after the last merge (the footprint).
    pub fn num_centroids(&mut self) -> usize {
        self.compress();
        self.centroids.len()
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
            Some(self.sum / self.count)
        }
    }
    /// The configured compression.
    pub fn compression(&self) -> f64 {
        self.compression
    }

    /// Estimate the value at quantile `q` in `[0, 1]`. `None` if empty.
    pub fn quantile(&mut self, q: f64) -> Option<f64> {
        if self.is_empty() {
            return None;
        }
        self.compress();
        let q = q.clamp(0.0, 1.0);
        let cs = &self.centroids;
        if cs.len() == 1 {
            return Some(cs[0].mean);
        }
        let target = q * self.count;

        // cumulative weight at the *center* of each centroid.
        let mut cum = 0.0;
        let mut centers = Vec::with_capacity(cs.len());
        for c in cs {
            centers.push(cum + c.weight / 2.0);
            cum += c.weight;
        }

        // before the first center: interpolate from the exact min.
        if target < centers[0] {
            let c0 = centers[0];
            if c0 <= 0.0 {
                return Some(cs[0].mean);
            }
            let t = target / c0;
            return Some(self.min + t * (cs[0].mean - self.min));
        }
        // after the last center: interpolate to the exact max.
        let last = cs.len() - 1;
        if target >= centers[last] {
            let span = self.count - centers[last];
            if span <= 0.0 {
                return Some(cs[last].mean);
            }
            let t = (target - centers[last]) / span;
            return Some(cs[last].mean + t * (self.max - cs[last].mean));
        }
        // between two centroid centers: linear interpolation of their means.
        for i in 0..last {
            if target >= centers[i] && target < centers[i + 1] {
                let span = centers[i + 1] - centers[i];
                let t = if span > 0.0 {
                    (target - centers[i]) / span
                } else {
                    0.0
                };
                return Some(cs[i].mean + t * (cs[i + 1].mean - cs[i].mean));
            }
        }
        Some(cs[last].mean)
    }

    /// Estimate the cumulative rank `P(X <= v)` in `[0, 1]`. `None` if empty.
    pub fn cdf(&mut self, v: f64) -> Option<f64> {
        if self.is_empty() {
            return None;
        }
        self.compress();
        if v < self.min {
            return Some(0.0);
        }
        if v >= self.max {
            return Some(1.0);
        }
        let cs = &self.centroids;
        // accumulate weight of centroids with mean <= v, half-weighting the bucket
        // that straddles v for a smooth estimate.
        let mut cum = 0.0;
        for c in cs {
            if c.mean < v {
                cum += c.weight;
            } else if c.mean == v {
                cum += c.weight / 2.0;
            } else {
                break;
            }
        }
        Some((cum / self.count).clamp(0.0, 1.0))
    }

    /// Merge another digest (any compression) into this one.
    pub fn merge(&mut self, other: &TDigest) {
        if other.is_empty() {
            return;
        }
        // absorb the other's centroids (already merged) and buffer as points.
        self.buffer.extend(other.centroids.iter().copied());
        self.buffer.extend(other.buffer.iter().copied());
        self.count += other.count;
        self.sum += other.sum;
        if other.min < self.min {
            self.min = other.min;
        }
        if other.max > self.max {
            self.max = other.max;
        }
        self.compress();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn exact_quantile(data: &[f64], q: f64) -> f64 {
        let mut v = data.to_vec();
        v.sort_by(|a, b| a.total_cmp(b));
        let idx = (q * (v.len() - 1) as f64).round() as usize;
        v[idx.min(v.len() - 1)]
    }

    #[test]
    fn empty_returns_none() {
        let mut t = TDigest::with_default();
        assert!(t.quantile(0.5).is_none());
        assert!(t.min().is_none());
    }

    #[test]
    fn median_of_uniform() {
        let mut t = TDigest::new(100.0);
        let data: Vec<f64> = (1..=10_000).map(|i| i as f64).collect();
        for &v in &data {
            t.add(v);
        }
        let m = t.quantile(0.5).unwrap();
        let truth = exact_quantile(&data, 0.5);
        // within ~1% of the range.
        assert!((m - truth).abs() < 100.0, "median {m} truth {truth}");
    }

    #[test]
    fn tail_quantiles_accurate() {
        let mut t = TDigest::new(200.0);
        let data: Vec<f64> = (1..=100_000).map(|i| i as f64).collect();
        for &v in &data {
            t.add(v);
        }
        for &q in &[0.01, 0.1, 0.5, 0.9, 0.99, 0.999] {
            let est = t.quantile(q).unwrap();
            let truth = exact_quantile(&data, q);
            // t-digest gives rank error; for uniform data that maps to a small
            // value error, tighter at the tails.
            let rel = (est - truth).abs() / 100_000.0;
            assert!(rel < 0.01, "q={q} est={est} truth={truth} rel={rel}");
        }
    }

    #[test]
    fn extremes_are_exact() {
        let mut t = TDigest::new(100.0);
        for i in 1..=1000 {
            t.add(i as f64);
        }
        assert_eq!(t.min().unwrap(), 1.0);
        assert_eq!(t.max().unwrap(), 1000.0);
        // q=0 and q=1 anchor on the exact extremes.
        assert!((t.quantile(0.0).unwrap() - 1.0).abs() < 1.0);
        assert!((t.quantile(1.0).unwrap() - 1000.0).abs() < 1.0);
    }

    #[test]
    fn monotonic_quantiles() {
        let mut t = TDigest::new(100.0);
        for i in 0..5000 {
            t.add(((i * 7) % 1000) as f64);
        }
        let mut prev = f64::NEG_INFINITY;
        let mut q = 0.0;
        while q <= 1.0 {
            let v = t.quantile(q).unwrap();
            assert!(v >= prev - 1e-6, "non-monotone at q={q}: {v} < {prev}");
            prev = v;
            q += 0.05;
        }
    }

    #[test]
    fn negatives_and_mixed() {
        let mut t = TDigest::new(100.0);
        let data: Vec<f64> = (-5000..=5000).map(|i| i as f64).collect();
        for &v in &data {
            t.add(v);
        }
        let m = t.quantile(0.5).unwrap();
        assert!(m.abs() < 100.0, "median {m}");
    }

    #[test]
    fn bounded_footprint() {
        let mut t = TDigest::new(100.0);
        for i in 0..1_000_000u64 {
            t.add((i % 100_000) as f64);
        }
        // centroid count stays near the compression budget, not the sample count.
        let n = t.num_centroids();
        assert!(n <= 300, "centroids {n}");
    }

    #[test]
    fn cdf_inverts_quantile() {
        let mut t = TDigest::new(200.0);
        for i in 1..=10_000 {
            t.add(i as f64);
        }
        // cdf at the median value should be ~0.5.
        let c = t.cdf(5000.0).unwrap();
        assert!((c - 0.5).abs() < 0.02, "cdf {c}");
        assert_eq!(t.cdf(-1.0).unwrap(), 0.0);
        assert_eq!(t.cdf(20_000.0).unwrap(), 1.0);
    }

    #[test]
    fn merge_combines_shards() {
        let mut a = TDigest::new(100.0);
        let mut b = TDigest::new(100.0);
        let mut all = Vec::new();
        for i in 1..=5000 {
            a.add(i as f64);
            all.push(i as f64);
        }
        for i in 5001..=10000 {
            b.add(i as f64);
            all.push(i as f64);
        }
        a.merge(&b);
        assert_eq!(a.count(), 10000.0);
        for &q in &[0.1, 0.5, 0.9] {
            let est = a.quantile(q).unwrap();
            let truth = exact_quantile(&all, q);
            assert!(
                (est - truth).abs() / 10000.0 < 0.02,
                "q={q} est={est} truth={truth}"
            );
        }
    }

    #[test]
    fn weighted_add() {
        let mut t = TDigest::new(100.0);
        t.add_weighted(10.0, 500.0);
        t.add_weighted(20.0, 500.0);
        assert_eq!(t.count(), 1000.0);
        // half the weight at 10, half at 20 → median around the 10..20 boundary.
        let m = t.quantile(0.5).unwrap();
        assert!((10.0..=20.0).contains(&m), "median {m}");
    }

    #[test]
    fn exact_sum_and_mean() {
        let mut t = TDigest::new(100.0);
        for v in [1.0, 2.0, 3.0, 4.0] {
            t.add(v);
        }
        assert!((t.sum() - 10.0).abs() < 1e-9);
        assert!((t.mean().unwrap() - 2.5).abs() < 1e-9);
    }

    #[test]
    fn serde_round_trip() {
        let mut t = TDigest::new(100.0);
        for i in 1..=2000 {
            t.add(i as f64);
        }
        t.compress();
        let j = serde_json::to_string(&t).unwrap();
        let mut back: TDigest = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
        assert_eq!(t.clone().quantile(0.9), back.quantile(0.9));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
