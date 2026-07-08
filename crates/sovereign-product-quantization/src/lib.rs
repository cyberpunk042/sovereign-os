//! `sovereign-product-quantization` — compress vectors, approximate distance fast.
//!
//! Storing millions of float embeddings is expensive, and scanning them all for
//! the nearest is slow. **Product quantization** (Jégou, Douze, Schmid) attacks
//! both. Split each `D`-dimensional vector into `m` contiguous subvectors of
//! `D/m` dimensions. Run k-means *independently* in each subspace to learn a
//! small codebook of `k` centroids (here `k ≤ 256`, so a code is one byte). A
//! vector is then encoded as `m` bytes — the index of the nearest centroid in
//! each subspace — a 32-float vector in, say, 8 bytes out.
//!
//! The payoff is distance computation. To compare a *query* (kept in full
//! precision) against the compressed database, precompute, once per query, a
//! `m × k` table of squared distances from each query subvector to every centroid
//! in that subspace. The approximate squared distance to any encoded vector is
//! then just the sum of `m` table lookups — no decompression, one add per
//! subspace. This is *asymmetric distance computation*, the accurate PQ variant
//! (the query is not quantized).
//!
//! Training delegates each subspace to [`sovereign_kmeans`], so the codebooks are
//! deterministic for a given seed. [`ProductQuantizer::encode`] compresses a
//! vector, [`ProductQuantizer::decode`] reconstructs an approximation, and
//! [`ProductQuantizer::distance_table`] + [`ProductQuantizer::asymmetric_distance`]
//! do the fast query-time distance.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_kmeans::KMeans;
use thiserror::Error;

/// Schema version of the product-quantization surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors training or using a quantizer.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum PqError {
    /// The vector dimension is not divisible by the number of subspaces.
    #[error("dimension {dim} is not divisible by m={m} subspaces")]
    NotDivisible {
        /// Vector dimension.
        dim: usize,
        /// Requested subspaces.
        m: usize,
    },
    /// `k` (centroids per subspace) must be in `1..=256` so a code fits in a byte.
    #[error("k must be in 1..=256, got {0}")]
    BadK(usize),
    /// Not enough training vectors, empty input, or ragged dimensions.
    #[error("need at least k training vectors of a consistent, non-zero dimension")]
    BadTraining,
    /// A vector handed to encode/decode had the wrong dimension.
    #[error("expected dimension {expected}, got {got}")]
    BadDimension {
        /// Expected dimension.
        expected: usize,
        /// Actual dimension.
        got: usize,
    },
}

/// A trained product quantizer.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProductQuantizer {
    dim: usize,
    m: usize,
    sub_dim: usize,
    /// `m` codebooks, each `k` centroids of length `sub_dim`.
    codebooks: Vec<Vec<Vec<f32>>>,
}

impl ProductQuantizer {
    /// Train a quantizer over `vectors` with `m` subspaces and `k` centroids per
    /// subspace, seeded with `seed`.
    pub fn train(vectors: &[Vec<f32>], m: usize, k: usize, seed: u64) -> Result<Self, PqError> {
        if !(1..=256).contains(&k) {
            return Err(PqError::BadK(k));
        }
        if vectors.is_empty() || vectors[0].is_empty() {
            return Err(PqError::BadTraining);
        }
        let dim = vectors[0].len();
        if vectors.iter().any(|v| v.len() != dim) {
            return Err(PqError::BadTraining);
        }
        if m == 0 || dim % m != 0 {
            return Err(PqError::NotDivisible { dim, m });
        }
        if vectors.len() < k {
            return Err(PqError::BadTraining);
        }
        let sub_dim = dim / m;

        let mut codebooks = Vec::with_capacity(m);
        for s in 0..m {
            // gather the s-th subvector of every training vector
            let sub: Vec<Vec<f32>> = vectors
                .iter()
                .map(|v| v[s * sub_dim..(s + 1) * sub_dim].to_vec())
                .collect();
            // a distinct but deterministic seed per subspace
            let km = KMeans::new(k, 50, seed.wrapping_add(s as u64 * 0x9E37));
            let clustering = km.fit(&sub).map_err(|_| PqError::BadTraining)?;
            codebooks.push(clustering.centroids);
        }

        Ok(Self {
            dim,
            m,
            sub_dim,
            codebooks,
        })
    }

