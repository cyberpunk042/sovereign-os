//! `sovereign-rendezvous-hash` — place keys so that almost nothing moves on a change.
//!
//! Sharding a keyspace across nodes — cache slots, KV partitions, model replicas —
//! runs into the same trap as a naive `hash(key) % n`: change `n` and almost every
//! key remaps. A consistent-hash ring fixes that but needs virtual nodes to balance.
//! **Rendezvous hashing** (highest random weight, Thaler & Ravishankar) fixes it
//! more directly: for a key, compute a score for *every* node from `hash(node, key)`
//! and assign the key to the highest-scoring node. No ring, no virtual nodes.
//!
//! Its defining property falls out of that rule. Removing a node only affects the
//! keys whose top score was that node — they fall through to their second choice —
//! and *no other key moves*, because every surviving node's score for every other
//! key is unchanged. Adding a node only steals the keys for which it now scores
//! highest. So a membership change disturbs only its own fair share of the keyspace.
//!
//! Capacity is handled with **weights**: the score is `weight / -ln(u)` for a
//! uniform `u` derived from the hash, which makes a node's expected share of keys
//! proportional to its weight. [`RendezvousHash::select`] returns the assigned node;
//! [`RendezvousHash::select_k`] returns the top `k` nodes in score order — a stable
//! preference list for replication and failover. The scoring is deterministic, so
//! the same membership always maps a key the same way.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the rendezvous-hash surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

const FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01B3;

/// A node in the rendezvous set: an id and a positive capacity weight.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct Node {
    id: String,
    weight: f64,
}

/// A weighted rendezvous-hashing node set.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct RendezvousHash {
    nodes: Vec<Node>,
}

