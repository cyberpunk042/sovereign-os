//! `sovereign-data-plane` — M010 deterministic data plane (CRoaring).
//!
//! The dump's data plane names **CRoaring** (compressed bitmaps) as the
//! deterministic set substrate. This crate is its reference: a Roaring
//! bitmap over `u32` keys, partitioned by the high 16 bits into per-block
//! **containers** that are stored *sparse* (a sorted `u16` array) or
//! *dense* (a 65 536-bit bitmap), auto-converting once a container passes
//! the array threshold. Set operations (union / intersection / cardinality)
//! and membership are exact.
//!
//! This is the structure behind fast metadata filtering — keep large id
//! sets compact and intersect them cheaply.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::BTreeMap;

/// Schema version of the data-plane surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max elements held as a sorted array before a container converts to a
/// dense bitmap (the classic Roaring threshold).
pub const ARRAY_MAX: usize = 4096;

const BITMAP_WORDS: usize = 1024; // 1024 × 64 = 65536 bits

#[derive(Debug, Clone, PartialEq, Eq)]
enum Container {
    Array(Vec<u16>),
    Bitmap(Box<[u64; BITMAP_WORDS]>),
}

impl Default for Container {
    fn default() -> Self {
        Container::Array(Vec::new())
    }
}

impl Container {
    fn insert(&mut self, v: u16) -> bool {
        match self {
            Container::Array(arr) => match arr.binary_search(&v) {
                Ok(_) => false,
                Err(pos) => {
                    arr.insert(pos, v);
                    if arr.len() > ARRAY_MAX {
                        self.densify();
                    }
                    true
                }
            },
            Container::Bitmap(words) => {
                let (w, b) = ((v >> 6) as usize, v & 63);
                let mask = 1u64 << b;
                let was = words[w] & mask != 0;
                words[w] |= mask;
                !was
            }
        }
    }

    fn contains(&self, v: u16) -> bool {
        match self {
            Container::Array(arr) => arr.binary_search(&v).is_ok(),
            Container::Bitmap(words) => words[(v >> 6) as usize] & (1u64 << (v & 63)) != 0,
        }
    }

    fn cardinality(&self) -> usize {
        match self {
            Container::Array(arr) => arr.len(),
            Container::Bitmap(words) => words.iter().map(|w| w.count_ones() as usize).sum(),
        }
    }

    fn elements(&self) -> Vec<u16> {
        match self {
            Container::Array(arr) => arr.clone(),
            Container::Bitmap(words) => {
                let mut out = Vec::new();
                for (wi, &w) in words.iter().enumerate() {
                    let mut bits = w;
                    while bits != 0 {
                        let b = bits.trailing_zeros();
                        out.push((wi as u16) << 6 | b as u16);
                        bits &= bits - 1;
                    }
                }
                out
            }
        }
    }

    fn densify(&mut self) {
        if let Container::Array(arr) = self {
            let mut words = Box::new([0u64; BITMAP_WORDS]);
            for &v in arr.iter() {
                words[(v >> 6) as usize] |= 1u64 << (v & 63);
            }
            *self = Container::Bitmap(words);
        }
    }

    fn is_bitmap(&self) -> bool {
        matches!(self, Container::Bitmap(_))
    }
}

/// A Roaring-style compressed bitmap over `u32` keys.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RoaringBitmap {
    containers: BTreeMap<u16, Container>,
}

impl RoaringBitmap {
    /// An empty bitmap.
    pub fn new() -> Self {
        Self::default()
    }

    /// Build from an iterator of values.
    pub fn from_values(values: impl IntoIterator<Item = u32>) -> Self {
        let mut b = Self::new();
        for v in values {
            b.insert(v);
        }
        b
    }

    /// Insert a value; returns `true` if newly added.
    pub fn insert(&mut self, value: u32) -> bool {
        let hi = (value >> 16) as u16;
        let lo = (value & 0xffff) as u16;
        self.containers.entry(hi).or_default().insert(lo)
    }

    /// Membership test.
    pub fn contains(&self, value: u32) -> bool {
        let hi = (value >> 16) as u16;
        let lo = (value & 0xffff) as u16;
        self.containers.get(&hi).is_some_and(|c| c.contains(lo))
    }

    /// Number of distinct values (cardinality).
    pub fn cardinality(&self) -> usize {
        self.containers.values().map(Container::cardinality).sum()
    }

