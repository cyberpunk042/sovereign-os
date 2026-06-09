//! `sovereign-crdt` — distributed state that converges without coordination.
//!
//! When the same state lives on several nodes that update independently — offline
//! edits, multi-region replicas, a fleet of agents sharing a counter — you either
//! coordinate every write (slow, fragile) or you let writes happen anywhere and
//! reconcile later. **CRDTs** make reconciliation automatic: every replica holds a
//! value in a lattice, and a `merge` operation that is **commutative**,
//! **associative**, and **idempotent**. Those three laws are exactly what is needed
//! for replicas to exchange snapshots in any order, any number of times, and still
//! end up identical — no conflict resolution, no central authority.
//!
//! This crate provides the four state-based building blocks:
//!
//! - [`GCounter`] — a grow-only counter; merge takes the per-replica maximum.
//! - [`PNCounter`] — increments *and* decrements, as two grow-only counters.
//! - [`LwwRegister`] — a single value where the last write (by timestamp, ties
//!   broken by replica id) wins.
//! - [`OrSet`] — an observed-remove set where, under a concurrent add and remove of
//!   the same element, the add wins, because removes only erase the specific
//!   add-tags they have actually seen.
//!
//! Each carries its own `merge`, and the tests verify the lattice laws and that
//! divergent replicas reconcile. Replicas are identified by a [`ReplicaId`].
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

/// Schema version of the CRDT surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A replica identifier (each node uses a distinct value).
pub type ReplicaId = u64;

/// A grow-only counter: increments only, merge by per-replica maximum.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct GCounter {
    counts: BTreeMap<ReplicaId, u64>,
}

impl GCounter {
    /// An empty counter.
    pub fn new() -> Self {
        Self::default()
    }

    /// Increment this replica's component by `by`.
    pub fn increment(&mut self, replica: ReplicaId, by: u64) {
        *self.counts.entry(replica).or_insert(0) += by;
    }

    /// The counter's value: the sum of all replica components.
    pub fn value(&self) -> u64 {
        self.counts.values().sum()
    }

    /// Merge `other` in, taking the maximum of each replica component.
    pub fn merge(&mut self, other: &GCounter) {
        for (&r, &c) in &other.counts {
            let e = self.counts.entry(r).or_insert(0);
            *e = (*e).max(c);
        }
    }

    /// A merged copy of `self` and `other`.
    pub fn merged(&self, other: &GCounter) -> GCounter {
        let mut out = self.clone();
        out.merge(other);
        out
    }
}

/// A counter supporting increment and decrement, as a pair of [`GCounter`]s.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct PNCounter {
    p: GCounter,
    n: GCounter,
}

impl PNCounter {
    /// An empty counter.
    pub fn new() -> Self {
        Self::default()
    }

    /// Increment this replica's component by `by`.
    pub fn increment(&mut self, replica: ReplicaId, by: u64) {
        self.p.increment(replica, by);
    }

    /// Decrement this replica's component by `by`.
    pub fn decrement(&mut self, replica: ReplicaId, by: u64) {
        self.n.increment(replica, by);
    }

    /// The signed value (increments minus decrements).
    pub fn value(&self) -> i64 {
        self.p.value() as i64 - self.n.value() as i64
    }

    /// Merge `other` in (merge both halves).
    pub fn merge(&mut self, other: &PNCounter) {
        self.p.merge(&other.p);
        self.n.merge(&other.n);
    }

    /// A merged copy.
    pub fn merged(&self, other: &PNCounter) -> PNCounter {
        let mut out = self.clone();
        out.merge(other);
        out
    }
}

/// A last-writer-wins register: a single value timestamped by `(timestamp, replica)`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LwwRegister<T> {
    value: T,
    timestamp: u64,
    replica: ReplicaId,
}

impl<T: Clone> LwwRegister<T> {
    /// A register initialised with `value`, written at `timestamp` by `replica`.
    pub fn new(value: T, timestamp: u64, replica: ReplicaId) -> Self {
        Self {
            value,
            timestamp,
            replica,
        }
    }

    /// The current value.
    pub fn value(&self) -> &T {
        &self.value
    }
    /// The current write timestamp.
    pub fn timestamp(&self) -> u64 {
        self.timestamp
    }

    /// Whether the given `(ts, replica)` is strictly newer than the current write
    /// stamp (ties on timestamp broken by the larger replica id).
    fn is_newer(&self, ts: u64, replica: ReplicaId) -> bool {
        (ts, replica) > (self.timestamp, self.replica)
    }

    /// Write `value` at `timestamp` by `replica`; applied only if it is newer than
    /// the current write (ties broken by the larger replica id).
    pub fn set(&mut self, value: T, timestamp: u64, replica: ReplicaId) {
        if self.is_newer(timestamp, replica) {
            self.value = value;
            self.timestamp = timestamp;
            self.replica = replica;
        }
    }

