//! `sovereign-ivf` — inverted-file approximate nearest-neighbour search.
//!
//! The other way to make vector search sub-linear (the graph-based way being
//! HNSW) is to **partition** the space and only look in the right neighbourhood.
//! That is the **IVF** (inverted file) index used throughout FAISS-scale systems.
//!
//! A k-means **coarse quantizer** carves the vectors into `num_lists` Voronoi
//! cells; each stored vector is filed into the posting list of its nearest
//! centroid. To search, you do not scan every vector — you find the `n_probe`
//! centroids closest to the query and scan only those cells' posting lists,
//! ranking their members by exact distance. With thousands of cells and a handful
//! probed, that is a small fraction of the corpus, and `n_probe` is the dial: more
//! probes, higher recall, more work. It misses a true neighbour only when it sits
//! in a cell whose centroid was not among the probed ones — rare, and the price of
//! the speedup.
//!
//! [`IvfIndex::build`] trains the quantizer and files every vector in one shot;
//! [`IvfIndex::add`] files one more afterward. [`IvfIndex::search`] returns the `k`
//! nearest under the configured [`Metric`] (cosine vectors are normalized so only
//! direction matters). This is also the front half of **IVF-PQ**: swap the exact
//! re-ranking for product-quantized codes and the same partitioning scales to
//! billions.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_kmeans::KMeans;

/// Schema version of the IVF surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Distance function used to compare vectors.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum Metric {
    /// Squared Euclidean distance (monotone in Euclidean; no sqrt).
    #[default]
    L2,
    /// Cosine *distance* `1 - cos`; vectors are L2-normalized on insert.
    Cosine,
}

/// IVF build/search parameters.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct IvfConfig {
    /// Number of Voronoi cells / posting lists (the coarse-quantizer `k`).
    pub num_lists: usize,
    /// How many of the nearest cells to scan per query.
    pub n_probe: usize,
    /// k-means iteration cap when training the quantizer.
    pub max_iters: usize,
    /// Seed for the (k-means++) quantizer training — reproducible builds.
    pub seed: u64,
    /// Distance metric.
    pub metric: Metric,
}

impl Default for IvfConfig {
    fn default() -> Self {
        Self {
            num_lists: 16,
            n_probe: 4,
            max_iters: 25,
            seed: 0xA5A5,
            metric: Metric::L2,
        }
    }
}

/// A neighbour result: stored item index and its distance to the query.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Neighbor {
    /// Index of the stored vector (its insertion order).
    pub index: usize,
    /// Distance to the query under the configured [`Metric`].
    pub distance: f32,
}

/// Errors from building an IVF index.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum IvfError {
    /// No vectors were supplied to train on.
    NoVectors,
    /// Fewer training vectors than requested lists (cannot seed `num_lists` cells).
    TooFewVectors {
        /// Vectors supplied.
        have: usize,
        /// Lists requested.
        want: usize,
    },
    /// Vectors had inconsistent lengths or were empty.
    RaggedVectors,
    /// `num_lists` was zero.
    ZeroLists,
}

impl std::fmt::Display for IvfError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            IvfError::NoVectors => write!(f, "no vectors to train on"),
            IvfError::TooFewVectors { have, want } => {
                write!(
                    f,
                    "too few vectors: have {have}, need at least {want} lists"
                )
            }
            IvfError::RaggedVectors => write!(f, "vectors are empty or of inconsistent length"),
            IvfError::ZeroLists => write!(f, "num_lists must be at least 1"),
        }
    }
}
impl std::error::Error for IvfError {}

/// An inverted-file ANN index: a coarse quantizer plus per-cell posting lists.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IvfIndex {
    config: IvfConfig,
    dim: usize,
    /// Coarse-quantizer centroids (one per list).
    centroids: Vec<Vec<f32>>,
    /// `lists[c]` = ids of vectors filed in cell `c`.
    lists: Vec<Vec<u32>>,
    /// All stored vectors (normalized for cosine), indexed by id.
    vectors: Vec<Vec<f32>>,
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

fn normalize(v: &[f32]) -> Vec<f32> {
    let norm: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 0.0 {
        v.iter().map(|x| x / norm).collect()
    } else {
        v.to_vec()
    }
}

impl IvfIndex {
    /// Train a coarse quantizer on `vectors` and file each into its cell.
    pub fn build(vectors: &[Vec<f32>], config: IvfConfig) -> Result<Self, IvfError> {
        if config.num_lists == 0 {
            return Err(IvfError::ZeroLists);
        }
        if vectors.is_empty() {
            return Err(IvfError::NoVectors);
        }
        let dim = vectors[0].len();
        if dim == 0 || vectors.iter().any(|v| v.len() != dim) {
            return Err(IvfError::RaggedVectors);
        }
        if vectors.len() < config.num_lists {
            return Err(IvfError::TooFewVectors {
                have: vectors.len(),
                want: config.num_lists,
            });
        }

        let prepared: Vec<Vec<f32>> = match config.metric {
            Metric::L2 => vectors.to_vec(),
            Metric::Cosine => vectors.iter().map(|v| normalize(v)).collect(),
        };

        // train the coarse quantizer on the prepared vectors.
        let clustering = KMeans::new(config.num_lists, config.max_iters, config.seed)
            .fit(&prepared)
            // KMeans validates k>0, enough points, non-ragged — already checked above,
            // so a failure here means the same class of input problem.
            .map_err(|_| IvfError::RaggedVectors)?;

        let mut lists = vec![Vec::new(); config.num_lists];
        for (id, &cell) in clustering.assignments.iter().enumerate() {
            lists[cell].push(id as u32);
        }

        Ok(Self {
            config,
            dim,
            centroids: clustering.centroids,
            lists,
            vectors: prepared,
        })
    }

