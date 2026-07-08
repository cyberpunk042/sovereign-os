//! `sovereign-kv-cache` — M011 KV cache as a memory hierarchy.
//!
//! The dump frames the KV cache as a tiered store — hot context resident in
//! VRAM, cooler blocks spilling to RAM then NVMe — with prefix reuse ("keep
//! stable prefixes resident", "reuse hot context"). This crate is the
//! native controller's reference: KV blocks (keyed by a content hash) live
//! across three [`Tier`]s; inserting past a tier's byte capacity **demotes**
//! its least-recently-used blocks to the next-slower tier (dropping off the
//! bottom), and a cache **hit promotes** the block back to VRAM so hot
//! context stays fast.
//!
//! Everything is byte-accounted and deterministic; the per-tier hit stats
//! mirror the dashboard metrics the dump calls for.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the KV-cache surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The three storage tiers, fastest first.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Tier {
    /// On-GPU VRAM — fastest, smallest.
    Vram,
    /// Host RAM — middle.
    Ram,
    /// NVMe — slowest, largest.
    Nvme,
}

impl Tier {
    /// Tier ordering index (0 = fastest).
    pub fn index(self) -> usize {
        match self {
            Tier::Vram => 0,
            Tier::Ram => 1,
            Tier::Nvme => 2,
        }
    }

    const ALL: [Tier; 3] = [Tier::Vram, Tier::Ram, Tier::Nvme];
}

#[derive(Debug, Clone, Copy)]
struct Block {
    bytes: u64,
    last_used: u64,
}

#[derive(Debug, Default)]
struct TierStore {
    capacity_bytes: u64,
    used_bytes: u64,
    blocks: HashMap<u64, Block>,
}

impl TierStore {
    fn pop_lru(&mut self) -> Option<(u64, Block)> {
        let victim = self
            .blocks
            .iter()
            .min_by_key(|(_, b)| b.last_used)
            .map(|(&h, &b)| (h, b))?;
        self.blocks.remove(&victim.0);
        self.used_bytes -= victim.1.bytes;
        Some(victim)
    }

    fn put(&mut self, hash: u64, block: Block) {
        if let Some(old) = self.blocks.insert(hash, block) {
            self.used_bytes -= old.bytes;
        }
        self.used_bytes += block.bytes;
    }

    fn take(&mut self, hash: u64) -> Option<Block> {
        let b = self.blocks.remove(&hash)?;
        self.used_bytes -= b.bytes;
        Some(b)
    }
}

/// Per-tier occupancy snapshot.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct TierOccupancy {
    /// The tier.
    pub tier: Tier,
    /// Blocks resident.
    pub blocks: usize,
    /// Bytes used.
    pub used_bytes: u64,
    /// Capacity in bytes.
    pub capacity_bytes: u64,
}

/// A tiered KV-block cache (VRAM → RAM → NVMe).
#[derive(Debug)]
pub struct KvCache {
    tiers: [TierStore; 3],
    clock: u64,
    hits: u64,
    misses: u64,
}

impl KvCache {
    /// Create a cache with per-tier byte capacities.
    pub fn new(vram_bytes: u64, ram_bytes: u64, nvme_bytes: u64) -> Self {
        let mut tiers: [TierStore; 3] = Default::default();
        tiers[0].capacity_bytes = vram_bytes;
        tiers[1].capacity_bytes = ram_bytes;
        tiers[2].capacity_bytes = nvme_bytes;
        Self {
            tiers,
            clock: 0,
            hits: 0,
            misses: 0,
        }
    }

    fn tick(&mut self) -> u64 {
        self.clock += 1;
        self.clock
    }

    /// Insert (or refresh) a block, placing it in VRAM; over-capacity tiers
    /// demote their LRU blocks downward, dropping off the bottom.
    pub fn insert(&mut self, hash: u64, bytes: u64) {
        let now = self.tick();
        // remove any existing copy first (re-home to VRAM)
        for t in &mut self.tiers {
            t.take(hash);
        }
        self.tiers[0].put(
            hash,
            Block {
                bytes,
                last_used: now,
            },
        );
        self.rebalance();
    }

    /// Look up a block. On a hit, the block is promoted to VRAM (hot context
    /// stays resident) and its tier *before* promotion is returned.
    pub fn lookup(&mut self, hash: u64) -> Option<Tier> {
        let found = Tier::ALL
            .into_iter()
            .find(|t| self.tiers[t.index()].blocks.contains_key(&hash));
        match found {
            Some(tier) => {
                self.hits += 1;
                let now = self.tick();
                if tier != Tier::Vram
                    && let Some(mut b) = self.tiers[tier.index()].take(hash)
                {
                    b.last_used = now;
                    self.tiers[0].put(hash, b);
                    self.rebalance();
                } else if let Some(b) = self.tiers[0].blocks.get_mut(&hash) {
                    b.last_used = now;
                }
                Some(tier)
            }
            None => {
                self.misses += 1;
                None
            }
        }
    }

    /// Whether a block is resident in any tier (no stats/promotion effect).
    pub fn contains(&self, hash: u64) -> bool {
        Tier::ALL
            .into_iter()
            .any(|t| self.tiers[t.index()].blocks.contains_key(&hash))
    }