    /// Whether the bitmap is empty.
    pub fn is_empty(&self) -> bool {
        self.cardinality() == 0
    }

    /// All values in ascending order.
    pub fn to_vec(&self) -> Vec<u32> {
        let mut out = Vec::with_capacity(self.cardinality());
        for (&hi, c) in &self.containers {
            for lo in c.elements() {
                out.push((hi as u32) << 16 | lo as u32);
            }
        }
        out
    }

    /// Set union.
    pub fn union(&self, other: &RoaringBitmap) -> RoaringBitmap {
        let mut result = self.clone();
        for v in other.to_vec() {
            result.insert(v);
        }
        result
    }

    /// Set intersection.
    pub fn intersection(&self, other: &RoaringBitmap) -> RoaringBitmap {
        // Iterate the smaller side for efficiency.
        let (small, big) = if self.cardinality() <= other.cardinality() {
            (self, other)
        } else {
            (other, self)
        };
        let mut result = RoaringBitmap::new();
        for v in small.to_vec() {
            if big.contains(v) {
                result.insert(v);
            }
        }
        result
    }

    /// How many containers are dense (bitmap) vs total — introspection of
    /// the sparse↔dense compression behaviour.
    pub fn dense_container_count(&self) -> usize {
        self.containers.values().filter(|c| c.is_bitmap()).count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn insert_contains_cardinality_vs_hashset() {
        let vals = [1u32, 2, 2, 70_000, 70_001, 1 << 20, (1 << 20) + 5];
        let mut r = RoaringBitmap::new();
        let mut h = HashSet::new();
        for &v in &vals {
            r.insert(v);
            h.insert(v);
        }
        assert_eq!(r.cardinality(), h.len());
        for &v in &vals {
            assert!(r.contains(v));
        }
        assert!(!r.contains(999));
    }

    #[test]
    fn array_converts_to_bitmap_past_threshold() {
        let mut r = RoaringBitmap::new();
        // all in the same high-16 block (0) → one container
        for v in 0..(ARRAY_MAX as u32 + 100) {
            r.insert(v);
        }
        assert_eq!(r.cardinality(), ARRAY_MAX + 100);
        assert_eq!(
            r.dense_container_count(),
            1,
            "container should have gone dense"
        );
    }

    #[test]
    fn stays_sparse_below_threshold() {
        let mut r = RoaringBitmap::new();
        for v in 0..100u32 {
            r.insert(v);
        }
        assert_eq!(r.dense_container_count(), 0);
    }

    #[test]
    fn union_matches_reference() {
        let a = RoaringBitmap::from_values([1, 2, 3, 100_000]);
        let b = RoaringBitmap::from_values([3, 4, 100_000, 200_000]);
        let u = a.union(&b);
        let mut expect: Vec<u32> = [1, 2, 3, 4, 100_000, 200_000].into();
        expect.sort_unstable();
        assert_eq!(u.to_vec(), expect);
    }

    #[test]
    fn intersection_matches_reference() {
        let a = RoaringBitmap::from_values([1, 2, 3, 100_000, 200_000]);
        let b = RoaringBitmap::from_values([3, 4, 100_000]);
        assert_eq!(a.intersection(&b).to_vec(), vec![3, 100_000]);
    }

    #[test]
    fn disjoint_intersection_is_empty() {
        let a = RoaringBitmap::from_values([1, 2, 3]);
        let b = RoaringBitmap::from_values([4, 5, 6]);
        assert!(a.intersection(&b).is_empty());
    }

    #[test]
    fn to_vec_is_sorted_ascending() {
        let r = RoaringBitmap::from_values([500_000, 1, 70_000, 2]);
        let v = r.to_vec();
        let mut sorted = v.clone();
        sorted.sort_unstable();
        assert_eq!(v, sorted);
    }

    #[test]
    fn ops_correct_with_dense_containers() {
        // force both sides dense in block 0, verify intersection still exact
        let a = RoaringBitmap::from_values(0..5000);
        let b = RoaringBitmap::from_values(2500..7500);
        assert_eq!(a.dense_container_count(), 1);
        let i = a.intersection(&b);
        assert_eq!(i.cardinality(), 2500); // 2500..5000
        assert!(i.contains(3000) && !i.contains(6000));
    }
}