    /// Number of stored vectors.
    pub fn len(&self) -> usize {
        self.vectors.len()
    }
    /// Whether the index holds no vectors.
    pub fn is_empty(&self) -> bool {
        self.vectors.is_empty()
    }
    /// Vector dimension.
    pub fn dim(&self) -> usize {
        self.dim
    }
    /// Number of posting lists (Voronoi cells).
    pub fn num_lists(&self) -> usize {
        self.centroids.len()
    }
    /// The size of each posting list, indexed by cell.
    pub fn list_sizes(&self) -> Vec<usize> {
        self.lists.iter().map(|l| l.len()).collect()
    }

    /// Index of the centroid nearest `v` (under L2 over the prepared space).
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

    /// File one more vector into its nearest cell after the index is built.
    /// Returns its assigned item index, or `Err` on a dimension mismatch.
    pub fn add(&mut self, vector: &[f32]) -> Result<usize, IvfError> {
        if vector.len() != self.dim || self.dim == 0 {
            return Err(IvfError::RaggedVectors);
        }
        let v = match self.config.metric {
            Metric::L2 => vector.to_vec(),
            Metric::Cosine => normalize(vector),
        };
        let cell = self.nearest_cell(&v);
        let id = self.vectors.len() as u32;
        self.lists[cell].push(id);
        self.vectors.push(v);
        Ok(id as usize)
    }

    fn distance(&self, a: &[f32], b: &[f32]) -> f32 {
        match self.config.metric {
            Metric::L2 => l2(a, b),
            Metric::Cosine => 1.0 - a.iter().zip(b).map(|(x, y)| x * y).sum::<f32>(),
        }
    }

