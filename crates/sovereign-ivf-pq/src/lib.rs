//! `sovereign-ivf-pq` — compressed vector search at memory scales nothing else reaches.
//!
//! HNSW and plain IVF both keep every full vector in memory; at a billion vectors
//! that is terabytes. **IVF-PQ** (FAISS's IVFADC) is the method that fits the same
//! index in a fraction of the space by storing each vector as a handful of bytes,
//! at the cost of approximate distances.
//!
//! It layers two ideas this workspace already has. An **IVF coarse quantizer**
//! (k-means) partitions the space into cells; a vector is filed in its nearest
//! cell. But instead of storing the vector, IVF-PQ stores the **product-quantized
//! residual** — the offset of the vector from its cell centroid, compressed by a
//! [product quantizer][sovereign_product_quantization] into one byte per subspace.
//! Residuals are small and cluster tightly, so the quantizer reconstructs them
//! well, and a `dim`-dimensional float vector collapses to `m` bytes.
//!
//! Search is **asymmetric distance computation**. For each of the `n_probe`
//! nearest cells, the query's residual against that centroid is turned into a
//! lookup table — for every subspace, the distance from the query subvector to each
//! codebook centroid — and each stored code's distance is then a sum of `m` table
//! reads, no decompression. The probed cells' candidates are ranked by that
//! approximate distance.
//!
//! [`IvfPqIndex::build`] trains both quantizers and encodes every vector;
//! [`IvfPqIndex::add`] encodes one more; [`IvfPqIndex::search`] returns the `k`
//! nearest by approximate L2 distance; [`IvfPqIndex::reconstruct`] recovers a
//! vector's lossy approximation (centroid + decoded residual). The index is
//! Euclidean by construction — residual quantization is an L2 method.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_kmeans::KMeans;
use sovereign_product_quantization::ProductQuantizer;

/// Schema version of the IVF-PQ surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// IVF-PQ build/search parameters.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct IvfPqConfig {
    /// Number of coarse-quantizer cells / posting lists.
    pub num_lists: usize,
    /// How many of the nearest cells to scan per query.
    pub n_probe: usize,
    /// Product-quantizer subspaces `m` (the code length in bytes). `dim` must be
    /// divisible by this.
    pub pq_subspaces: usize,
    /// Centroids per PQ subspace codebook (`1..=256`, one byte per code).
    pub pq_centroids: usize,
    /// k-means iteration cap for the coarse quantizer.
    pub max_iters: usize,
    /// Seed for both quantizers — reproducible builds.
    pub seed: u64,
}

impl Default for IvfPqConfig {
    fn default() -> Self {
        Self {
            num_lists: 16,
            n_probe: 4,
            pq_subspaces: 4,
            pq_centroids: 64,
            max_iters: 25,
            seed: 0xC0DE,
        }
    }
}

/// A neighbour result: stored item index and its approximate distance.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Neighbor {
    /// Index of the stored vector (its insertion order).
    pub index: usize,
    /// Approximate squared-Euclidean distance to the query (via ADC).
    pub distance: f64,
}

/// Errors from building or extending an IVF-PQ index.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum IvfPqError {
    /// No vectors supplied.
    NoVectors,
    /// `num_lists` was zero.
    ZeroLists,
    /// Vectors empty or of inconsistent length.
    RaggedVectors,
    /// Fewer vectors than coarse cells, or than PQ centroids — cannot train.
    TooFewVectors {
        /// Vectors supplied.
        have: usize,
        /// Minimum required (max of `num_lists` and `pq_centroids`).
        need: usize,
    },
    /// `dim` is not divisible by `pq_subspaces`.
    DimNotDivisible {
        /// Vector dimension.
        dim: usize,
        /// Requested subspaces.
        subspaces: usize,
    },
    /// `pq_centroids` is outside `1..=256`.
    BadCentroids(usize),
    /// A vector handed to `add` had the wrong dimension.
    DimMismatch {
        /// Expected dimension.
        expected: usize,
        /// Actual length.
        got: usize,
    },
}

