//! `sovereign-kmeans` — partition vectors into clusters by nearest centroid.
//!
//! Many jobs over embeddings reduce to "group these vectors": cluster retrieved
//! chunks by topic, build a codebook for vector quantization, find the modes of a
//! set of generations. **K-means** is the workhorse. It seeks `k` centroids that
//! minimise the total squared distance from each point to its nearest centroid
//! (the *inertia*), alternating two steps until they stop changing: **assign**
//! every point to its closest centroid, then **update** each centroid to the mean
//! of the points assigned to it (Lloyd's algorithm). Each step can only lower the
//! inertia, so it converges.
//!
//! The result depends on where the centroids start, so initialisation uses
//! **k-means++**: the first centroid is a random point, and each subsequent one is
//! chosen with probability proportional to its squared distance from the nearest
//! centroid already picked — spreading the seeds out and giving a provably good
//! expected starting inertia. Randomness is a seeded **splitmix64** generator, so
//! a given seed and data always yield the same clustering.
//!
//! Points are `Vec<f32>` of equal dimension; distance is squared Euclidean.
//! [`KMeans::fit`] returns the [`Clustering`]; [`Clustering::predict`] assigns a
//! new point to the nearest learned centroid.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the k-means surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors fitting a model.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum KMeansError {
    /// `k` was zero.
    #[error("k must be >= 1")]
    ZeroK,
    /// There were fewer points than clusters requested.
    #[error("need at least k={k} points, got {n}")]
    TooFewPoints {
        /// Requested clusters.
        k: usize,
        /// Points supplied.
        n: usize,
    },
    /// Points had inconsistent dimensions, or were empty.
    #[error("points must be non-empty and all the same dimension")]
    BadShape,
}

/// K-means configuration.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct KMeans {
    /// Number of clusters.
    pub k: usize,
    /// Maximum Lloyd iterations.
    pub max_iters: usize,
    /// RNG seed for k-means++ initialisation.
    pub seed: u64,
}

/// A fitted clustering.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Clustering {
    /// The `k` centroids.
    pub centroids: Vec<Vec<f32>>,
    /// Cluster index assigned to each input point (parallel to the input).
    pub assignments: Vec<usize>,
    /// Total within-cluster squared distance.
    pub inertia: f64,
    /// Number of Lloyd iterations actually run.
    pub iterations: usize,
}

impl KMeans {
    /// A configuration for `k` clusters with the given iteration cap and seed.
    pub fn new(k: usize, max_iters: usize, seed: u64) -> Self {
        Self { k, max_iters, seed }
    }

    /// Cluster `points`. Returns an error if `k == 0`, there are fewer points
    /// than `k`, or the points are empty / ragged.
    pub fn fit(&self, points: &[Vec<f32>]) -> Result<Clustering, KMeansError> {
        if self.k == 0 {
            return Err(KMeansError::ZeroK);
        }
        if points.is_empty() || points[0].is_empty() {
            return Err(KMeansError::BadShape);
        }
        let dim = points[0].len();
        if points.iter().any(|p| p.len() != dim) {
            return Err(KMeansError::BadShape);
        }
        if points.len() < self.k {
            return Err(KMeansError::TooFewPoints {
                k: self.k,
                n: points.len(),
            });
        }

        let mut rng = self.seed | 1;
        let mut centroids = self.kmeans_plus_plus(points, &mut rng);
        let mut assignments = vec![0usize; points.len()];
        let mut iterations = 0;

        for _ in 0..self.max_iters.max(1) {
            iterations += 1;
            // assignment step
            let mut changed = false;
            for (i, p) in points.iter().enumerate() {
                let c = nearest(p, &centroids).0;
                if c != assignments[i] {
                    assignments[i] = c;
                    changed = true;
                }
            }
            // update step
            let mut sums = vec![vec![0.0f64; dim]; self.k];
            let mut counts = vec![0usize; self.k];
            for (p, &a) in points.iter().zip(assignments.iter()) {
                counts[a] += 1;
                for (s, &x) in sums[a].iter_mut().zip(p.iter()) {
                    *s += x as f64;
                }
            }
            for c in 0..self.k {
                if counts[c] > 0 {
                    for d in 0..dim {
                        centroids[c][d] = (sums[c][d] / counts[c] as f64) as f32;
                    }
                }
                // empty clusters keep their previous centroid (a stable choice).
            }
            if !changed {
                break; // converged: no reassignments
            }
        }

        // final assignment + inertia with the last centroids
        let mut inertia = 0.0;
        for (i, p) in points.iter().enumerate() {
            let (c, d2) = nearest(p, &centroids);
            assignments[i] = c;
            inertia += d2;
        }

        Ok(Clustering {
            centroids,
            assignments,
            inertia,
            iterations,
        })
    }