    /// The full vector dimension.
    pub fn dim(&self) -> usize {
        self.dim
    }

    /// The number of subspaces.
    pub fn subspaces(&self) -> usize {
        self.m
    }

    /// The number of centroids per subspace codebook.
    pub fn codebook_size(&self) -> usize {
        self.codebooks[0].len()
    }

    fn check_dim(&self, v: &[f32]) -> Result<(), PqError> {
        if v.len() != self.dim {
            return Err(PqError::BadDimension {
                expected: self.dim,
                got: v.len(),
            });
        }
        Ok(())
    }

    /// Encode `vector` to `m` codes (one byte per subspace).
    pub fn encode(&self, vector: &[f32]) -> Result<Vec<u8>, PqError> {
        self.check_dim(vector)?;
        let mut codes = Vec::with_capacity(self.m);
        for s in 0..self.m {
            let sub = &vector[s * self.sub_dim..(s + 1) * self.sub_dim];
            let mut best = 0usize;
            let mut best_d = f64::INFINITY;
            for (c, centroid) in self.codebooks[s].iter().enumerate() {
                let d = dist2(sub, centroid);
                if d < best_d {
                    best_d = d;
                    best = c;
                }
            }
            codes.push(best as u8);
        }
        Ok(codes)
    }

    /// Reconstruct an approximate vector from its codes (concatenate the chosen
    /// centroids).
    pub fn decode(&self, codes: &[u8]) -> Vec<f32> {
        let mut out = Vec::with_capacity(self.dim);
        for (s, &code) in codes.iter().enumerate().take(self.m) {
            out.extend_from_slice(&self.codebooks[s][code as usize]);
        }
        out
    }

    /// Precompute, for a full-precision `query`, the `m × k` table of squared
    /// distances from each query subvector to every centroid in that subspace.
    pub fn distance_table(&self, query: &[f32]) -> Result<Vec<Vec<f64>>, PqError> {
        self.check_dim(query)?;
        let mut table = Vec::with_capacity(self.m);
        for s in 0..self.m {
            let sub = &query[s * self.sub_dim..(s + 1) * self.sub_dim];
            let row: Vec<f64> = self.codebooks[s].iter().map(|c| dist2(sub, c)).collect();
            table.push(row);
        }
        Ok(table)
    }

