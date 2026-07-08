//! `sovereign-load-balance` — smooth weighted round-robin.
//!
//! The sovereign runtime has several compute backends of different capacity —
//! a CPU draft model, two GPUs, a cloud plane — and wants to spread work across
//! them *in proportion to capacity*. Naive weighted round-robin (emit a heavy
//! backend's N turns, then the next) bursts load; **smooth** weighted
//! round-robin (the algorithm nginx uses) interleaves the turns so that over
//! any window the selection tracks the weights closely.
//!
//! Each pick adds every backend's weight to a running `current_weight`, selects
//! the maximum, and subtracts the total weight from the winner. Over a full
//! cycle each backend is chosen exactly `weight` times, but the order is
//! spread out — `5,1,1` yields `A A B A C A A`, not `A A A A A B C`. It is
//! deterministic, so routing is reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the load-balance surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct Node {
    id: String,
    weight: i64,
    current: i64,
}

/// A smooth weighted round-robin selector.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WeightedRoundRobin {
    nodes: Vec<Node>,
}

impl WeightedRoundRobin {
    /// Build from `(id, weight)` pairs. Zero/negative weights are ignored.
    pub fn new<I, S>(backends: I) -> Self
    where
        I: IntoIterator<Item = (S, i64)>,
        S: Into<String>,
    {
        let nodes = backends
            .into_iter()
            .filter(|(_, w)| *w > 0)
            .map(|(id, weight)| Node {
                id: id.into(),
                weight,
                current: 0,
            })
            .collect();
        Self { nodes }
    }

    /// Number of active backends.
    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    /// Whether there are no backends.
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    /// Pick the next backend id, advancing the smooth-WRR state. `None` if there
    /// are no backends.
    pub fn pick(&mut self) -> Option<String> {
        if self.nodes.is_empty() {
            return None;
        }
        let total: i64 = self.nodes.iter().map(|n| n.weight).sum();
        // add weight to each running counter
        for n in &mut self.nodes {
            n.current += n.weight;
        }
        // select the max current (ties → earliest index for determinism)
        let mut best = 0usize;
        for i in 1..self.nodes.len() {
            if self.nodes[i].current > self.nodes[best].current {
                best = i;
            }
        }
        self.nodes[best].current -= total;
        Some(self.nodes[best].id.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn picks(wrr: &mut WeightedRoundRobin, n: usize) -> Vec<String> {
        (0..n).filter_map(|_| wrr.pick()).collect()
    }

    #[test]
    fn distribution_matches_weights_over_a_cycle() {
        let mut wrr = WeightedRoundRobin::new([("a", 5), ("b", 1), ("c", 1)]);
        let seq = picks(&mut wrr, 7); // one full cycle (5+1+1)
        let mut counts: HashMap<&str, usize> = HashMap::new();
        for s in &seq {
            *counts.entry(s.as_str()).or_insert(0) += 1;
        }
        assert_eq!(counts["a"], 5);
        assert_eq!(counts["b"], 1);
        assert_eq!(counts["c"], 1);
    }

    #[test]
    fn selection_is_smooth_not_bursty() {
        // the classic nginx example: 5,1,1 → a a b a c a a
        let mut wrr = WeightedRoundRobin::new([("a", 5), ("b", 1), ("c", 1)]);
        assert_eq!(picks(&mut wrr, 7), vec!["a", "a", "b", "a", "c", "a", "a"]);
    }

    #[test]
    fn cycle_repeats() {
        let mut wrr = WeightedRoundRobin::new([("a", 5), ("b", 1), ("c", 1)]);
        let first = picks(&mut wrr, 7);
        let second = picks(&mut wrr, 7);
        assert_eq!(first, second); // state returns to start each cycle
    }

    #[test]
    fn equal_weights_round_robin() {
        let mut wrr = WeightedRoundRobin::new([("x", 1), ("y", 1), ("z", 1)]);
        assert_eq!(picks(&mut wrr, 6), vec!["x", "y", "z", "x", "y", "z"]);
    }

    #[test]
    fn single_backend_always_picked() {
        let mut wrr = WeightedRoundRobin::new([("only", 3)]);
        assert_eq!(picks(&mut wrr, 4), vec!["only"; 4]);
    }

    #[test]
    fn zero_and_negative_weights_ignored() {
        let wrr = WeightedRoundRobin::new([("a", 1), ("b", 0), ("c", -5)]);
        assert_eq!(wrr.len(), 1);
    }

    #[test]
    fn empty_picks_none() {
        let mut wrr = WeightedRoundRobin::new(Vec::<(String, i64)>::new());
        assert!(wrr.is_empty());
        assert_eq!(wrr.pick(), None);
    }

    #[test]
    fn serde_round_trip() {
        let mut wrr = WeightedRoundRobin::new([("a", 2), ("b", 1)]);
        wrr.pick();
        let j = serde_json::to_string(&wrr).unwrap();
        let back: WeightedRoundRobin = serde_json::from_str(&j).unwrap();
        assert_eq!(wrr, back);
    }
}
