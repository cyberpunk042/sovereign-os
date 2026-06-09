//! The behavioral memory engine — hot/cold store, ground-truth layer, and
//! the multi-stage hot-metadata retrieval scan.
//!
//! The taxonomy in `lib.rs` makes the M028 *catalog* executable (the 8
//! types, the 11-stage lifecycle). This module is the part that makes
//! memory **living structure, not retrieve-similar-chunks** (F02297):
//!
//! - [`HotMeta`] — the 10-`u64` hot metadata record (M00467). Small,
//!   cache-dense, scannable; the cold blob never touches the scan path.
//! - [`GroundTruth`] — the ground-truth layer (M00466) that **does not
//!   summarize away truth** (F02316): the raw episode is always retained,
//!   so the system recovers if a summary was wrong (F02326).
//! - [`MemoryStore`] — hot/cold split (M00468): hot metadata stays
//!   resident for the scan, the actual text lives cold and is fetched
//!   only for the survivors.
//! - [`MemoryStore::retrieve`] — the staged scan (F02339-F02345):
//!   permission/flag filter → sketch popcount relevance → trust/value/
//!   freshness weighting → top-k, with optional 1-hop graph expansion.
//!
//! The "AVX-512 hot metadata scan" the dump describes is implemented here
//! as the portable scalar reference: `u64::count_ones` is the popcount
//! (`VPOPCNTDQ`) and the `&`-then-popcount over the sketches is the bitset
//! relevance kernel. The numerics are identical to a future SIMD path.

use crate::MemoryType;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// `flags` bit: the item is readable under the current permission scope.
/// An item without this bit is never returned by [`MemoryStore::retrieve`].
pub const FLAG_READABLE: u64 = 1 << 0;
/// `flags` bit: the item is relevant to a *failure* (F02345) — lets the
/// scan prefer post-mortem material when the query asks for it.
pub const FLAG_FAILURE_RELEVANT: u64 = 1 << 1;

/// The hot metadata record (M00467) — exactly the ten `u64` fields the
/// spec enumerates (F02327-F02336). Everything here is scanned; nothing
/// here is the payload.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct HotMeta {
    /// Stable id; also the key into the cold store.
    pub id: u64,
    /// [`MemoryType`] as its canonical 1..8 index.
    pub type_code: u64,
    /// Provenance handle (which source/project produced this).
    pub source_ref: u64,
    /// Packed observation time / validity window.
    pub time_range: u64,
    /// Trust score, `0..=1000`.
    pub trust: u64,
    /// Freshness as an epoch tick; decays relative to the query's `now`.
    pub freshness: u64,
    /// 64-bit topic sketch (SimHash-style bitset) for popcount relevance.
    pub topic_sketch: u64,
    /// 64-bit entity sketch for popcount relevance + graph expansion.
    pub entity_sketch: u64,
    /// Value-plane score, `0..=1000`.
    pub value_score: u64,
    /// Bitflags — permission/scope/failure-relevance (see `FLAG_*`).
    pub flags: u64,
}

impl HotMeta {
    /// Construct from a [`MemoryType`] plus the scannable fields.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        id: u64,
        memory_type: MemoryType,
        source_ref: u64,
        time_range: u64,
        trust: u64,
        freshness: u64,
        topic_sketch: u64,
        entity_sketch: u64,
        value_score: u64,
        flags: u64,
    ) -> Self {
        Self {
            id,
            type_code: memory_type.index() as u64,
            source_ref,
            time_range,
            trust,
            freshness,
            topic_sketch,
            entity_sketch,
            value_score,
            flags,
        }
    }
}

/// The ground-truth layer (M00466). The raw episode is sacrosanct: the
/// summary is a convenience, never a replacement (F02316, F02317).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GroundTruth {
    /// The raw episode — the truth. Never discarded, never overwritten by
    /// a summary.
    pub raw_episode: String,
    /// Facts distilled from the episode (lossy; cross-checkable).
    pub derived_facts: Vec<String>,
    /// Human/agent summary (lossy convenience).
    pub summary: String,
    /// Graph edges `(from_entity, to_entity)`.
    pub graph_edges: Vec<(u64, u64)>,
    /// Trust score `0..=1000`.
    pub trust: u16,
    /// Freshness epoch tick.
    pub freshness: u64,
    /// Set when the summary is known/suspected to be wrong; flips
    /// [`GroundTruth::best_available`] back to the raw episode (F02326).
    pub summary_suspect: bool,
}