/// Hash node bytes then key bytes through FNV-1a and a SplitMix64 finalizer.
fn hash(node: &str, key: &[u8]) -> u64 {
    let mut h = FNV_OFFSET;
    for &b in node.as_bytes() {
        h ^= b as u64;
        h = h.wrapping_mul(FNV_PRIME);
    }
    // separator so ("ab","c") and ("a","bc") do not collide.
    h ^= 0xFF;
    h = h.wrapping_mul(FNV_PRIME);
    for &b in key {
        h ^= b as u64;
        h = h.wrapping_mul(FNV_PRIME);
    }
    // SplitMix64 finalizer for good avalanche.
    let mut z = h.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

/// Weighted rendezvous score: `weight / -ln(u)` with `u` uniform in `(0, 1)`.
fn score(node: &Node, key: &[u8]) -> f64 {
    let h = hash(&node.id, key);
    // u in (0, 1): map the top 53 bits, never 0 or 1.
    let u = ((h >> 11) as f64 + 1.0) / ((1u64 << 53) as f64 + 1.0);
    node.weight / -u.ln()
}

impl RendezvousHash {
    /// An empty node set.
    pub fn new() -> Self {
        Self::default()
    }

    /// Number of nodes.
    pub fn len(&self) -> usize {
        self.nodes.len()
    }
    /// Whether there are no nodes.
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }
    /// The node ids currently in the set, in insertion order.
    pub fn nodes(&self) -> Vec<&str> {
        self.nodes.iter().map(|n| n.id.as_str()).collect()
    }

    /// Add (or update the weight of) a node. A non-positive or non-finite weight is
    /// treated as `1.0`.
    pub fn add_node(&mut self, id: impl Into<String>, weight: f64) {
        let id = id.into();
        let weight = if weight.is_finite() && weight > 0.0 {
            weight
        } else {
            1.0
        };
        if let Some(n) = self.nodes.iter_mut().find(|n| n.id == id) {
            n.weight = weight;
        } else {
            self.nodes.push(Node { id, weight });
        }
    }

    /// Remove a node by id; returns whether it was present.
    pub fn remove_node(&mut self, id: &str) -> bool {
        let before = self.nodes.len();
        self.nodes.retain(|n| n.id != id);
        self.nodes.len() != before
    }

    /// The node a `key` is assigned to (highest score), or `None` if empty.
    pub fn select(&self, key: &[u8]) -> Option<&str> {
        self.nodes
            .iter()
            .map(|n| (score(n, key), n))
            .max_by(|a, b| a.0.total_cmp(&b.0).then(b.1.id.cmp(&a.1.id)))
            .map(|(_, n)| n.id.as_str())
    }

    /// The top `k` nodes for a `key`, in descending score order — a stable
    /// preference list for replication/failover.
    pub fn select_k(&self, key: &[u8], k: usize) -> Vec<&str> {
        let mut scored: Vec<(f64, &Node)> = self.nodes.iter().map(|n| (score(n, key), n)).collect();
        // sort by score desc, ties by id desc to match `select`.
        scored.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.id.cmp(&b.1.id)));
        scored
            .into_iter()
            .take(k)
            .map(|(_, n)| n.id.as_str())
            .collect()
    }

    /// Convenience: select for a string key.
    pub fn select_str(&self, key: &str) -> Option<&str> {
        self.select(key.as_bytes())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn ring(ids: &[&str]) -> RendezvousHash {
        let mut r = RendezvousHash::new();
        for &id in ids {
            r.add_node(id, 1.0);
        }
        r
    }

    #[test]
    fn empty_selects_none() {
        let r = RendezvousHash::new();
        assert!(r.select(b"key").is_none());
    }

    #[test]
    fn single_node_always_selected() {
        let r = ring(&["a"]);
        for k in ["x", "y", "z"] {
            assert_eq!(r.select_str(k), Some("a"));
        }
    }

    #[test]
    fn selection_is_deterministic() {
        let r = ring(&["a", "b", "c", "d"]);
        let first = r.select_str("hello").unwrap().to_string();
        for _ in 0..5 {
            assert_eq!(r.select_str("hello"), Some(first.as_str()));
        }
    }

    #[test]
    fn distribution_is_roughly_even() {
        let r = ring(&["a", "b", "c", "d", "e"]);
        let mut counts: HashMap<&str, u32> = HashMap::new();
        for i in 0..50_000u32 {
            let key = format!("key{i}");
            *counts.entry(r.select_str(&key).unwrap()).or_insert(0) += 1;
        }
        let expected = 50_000.0 / 5.0;
        for (&node, &c) in &counts {
            let dev = (c as f64 - expected).abs() / expected;
            assert!(dev < 0.1, "node {node} got {c}, dev {dev}");
        }
    }

    #[test]
    fn weights_bias_distribution() {
        let mut r = RendezvousHash::new();
        r.add_node("small", 1.0);
        r.add_node("big", 4.0);
        let mut big = 0u32;
        let mut small = 0u32;
        for i in 0..50_000u32 {
            match r.select_str(&format!("k{i}")).unwrap() {
                "big" => big += 1,
                _ => small += 1,
            }
        }
        // big should get roughly 4x the small node's share.
        let ratio = big as f64 / small as f64;
        assert!(
            (3.0..5.0).contains(&ratio),
            "ratio {ratio} (big {big} small {small})"
        );
    }

    #[test]
    fn removing_a_node_only_moves_its_keys() {
        let r = ring(&["a", "b", "c", "d", "e"]);
        // record assignments.
        let keys: Vec<String> = (0..20_000).map(|i| format!("key{i}")).collect();
        let before: HashMap<&str, String> = keys
            .iter()
            .map(|k| (k.as_str(), r.select_str(k).unwrap().to_string()))
            .collect();

        let mut r2 = r.clone();
        assert!(r2.remove_node("c"));

        for k in &keys {
            let new = r2.select_str(k).unwrap();
            let old = &before[k.as_str()];
            if old == "c" {
                // its keys move to some other node.
                assert_ne!(new, "c");
            } else {
                // every key NOT on c keeps its node — the rendezvous guarantee.
                assert_eq!(new, old.as_str(), "key {k} moved unexpectedly");
            }
        }
    }

    #[test]
    fn adding_a_node_only_steals_a_fair_share() {
        let r = ring(&["a", "b", "c", "d"]);
        let keys: Vec<String> = (0..20_000).map(|i| format!("k{i}")).collect();
        let before: HashMap<&str, String> = keys
            .iter()
            .map(|k| (k.as_str(), r.select_str(k).unwrap().to_string()))
            .collect();

        let mut r2 = r.clone();
        r2.add_node("e", 1.0);

        let mut moved = 0;
        for k in &keys {
            let new = r2.select_str(k).unwrap();
            if new != before[k.as_str()] {
                moved += 1;
                assert_eq!(new, "e", "key {k} moved to a node other than the new one");
            }
        }
        // roughly 1/5 of keys should move to the new node.
        let frac = moved as f64 / keys.len() as f64;
        assert!((0.12..0.28).contains(&frac), "moved fraction {frac}");
    }

    #[test]
    fn select_k_orders_and_is_consistent_with_select() {
        let r = ring(&["a", "b", "c", "d", "e"]);
        let top = r.select_k(b"some-key", 3);
        assert_eq!(top.len(), 3);
        // the first of the preference list equals the single selection.
        assert_eq!(Some(top[0]), r.select(b"some-key"));
        // distinct nodes.
        let set: std::collections::HashSet<_> = top.iter().collect();
        assert_eq!(set.len(), 3);
    }

    #[test]
    fn update_weight_in_place() {
        let mut r = RendezvousHash::new();
        r.add_node("a", 1.0);
        r.add_node("a", 5.0); // update, not duplicate
        assert_eq!(r.len(), 1);
    }

    #[test]
    fn serde_round_trip() {
        let mut r = RendezvousHash::new();
        r.add_node("a", 1.0);
        r.add_node("b", 2.0);
        let j = serde_json::to_string(&r).unwrap();
        let back: RendezvousHash = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
        assert_eq!(r.select_str("k"), back.select_str("k"));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
