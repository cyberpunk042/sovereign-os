//! `sovereign-cuckoo-filter` — approximate membership that can also *forget*.
//!
//! A Bloom filter answers "have I seen this?" in tiny space but can never remove
//! an item — so it cannot back a sliding window of "tokens seen in the last N
//! steps", where old entries must expire. A **cuckoo filter** keeps the small
//! footprint and adds deletion. Instead of setting bits, it stores a short
//! *fingerprint* of each item in a hash table; every item has two candidate
//! buckets, and on a collision it relocates an existing fingerprint to *its* other
//! bucket (the "cuckoo" kick), making room. Because both candidate buckets are
//! derived from the fingerprint alone — `i2 = i1 XOR hash(fingerprint)` — a
//! stored fingerprint can always compute its alternate location without knowing
//! the original item, which is what lets relocation (and therefore deletion)
//! work.
//!
//! Lookups check both buckets for the fingerprint; membership has a tunable
//! false-positive rate but **no false negatives** for items actually present.
//! Deletion removes one matching fingerprint. Inserts can fail when the table is
//! near capacity and a kick chain exceeds the limit — reported honestly as a
//! [`CuckooError`] rather than silently corrupting the filter.
//!
//! Kicks use a seeded **splitmix64** generator, so the filter is deterministic
//! and serializable.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the cuckoo-filter surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Slots per bucket (4 is the standard choice balancing load and lookups).
pub const BUCKET_SIZE: usize = 4;

/// Maximum relocation attempts before an insert is declared a failure.
pub const MAX_KICKS: usize = 500;

/// Insert errors.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum CuckooError {
    /// The filter is too full: a kick chain exceeded [`MAX_KICKS`].
    #[error("cuckoo filter is full (kick chain exceeded {0} relocations)")]
    Full(usize),
}

/// A cuckoo filter over byte keys.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CuckooFilter {
    /// `num_buckets * BUCKET_SIZE` fingerprint slots; 0 means empty.
    buckets: Vec<u8>,
    num_buckets: usize,
    count: usize,
    rng: u64,
}

impl CuckooFilter {
    /// A filter with capacity for about `capacity` items (rounded up to a power
    /// of two of buckets), seeded with `seed`.
    pub fn new(capacity: usize, seed: u64) -> Self {
        let needed = (capacity / BUCKET_SIZE).max(1);
        let num_buckets = needed.next_power_of_two();
        Self {
            buckets: vec![0u8; num_buckets * BUCKET_SIZE],
            num_buckets,
            count: 0,
            rng: seed | 1,
        }
    }

    /// Number of stored items.
    pub fn len(&self) -> usize {
        self.count
    }

    /// Whether the filter holds no items.
    pub fn is_empty(&self) -> bool {
        self.count == 0
    }

    /// Total fingerprint slots.
    pub fn capacity(&self) -> usize {
        self.num_buckets * BUCKET_SIZE
    }

    fn hash(key: &[u8]) -> u64 {
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        for &b in key {
            h ^= b as u64;
            h = h.wrapping_mul(0x0000_0100_0000_01b3);
        }
        h ^= h >> 33;
        h = h.wrapping_mul(0xff51_afd7_ed55_8ccd);
        h ^= h >> 33;
        h
    }

    /// Fingerprint: a non-zero byte derived from the key's hash.
    fn fingerprint(h: u64) -> u8 {
        let fp = (h & 0xFF) as u8;
        if fp == 0 { 1 } else { fp }
    }

    fn index_for(&self, h: u64) -> usize {
        // Use the HIGH bits for the bucket index so it is independent of the
        // fingerprint (taken from the low byte). num_buckets is a power of two,
        // so a mask is an exact modulo. If index and fingerprint shared bits,
        // items with the same fingerprint would cluster into the same buckets and
        // wreck the false-positive rate.
        ((h >> 32) as usize) & (self.num_buckets - 1)
    }

    /// The alternate bucket for fingerprint `fp` given bucket `i`.
    fn alt_index(&self, i: usize, fp: u8) -> usize {
        let fph = Self::hash(&[fp]);
        (i ^ self.index_for(fph)) % self.num_buckets
    }

    fn bucket(&self, i: usize) -> &[u8] {
        &self.buckets[i * BUCKET_SIZE..(i + 1) * BUCKET_SIZE]
    }

    fn try_insert_into(&mut self, i: usize, fp: u8) -> bool {
        let base = i * BUCKET_SIZE;
        for slot in 0..BUCKET_SIZE {
            if self.buckets[base + slot] == 0 {
                self.buckets[base + slot] = fp;
                return true;
            }
        }
        false
    }

