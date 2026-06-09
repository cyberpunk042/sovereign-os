//! `sovereign-hnsw` — fast approximate nearest-neighbour search over embeddings.
//!
//! Semantic retrieval ends in a vector query: given an embedding, find the most
//! similar stored vectors. Brute force scans every vector — fine for thousands,
//! ruinous for millions. **HNSW** (Hierarchical Navigable Small World, Malkov &
//! Yashunin) is the index that production vector databases reach for: it gives
//! near-logarithmic search with high recall.
//!
//! The structure is a stack of proximity graphs. Every inserted vector lives in
//! layer 0; a geometrically-thinning random subset also lives in higher layers,
//! so the top layers are sparse long-range "express lanes" and the bottom layer
//! is dense and local. A search starts at the single top entry point and greedily
//! walks toward the query, descending a layer each time it can get no closer —
//! the high layers cover distance fast, the low layer refines. At layer 0 the
//! walk widens into a beam of size `ef` to recover recall.
//!
//! Construction mirrors search: to insert a vector, find its nearest neighbours at
//! each layer and link to a curated `M` of them. The neighbour curation is the
//! paper's heuristic (Algorithm 4) — keep a candidate only if it is closer to the
//! new node than to any already-kept neighbour — which spreads links across
//! directions instead of clumping them, the key to a navigable graph. Links are
//! bidirectional and pruned back to `M` (to `2M` on the dense layer 0) when a node
//! grows too many.
//!
//! [`Hnsw::insert`] adds a vector; [`Hnsw::search`] returns the `k` nearest with
//! distances. [`Metric`] selects squared-Euclidean or cosine distance (cosine
//! vectors are normalized on insert). Level assignment is seeded, so a given
//! insertion order builds an identical graph.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashSet};

/// Schema version of the HNSW surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Distance function used to compare vectors.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum Metric {
    /// Squared Euclidean distance (monotone in Euclidean; cheaper, no sqrt).
    #[default]
    L2,
    /// Cosine *distance* `1 - cos`; vectors are L2-normalized on insert.
    Cosine,
}

/// HNSW build/search parameters.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct HnswConfig {
    /// Target out-degree per node on the upper layers.
    pub m: usize,
    /// Beam width while building (larger = better graph, slower build).
    pub ef_construction: usize,
    /// Beam width while searching (larger = higher recall, slower query).
    pub ef_search: usize,
    /// Seed for the random level assignment (reproducible builds).
    pub seed: u64,
    /// Distance metric.
    pub metric: Metric,
}

impl Default for HnswConfig {
    fn default() -> Self {
        Self {
            m: 16,
            ef_construction: 64,
            ef_search: 32,
            seed: 0x1234_5678,
            metric: Metric::L2,
        }
    }
}

/// A neighbour result: stored item index and its distance to the query.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Neighbor {
    /// Index of the stored vector (the order it was inserted).
    pub index: usize,
    /// Distance to the query under the configured [`Metric`].
    pub distance: f32,
}

/// A candidate ordered by distance; used inside the priority queues. `Ord` sorts
/// by distance (ties by node index) so it can drive both a min- and max-heap.
#[derive(Clone, Copy, PartialEq)]
struct Cand {
    dist: f32,
    node: u32,
}
impl Eq for Cand {}
impl Ord for Cand {
    fn cmp(&self, other: &Self) -> Ordering {
        self.dist
            .total_cmp(&other.dist)
            .then(self.node.cmp(&other.node))
    }
}
impl PartialOrd for Cand {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
/// Wrap a [`Cand`] so a `BinaryHeap` (max-heap) yields the *closest* first.
#[derive(Clone, Copy, PartialEq, Eq)]
struct MinCand(Cand);
impl Ord for MinCand {
    fn cmp(&self, other: &Self) -> Ordering {
        other.0.cmp(&self.0)
    }
}
impl PartialOrd for MinCand {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

/// SplitMix64 — small deterministic RNG for level assignment.
struct Rng(u64);
impl Rng {
    fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
    /// Uniform in `(0, 1]`.
    fn unit(&mut self) -> f64 {
        // 53-bit mantissa; +1 keeps it strictly positive so ln() is finite.
        let v = (self.next_u64() >> 11) + 1;
        v as f64 / (1u64 << 53) as f64
    }
}

/// A Hierarchical Navigable Small World index over fixed-dimension vectors.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Hnsw {
    config: HnswConfig,
    dim: usize,
    /// Stored vectors (normalized if metric is cosine).
    vectors: Vec<Vec<f32>>,
    /// `links[node][layer]` = neighbour node ids at that layer.
    links: Vec<Vec<Vec<u32>>>,
    /// Top layer index reachable from each node.
    node_level: Vec<usize>,
    /// Current global entry point (a node at the highest layer), if any.
    entry: Option<u32>,
    /// Highest layer currently populated.
    max_level: usize,
    /// `1 / ln(M)`, the level-distribution scale.
    level_mult: f64,
    rng_state: u64,
}

impl Hnsw {
    /// Create an empty index. The dimension is fixed by the first inserted vector.
    pub fn new(config: HnswConfig) -> Self {
        let m = config.m.max(2);
        let level_mult = 1.0 / (m as f64).ln();
        let seed = config.seed;
        Self {
            config: HnswConfig { m, ..config },
            dim: 0,
            vectors: Vec::new(),
            links: Vec::new(),
            node_level: Vec::new(),
            entry: None,
            max_level: 0,
            level_mult,
            rng_state: seed | 1,
        }
    }