impl std::fmt::Display for IvfPqError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            IvfPqError::NoVectors => write!(f, "no vectors to train on"),
            IvfPqError::ZeroLists => write!(f, "num_lists must be at least 1"),
            IvfPqError::RaggedVectors => write!(f, "vectors are empty or of inconsistent length"),
            IvfPqError::TooFewVectors { have, need } => {
                write!(f, "too few vectors: have {have}, need at least {need}")
            }
            IvfPqError::DimNotDivisible { dim, subspaces } => {
                write!(f, "dimension {dim} not divisible by {subspaces} subspaces")
            }
            IvfPqError::BadCentroids(k) => write!(f, "pq_centroids must be in 1..=256, got {k}"),
            IvfPqError::DimMismatch { expected, got } => {
                write!(f, "dimension mismatch: expected {expected}, got {got}")
            }
        }
    }
}
impl std::error::Error for IvfPqError {}

/// An IVF-PQ index: coarse centroids, a residual product quantizer, and per-cell
/// posting lists of compressed codes.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IvfPqIndex {
    config: IvfPqConfig,
    dim: usize,
    /// Coarse-quantizer centroids (one per cell).
    centroids: Vec<Vec<f32>>,
    /// The product quantizer trained on residuals.
    pq: ProductQuantizer,
    /// `lists[c]` = ids filed in cell `c`.
    lists: Vec<Vec<u32>>,
    /// Cell each id belongs to (parallel to insertion order).
    cell_of: Vec<u32>,
    /// PQ codes for each id (the encoded residual).
    codes_of: Vec<Vec<u8>>,
}

fn l2(a: &[f32], b: &[f32]) -> f32 {
    a.iter()
        .zip(b)
        .map(|(x, y)| {
            let d = x - y;
            d * d
        })
        .sum()
}

fn residual(v: &[f32], centroid: &[f32]) -> Vec<f32> {
    v.iter().zip(centroid).map(|(x, c)| x - c).collect()
}

impl IvfPqIndex {
    /// Train the coarse quantizer and residual product quantizer on `vectors` and
    /// encode every vector into its cell.
    pub fn build(vectors: &[Vec<f32>], config: IvfPqConfig) -> Result<Self, IvfPqError> {
        if config.num_lists == 0 {
            return Err(IvfPqError::ZeroLists);
        }
        if !(1..=256).contains(&config.pq_centroids) {
            return Err(IvfPqError::BadCentroids(config.pq_centroids));
        }
        if vectors.is_empty() {
            return Err(IvfPqError::NoVectors);
        }
        let dim = vectors[0].len();
        if dim == 0 || vectors.iter().any(|v| v.len() != dim) {
            return Err(IvfPqError::RaggedVectors);
        }
        if config.pq_subspaces == 0 || dim % config.pq_subspaces != 0 {
            return Err(IvfPqError::DimNotDivisible {
                dim,
                subspaces: config.pq_subspaces,
            });
        }
        let need = config.num_lists.max(config.pq_centroids);
        if vectors.len() < need {
            return Err(IvfPqError::TooFewVectors {
                have: vectors.len(),
                need,
            });
        }

        // 1. coarse quantizer.
        let coarse = KMeans::new(config.num_lists, config.max_iters, config.seed)
            .fit(vectors)
            .map_err(|_| IvfPqError::RaggedVectors)?;
        let centroids = coarse.centroids;

        // 2. residuals of every vector from its assigned centroid.
        let residuals: Vec<Vec<f32>> = vectors
            .iter()
            .zip(&coarse.assignments)
            .map(|(v, &c)| residual(v, &centroids[c]))
            .collect();

        // 3. one product quantizer over all residuals.
        let pq = ProductQuantizer::train(
            &residuals,
            config.pq_subspaces,
            config.pq_centroids,
            // a fixed offset so the residual PQ does not share the coarse seed.
            config.seed ^ 0x5E50_1D5E_A11D_0000,
        )
        .map_err(|_| IvfPqError::RaggedVectors)?;

        // 4. encode and file.
        let mut lists = vec![Vec::new(); config.num_lists];
        let mut cell_of = Vec::with_capacity(vectors.len());
        let mut codes_of = Vec::with_capacity(vectors.len());
        for (id, (&cell, res)) in coarse.assignments.iter().zip(&residuals).enumerate() {
            let codes = pq.encode(res).map_err(|_| IvfPqError::RaggedVectors)?;
            lists[cell].push(id as u32);
            cell_of.push(cell as u32);
            codes_of.push(codes);
        }

        Ok(Self {
            config,
            dim,
            centroids,
            pq,
            lists,
            cell_of,
            codes_of,
        })
    }

