//! `sovereign-vector-clock` — did this happen before that, or at the same time?
//!
//! Across replicas there is no single clock to trust, and a scalar timestamp cannot
//! tell a *causal* order from a coincidence: two events with different wall-clock
//! times may be genuinely **concurrent** (neither could have influenced the other).
//! Getting that distinction right is what lets a system order events, detect
//! conflicts, and reconcile state correctly.
//!
//! A [`VectorClock`] answers it exactly. Each replica keeps a counter per replica;
//! it [`tick`](VectorClock::tick)s its own counter on each local event and
//! [`merge`](VectorClock::merge)s in the clock attached to every message it
//! receives (taking the per-replica maximum). Comparing two clocks then yields one
//! of four [`Ordering`]s: one strictly **Before** the other, one **After**,
//! **Equal**, or **Concurrent** — and concurrency is exactly the case a single
//! number can never detect.
//!
//! When full concurrency detection is more than you need, a [`LamportClock`] gives
//! a single integer that is cheap and guarantees only the one-way implication that
//! still matters: if `a` happened-before `b`, then `a`'s stamp is less than `b`'s.
//! That is enough for a deterministic total order (ties broken by replica id) over
//! events, even though it cannot, by itself, tell concurrency from causality.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

/// Schema version of the vector-clock surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A replica identifier.
pub type ReplicaId = u64;

/// The causal relationship between two vector clocks.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Ordering {
    /// The clocks are identical.
    Equal,
    /// The left clock strictly happened-before the right.
    Before,
    /// The left clock strictly happened-after the right.
    After,
    /// Neither happened-before the other: they are concurrent.
    Concurrent,
}

/// A vector clock: one counter per replica, tracking causal history.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct VectorClock {
    clock: BTreeMap<ReplicaId, u64>,
}

impl VectorClock {
    /// An empty clock (all components zero).
    pub fn new() -> Self {
        Self::default()
    }

    /// The counter for `replica` (zero if never seen).
    pub fn get(&self, replica: ReplicaId) -> u64 {
        self.clock.get(&replica).copied().unwrap_or(0)
    }

    /// Record a local event on `replica`: increment its counter. Returns the new
    /// value.
    pub fn tick(&mut self, replica: ReplicaId) -> u64 {
        let e = self.clock.entry(replica).or_insert(0);
        *e += 1;
        *e
    }

    /// Merge `other` in by taking the per-replica maximum (used on receive).
    pub fn merge(&mut self, other: &VectorClock) {
        for (&r, &c) in &other.clock {
            let e = self.clock.entry(r).or_insert(0);
            *e = (*e).max(c);
        }
    }

    /// A merged copy.
    pub fn merged(&self, other: &VectorClock) -> VectorClock {
        let mut out = self.clone();
        out.merge(other);
        out
    }

    /// Compare causal order with `other`.
    pub fn compare(&self, other: &VectorClock) -> Ordering {
        // consider every replica mentioned in either clock.
        let keys: BTreeSet<ReplicaId> = self
            .clock
            .keys()
            .chain(other.clock.keys())
            .copied()
            .collect();
        let mut less = false; // some component self < other
        let mut greater = false; // some component self > other
        for r in keys {
            let a = self.get(r);
            let b = other.get(r);
            if a < b {
                less = true;
            } else if a > b {
                greater = true;
            }
        }
        match (less, greater) {
            (false, false) => Ordering::Equal,
            (true, false) => Ordering::Before,
            (false, true) => Ordering::After,
            (true, true) => Ordering::Concurrent,
        }
    }

    /// Whether `self` strictly happened-before `other`.
    pub fn happens_before(&self, other: &VectorClock) -> bool {
        matches!(self.compare(other), Ordering::Before)
    }

    /// Whether `self` and `other` are concurrent (causally independent).
    pub fn concurrent_with(&self, other: &VectorClock) -> bool {
        matches!(self.compare(other), Ordering::Concurrent)
    }
}

/// A scalar Lamport logical clock.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct LamportClock {
    time: u64,
    replica: ReplicaId,
}

impl LamportClock {
    /// A clock for `replica`, starting at zero.
    pub fn new(replica: ReplicaId) -> Self {
        Self { time: 0, replica }
    }

    /// The current logical time.
    pub fn time(&self) -> u64 {
        self.time
    }

    /// Record a local event: increment and return the new time.
    pub fn tick(&mut self) -> u64 {
        self.time += 1;
        self.time
    }