impl GroundTruth {
    /// The raw truth — always available, regardless of summary state.
    pub fn recover(&self) -> &str {
        &self.raw_episode
    }

    /// The best representation to use: the summary when it is trusted, but
    /// the raw episode whenever the summary is suspect — so a wrong
    /// summary can never mask the truth (F02326).
    pub fn best_available(&self) -> &str {
        if self.summary_suspect {
            &self.raw_episode
        } else {
            &self.summary
        }
    }
}

/// A retrieval query against the hot metadata.
#[derive(Debug, Clone, Copy)]
pub struct Query {
    /// Topic bitset to match against [`HotMeta::topic_sketch`].
    pub topic: u64,
    /// Entity bitset to match against [`HotMeta::entity_sketch`].
    pub entity: u64,
    /// Flags every candidate MUST carry (e.g. `FLAG_READABLE`).
    pub require_flags: u64,
    /// Current epoch tick for freshness decay.
    pub now: u64,
    /// Freshness half-life in ticks (older memories rank lower).
    pub half_life: u64,
}

impl Query {
    /// A readable-only topic/entity query at time `now`.
    pub fn new(topic: u64, entity: u64, now: u64, half_life: u64) -> Self {
        Self {
            topic,
            entity,
            require_flags: FLAG_READABLE,
            now,
            half_life: half_life.max(1),
        }
    }
}

/// A scored retrieval hit.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Hit {
    /// Item id (key into the cold store).
    pub id: u64,
    /// Combined relevance score (higher = better).
    pub relevance: f64,
    /// Raw sketch-overlap popcount (topic + entity bits in common).
    pub sketch_overlap: u32,
}

// Relevance weights. Sketch overlap dominates; trust and value modulate;
// freshness multiplies the whole thing.
const W_SKETCH: f64 = 1.0;
const W_TRUST: f64 = 0.001; // trust is 0..1000
const W_VALUE: f64 = 0.001; // value is 0..1000

/// Hot/cold memory store with staged retrieval.
#[derive(Debug, Default)]
pub struct MemoryStore {
    hot: Vec<HotMeta>,
    cold: HashMap<u64, GroundTruth>,
    /// Optional capacity bound; `None` = unbounded.
    capacity: Option<usize>,
}

impl MemoryStore {
    /// Empty, unbounded store.
    pub fn new() -> Self {
        Self::default()
    }