    /// Number of stored vectors.
    pub fn len(&self) -> usize {
        self.vectors.len()
    }
    /// Whether the index holds no vectors.
    pub fn is_empty(&self) -> bool {
        self.vectors.is_empty()
    }
    /// The fixed vector dimension (0 until the first insert).
    pub fn dim(&self) -> usize {
        self.dim
    }

    /// Maximum links a node may keep at `layer` (`2M` at layer 0, `M` above).
    fn max_degree(&self, layer: usize) -> usize {
        if layer == 0 {
            self.config.m * 2
        } else {
            self.config.m
        }
    }

    fn distance(&self, a: &[f32], b: &[f32]) -> f32 {
        match self.config.metric {
            Metric::L2 => a
                .iter()
                .zip(b)
                .map(|(x, y)| {
                    let d = x - y;
                    d * d
                })
                .sum(),
            // both sides are pre-normalized, so dot == cosine similarity.
            Metric::Cosine => {
                let dot: f32 = a.iter().zip(b).map(|(x, y)| x * y).sum();
                1.0 - dot
            }
        }
    }

    /// Prepare an input vector: copy, and normalize when the metric is cosine.
    fn prepare(&self, v: &[f32]) -> Vec<f32> {
        let mut out = v.to_vec();
        if self.config.metric == Metric::Cosine {
            let norm: f32 = out.iter().map(|x| x * x).sum::<f32>().sqrt();
            if norm > 0.0 {
                for x in &mut out {
                    *x /= norm;
                }
            }
        }
        out
    }

    /// Draw a random level: `floor(-ln(U) * level_mult)`, a geometric thinning.
    fn random_level(&mut self) -> usize {
        let mut rng = Rng(self.rng_state);
        let u = rng.unit();
        self.rng_state = rng.0;
        (-u.ln() * self.level_mult).floor() as usize
    }

    /// Insert a vector and return its assigned item index. The first vector fixes
    /// the dimension; a vector of any other length is rejected with `Err`.
    pub fn insert(&mut self, vector: &[f32]) -> Result<usize, HnswError> {
        if self.vectors.is_empty() {
            if vector.is_empty() {
                return Err(HnswError::EmptyVector);
            }
            self.dim = vector.len();
        } else if vector.len() != self.dim {
            return Err(HnswError::DimMismatch {
                expected: self.dim,
                got: vector.len(),
            });
        }

        let node = self.vectors.len() as u32;
        let vec = self.prepare(vector);
        let level = self.random_level();
        self.vectors.push(vec);
        self.links.push(vec![Vec::new(); level + 1]);
        self.node_level.push(level);

        let entry = match self.entry {
            Some(e) => e,
            None => {
                // first node becomes the global entry point.
                self.entry = Some(node);
                self.max_level = level;
                return Ok(node as usize);
            }
        };

        let query = self.vectors[node as usize].clone();
        let mut ep = entry;

        // descend from the top down to just above the new node's level, taking a
        // single greedy step per layer (ef = 1).
        let mut layer = self.max_level;
        while layer > level {
            ep = self.greedy_descend(&query, ep, layer);
            layer -= 1;
        }

        // at every layer the node occupies, find ef_construction neighbours,
        // curate them, and wire bidirectional links.
        let mut layer = level.min(self.max_level);
        loop {
            let found = self.search_layer(&query, &[ep], self.config.ef_construction, layer);
            let m = self.max_degree(layer);
            let selected = self.select_neighbors(&query, &found, m);
            // link new node → selected.
            self.links[node as usize][layer] = selected.iter().map(|c| c.node).collect();
            // link selected → new node, pruning each back to its degree cap.
            for c in &selected {
                self.add_link(c.node, node, layer);
            }
            if let Some(best) = found.first() {
                ep = best.node;
            }
            if layer == 0 {
                break;
            }
            layer -= 1;
        }

        if level > self.max_level {
            self.max_level = level;
            self.entry = Some(node);
        }
        Ok(node as usize)
    }