    /// Merge `other` in, keeping whichever write is newer.
    pub fn merge(&mut self, other: &LwwRegister<T>) {
        // if other's write is newer than ours, adopt it; otherwise keep self.
        if self.is_newer(other.timestamp, other.replica) {
            self.value = other.value.clone();
            self.timestamp = other.timestamp;
            self.replica = other.replica;
        }
    }

    /// A merged copy.
    pub fn merged(&self, other: &LwwRegister<T>) -> LwwRegister<T> {
        let mut out = self.clone();
        out.merge(other);
        out
    }
}

/// A unique add-tag: `(replica, per-replica sequence number)`.
type Tag = (ReplicaId, u64);

/// An observed-remove set: concurrent add and remove of an element resolve in
/// favour of the add.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct OrSet<T: Ord + Clone> {
    /// element -> the set of add-tags currently asserting its presence.
    adds: BTreeMap<T, BTreeSet<Tag>>,
    /// tombstones: tags whose adds have been observed-removed.
    removed: BTreeSet<Tag>,
    /// per-replica sequence counter for minting fresh tags.
    clock: BTreeMap<ReplicaId, u64>,
}

impl<T: Ord + Clone> OrSet<T> {
    /// An empty set.
    pub fn new() -> Self {
        Self {
            adds: BTreeMap::new(),
            removed: BTreeSet::new(),
            clock: BTreeMap::new(),
        }
    }

    /// Mint a fresh globally-unique tag for `replica`.
    fn fresh_tag(&mut self, replica: ReplicaId) -> Tag {
        let c = self.clock.entry(replica).or_insert(0);
        *c += 1;
        (replica, *c)
    }

    /// Add `item` on behalf of `replica` (with a fresh add-tag).
    pub fn add(&mut self, replica: ReplicaId, item: T) {
        let tag = self.fresh_tag(replica);
        self.adds.entry(item).or_default().insert(tag);
    }

    /// Remove `item`: tombstone every add-tag for it that is currently visible
    /// (observed-remove — only what this replica has seen).
    pub fn remove(&mut self, item: &T) {
        if let Some(tags) = self.adds.get(item) {
            for &t in tags {
                if !self.removed.contains(&t) {
                    self.removed.insert(t);
                }
            }
        }
    }

    /// Whether `item` is present: it has an add-tag not yet tombstoned.
    pub fn contains(&self, item: &T) -> bool {
        self.adds
            .get(item)
            .map(|tags| tags.iter().any(|t| !self.removed.contains(t)))
            .unwrap_or(false)
    }

    /// The current set elements, sorted.
    pub fn elements(&self) -> Vec<T> {
        self.adds
            .keys()
            .filter(|k| self.contains(k))
            .cloned()
            .collect()
    }

    /// Number of present elements.
    pub fn len(&self) -> usize {
        self.adds.keys().filter(|k| self.contains(k)).count()
    }
    /// Whether the set is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Merge `other` in: union the add-tags, union the tombstones, and advance the
    /// clock to the per-replica maximum.
    pub fn merge(&mut self, other: &OrSet<T>) {
        for (item, tags) in &other.adds {
            let e = self.adds.entry(item.clone()).or_default();
            for &t in tags {
                e.insert(t);
            }
        }
        for &t in &other.removed {
            self.removed.insert(t);
        }
        for (&r, &c) in &other.clock {
            let e = self.clock.entry(r).or_insert(0);
            *e = (*e).max(c);
        }
    }