    /// Approximate squared distance from a query (via its [`distance_table`]) to
    /// an encoded vector: the sum of one table lookup per subspace.
    ///
    /// [`distance_table`]: Self::distance_table
    pub fn asymmetric_distance(&self, table: &[Vec<f64>], codes: &[u8]) -> f64 {
        codes
            .iter()
            .enumerate()
            .take(self.m)
            .map(|(s, &code)| table[s][code as usize])
            .sum()
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

#[cfg(test)]
mod tests {
    use super::*;

    /// Deterministic synthetic vectors: `n` points in `dim` dimensions drawn from
    /// a few cluster centers so quantization has structure to capture.
    fn data(n: usize, dim: usize) -> Vec<Vec<f32>> {
        let mut rng = 0x1234_5678u64;
        let mut next = || {
            rng = rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = rng;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            ((z ^ (z >> 31)) >> 40) as f32 / (1u64 << 24) as f32
        };
        (0..n)
            .map(|i| {
                let center = (i % 4) as f32 * 5.0;
                (0..dim).map(|_| center + next()).collect()
            })
            .collect()
    }

    #[test]
    fn rejects_bad_parameters() {
        let v = data(50, 8);
        assert!(matches!(
            ProductQuantizer::train(&v, 3, 16, 1),
            Err(PqError::NotDivisible { dim: 8, m: 3 })
        ));
        assert!(matches!(
            ProductQuantizer::train(&v, 4, 0, 1),
            Err(PqError::BadK(0))
        ));
        assert!(matches!(
            ProductQuantizer::train(&v, 4, 300, 1),
            Err(PqError::BadK(300))
        ));
        assert_eq!(
            ProductQuantizer::train(&[], 4, 16, 1),
            Err(PqError::BadTraining)
        );
    }

    #[test]
    fn encode_produces_one_code_per_subspace() {
        let v = data(100, 8);
        let pq = ProductQuantizer::train(&v, 4, 16, 7).unwrap();
        let codes = pq.encode(&v[0]).unwrap();
        assert_eq!(codes.len(), 4);
        assert_eq!(pq.subspaces(), 4);
        assert_eq!(pq.codebook_size(), 16);
    }

    #[test]
    fn decode_approximates_the_original() {
        let v = data(200, 8);
        let pq = ProductQuantizer::train(&v, 4, 32, 3).unwrap();
        // reconstruction error should be small relative to the vector magnitude
        let codes = pq.encode(&v[10]).unwrap();
        let recon = pq.decode(&codes);
        assert_eq!(recon.len(), 8);
        let err = dist2(&v[10], &recon).sqrt();
        let mag = dist2(&v[10], &[0.0; 8]).sqrt();
        assert!(err < 0.25 * mag.max(1.0), "recon err {err} vs mag {mag}");
    }

    #[test]
    fn asymmetric_distance_tracks_true_distance() {
        let v = data(300, 8);
        let pq = ProductQuantizer::train(&v, 4, 32, 11).unwrap();
        let query = v[0].clone();
        let table = pq.distance_table(&query).unwrap();

        // the encoded copy of the query itself should be among the closest
        let self_codes = pq.encode(&query).unwrap();
        let self_approx = pq.asymmetric_distance(&table, &self_codes);

        // a far-away vector (different cluster) should score much larger
        let far = v.iter().find(|x| dist2(&query, x) > 50.0).unwrap().clone();
        let far_codes = pq.encode(&far).unwrap();
        let far_approx = pq.asymmetric_distance(&table, &far_codes);

        assert!(
            self_approx < far_approx,
            "self {self_approx} far {far_approx}"
        );
        // approximate self-distance is small
        assert!(self_approx < 1.0, "self approx {self_approx}");
    }

    #[test]
    fn ranking_agrees_with_exact_for_clear_cases() {
        let v = data(300, 16);
        let pq = ProductQuantizer::train(&v, 8, 64, 5).unwrap();
        let query = v[0].clone();
        let table = pq.distance_table(&query).unwrap();

        // pick a near and a far database vector by exact distance, check PQ agrees
        let mut exact: Vec<(usize, f64)> = v
            .iter()
            .enumerate()
            .map(|(i, x)| (i, dist2(&query, x)))
            .collect();
        exact.sort_by(|a, b| a.1.total_cmp(&b.1));
        let near = exact[1].0; // closest other than itself
        let far = exact[exact.len() - 1].0;

        let dn = pq.asymmetric_distance(&table, &pq.encode(&v[near]).unwrap());
        let df = pq.asymmetric_distance(&table, &pq.encode(&v[far]).unwrap());
        assert!(dn < df, "near {dn} should be < far {df}");
    }

    #[test]
    fn encode_wrong_dimension_errors() {
        let v = data(50, 8);
        let pq = ProductQuantizer::train(&v, 4, 16, 1).unwrap();
        assert!(matches!(
            pq.encode(&[1.0, 2.0, 3.0]),
            Err(PqError::BadDimension {
                expected: 8,
                got: 3
            })
        ));
    }

    #[test]
    fn deterministic_for_a_seed() {
        let v = data(120, 8);
        let a = ProductQuantizer::train(&v, 4, 16, 42).unwrap();
        let b = ProductQuantizer::train(&v, 4, 16, 42).unwrap();
        assert_eq!(a, b);
        assert_eq!(a.encode(&v[5]).unwrap(), b.encode(&v[5]).unwrap());
    }

    #[test]
    fn serde_round_trip() {
        let v = data(80, 8);
        let pq = ProductQuantizer::train(&v, 4, 16, 9).unwrap();
        let j = serde_json::to_string(&pq).unwrap();
        let back: ProductQuantizer = serde_json::from_str(&j).unwrap();
        assert_eq!(pq, back);
        assert_eq!(back.encode(&v[0]).unwrap(), pq.encode(&v[0]).unwrap());
    }
}