    /// One greedy hop-chain at a single layer: repeatedly move to the neighbour
    /// closest to the query until none is closer.
    fn greedy_descend(&self, query: &[f32], entry: u32, layer: usize) -> u32 {
        let mut best = entry;
        let mut best_d = self.distance(query, &self.vectors[best as usize]);
        loop {
            let mut improved = false;
            for &nbr in &self.links[best as usize][layer] {
                let d = self.distance(query, &self.vectors[nbr as usize]);
                if d < best_d {
                    best_d = d;
                    best = nbr;
                    improved = true;
                }
            }
            if !improved {
                return best;
            }
        }
    }

    /// Beam search at one layer: explore from `entry_points`, keeping the `ef`
    /// closest found. Returns them sorted nearest-first.
    fn search_layer(
        &self,
        query: &[f32],
        entry_points: &[u32],
        ef: usize,
        layer: usize,
    ) -> Vec<Cand> {
        let mut visited: HashSet<u32> = HashSet::new();
        let mut candidates: BinaryHeap<MinCand> = BinaryHeap::new(); // min-heap (closest first)
        let mut result: BinaryHeap<Cand> = BinaryHeap::new(); // max-heap (farthest first)

        for &ep in entry_points {
            if visited.insert(ep) {
                let d = self.distance(query, &self.vectors[ep as usize]);
                let c = Cand { dist: d, node: ep };
                candidates.push(MinCand(c));
                result.push(c);
            }
        }

        while let Some(MinCand(cur)) = candidates.pop() {
            // farthest distance currently held in the result set.
            let farthest = result.peek().map(|c| c.dist).unwrap_or(f32::INFINITY);
            if cur.dist > farthest && result.len() >= ef {
                break;
            }
            for &nbr in &self.links[cur.node as usize][layer] {
                if visited.insert(nbr) {
                    let d = self.distance(query, &self.vectors[nbr as usize]);
                    let farthest = result.peek().map(|c| c.dist).unwrap_or(f32::INFINITY);
                    if d < farthest || result.len() < ef {
                        let c = Cand { dist: d, node: nbr };
                        candidates.push(MinCand(c));
                        result.push(c);
                        if result.len() > ef {
                            result.pop(); // drop the farthest
                        }
                    }
                }
            }
        }

        let mut out: Vec<Cand> = result.into_vec();
        out.sort_unstable(); // nearest first
        out
    }

    /// Neighbour-selection heuristic (paper Algorithm 4): walk candidates nearest
    /// first and keep one only if it is closer to the query than to every already
    /// kept neighbour — spreading links across directions, not clumping them.
    fn select_neighbors(&self, _query: &[f32], candidates: &[Cand], m: usize) -> Vec<Cand> {
        let mut kept: Vec<Cand> = Vec::with_capacity(m);
        for &c in candidates {
            if kept.len() >= m {
                break;
            }
            let cv = &self.vectors[c.node as usize];
            let mut good = true;
            for k in &kept {
                let d_to_kept = self.distance(cv, &self.vectors[k.node as usize]);
                if d_to_kept < c.dist {
                    good = false;
                    break;
                }
            }
            if good {
                kept.push(c);
            }
        }
        // if the heuristic was too strict to fill M, top up with the closest
        // remaining candidates so the node is not under-connected.
        if kept.len() < m {
            for &c in candidates {
                if kept.len() >= m {
                    break;
                }
                if !kept.iter().any(|k| k.node == c.node) {
                    kept.push(c);
                }
            }
        }
        kept
    }