    /// A merged copy.
    pub fn merged(&self, other: &OrSet<T>) -> OrSet<T> {
        let mut out = self.clone();
        out.merge(other);
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gcounter_sums_and_merges() {
        let mut a = GCounter::new();
        let mut b = GCounter::new();
        a.increment(1, 3);
        b.increment(2, 5);
        a.increment(1, 2); // replica 1 total 5
        assert_eq!(a.value(), 5);
        let m = a.merged(&b);
        assert_eq!(m.value(), 10); // 5 + 5
    }

    #[test]
    fn gcounter_merge_is_idempotent_and_commutative() {
        let mut a = GCounter::new();
        let mut b = GCounter::new();
        a.increment(1, 4);
        b.increment(1, 7); // same replica, divergent views
        b.increment(2, 1);
        // commutative
        assert_eq!(a.merged(&b).value(), b.merged(&a).value());
        // merge takes max for replica 1 (7), plus replica 2 (1) = 8
        let m = a.merged(&b);
        assert_eq!(m.value(), 8);
        // idempotent
        assert_eq!(m.merged(&m), m);
        assert_eq!(m.merged(&b), m);
    }

    #[test]
    fn pncounter_signed_value() {
        let mut c = PNCounter::new();
        c.increment(1, 10);
        c.decrement(1, 3);
        c.decrement(2, 2);
        assert_eq!(c.value(), 5);
    }

    #[test]
    fn pncounter_converges() {
        let mut a = PNCounter::new();
        let mut b = PNCounter::new();
        a.increment(1, 5);
        a.decrement(1, 1);
        b.increment(2, 3);
        b.decrement(2, 4);
        let m1 = a.merged(&b);
        let m2 = b.merged(&a);
        assert_eq!(m1.value(), m2.value());
        assert_eq!(m1.value(), (5 - 1) + (3 - 4)); // 4 + (-1) = 3
    }

    #[test]
    fn lww_last_write_wins() {
        let mut r = LwwRegister::new("a", 1, 1);
        r.set("b", 5, 1);
        assert_eq!(*r.value(), "b");
        r.set("c", 3, 1); // older → ignored
        assert_eq!(*r.value(), "b");
    }

    #[test]
    fn lww_tie_broken_by_replica() {
        let mut r1 = LwwRegister::new("x", 10, 1);
        let r2 = LwwRegister::new("y", 10, 2); // same ts, higher replica wins
        r1.merge(&r2);
        assert_eq!(*r1.value(), "y");
        // commutative: merging the other way gives the same winner.
        let mut r2b = LwwRegister::new("y", 10, 2);
        r2b.merge(&LwwRegister::new("x", 10, 1));
        assert_eq!(*r2b.value(), "y");
    }

    #[test]
    fn lww_merge_commutes() {
        let a = LwwRegister::new(1, 7, 1);
        let b = LwwRegister::new(2, 9, 2);
        assert_eq!(*a.merged(&b).value(), *b.merged(&a).value());
        assert_eq!(*a.merged(&b).value(), 2); // ts 9 wins
    }

    #[test]
    fn orset_add_remove_contains() {
        let mut s: OrSet<String> = OrSet::new();
        s.add(1, "x".to_string());
        assert!(s.contains(&"x".to_string()));
        s.remove(&"x".to_string());
        assert!(!s.contains(&"x".to_string()));
        assert!(s.is_empty());
    }

    #[test]
    fn orset_add_wins_concurrent() {
        // replica 1 adds x; replica 2 receives it, removes it; concurrently
        // replica 1 re-adds x with a new tag. After merge, x is present.
        let mut r1: OrSet<String> = OrSet::new();
        r1.add(1, "x".to_string());

        let mut r2 = r1.clone();
        r2.remove(&"x".to_string()); // r2 tombstones the tag it saw

        r1.add(1, "x".to_string()); // r1 adds a fresh, unseen tag

        // merge in both directions → same result, x present (add wins).
        let m1 = r1.merged(&r2);
        let m2 = r2.merged(&r1);
        assert!(m1.contains(&"x".to_string()));
        assert_eq!(m1.elements(), m2.elements());
    }

    #[test]
    fn orset_remove_is_observed_only() {
        // a remove only erases tags it has actually seen; a concurrent add on
        // another replica survives.
        let mut r1: OrSet<i32> = OrSet::new();
        r1.add(1, 42);
        let mut r2: OrSet<i32> = OrSet::new();
        r2.add(2, 42); // independent add of the same element, different tag

        let mut r1b = r1.clone();
        r1b.remove(&42); // removes only r1's tag

        let merged = r1b.merged(&r2);
        assert!(merged.contains(&42)); // r2's add survives
    }

    #[test]
    fn orset_merge_idempotent_and_associative() {
        let mut a: OrSet<i32> = OrSet::new();
        a.add(1, 1);
        a.add(1, 2);
        let mut b: OrSet<i32> = OrSet::new();
        b.add(2, 2);
        b.add(2, 3);
        b.remove(&3);
        let mut c: OrSet<i32> = OrSet::new();
        c.add(3, 4);

        // associativity: (a∪b)∪c == a∪(b∪c)
        let left = a.merged(&b).merged(&c);
        let right = a.merged(&b.merged(&c));
        assert_eq!(left.elements(), right.elements());
        // idempotence
        assert_eq!(left.merged(&left).elements(), left.elements());
        assert_eq!(left.elements(), vec![1, 2, 4]);
    }

    #[test]
    fn serde_round_trip() {
        let mut g = GCounter::new();
        g.increment(1, 5);
        g.increment(2, 3);
        let j = serde_json::to_string(&g).unwrap();
        let back: GCounter = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);

        let mut s: OrSet<String> = OrSet::new();
        s.add(1, "a".to_string());
        s.add(2, "b".to_string());
        let js = serde_json::to_string(&s).unwrap();
        let backs: OrSet<String> = serde_json::from_str(&js).unwrap();
        assert_eq!(s, backs);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