    /// k-means++ seeding: spread initial centroids by D²-weighted sampling.
    fn kmeans_plus_plus(&self, points: &[Vec<f32>], rng: &mut u64) -> Vec<Vec<f32>> {
        let mut centroids = Vec::with_capacity(self.k);
        // first centroid: uniform random point
        let first = (next_u64(rng) % points.len() as u64) as usize;
        centroids.push(points[first].clone());

        while centroids.len() < self.k {
            // squared distance of each point to its nearest chosen centroid
            let d2: Vec<f64> = points.iter().map(|p| nearest(p, &centroids).1).collect();
            let total: f64 = d2.iter().sum();
            if total <= 0.0 {
                // all remaining points coincide with centroids: pad with a point
                centroids.push(points[centroids.len() % points.len()].clone());
                continue;
            }
            // sample proportional to d2
            let target = (next_unit(rng)) * total;
            let mut acc = 0.0;
            let mut chosen = points.len() - 1;
            for (i, &w) in d2.iter().enumerate() {
                acc += w;
                if acc >= target {
                    chosen = i;
                    break;
                }
            }
            centroids.push(points[chosen].clone());
        }
        centroids
    }
}

impl Clustering {
    /// The number of clusters.
    pub fn k(&self) -> usize {
        self.centroids.len()
    }

    /// Assign a new point to its nearest learned centroid.
    pub fn predict(&self, point: &[f32]) -> usize {
        nearest(point, &self.centroids).0
    }

    /// The number of points assigned to each cluster (parallel to `centroids`).
    pub fn cluster_sizes(&self) -> Vec<usize> {
        let mut sizes = vec![0usize; self.centroids.len()];
        for &a in &self.assignments {
            sizes[a] += 1;
        }
        sizes
    }
}

/// Squared Euclidean distance.
fn dist2(a: &[f32], b: &[f32]) -> f64 {
    a.iter()
        .zip(b.iter())
        .map(|(&x, &y)| {
            let d = x as f64 - y as f64;
            d * d
        })
        .sum()
}

/// The index and squared distance of the nearest centroid to `p`.
fn nearest(p: &[f32], centroids: &[Vec<f32>]) -> (usize, f64) {
    let mut best = 0usize;
    let mut best_d = f64::INFINITY;
    for (i, c) in centroids.iter().enumerate() {
        let d = dist2(p, c);
        if d < best_d {
            best_d = d;
            best = i;
        }
    }
    (best, best_d)
}

fn next_u64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