    /// Observe a message stamped `received`: advance to `max(self, received) + 1`.
    pub fn observe(&mut self, received: u64) -> u64 {
        self.time = self.time.max(received) + 1;
        self.time
    }

    /// The totally-ordered stamp `(time, replica)` — a deterministic tiebreak that
    /// is consistent with causality.
    pub fn stamp(&self) -> (u64, ReplicaId) {
        (self.time, self.replica)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tick_increments() {
        let mut v = VectorClock::new();
        assert_eq!(v.tick(1), 1);
        assert_eq!(v.tick(1), 2);
        assert_eq!(v.get(1), 2);
        assert_eq!(v.get(2), 0);
    }

    #[test]
    fn causal_chain_happens_before() {
        // a then (a merged + tick) → strictly after.
        let mut a = VectorClock::new();
        a.tick(1);
        let mut b = a.clone();
        b.tick(2);
        assert!(a.happens_before(&b));
        assert_eq!(a.compare(&b), Ordering::Before);
        assert_eq!(b.compare(&a), Ordering::After);
    }

    #[test]
    fn concurrent_detected() {
        // two replicas tick independently from the same origin → concurrent.
        let origin = VectorClock::new();
        let mut a = origin.clone();
        a.tick(1);
        let mut b = origin.clone();
        b.tick(2);
        assert_eq!(a.compare(&b), Ordering::Concurrent);
        assert!(a.concurrent_with(&b));
        assert!(!a.happens_before(&b));
    }

    #[test]
    fn equal_clocks() {
        let mut a = VectorClock::new();
        a.tick(1);
        a.tick(2);
        let b = a.clone();
        assert_eq!(a.compare(&b), Ordering::Equal);
    }

    #[test]
    fn merge_takes_max() {
        let mut a = VectorClock::new();
        a.tick(1);
        a.tick(1); // r1 = 2
        let mut b = VectorClock::new();
        b.tick(1); // r1 = 1
        b.tick(2); // r2 = 1
        let m = a.merged(&b);
        assert_eq!(m.get(1), 2);
        assert_eq!(m.get(2), 1);
    }

    #[test]
    fn merge_makes_receiver_after_sender() {
        // replica 2 receives replica 1's clock and ticks → strictly after sender.
        let mut sender = VectorClock::new();
        sender.tick(1);
        let mut receiver = VectorClock::new();
        receiver.tick(2);
        receiver.merge(&sender);
        receiver.tick(2);
        assert_eq!(sender.compare(&receiver), Ordering::Before);
    }

    #[test]
    fn transitive_causality() {
        let mut a = VectorClock::new();
        a.tick(1);
        let mut b = a.clone();
        b.tick(2);
        let mut c = b.clone();
        c.tick(3);
        assert!(a.happens_before(&b));
        assert!(b.happens_before(&c));
        assert!(a.happens_before(&c)); // transitive
    }

    #[test]
    fn lamport_monotonic() {
        let mut l = LamportClock::new(1);
        assert_eq!(l.tick(), 1);
        assert_eq!(l.tick(), 2);
        // observe a higher remote time jumps ahead.
        assert_eq!(l.observe(10), 11);
        assert_eq!(l.tick(), 12);
    }

    #[test]
    fn lamport_preserves_causality() {
        // if a -> b (b observed a's stamp), then stamp(a) < stamp(b).
        let mut a = LamportClock::new(1);
        let sa = a.tick();
        let mut b = LamportClock::new(2);
        b.observe(sa);
        assert!(a.stamp() < b.stamp(), "{:?} !< {:?}", a.stamp(), b.stamp());
    }

    #[test]
    fn lamport_stamp_breaks_ties_by_replica() {
        let a = LamportClock {
            time: 5,
            replica: 1,
        };
        let b = LamportClock {
            time: 5,
            replica: 2,
        };
        assert!(a.stamp() < b.stamp());
    }

    #[test]
    fn serde_round_trip() {
        let mut v = VectorClock::new();
        v.tick(1);
        v.tick(2);
        let j = serde_json::to_string(&v).unwrap();
        let back: VectorClock = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
        let l = LamportClock {
            time: 7,
            replica: 3,
        };
        let jl = serde_json::to_string(&l).unwrap();
        assert_eq!(serde_json::from_str::<LamportClock>(&jl).unwrap(), l);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
