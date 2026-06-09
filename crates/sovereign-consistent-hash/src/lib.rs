//! `sovereign-consistent-hash` — shard keys so scaling barely moves anything.
//!
//! When requests, cache shards, or sessions are spread across a set of worker
//! nodes, the naive map `node = hash(key) % n` has a fatal flaw: change `n` (a
//! worker joins or dies) and *almost every* key moves to a different node, blowing
//! away every cache at once. **Consistent hashing** fixes this. Place both the
//! nodes and the keys on a circular hash space (a "ring"); a key belongs to the
//! first node found clockwise from it. Add a node and only the keys between it and
//! its predecessor move — about `1/n` of them — leaving the rest exactly where
//! they were.
//!
//! To keep the load even (a few randomly-placed nodes would otherwise carve
//! lopsided arcs), each node is hashed to many **virtual nodes** scattered around
//! the ring, so every real node ends up owning a similar total share.
//!
//! [`HashRing::add_node`] / [`remove_node`] reshape the ring; [`get`] resolves a
//! key to its owning node; [`get_n`] returns the next `n` distinct nodes clockwise
//! (for replication). Hashing is deterministic, so the same nodes always produce
//! the same ring.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Schema version of the consistent-hash surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Default number of virtual nodes per real node.
pub const DEFAULT_VNODES: usize = 160;

/// A consistent hash ring over `String` node ids.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HashRing {
    /// ring position → node id.
    ring: BTreeMap<u64, String>,
    /// the set of real nodes.
    nodes: Vec<String>,
    vnodes: usize,
}

impl HashRing {
    /// An empty ring with the default virtual-node count.
    pub fn new() -> Self {
        Self::with_vnodes(DEFAULT_VNODES)
    }

    /// An empty ring with `vnodes` virtual nodes per real node.
    ///
    /// # Panics
    /// Panics if `vnodes == 0`.
    pub fn with_vnodes(vnodes: usize) -> Self {
        assert!(vnodes > 0, "vnodes must be > 0");
        Self {
            ring: BTreeMap::new(),
            nodes: Vec::new(),
            vnodes,
        }
    }

    /// The real nodes currently on the ring (sorted).
    pub fn nodes(&self) -> Vec<String> {
        let mut n = self.nodes.clone();
        n.sort();
        n
    }

    /// Number of real nodes.
    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    /// Whether the ring has no nodes.
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    /// Add a node (placing its virtual nodes on the ring). Re-adding is a no-op.
    pub fn add_node(&mut self, node: &str) {
        if self.nodes.iter().any(|n| n == node) {
            return;
        }
        self.nodes.push(node.to_string());
        for v in 0..self.vnodes {
            let pos = hash(&format!("{node}#{v}"));
            self.ring.insert(pos, node.to_string());
        }
    }

    /// Remove a node and all its virtual nodes.
    pub fn remove_node(&mut self, node: &str) {
        self.nodes.retain(|n| n != node);
        self.ring.retain(|_, n| n != node);
    }

    /// The node that owns `key` (the first node clockwise from `hash(key)`), or
    /// `None` if the ring is empty.
    pub fn get(&self, key: &str) -> Option<&str> {
        if self.ring.is_empty() {
            return None;
        }
        let h = hash(key);
        // first ring entry with position >= h, wrapping to the first entry.
        self.ring
            .range(h..)
            .next()
            .or_else(|| self.ring.iter().next())
            .map(|(_, n)| n.as_str())
    }

    /// The next `n` *distinct* nodes clockwise from `key` (for replication).
    /// Returns fewer than `n` only if the ring has fewer real nodes.
    pub fn get_n(&self, key: &str, n: usize) -> Vec<String> {
        if self.ring.is_empty() || n == 0 {
            return Vec::new();
        }
        let h = hash(key);
        let mut out: Vec<String> = Vec::new();
        // iterate clockwise from h, wrapping once, collecting distinct nodes.
        let forward = self.ring.range(h..).chain(self.ring.range(..h));
        for (_, node) in forward {
            if !out.iter().any(|x| x == node) {
                out.push(node.clone());
                if out.len() == n.min(self.nodes.len()) {
                    break;
                }
            }
        }
        out
    }
}

impl Default for HashRing {
    fn default() -> Self {
        Self::new()
    }
}