    /// Add `to` to `from`'s neighbour list at `layer`, then re-prune `from` back to
    /// its degree cap using the same heuristic if it overflowed.
    fn add_link(&mut self, from: u32, to: u32, layer: usize) {
        if from == to {
            return;
        }
        if self.links[from as usize][layer].contains(&to) {
            return;
        }
        self.links[from as usize][layer].push(to);
        let cap = self.max_degree(layer);
        if self.links[from as usize][layer].len() <= cap {
            return;
        }
        // overflow: recompute distances from `from` and keep the curated cap.
        let fv = self.vectors[from as usize].clone();
        let mut cands: Vec<Cand> = self.links[from as usize][layer]
            .iter()
            .map(|&n| Cand {
                dist: self.distance(&fv, &self.vectors[n as usize]),
                node: n,
            })
            .collect();
        cands.sort_unstable();
        let kept = self.select_neighbors(&fv, &cands, cap);
        self.links[from as usize][layer] = kept.iter().map(|c| c.node).collect();
    }

    /// Find the `k` nearest stored vectors to `query`. Returns nearest-first; an
    /// empty index (or a dimension mismatch) yields an empty result.
    pub fn search(&self, query: &[f32], k: usize) -> Vec<Neighbor> {
        if self.vectors.is_empty() || k == 0 || query.len() != self.dim {
            return Vec::new();
        }
        let q = self.prepare(query);
        let mut ep = self.entry.expect("non-empty index has an entry point");

        // descend the express lanes greedily.
        let mut layer = self.max_level;
        while layer > 0 {
            ep = self.greedy_descend(&q, ep, layer);
            layer -= 1;
        }

        // widen at the base layer.
        let ef = self.config.ef_search.max(k);
        let found = self.search_layer(&q, &[ep], ef, 0);
        found
            .into_iter()
            .take(k)
            .map(|c| Neighbor {
                index: c.node as usize,
                distance: c.dist,
            })
            .collect()
    }

    /// The stored vector at `index`, if present (normalized for cosine metric).
    pub fn vector(&self, index: usize) -> Option<&[f32]> {
        self.vectors.get(index).map(|v| v.as_slice())
    }
}

/// Errors from building an HNSW index.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum HnswError {
    /// The first inserted vector was empty (cannot fix a zero dimension).
    EmptyVector,
    /// A vector's length did not match the index's fixed dimension.
    DimMismatch {
        /// The dimension fixed by the first insert.
        expected: usize,
        /// The length of the offending vector.
        got: usize,
    },
}

impl std::fmt::Display for HnswError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HnswError::EmptyVector => write!(f, "cannot insert an empty vector"),
            HnswError::DimMismatch { expected, got } => {
                write!(f, "dimension mismatch: expected {expected}, got {got}")
            }
        }
    }
}
impl std::error::Error for HnswError {}

#[cfg(test)]
mod tests {
    use super::*;

    /// Exact nearest neighbour by brute force, for recall checks.
    fn brute_nearest(data: &[Vec<f32>], q: &[f32]) -> usize {
        let mut best = 0;
        let mut best_d = f32::INFINITY;
        for (i, v) in data.iter().enumerate() {
            let d: f32 = v.iter().zip(q).map(|(a, b)| (a - b) * (a - b)).sum();
            if d < best_d {
                best_d = d;
                best = i;
            }
        }
        best
    }

    fn build(data: &[Vec<f32>], cfg: HnswConfig) -> Hnsw {
        let mut h = Hnsw::new(cfg);
        for v in data {
            h.insert(v).unwrap();
        }
        h
    }

    #[test]
    fn empty_index_returns_nothing() {
        let h = Hnsw::new(HnswConfig::default());
        assert!(h.is_empty());
        assert_eq!(h.search(&[1.0, 2.0], 5), vec![]);
    }