    /// Number of stored vectors.
    pub fn len(&self) -> usize {
        self.codes_of.len()
    }
    /// Whether the index holds no vectors.
    pub fn is_empty(&self) -> bool {
        self.codes_of.is_empty()
    }
    /// Vector dimension.
    pub fn dim(&self) -> usize {
        self.dim
    }
    /// Number of cells.
    pub fn num_lists(&self) -> usize {
        self.centroids.len()
    }
    /// Bytes per stored vector (the PQ code length).
    pub fn code_len(&self) -> usize {
        self.config.pq_subspaces
    }
    /// Posting-list sizes by cell.
    pub fn list_sizes(&self) -> Vec<usize> {
        self.lists.iter().map(|l| l.len()).collect()
    }

    /// Index of the centroid nearest `v`.
    fn nearest_cell(&self, v: &[f32]) -> usize {
        let mut best = 0;
        let mut best_d = f32::INFINITY;
        for (c, cent) in self.centroids.iter().enumerate() {
            let d = l2(v, cent);
            if d < best_d {
                best_d = d;
                best = c;
            }
        }
        best
    }

    /// File one more vector after the index is built (using the already-trained
    /// quantizers). Returns its assigned item index.
    pub fn add(&mut self, vector: &[f32]) -> Result<usize, IvfPqError> {
        if vector.len() != self.dim {
            return Err(IvfPqError::DimMismatch {
                expected: self.dim,
                got: vector.len(),
            });
        }
        let cell = self.nearest_cell(vector);
        let res = residual(vector, &self.centroids[cell]);
        let codes = self
            .pq
            .encode(&res)
            .map_err(|_| IvfPqError::RaggedVectors)?;
        let id = self.codes_of.len() as u32;
        self.lists[cell].push(id);
        self.cell_of.push(cell as u32);
        self.codes_of.push(codes);
        Ok(id as usize)
    }

    /// Find the `k` nearest stored vectors to `query` by asymmetric distance over
    /// the `n_probe` nearest cells. Returns nearest-first; an empty index or a
    /// dimension mismatch yields an empty result.
    pub fn search(&self, query: &[f32], k: usize) -> Vec<Neighbor> {
        if self.is_empty() || k == 0 || query.len() != self.dim {
            return Vec::new();
        }
        // rank cells by centroid distance, probe the nearest.
        let mut cells: Vec<(f32, usize)> = self
            .centroids
            .iter()
            .enumerate()
            .map(|(c, cent)| (l2(query, cent), c))
            .collect();
        cells.sort_by(|a, b| a.0.total_cmp(&b.0));
        let probe = self.config.n_probe.clamp(1, self.centroids.len());

        let mut found: Vec<Neighbor> = Vec::new();
        for &(_, cell) in cells.iter().take(probe) {
            if self.lists[cell].is_empty() {
                continue;
            }
            // asymmetric distance: build the lookup table from the query's residual
            // against THIS centroid, then sum table reads per stored code.
            let res_q = residual(query, &self.centroids[cell]);
            let table = match self.pq.distance_table(&res_q) {
                Ok(t) => t,
                Err(_) => continue,
            };
            for &id in &self.lists[cell] {
                let d = self
                    .pq
                    .asymmetric_distance(&table, &self.codes_of[id as usize]);
                found.push(Neighbor {
                    index: id as usize,
                    distance: d,
                });
            }
        }
        found.sort_by(|a, b| {
            a.distance
                .total_cmp(&b.distance)
                .then(a.index.cmp(&b.index))
        });
        found.truncate(k);
        found
    }