    /// A store bounded to at most `capacity` items. Admitting beyond the
    /// bound evicts the lowest-value resident item — so a long-running,
    /// continuously-learning cortex keeps its best memories and discards the
    /// rest instead of growing without limit.
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            capacity: Some(capacity),
            ..Self::default()
        }
    }

    /// Admit an item: hot metadata stays resident, the ground truth goes
    /// cold keyed by id. Re-admitting the same id replaces both. If a
    /// capacity is set and now exceeded, the lowest-value item is evicted.
    pub fn admit(&mut self, meta: HotMeta, truth: GroundTruth) {
        self.hot.retain(|m| m.id != meta.id);
        self.hot.push(meta);
        self.cold.insert(meta.id, truth);
        if let Some(cap) = self.capacity {
            while self.hot.len() > cap {
                self.evict_lowest_value();
            }
        }
    }

    /// Evict the lowest-`value_score` item (ties → oldest freshness, then
    /// lowest id). Removes it from both the hot scan set and the cold store.
    fn evict_lowest_value(&mut self) {
        if let Some((idx, victim_id)) = self
            .hot
            .iter()
            .enumerate()
            .min_by(|(_, a), (_, b)| {
                a.value_score
                    .cmp(&b.value_score)
                    .then(a.freshness.cmp(&b.freshness))
                    .then(a.id.cmp(&b.id))
            })
            .map(|(i, m)| (i, m.id))
        {
            self.hot.remove(idx);
            self.cold.remove(&victim_id);
        }
    }

    /// Number of resident items.
    pub fn len(&self) -> usize {
        self.hot.len()
    }

    /// Whether the store is empty.
    pub fn is_empty(&self) -> bool {
        self.hot.is_empty()
    }

    /// Fetch the cold ground truth for an id (only done for scan survivors).
    pub fn ground_truth(&self, id: u64) -> Option<&GroundTruth> {
        self.cold.get(&id)
    }

    /// The staged hot-metadata scan (M00468, F02339-F02345).
    ///
    /// 1. **Permission/flag filter** — drop anything missing
    ///    `query.require_flags`.
    /// 2. **Sketch relevance** — `popcount(topic & q.topic) +
    ///    popcount(entity & q.entity)`; zero-overlap items drop out.
    /// 3. **Weighting** — fold in trust + value, then multiply by a
    ///    freshness decay factor derived from `now - freshness`.
    /// 4. **Top-k** — highest relevance first.
    ///
    /// Returns at most `k` hits. The cold blobs are never touched here.
    pub fn retrieve(&self, query: &Query, k: usize) -> Vec<Hit> {
        let mut hits: Vec<Hit> = self
            .hot
            .iter()
            .filter(|m| (m.flags & query.require_flags) == query.require_flags)
            .filter_map(|m| {
                let topic_overlap = (m.topic_sketch & query.topic).count_ones();
                let entity_overlap = (m.entity_sketch & query.entity).count_ones();
                let overlap = topic_overlap + entity_overlap;
                if overlap == 0 {
                    return None; // stage 2 cutoff: no shared bits, no relevance
                }
                let decay = freshness_decay(query.now, m.freshness, query.half_life);
                let base = overlap as f64 * W_SKETCH
                    + m.trust as f64 * W_TRUST
                    + m.value_score as f64 * W_VALUE;
                Some(Hit {
                    id: m.id,
                    relevance: base * decay,
                    sketch_overlap: overlap,
                })
            })
            .collect();

        hits.sort_by(|a, b| {
            b.relevance
                .partial_cmp(&a.relevance)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.id.cmp(&b.id)) // stable tie-break by id
        });
        hits.truncate(k);
        hits
    }

    /// 1-hop graph expansion (F02300 temporal-graph / Graph-RAG step):
    /// given a seed id, return ids of other items whose entity sketch
    /// shares at least `min_bits` bits with the seed's. This is the
    /// "follow the graph" stage that turns recall into structure.
    pub fn expand(&self, seed_id: u64, min_bits: u32) -> Vec<u64> {
        let Some(seed) = self.hot.iter().find(|m| m.id == seed_id) else {
            return Vec::new();
        };
        let mut out: Vec<u64> = self
            .hot
            .iter()
            .filter(|m| m.id != seed_id)
            .filter(|m| (m.entity_sketch & seed.entity_sketch).count_ones() >= min_bits)
            .map(|m| m.id)
            .collect();
        out.sort_unstable();
        out
    }

    /// Apply freshness decay bookkeeping: any item older than `ttl` ticks
    /// relative to `now` has its cold summary marked suspect (it should be
    /// re-derived) without ever touching the raw episode. Returns the
    /// number of items aged out. This is the M028 "decay" lifecycle stage
    /// made real — and it honours "do not summarize away truth": only the
    /// summary is invalidated, the raw episode is preserved.
    pub fn decay(&mut self, now: u64, ttl: u64) -> usize {
        let mut aged = 0;
        for meta in &self.hot {
            if now.saturating_sub(meta.freshness) > ttl
                && let Some(gt) = self.cold.get_mut(&meta.id)
                && !gt.summary_suspect
            {
                gt.summary_suspect = true;
                aged += 1;
            }
        }
        aged
    }
}