    #[test]
    fn single_vector_is_its_own_neighbour() {
        let mut h = Hnsw::new(HnswConfig::default());
        h.insert(&[1.0, 0.0, 0.0]).unwrap();
        let r = h.search(&[0.9, 0.1, 0.0], 1);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].index, 0);
        assert_eq!(h.dim(), 3);
    }

    #[test]
    fn finds_exact_nearest_on_a_grid() {
        // a 2-D integer grid; the nearest grid point to a query is unambiguous.
        let mut data = Vec::new();
        for x in 0..12 {
            for y in 0..12 {
                data.push(vec![x as f32, y as f32]);
            }
        }
        let h = build(&data, HnswConfig::default());
        let queries = [
            [2.1, 3.9],
            [7.4, 1.2],
            [10.8, 10.1],
            [0.3, 11.6],
            [5.5, 5.5],
        ];
        for q in &queries {
            let got = h.search(q, 1)[0].index;
            let want = brute_nearest(&data, q);
            assert_eq!(got, want, "query {q:?}");
        }
    }

    #[test]
    fn high_recall_at_k_on_random_data() {
        // build a random-ish dataset deterministically and check recall@10.
        let mut rng = Rng(99);
        let n = 400;
        let dim = 16;
        let mut data = Vec::with_capacity(n);
        for _ in 0..n {
            let v: Vec<f32> = (0..dim).map(|_| (rng.unit() as f32) * 2.0 - 1.0).collect();
            data.push(v);
        }
        let h = build(&data, HnswConfig::default());

        let mut hits = 0;
        let mut total = 0;
        for qi in 0..40 {
            let q = &data[qi * 7 % n];
            // exact top-10
            let mut exact: Vec<(f32, usize)> = data
                .iter()
                .enumerate()
                .map(|(i, v)| {
                    let d: f32 = v.iter().zip(q).map(|(a, b)| (a - b) * (a - b)).sum();
                    (d, i)
                })
                .collect();
            exact.sort_by(|a, b| a.0.total_cmp(&b.0));
            let truth: HashSet<usize> = exact.iter().take(10).map(|x| x.1).collect();
            let got = h.search(q, 10);
            for n in &got {
                if truth.contains(&n.index) {
                    hits += 1;
                }
            }
            total += 10;
        }
        let recall = hits as f64 / total as f64;
        assert!(recall > 0.90, "recall@10 was {recall}");
    }

    #[test]
    fn results_sorted_by_distance() {
        let data: Vec<Vec<f32>> = (0..50).map(|i| vec![i as f32, 0.0]).collect();
        let h = build(&data, HnswConfig::default());
        let r = h.search(&[25.3, 0.0], 8);
        assert!(r.len() >= 5);
        for w in r.windows(2) {
            assert!(w[0].distance <= w[1].distance, "not sorted: {r:?}");
        }
        // closest grid point to 25.3 is index 25.
        assert_eq!(r[0].index, 25);
    }

    #[test]
    fn cosine_metric_ranks_by_angle() {
        let cfg = HnswConfig {
            metric: Metric::Cosine,
            ..HnswConfig::default()
        };
        let mut h = Hnsw::new(cfg);
        h.insert(&[1.0, 0.0]).unwrap(); // 0°
        h.insert(&[0.0, 1.0]).unwrap(); // 90°
        h.insert(&[-1.0, 0.0]).unwrap(); // 180°
        // query points mostly along +x but longer — magnitude must not matter.
        let r = h.search(&[5.0, 0.2], 3);
        assert_eq!(r[0].index, 0);
        // 180° vector is the farthest.
        assert_eq!(r.last().unwrap().index, 2);
    }

    #[test]
    fn dimension_mismatch_is_rejected() {
        let mut h = Hnsw::new(HnswConfig::default());
        h.insert(&[1.0, 2.0, 3.0]).unwrap();
        assert_eq!(
            h.insert(&[1.0, 2.0]),
            Err(HnswError::DimMismatch {
                expected: 3,
                got: 2
            })
        );
    }

    #[test]
    fn empty_first_vector_is_rejected() {
        let mut h = Hnsw::new(HnswConfig::default());
        assert_eq!(h.insert(&[]), Err(HnswError::EmptyVector));
    }

    #[test]
    fn deterministic_build_same_seed() {
        let data: Vec<Vec<f32>> = (0..60)
            .map(|i| vec![(i % 7) as f32, (i / 7) as f32])
            .collect();
        let a = build(&data, HnswConfig::default());
        let b = build(&data, HnswConfig::default());
        let q = [3.2, 4.1];
        assert_eq!(a.search(&q, 5), b.search(&q, 5));
    }

    #[test]
    fn k_larger_than_index() {
        let data = vec![vec![0.0], vec![1.0], vec![2.0]];
        let h = build(&data, HnswConfig::default());
        let r = h.search(&[0.4], 10);
        assert_eq!(r.len(), 3); // capped at index size
        assert_eq!(r[0].index, 0);
    }

    #[test]
    fn serde_round_trip_preserves_search() {
        let data: Vec<Vec<f32>> = (0..30).map(|i| vec![i as f32, (i * 2) as f32]).collect();
        let h = build(&data, HnswConfig::default());
        let j = serde_json::to_string(&h).unwrap();
        let back: Hnsw = serde_json::from_str(&j).unwrap();
        let q = [10.1, 19.5];
        assert_eq!(h.search(&q, 5), back.search(&q, 5));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