    fn next_rng(&mut self) -> u64 {
        self.rng = self.rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.rng;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Insert `key`. Returns `Ok(())` on success or `Err(Full)` if the filter is
    /// too full to place it. Inserting the same key twice stores it twice (so a
    /// matching number of deletes is needed) — mirroring the reference design.
    pub fn insert(&mut self, key: &[u8]) -> Result<(), CuckooError> {
        let h = Self::hash(key);
        let fp = Self::fingerprint(h);
        let i1 = self.index_for(h);
        let i2 = self.alt_index(i1, fp);

        if self.try_insert_into(i1, fp) || self.try_insert_into(i2, fp) {
            self.count += 1;
            return Ok(());
        }

        // both candidate buckets full: relocate (kick) up to MAX_KICKS times.
        let mut i = if self.next_rng() & 1 == 0 { i1 } else { i2 };
        let mut carry = fp;
        for _ in 0..MAX_KICKS {
            let slot = (self.next_rng() as usize) % BUCKET_SIZE;
            let pos = i * BUCKET_SIZE + slot;
            std::mem::swap(&mut carry, &mut self.buckets[pos]);
            // the evicted fingerprint must go to its alternate bucket.
            i = self.alt_index(i, carry);
            if self.try_insert_into(i, carry) {
                self.count += 1;
                return Ok(());
            }
        }
        Err(CuckooError::Full(MAX_KICKS))
    }

    /// Whether `key` is (probably) present. No false negatives; false positives
    /// occur at a small rate set by the fingerprint width.
    pub fn contains(&self, key: &[u8]) -> bool {
        let h = Self::hash(key);
        let fp = Self::fingerprint(h);
        let i1 = self.index_for(h);
        let i2 = self.alt_index(i1, fp);
        self.bucket(i1).contains(&fp) || self.bucket(i2).contains(&fp)
    }

    /// Remove one occurrence of `key`. Returns `true` if a matching fingerprint
    /// was found and removed. Deleting a key never added can (rarely) remove a
    /// colliding fingerprint — the standard cuckoo-filter caveat.
    pub fn delete(&mut self, key: &[u8]) -> bool {
        let h = Self::hash(key);
        let fp = Self::fingerprint(h);
        let i1 = self.index_for(h);
        let i2 = self.alt_index(i1, fp);
        for i in [i1, i2] {
            let base = i * BUCKET_SIZE;
            for slot in 0..BUCKET_SIZE {
                if self.buckets[base + slot] == fp {
                    self.buckets[base + slot] = 0;
                    self.count -= 1;
                    return true;
                }
            }
        }
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn insert_and_contains() {
        let mut cf = CuckooFilter::new(1000, 1);
        for i in 0..200u32 {
            cf.insert(format!("item{i}").as_bytes()).unwrap();
        }
        for i in 0..200u32 {
            assert!(
                cf.contains(format!("item{i}").as_bytes()),
                "missing item{i}"
            );
        }
        assert_eq!(cf.len(), 200);
    }

    #[test]
    fn no_false_negatives() {
        let mut cf = CuckooFilter::new(500, 42);
        let keys: Vec<String> = (0..300).map(|i| format!("k{i}")).collect();
        for k in &keys {
            cf.insert(k.as_bytes()).unwrap();
        }
        // every inserted key must be found
        for k in &keys {
            assert!(cf.contains(k.as_bytes()));
        }
    }

    #[test]
    fn deletion_works() {
        let mut cf = CuckooFilter::new(100, 7);
        cf.insert(b"alpha").unwrap();
        cf.insert(b"beta").unwrap();
        assert!(cf.contains(b"alpha"));
        assert!(cf.delete(b"alpha"));
        // after deletion it should usually be gone (no other inserts collided)
        assert!(!cf.contains(b"alpha"));
        assert!(cf.contains(b"beta")); // unaffected
        assert_eq!(cf.len(), 1);
        // deleting something absent returns false
        assert!(!cf.delete(b"gamma"));
    }

    #[test]
    fn delete_then_reinsert() {
        let mut cf = CuckooFilter::new(100, 3);
        cf.insert(b"x").unwrap();
        assert!(cf.delete(b"x"));
        assert!(!cf.contains(b"x"));
        cf.insert(b"x").unwrap();
        assert!(cf.contains(b"x"));
        assert_eq!(cf.len(), 1);
    }

    #[test]
    fn absent_keys_mostly_not_found() {
        let mut cf = CuckooFilter::new(2000, 99);
        for i in 0..500u32 {
            cf.insert(format!("present{i}").as_bytes()).unwrap();
        }
        // count false positives over keys never inserted
        let mut fp = 0;
        for i in 0..2000u32 {
            if cf.contains(format!("absent{i}").as_bytes()) {
                fp += 1;
            }
        }
        // 8-bit fingerprints over a lightly loaded table → low FP rate
        let rate = fp as f64 / 2000.0;
        assert!(rate < 0.05, "false positive rate too high: {rate}");
    }

    #[test]
    fn sliding_window_semantics() {
        // simulate "seen in the last 3 steps": insert new, delete oldest.
        let mut cf = CuckooFilter::new(100, 5);
        let stream = ["a", "b", "c", "d", "e"];
        let window = 3;
        for (t, item) in stream.iter().enumerate() {
            cf.insert(item.as_bytes()).unwrap();
            if t >= window {
                cf.delete(stream[t - window].as_bytes());
            }
        }
        // after processing, only the last 3 (c, d, e) should be present
        assert!(!cf.contains(b"a"));
        assert!(!cf.contains(b"b"));
        assert!(cf.contains(b"c"));
        assert!(cf.contains(b"d"));
        assert!(cf.contains(b"e"));
    }

    #[test]
    fn serde_round_trip() {
        let mut cf = CuckooFilter::new(100, 11);
        for i in 0..20u32 {
            cf.insert(format!("s{i}").as_bytes()).unwrap();
        }
        let j = serde_json::to_string(&cf).unwrap();
        let back: CuckooFilter = serde_json::from_str(&j).unwrap();
        assert_eq!(cf, back);
        for i in 0..20u32 {
            assert!(back.contains(format!("s{i}").as_bytes()));
        }
    }
}