    /// Length of the longest prefix of `block_hashes` currently resident —
    /// the reusable cached prefix of a prompt (prefix caching).
    pub fn prefix_reuse(&self, block_hashes: &[u64]) -> usize {
        block_hashes
            .iter()
            .take_while(|&&h| self.contains(h))
            .count()
    }

    /// Cache hit rate in `[0, 1]` over all lookups so far.
    pub fn hit_rate(&self) -> f64 {
        let total = self.hits + self.misses;
        if total == 0 {
            0.0
        } else {
            self.hits as f64 / total as f64
        }
    }

    /// Per-tier occupancy snapshot.
    pub fn occupancy(&self) -> Vec<TierOccupancy> {
        Tier::ALL
            .into_iter()
            .map(|t| {
                let s = &self.tiers[t.index()];
                TierOccupancy {
                    tier: t,
                    blocks: s.blocks.len(),
                    used_bytes: s.used_bytes,
                    capacity_bytes: s.capacity_bytes,
                }
            })
            .collect()
    }

    // Demote LRU blocks down the hierarchy until each tier is within capacity;
    // blocks pushed off NVMe are dropped.
    fn rebalance(&mut self) {
        for i in 0..3 {
            while self.tiers[i].used_bytes > self.tiers[i].capacity_bytes {
                let Some((hash, block)) = self.tiers[i].pop_lru() else {
                    break; // nothing to evict
                };
                if i + 1 < 3 {
                    self.tiers[i + 1].put(hash, block); // demote
                }
                // else: fell off the bottom → dropped
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn insert_and_hit_in_vram() {
        let mut c = KvCache::new(1000, 1000, 1000);
        c.insert(1, 100);
        assert_eq!(c.lookup(1), Some(Tier::Vram));
        assert_eq!(c.lookup(2), None); // miss
        assert!((c.hit_rate() - 0.5).abs() < 1e-9);
    }

    #[test]
    fn overflow_demotes_lru_to_ram() {
        let mut c = KvCache::new(150, 1000, 1000); // VRAM holds ~1 block of 100
        c.insert(1, 100); // VRAM
        c.insert(2, 100); // VRAM over cap → LRU (block 1) demotes to RAM
        assert_eq!(c.lookup_tier_no_promote(1), Some(Tier::Ram));
        assert_eq!(c.lookup_tier_no_promote(2), Some(Tier::Vram));
    }

    #[test]
    fn hit_promotes_back_to_vram() {
        let mut c = KvCache::new(150, 1000, 1000);
        c.insert(1, 100);
        c.insert(2, 100); // block 1 demoted to RAM
        assert_eq!(c.lookup(1), Some(Tier::Ram)); // hit reports pre-promotion tier
        // now block 1 is back in VRAM, block 2 demoted
        assert_eq!(c.lookup_tier_no_promote(1), Some(Tier::Vram));
    }

    #[test]
    fn falls_off_the_bottom_when_all_tiers_full() {
        let mut c = KvCache::new(100, 100, 100); // each tier holds 1 block
        c.insert(1, 100);
        c.insert(2, 100); // 1 → RAM
        c.insert(3, 100); // 2 → RAM evicts 1 → NVMe
        c.insert(4, 100); // cascade: 3→RAM, evict→NVMe evict 1 off bottom
        assert!(!c.contains(1), "oldest block should have fallen off NVMe");
        assert!(c.contains(4));
    }

    #[test]
    fn prefix_reuse_counts_cached_prefix() {
        let mut c = KvCache::new(1000, 1000, 1000);
        c.insert(10, 50);
        c.insert(11, 50);
        c.insert(12, 50);
        // prompt blocks [10, 11, 99, 12]: prefix 10,11 cached, 99 not → reuse 2
        assert_eq!(c.prefix_reuse(&[10, 11, 99, 12]), 2);
        // fully-cached prefix
        assert_eq!(c.prefix_reuse(&[10, 11, 12]), 3);
        // first uncached → 0
        assert_eq!(c.prefix_reuse(&[99, 10]), 0);
    }

    #[test]
    fn occupancy_accounts_bytes() {
        let mut c = KvCache::new(1000, 1000, 1000);
        c.insert(1, 100);
        c.insert(2, 250);
        let occ = c.occupancy();
        assert_eq!(occ[0].tier, Tier::Vram);
        assert_eq!(occ[0].blocks, 2);
        assert_eq!(occ[0].used_bytes, 350);
    }

    #[test]
    fn reinsert_does_not_double_count_bytes() {
        let mut c = KvCache::new(1000, 1000, 1000);
        c.insert(1, 100);
        c.insert(1, 100); // same hash again
        assert_eq!(c.occupancy()[0].used_bytes, 100);
        assert_eq!(c.occupancy()[0].blocks, 1);
    }

    #[test]
    fn tier_serde_round_trip() {
        let occ = TierOccupancy {
            tier: Tier::Nvme,
            blocks: 3,
            used_bytes: 300,
            capacity_bytes: 1000,
        };
        let j = serde_json::to_string(&occ).unwrap();
        let back: TierOccupancy = serde_json::from_str(&j).unwrap();
        assert_eq!(occ, back);
    }

    // test-only: which tier holds a block, without promotion/stats.
    impl KvCache {
        fn lookup_tier_no_promote(&self, hash: u64) -> Option<Tier> {
            Tier::ALL
                .into_iter()
                .find(|t| self.tiers[t.index()].blocks.contains_key(&hash))
        }
    }
}