/// FNV-1a 64-bit hash with an avalanche finalizer (well-spread ring positions).
fn hash(s: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in s.bytes() {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h ^= h >> 33;
    h = h.wrapping_mul(0xff51_afd7_ed55_8ccd);
    h ^= h >> 33;
    h
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn routes_keys_to_nodes() {
        let mut r = HashRing::new();
        for n in ["a", "b", "c"] {
            r.add_node(n);
        }
        // every key maps to one of the nodes, deterministically.
        for i in 0..100 {
            let key = format!("key{i}");
            let node = r.get(&key).unwrap().to_string();
            assert!(["a", "b", "c"].contains(&node.as_str()));
            assert_eq!(r.get(&key), Some(node.as_str())); // stable
        }
    }

    #[test]
    fn load_is_roughly_balanced() {
        let mut r = HashRing::new();
        for n in ["a", "b", "c", "d"] {
            r.add_node(n);
        }
        let mut counts = std::collections::HashMap::new();
        let total = 10_000;
        for i in 0..total {
            let node = r.get(&format!("k{i}")).unwrap().to_string();
            *counts.entry(node).or_insert(0) += 1;
        }
        // each of 4 nodes should get roughly 25% (within a generous margin).
        for (_, c) in counts {
            let frac = c as f64 / total as f64;
            assert!((frac - 0.25).abs() < 0.08, "imbalanced: {frac}");
        }
    }

    #[test]
    fn adding_a_node_moves_few_keys() {
        let mut r = HashRing::new();
        for n in ["a", "b", "c"] {
            r.add_node(n);
        }
        let keys: Vec<String> = (0..5000).map(|i| format!("key{i}")).collect();
        let before: Vec<String> = keys.iter().map(|k| r.get(k).unwrap().to_string()).collect();

        r.add_node("d");
        let after: Vec<String> = keys.iter().map(|k| r.get(k).unwrap().to_string()).collect();

        let moved = before.iter().zip(&after).filter(|(a, b)| a != b).count();
        let frac = moved as f64 / keys.len() as f64;
        // adding a 4th node should move roughly 1/4 of keys, certainly far less
        // than the ~3/4 a modulo scheme would move.
        assert!(frac < 0.4, "moved {frac} of keys (expected ~0.25)");
        // and all moved keys went TO the new node 'd'
        for (a, b) in before.iter().zip(&after) {
            if a != b {
                assert_eq!(b, "d");
            }
        }
    }

    #[test]
    fn removing_a_node_redistributes_only_its_keys() {
        let mut r = HashRing::new();
        for n in ["a", "b", "c"] {
            r.add_node(n);
        }
        let keys: Vec<String> = (0..3000).map(|i| format!("k{i}")).collect();
        let before: Vec<String> = keys.iter().map(|k| r.get(k).unwrap().to_string()).collect();
        r.remove_node("b");
        for (k, was) in keys.iter().zip(&before) {
            let now = r.get(k).unwrap();
            if was != "b" {
                // keys not on 'b' stay exactly where they were.
                assert_eq!(now, was);
            } else {
                assert!(now == "a" || now == "c");
            }
        }
    }

    #[test]
    fn get_n_returns_distinct_replicas() {
        let mut r = HashRing::new();
        for n in ["a", "b", "c", "d"] {
            r.add_node(n);
        }
        let replicas = r.get_n("some-key", 3);
        assert_eq!(replicas.len(), 3);
        // distinct
        let mut s = replicas.clone();
        s.sort();
        s.dedup();
        assert_eq!(s.len(), 3);
        // the first replica is the primary owner
        assert_eq!(replicas[0], r.get("some-key").unwrap());
    }

    #[test]
    fn empty_ring() {
        let r = HashRing::new();
        assert!(r.is_empty());
        assert_eq!(r.get("anything"), None);
        assert!(r.get_n("x", 3).is_empty());
    }

    #[test]
    fn readd_is_noop() {
        let mut r = HashRing::with_vnodes(10);
        r.add_node("a");
        r.add_node("a");
        assert_eq!(r.len(), 1);
    }

    #[test]
    fn serde_round_trip() {
        let mut r = HashRing::with_vnodes(20);
        r.add_node("a");
        r.add_node("b");
        let j = serde_json::to_string(&r).unwrap();
        let back: HashRing = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
        assert_eq!(back.get("key1"), r.get("key1"));
    }
}