fn next_unit(state: &mut u64) -> f64 {
    (next_u64(state) >> 11) as f64 / (1u64 << 53) as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Three well-separated 2-D blobs.
    fn blobs() -> Vec<Vec<f32>> {
        let mut pts = Vec::new();
        // around (0,0)
        for d in [-0.1, 0.0, 0.1] {
            pts.push(vec![d, d]);
        }
        // around (10,10)
        for d in [-0.1, 0.0, 0.1] {
            pts.push(vec![10.0 + d, 10.0 + d]);
        }
        // around (0,10)
        for d in [-0.1, 0.0, 0.1] {
            pts.push(vec![d, 10.0 + d]);
        }
        pts
    }

    #[test]
    fn rejects_bad_input() {
        let km = KMeans::new(0, 10, 1);
        assert_eq!(km.fit(&[vec![1.0]]), Err(KMeansError::ZeroK));
        let km = KMeans::new(3, 10, 1);
        assert!(matches!(
            km.fit(&[vec![1.0], vec![2.0]]),
            Err(KMeansError::TooFewPoints { k: 3, n: 2 })
        ));
        assert_eq!(km.fit(&[]), Err(KMeansError::BadShape));
        assert_eq!(
            KMeans::new(1, 10, 1).fit(&[vec![1.0], vec![1.0, 2.0]]),
            Err(KMeansError::BadShape)
        );
    }

    #[test]
    fn separates_well_separated_blobs() {
        let pts = blobs();
        let km = KMeans::new(3, 50, 42);
        let c = km.fit(&pts).unwrap();
        // points 0-2, 3-5, 6-8 should each be one cluster
        assert_eq!(c.assignments[0], c.assignments[1]);
        assert_eq!(c.assignments[1], c.assignments[2]);
        assert_eq!(c.assignments[3], c.assignments[4]);
        assert_eq!(c.assignments[6], c.assignments[8]);
        // the three blobs are in three different clusters
        assert_ne!(c.assignments[0], c.assignments[3]);
        assert_ne!(c.assignments[0], c.assignments[6]);
        assert_ne!(c.assignments[3], c.assignments[6]);
        assert_eq!(c.cluster_sizes().iter().sum::<usize>(), 9);
        // inertia is tiny since blobs are tight
        assert!(c.inertia < 1.0, "inertia {}", c.inertia);
    }

    #[test]
    fn predict_assigns_new_points() {
        let pts = blobs();
        let c = KMeans::new(3, 50, 7).fit(&pts).unwrap();
        // a point near (10,10) should land in the same cluster as point 3
        let near_blob2 = c.predict(&[10.05, 9.95]);
        assert_eq!(near_blob2, c.assignments[3]);
        // a point near origin → same as point 0
        assert_eq!(c.predict(&[0.02, -0.02]), c.assignments[0]);
    }

    #[test]
    fn k_equals_one_centroid_is_the_mean() {
        let pts = vec![
            vec![0.0f32, 0.0],
            vec![2.0, 0.0],
            vec![0.0, 2.0],
            vec![2.0, 2.0],
        ];
        let c = KMeans::new(1, 10, 1).fit(&pts).unwrap();
        assert_eq!(c.k(), 1);
        // mean is (1,1)
        assert!((c.centroids[0][0] - 1.0).abs() < 1e-6);
        assert!((c.centroids[0][1] - 1.0).abs() < 1e-6);
        assert!(c.assignments.iter().all(|&a| a == 0));
    }

    #[test]
    fn k_equals_n_gives_zero_inertia() {
        let pts = blobs();
        let n = pts.len();
        let c = KMeans::new(n, 50, 3).fit(&pts).unwrap();
        // each point its own cluster → inertia ~0
        assert!(c.inertia < 1e-6, "inertia {}", c.inertia);
    }

    #[test]
    fn deterministic_for_a_seed() {
        let pts = blobs();
        let a = KMeans::new(3, 50, 99).fit(&pts).unwrap();
        let b = KMeans::new(3, 50, 99).fit(&pts).unwrap();
        assert_eq!(a.assignments, b.assignments);
        assert_eq!(a.centroids, b.centroids);
    }

    #[test]
    fn converges_before_max_iters_on_easy_data() {
        let pts = blobs();
        let c = KMeans::new(3, 100, 5).fit(&pts).unwrap();
        // well-separated blobs converge quickly, well under the cap
        assert!(c.iterations < 100, "took {} iters", c.iterations);
    }

    #[test]
    fn serde_round_trip() {
        let pts = blobs();
        let c = KMeans::new(3, 50, 1).fit(&pts).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: Clustering = serde_json::from_str(&j).unwrap();
        // assignments and centroids round-trip exactly; inertia is f64 and may
        // shift by a ULP through JSON, so compare it with tolerance.
        assert_eq!(c.assignments, back.assignments);
        assert_eq!(c.centroids, back.centroids);
        assert!((c.inertia - back.inertia).abs() < 1e-9);
    }
}