    /// Find the `k` nearest stored vectors to `query`, scanning the `n_probe`
    /// nearest cells. Returns nearest-first; an empty index or dimension mismatch
    /// yields an empty result.
    pub fn search(&self, query: &[f32], k: usize) -> Vec<Neighbor> {
        if self.is_empty() || k == 0 || query.len() != self.dim {
            return Vec::new();
        }
        let q = match self.config.metric {
            Metric::L2 => query.to_vec(),
            Metric::Cosine => normalize(query),
        };

        // rank cells by centroid distance, take the n_probe nearest.
        let mut cells: Vec<(f32, usize)> = self
            .centroids
            .iter()
            .enumerate()
            .map(|(c, cent)| (l2(&q, cent), c))
            .collect();
        cells.sort_by(|a, b| a.0.total_cmp(&b.0));
        let probe = self.config.n_probe.clamp(1, self.centroids.len());

        // gather candidates from the probed cells and rank by exact distance.
        let mut found: Vec<Neighbor> = Vec::new();
        for &(_, cell) in cells.iter().take(probe) {
            for &id in &self.lists[cell] {
                let d = self.distance(&q, &self.vectors[id as usize]);
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

    /// The stored vector at `index` (normalized for the cosine metric).
    pub fn vector(&self, index: usize) -> Option<&[f32]> {
        self.vectors.get(index).map(|v| v.as_slice())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// SplitMix64 for deterministic test data.
    struct Rng(u64);
    impl Rng {
        fn unit(&mut self) -> f32 {
            self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = self.0;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z = z ^ (z >> 31);
            ((z >> 11) as f32) / ((1u64 << 53) as f32)
        }
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
    fn build_files_every_vector() {
        let data: Vec<Vec<f32>> = (0..40).map(|i| vec![i as f32, (i % 5) as f32]).collect();
        let idx = IvfIndex::build(&data, IvfConfig::default()).unwrap();
        assert_eq!(idx.len(), 40);
        // every vector is in exactly one list.
        let total: usize = idx.list_sizes().iter().sum();
        assert_eq!(total, 40);
        assert_eq!(idx.num_lists(), 16);
    }

    #[test]
    fn finds_nearest_when_probing_all_cells() {
        // probing every cell makes IVF exact.
        let data: Vec<Vec<f32>> = (0..60)
            .map(|i| vec![(i % 8) as f32, (i / 8) as f32])
            .collect();
        let cfg = IvfConfig {
            num_lists: 8,
            n_probe: 8, // probe all → exact
            ..IvfConfig::default()
        };
        let idx = IvfIndex::build(&data, cfg).unwrap();
        for q in [[3.1, 2.0], [0.2, 6.8], [7.4, 4.4]] {
            let got = idx.search(&q, 1)[0].index;
            let want = brute_topk(&data, &q, 1)[0];
            assert_eq!(got, want, "query {q:?}");
        }
    }

    #[test]
    fn high_recall_with_modest_probe() {
        // clustered data: a few probes should recover most true neighbours.
        let mut rng = Rng(7);
        let mut data = Vec::new();
        // 6 gaussian-ish blobs.
        for c in 0..6 {
            let cx = (c % 3) as f32 * 10.0;
            let cy = (c / 3) as f32 * 10.0;
            for _ in 0..60 {
                data.push(vec![cx + rng.unit() * 2.0, cy + rng.unit() * 2.0]);
            }
        }
        let cfg = IvfConfig {
            num_lists: 12,
            n_probe: 4,
            max_iters: 30,
            seed: 1,
            metric: Metric::L2,
        };
        let idx = IvfIndex::build(&data, cfg).unwrap();
        let mut hits = 0;
        let mut total = 0;
        for qi in (0..data.len()).step_by(13) {
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
        assert!(recall > 0.85, "recall@5 = {recall}");
    }

    #[test]
    fn results_sorted_nearest_first() {
        let data: Vec<Vec<f32>> = (0..50).map(|i| vec![i as f32]).collect();
        let cfg = IvfConfig {
            num_lists: 5,
            n_probe: 5,
            ..IvfConfig::default()
        };
        let idx = IvfIndex::build(&data, cfg).unwrap();
        let r = idx.search(&[25.4], 6);
        for w in r.windows(2) {
            assert!(w[0].distance <= w[1].distance);
        }
        assert_eq!(r[0].index, 25);
    }

    #[test]
    fn cosine_metric_ignores_magnitude() {
        let data = vec![
            vec![1.0, 0.0],
            vec![0.0, 1.0],
            vec![-1.0, 0.0],
            vec![0.7, 0.7],
        ];
        let cfg = IvfConfig {
            num_lists: 2,
            n_probe: 2,
            metric: Metric::Cosine,
            ..IvfConfig::default()
        };
        let idx = IvfIndex::build(&data, cfg).unwrap();
        let r = idx.search(&[9.0, 0.1], 4); // long vector along +x
        assert_eq!(r[0].index, 0);
        assert_eq!(r.last().unwrap().index, 2); // opposite direction is farthest
    }

    #[test]
    fn add_after_build() {
        let data: Vec<Vec<f32>> = (0..20).map(|i| vec![i as f32, 0.0]).collect();
        let cfg = IvfConfig {
            num_lists: 4,
            n_probe: 4,
            ..IvfConfig::default()
        };
        let mut idx = IvfIndex::build(&data, cfg).unwrap();
        let id = idx.add(&[100.0, 0.0]).unwrap();
        assert_eq!(id, 20);
        assert_eq!(idx.len(), 21);
        // the new point is its own nearest neighbour for a nearby query.
        let r = idx.search(&[99.0, 0.0], 1);
        assert_eq!(r[0].index, 20);
    }

    #[test]
    fn errors_on_bad_input() {
        assert_eq!(
            IvfIndex::build(&[], IvfConfig::default()),
            Err(IvfError::NoVectors)
        );
        assert_eq!(
            IvfIndex::build(&[vec![1.0]], IvfConfig::default()),
            Err(IvfError::TooFewVectors { have: 1, want: 16 })
        );
        let ragged = vec![vec![1.0, 2.0], vec![3.0]];
        let cfg = IvfConfig {
            num_lists: 2,
            ..IvfConfig::default()
        };
        assert_eq!(IvfIndex::build(&ragged, cfg), Err(IvfError::RaggedVectors));
    }

    #[test]
    fn empty_or_mismatched_query() {
        let data: Vec<Vec<f32>> = (0..20).map(|i| vec![i as f32, 0.0]).collect();
        let idx = IvfIndex::build(&data, IvfConfig::default()).unwrap();
        assert!(idx.search(&[1.0, 2.0, 3.0], 5).is_empty()); // wrong dim
        assert!(idx.search(&[1.0, 2.0], 0).is_empty()); // k = 0
    }

    #[test]
    fn deterministic_build() {
        let data: Vec<Vec<f32>> = (0..40)
            .map(|i| vec![(i % 6) as f32, (i / 6) as f32])
            .collect();
        let a = IvfIndex::build(&data, IvfConfig::default()).unwrap();
        let b = IvfIndex::build(&data, IvfConfig::default()).unwrap();
        let q = [3.0, 4.0];
        assert_eq!(a.search(&q, 5), b.search(&q, 5));
    }

    #[test]
    fn serde_round_trip() {
        let data: Vec<Vec<f32>> = (0..30).map(|i| vec![i as f32, (i * 2) as f32]).collect();
        let idx = IvfIndex::build(&data, IvfConfig::default()).unwrap();
        let j = serde_json::to_string(&idx).unwrap();
        let back: IvfIndex = serde_json::from_str(&j).unwrap();
        let q = [12.0, 24.0];
        assert_eq!(idx.search(&q, 5), back.search(&q, 5));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