    /// Recover the lossy approximation of vector `index`: its cell centroid plus the
    /// decoded residual. `None` if the index is out of range.
    pub fn reconstruct(&self, index: usize) -> Option<Vec<f32>> {
        let codes = self.codes_of.get(index)?;
        let cell = self.cell_of[index] as usize;
        let res = self.pq.decode(codes);
        Some(
            self.centroids[cell]
                .iter()
                .zip(&res)
                .map(|(c, r)| c + r)
                .collect(),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Rng(u64);
    impl Rng {
        fn unit(&mut self) -> f32 {
            self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = self.0;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z ^= z >> 31;
            ((z >> 11) as f32) / ((1u64 << 53) as f32)
        }
    }

    /// Deterministic clustered dataset: `blobs` tight gaussians in `dim` dims.
    fn clustered(blobs: usize, per: usize, dim: usize, seed: u64) -> Vec<Vec<f32>> {
        let mut rng = Rng(seed);
        let mut data = Vec::new();
        let mut centers = Vec::new();
        for _ in 0..blobs {
            centers.push((0..dim).map(|_| rng.unit() * 20.0).collect::<Vec<f32>>());
        }
        for c in &centers {
            for _ in 0..per {
                data.push(c.iter().map(|x| x + rng.unit() * 1.5).collect());
            }
        }
        data
    }

    fn brute_topk(data: &[Vec<f32>], q: &[f32], k: usize) -> Vec<usize> {
        let mut d: Vec<(f32, usize)> = data
            .iter()
            .enumerate()
            .map(|(i, v)| (l2(v, q), i))
            .collect();
        d.sort_by(|a, b| a.0.total_cmp(&b.0));
        d.into_iter().take(k).map(|x| x.1).collect()
    }

    #[test]
    fn build_stores_compressed_codes() {
        let data = clustered(8, 40, 8, 1);
        let idx = IvfPqIndex::build(&data, IvfPqConfig::default()).unwrap();
        assert_eq!(idx.len(), 320);
        assert_eq!(idx.code_len(), 4); // 4 bytes per vector, not 8 floats
        let total: usize = idx.list_sizes().iter().sum();
        assert_eq!(total, 320);
    }

    #[test]
    fn high_recall_on_clustered_data() {
        let data = clustered(10, 50, 8, 7);
        let cfg = IvfPqConfig {
            num_lists: 10,
            n_probe: 4,
            pq_subspaces: 4,
            pq_centroids: 64,
            max_iters: 30,
            seed: 3,
        };
        let idx = IvfPqIndex::build(&data, cfg).unwrap();
        let mut hits = 0;
        let mut total = 0;
        for qi in (0..data.len()).step_by(11) {
            let q = &data[qi];
            let truth: std::collections::HashSet<usize> =
                brute_topk(&data, q, 5).into_iter().collect();
            for n in idx.search(q, 5) {
                if truth.contains(&n.index) {
                    hits += 1;
                }
            }
            total += 5;
        }
        let recall = hits as f64 / total as f64;
        assert!(recall > 0.7, "recall@5 = {recall}");
    }

    #[test]
    fn finds_query_itself_near_top() {
        let data = clustered(8, 40, 8, 5);
        let cfg = IvfPqConfig {
            num_lists: 8,
            n_probe: 8, // probe all cells
            ..IvfPqConfig::default()
        };
        let idx = IvfPqIndex::build(&data, cfg).unwrap();
        // a stored vector should retrieve itself within the top few results.
        for qi in [0, 50, 130, 250, 319] {
            let got: Vec<usize> = idx
                .search(&data[qi], 5)
                .into_iter()
                .map(|n| n.index)
                .collect();
            assert!(got.contains(&qi), "query {qi} not in top-5: {got:?}");
        }
    }

    #[test]
    fn results_sorted_by_distance() {
        let data = clustered(6, 40, 8, 9);
        let idx = IvfPqIndex::build(&data, IvfPqConfig::default()).unwrap();
        let r = idx.search(&data[10], 8);
        for w in r.windows(2) {
            assert!(w[0].distance <= w[1].distance);
        }
    }

    #[test]
    fn reconstruct_approximates_original() {
        let data = clustered(8, 50, 8, 2);
        let idx = IvfPqIndex::build(&data, IvfPqConfig::default()).unwrap();
        // reconstruction error should be small relative to vector magnitude.
        let mut err = 0.0f32;
        let mut mag = 0.0f32;
        for (i, v) in data.iter().enumerate() {
            let r = idx.reconstruct(i).unwrap();
            err += l2(v, &r).sqrt();
            mag += v.iter().map(|x| x * x).sum::<f32>().sqrt();
        }
        let rel = err / mag;
        assert!(rel < 0.2, "relative reconstruction error {rel}");
        assert!(idx.reconstruct(99999).is_none());
    }

    #[test]
    fn add_after_build() {
        let data = clustered(8, 40, 8, 4);
        let cfg = IvfPqConfig {
            n_probe: 8,
            ..IvfPqConfig::default()
        };
        let mut idx = IvfPqIndex::build(&data, cfg).unwrap();
        let newv: Vec<f32> = vec![100.0; 8];
        let id = idx.add(&newv).unwrap();
        assert_eq!(id, 320);
        assert_eq!(idx.len(), 321);
        // querying near the new vector retrieves it.
        let got: Vec<usize> = idx.search(&newv, 3).into_iter().map(|n| n.index).collect();
        assert!(got.contains(&320), "got {got:?}");
    }

    #[test]
    fn errors_on_bad_input() {
        assert_eq!(
            IvfPqIndex::build(&[], IvfPqConfig::default()),
            Err(IvfPqError::NoVectors)
        );
        // dim 7 not divisible by 4 subspaces.
        let data: Vec<Vec<f32>> = (0..100).map(|i| vec![i as f32; 7]).collect();
        assert_eq!(
            IvfPqIndex::build(&data, IvfPqConfig::default()),
            Err(IvfPqError::DimNotDivisible {
                dim: 7,
                subspaces: 4
            })
        );
        // too few vectors (need max(num_lists=16, pq_centroids=64) = 64).
        let few = clustered(2, 5, 8, 1); // 10 vectors
        assert_eq!(
            IvfPqIndex::build(&few, IvfPqConfig::default()),
            Err(IvfPqError::TooFewVectors { have: 10, need: 64 })
        );
    }

    #[test]
    fn empty_or_mismatched_query() {
        let data = clustered(8, 40, 8, 1);
        let idx = IvfPqIndex::build(&data, IvfPqConfig::default()).unwrap();
        assert!(idx.search(&[1.0; 7], 5).is_empty()); // wrong dim
        assert!(idx.search(&[1.0; 8], 0).is_empty()); // k = 0
    }

    #[test]
    fn deterministic_build() {
        let data = clustered(8, 40, 8, 6);
        let a = IvfPqIndex::build(&data, IvfPqConfig::default()).unwrap();
        let b = IvfPqIndex::build(&data, IvfPqConfig::default()).unwrap();
        let q = &data[33];
        assert_eq!(a.search(q, 5), b.search(q, 5));
    }

    #[test]
    fn serde_round_trip() {
        let data = clustered(8, 40, 8, 8);
        let idx = IvfPqIndex::build(&data, IvfPqConfig::default()).unwrap();
        let j = serde_json::to_string(&idx).unwrap();
        let back: IvfPqIndex = serde_json::from_str(&j).unwrap();
        let q = &data[17];
        assert_eq!(idx.search(q, 5), back.search(q, 5));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