/// Freshness decay multiplier in `(0, 1]`: `0.5 ^ (age / half_life)`.
/// Fresh items (age 0) score 1.0; an item one half-life old scores 0.5.
fn freshness_decay(now: u64, freshness: u64, half_life: u64) -> f64 {
    let age = now.saturating_sub(freshness) as f64;
    0.5_f64.powf(age / half_life as f64)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn gt(raw: &str) -> GroundTruth {
        GroundTruth {
            raw_episode: raw.into(),
            derived_facts: vec![],
            summary: format!("summary-of-{raw}"),
            graph_edges: vec![],
            trust: 800,
            freshness: 100,
            summary_suspect: false,
        }
    }

    // --- ground truth: do not summarize away truth ---

    #[test]
    fn raw_episode_always_recoverable() {
        let g = gt("the-real-episode");
        assert_eq!(g.recover(), "the-real-episode");
        // trusted summary is used by default
        assert_eq!(g.best_available(), "summary-of-the-real-episode");
    }

    #[test]
    fn suspect_summary_falls_back_to_truth() {
        let mut g = gt("ground-truth-text");
        g.summary_suspect = true;
        // F02326: system recovers when the summary was wrong
        assert_eq!(g.best_available(), "ground-truth-text");
        // and the raw episode was never discarded
        assert_eq!(g.recover(), "ground-truth-text");
    }

    // --- hot/cold split ---

    #[test]
    fn admit_keeps_hot_meta_and_cold_truth() {
        let mut s = MemoryStore::new();
        let m = HotMeta::new(
            7,
            MemoryType::Semantic,
            0,
            0,
            800,
            100,
            0b1,
            0b1,
            500,
            FLAG_READABLE,
        );
        s.admit(m, gt("episode-7"));
        assert_eq!(s.len(), 1);
        assert_eq!(s.ground_truth(7).unwrap().raw_episode, "episode-7");
        assert!(s.ground_truth(999).is_none());
    }

    #[test]
    fn readmit_replaces() {
        let mut s = MemoryStore::new();
        let base = HotMeta::new(
            1,
            MemoryType::Working,
            0,
            0,
            100,
            100,
            1,
            1,
            0,
            FLAG_READABLE,
        );
        s.admit(base, gt("v1"));
        s.admit(base, gt("v2"));
        assert_eq!(s.len(), 1);
        assert_eq!(s.ground_truth(1).unwrap().raw_episode, "v2");
    }

    // --- bounded capacity + eviction ---

    fn meta_val(id: u64, value_score: u64) -> HotMeta {
        HotMeta::new(
            id,
            MemoryType::Semantic,
            0,
            0,
            0,
            100,
            1,
            1,
            value_score,
            FLAG_READABLE,
        )
    }

    #[test]
    fn capacity_evicts_lowest_value() {
        let mut s = MemoryStore::with_capacity(2);
        s.admit(meta_val(1, 100), gt("a")); // lowest value
        s.admit(meta_val(2, 500), gt("b"));
        s.admit(meta_val(3, 300), gt("c"));
        assert_eq!(s.len(), 2);
        assert!(
            s.ground_truth(1).is_none(),
            "lowest-value item should be evicted"
        );
        assert!(s.ground_truth(2).is_some());
        assert!(s.ground_truth(3).is_some());
    }

    #[test]
    fn capacity_one_keeps_the_highest_value() {
        let mut s = MemoryStore::with_capacity(1);
        s.admit(meta_val(1, 900), gt("hi"));
        s.admit(meta_val(2, 100), gt("lo")); // lower value → evicted
        assert_eq!(s.len(), 1);
        assert!(s.ground_truth(1).is_some());
        assert!(s.ground_truth(2).is_none());
    }

    #[test]
    fn unbounded_store_keeps_everything() {
        let mut s = MemoryStore::new();
        for id in 0..10 {
            s.admit(meta_val(id, id), gt("x"));
        }
        assert_eq!(s.len(), 10);
    }

    // --- retrieval scan ---

    fn store_with_three() -> MemoryStore {
        let mut s = MemoryStore::new();
        // strong topic overlap
        s.admit(
            HotMeta::new(
                1,
                MemoryType::Semantic,
                0,
                0,
                900,
                100,
                0b1111_0000,
                0,
                600,
                FLAG_READABLE,
            ),
            gt("a"),
        );
        // weak topic overlap
        s.admit(
            HotMeta::new(
                2,
                MemoryType::Semantic,
                0,
                0,
                900,
                100,
                0b1000_0000,
                0,
                600,
                FLAG_READABLE,
            ),
            gt("b"),
        );
        // no overlap at all
        s.admit(
            HotMeta::new(
                3,
                MemoryType::Semantic,
                0,
                0,
                900,
                100,
                0b0000_0001,
                0,
                600,
                FLAG_READABLE,
            ),
            gt("c"),
        );
        s
    }

    #[test]
    fn retrieval_ranks_by_sketch_overlap() {
        let s = store_with_three();
        let q = Query::new(0b1111_0000, 0, 100, 1000);
        let hits = s.retrieve(&q, 10);
        // item 3 (no overlap) excluded; 1 outranks 2 (more shared bits)
        assert_eq!(hits.len(), 2);
        assert_eq!(hits[0].id, 1);
        assert_eq!(hits[0].sketch_overlap, 4);
        assert_eq!(hits[1].id, 2);
        assert_eq!(hits[1].sketch_overlap, 1);
        assert!(hits[0].relevance > hits[1].relevance);
    }

    #[test]
    fn permission_filter_excludes_unreadable() {
        let mut s = MemoryStore::new();
        // same strong overlap but NOT readable
        s.admit(
            HotMeta::new(1, MemoryType::Semantic, 0, 0, 900, 100, 0xFF, 0, 0, 0),
            gt("secret"),
        );
        let q = Query::new(0xFF, 0, 100, 1000);
        assert!(s.retrieve(&q, 10).is_empty());
    }

    #[test]
    fn entity_overlap_contributes() {
        let mut s = MemoryStore::new();
        s.admit(
            HotMeta::new(
                1,
                MemoryType::TemporalGraph,
                0,
                0,
                0,
                100,
                0,
                0b1111,
                0,
                FLAG_READABLE,
            ),
            gt("entity-rich"),
        );
        let q = Query::new(0, 0b1111, 100, 1000);
        let hits = s.retrieve(&q, 10);
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].sketch_overlap, 4);
    }

    #[test]
    fn fresher_memory_outranks_stale_with_equal_overlap() {
        let mut s = MemoryStore::new();
        s.admit(
            HotMeta::new(
                1,
                MemoryType::Episodic,
                0,
                0,
                500,
                100,
                0xF,
                0,
                0,
                FLAG_READABLE,
            ),
            gt("fresh"),
        );
        s.admit(
            HotMeta::new(
                2,
                MemoryType::Episodic,
                0,
                0,
                500,
                0,
                0xF,
                0,
                0,
                FLAG_READABLE,
            ),
            gt("stale"),
        );
        // now=100, half_life=100: item1 age 0 (decay 1.0), item2 age 100 (decay 0.5)
        let q = Query::new(0xF, 0, 100, 100);
        let hits = s.retrieve(&q, 10);
        assert_eq!(hits[0].id, 1, "fresher item should rank first");
        assert!(hits[0].relevance > hits[1].relevance);
    }

    #[test]
    fn top_k_truncates() {
        let s = store_with_three();
        let q = Query::new(0xFF, 0, 100, 1000);
        assert_eq!(s.retrieve(&q, 1).len(), 1);
    }

    // --- graph expansion ---

    #[test]
    fn expand_follows_shared_entity_bits() {
        let mut s = MemoryStore::new();
        s.admit(
            HotMeta::new(
                1,
                MemoryType::TemporalGraph,
                0,
                0,
                0,
                100,
                0,
                0b1100,
                0,
                FLAG_READABLE,
            ),
            gt("seed"),
        );
        s.admit(
            HotMeta::new(
                2,
                MemoryType::TemporalGraph,
                0,
                0,
                0,
                100,
                0,
                0b0100,
                0,
                FLAG_READABLE,
            ),
            gt("shares-1"),
        );
        s.admit(
            HotMeta::new(
                3,
                MemoryType::TemporalGraph,
                0,
                0,
                0,
                100,
                0,
                0b0011,
                0,
                FLAG_READABLE,
            ),
            gt("shares-0"),
        );
        let neighbours = s.expand(1, 1);
        assert_eq!(neighbours, vec![2]); // only id 2 shares an entity bit
    }

    #[test]
    fn expand_unknown_seed_is_empty() {
        let s = store_with_three();
        assert!(s.expand(404, 1).is_empty());
    }

    // --- decay: invalidate summary, never the truth ---

    #[test]
    fn decay_marks_summary_suspect_but_keeps_raw() {
        let mut s = MemoryStore::new();
        s.admit(
            HotMeta::new(1, MemoryType::Episodic, 0, 0, 0, 10, 1, 1, 0, FLAG_READABLE),
            gt("durable-truth"),
        );
        // now=1000, ttl=100 -> age 990 > 100 -> aged out
        let aged = s.decay(1000, 100);
        assert_eq!(aged, 1);
        let g = s.ground_truth(1).unwrap();
        assert!(g.summary_suspect);
        assert_eq!(g.recover(), "durable-truth"); // truth preserved
        assert_eq!(g.best_available(), "durable-truth"); // recovers to truth
        // idempotent: second decay doesn't re-count
        assert_eq!(s.decay(1000, 100), 0);
    }

    #[test]
    fn fresh_items_survive_decay() {
        let mut s = MemoryStore::new();
        s.admit(
            HotMeta::new(1, MemoryType::Working, 0, 0, 0, 950, 1, 1, 0, FLAG_READABLE),
            gt("recent"),
        );
        assert_eq!(s.decay(1000, 100), 0); // age 50 < ttl 100
        assert!(!s.ground_truth(1).unwrap().summary_suspect);
    }

    // --- popcount kernel sanity (the VPOPCNTDQ reference) ---

    #[test]
    fn popcount_overlap_is_bitwise_and_count() {
        let a: u64 = 0b1011_0110;
        let b: u64 = 0b1101_0100;
        assert_eq!((a & b).count_ones(), 0b1001_0100u64.count_ones());
    }
}
