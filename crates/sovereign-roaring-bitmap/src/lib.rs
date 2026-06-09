//! `sovereign-roaring-bitmap` — sets of integers that stay small and combine fast.
//!
//! Retrieval and filtering run on sets of ids: the documents containing a term, the
//! rows passing a predicate, the items with a flag. A plain bitset over a 32-bit id
//! space is 512 MB whether it holds three ids or three million; a hash set is
//! compact but slow to intersect. **Roaring bitmaps** get both — small storage *and*
//! fast set algebra — by splitting each value into a 16-bit high chunk and a 16-bit
//! low part, and storing each chunk in the representation that fits it: a sorted
//! **array** when the chunk is sparse, a dense **bitset** when it is full. A handful
//! of ids costs a few bytes; a saturated chunk costs a flat 8 KB and never more.
//!
//! Because chunks are keyed and ordered, [`union`](RoaringBitmap::union),
//! [`intersection`](RoaringBitmap::intersection), and
//! [`difference`](RoaringBitmap::difference) walk the two bitmaps chunk by chunk and
//! combine matching chunks with a linear sorted merge — so combining two posting
//! lists costs work proportional to what they contain, not to the id space. Single
//! values go in and out with [`insert`](RoaringBitmap::insert) /
//! [`remove`](RoaringBitmap::remove) / [`contains`](RoaringBitmap::contains),
//! [`iter`](RoaringBitmap::iter) yields them in ascending order, and
//! [`len`](RoaringBitmap::len) is the cardinality. Containers convert between array
//! and bitset automatically as they cross the density threshold.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Schema version of the roaring-bitmap surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Above this cardinality a chunk is stored as a dense bitset, below as an array.
const ARRAY_MAX: usize = 4096;
/// 65536 bits / 64 = 1024 words per dense container.
const BITMAP_WORDS: usize = 1024;

/// A per-chunk container: sparse sorted array or dense bitset.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
enum Container {
    /// Sorted, de-duplicated low-16-bit values.
    Array(Vec<u16>),
    /// 65536-bit dense bitset (1024 u64 words).
    Bitmap(Vec<u64>),
}

impl Container {
    fn contains(&self, lo: u16) -> bool {
        match self {
            Container::Array(v) => v.binary_search(&lo).is_ok(),
            Container::Bitmap(w) => (w[(lo >> 6) as usize] >> (lo & 63)) & 1 == 1,
        }
    }

    fn cardinality(&self) -> usize {
        match self {
            Container::Array(v) => v.len(),
            Container::Bitmap(w) => w.iter().map(|x| x.count_ones() as usize).sum(),
        }
    }

    /// Insert `lo`; returns whether it was newly added.
    fn insert(&mut self, lo: u16) -> bool {
        let added = match self {
            Container::Array(v) => match v.binary_search(&lo) {
                Ok(_) => false,
                Err(i) => {
                    v.insert(i, lo);
                    true
                }
            },
            Container::Bitmap(w) => {
                let word = (lo >> 6) as usize;
                let bit = 1u64 << (lo & 63);
                if w[word] & bit == 0 {
                    w[word] |= bit;
                    true
                } else {
                    false
                }
            }
        };
        if added {
            self.maybe_upgrade();
        }
        added
    }

    /// Remove `lo`; returns whether it was present.
    fn remove(&mut self, lo: u16) -> bool {
        let removed = match self {
            Container::Array(v) => match v.binary_search(&lo) {
                Ok(i) => {
                    v.remove(i);
                    true
                }
                Err(_) => false,
            },
            Container::Bitmap(w) => {
                let word = (lo >> 6) as usize;
                let bit = 1u64 << (lo & 63);
                if w[word] & bit != 0 {
                    w[word] &= !bit;
                    true
                } else {
                    false
                }
            }
        };
        if removed {
            self.maybe_downgrade();
        }
        removed
    }

    /// The values in ascending order.
    fn values(&self) -> Vec<u16> {
        match self {
            Container::Array(v) => v.clone(),
            Container::Bitmap(w) => {
                let mut out = Vec::with_capacity(self.cardinality());
                for (wi, &word) in w.iter().enumerate() {
                    let mut bits = word;
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

    /// Promote a too-large array to a bitset.
    fn maybe_upgrade(&mut self) {
        if let Container::Array(v) = self {
            if v.len() > ARRAY_MAX {
                let mut w = vec![0u64; BITMAP_WORDS];
                for &lo in v.iter() {
                    w[(lo >> 6) as usize] |= 1u64 << (lo & 63);
                }
                *self = Container::Bitmap(w);
            }
        }
    }

    /// Demote a sparse bitset back to an array.
    fn maybe_downgrade(&mut self) {
        if let Container::Bitmap(_) = self {
            if self.cardinality() <= ARRAY_MAX {
                *self = Container::Array(self.values());
            }
        }
    }

    /// Build the most compact container for a sorted value list, or `None` if empty.
    fn from_values(values: Vec<u16>) -> Option<Container> {
        if values.is_empty() {
            return None;
        }
        if values.len() > ARRAY_MAX {
            let mut w = vec![0u64; BITMAP_WORDS];
            for &lo in &values {
                w[(lo >> 6) as usize] |= 1u64 << (lo & 63);
            }
            Some(Container::Bitmap(w))
        } else {
            Some(Container::Array(values))
        }
    }
}

/// Merge two sorted, distinct `u16` lists by `op`.
fn merge<F>(a: &[u16], b: &[u16], op: F) -> Vec<u16>
where
    F: Fn(bool, bool) -> bool, // (in_a, in_b) -> keep
{
    let mut out = Vec::new();
    let (mut i, mut j) = (0, 0);
    while i < a.len() || j < b.len() {
        match (a.get(i), b.get(j)) {
            (Some(&x), Some(&y)) if x == y => {
                if op(true, true) {
                    out.push(x);
                }
                i += 1;
                j += 1;
            }
            (Some(&x), Some(&y)) if x < y => {
                if op(true, false) {
                    out.push(x);
                }
                i += 1;
            }
            (Some(_), Some(&y)) => {
                if op(false, true) {
                    out.push(y);
                }
                j += 1;
            }
            (Some(&x), None) => {
                if op(true, false) {
                    out.push(x);
                }
                i += 1;
            }
            (None, Some(&y)) => {
                if op(false, true) {
                    out.push(y);
                }
                j += 1;
            }
            (None, None) => break,
        }
    }
    out
}

/// A compressed bitmap of `u32` values.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct RoaringBitmap {
    /// high-16-bits chunk key -> container of low 16 bits.
    chunks: BTreeMap<u16, Container>,
}

#[inline]
fn split(x: u32) -> (u16, u16) {
    ((x >> 16) as u16, (x & 0xFFFF) as u16)
}
#[inline]
fn join(hi: u16, lo: u16) -> u32 {
    ((hi as u32) << 16) | lo as u32
}

impl RoaringBitmap {
    /// An empty bitmap.
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert `x`; returns whether it was newly added.
    pub fn insert(&mut self, x: u32) -> bool {
        let (hi, lo) = split(x);
        self.chunks
            .entry(hi)
            .or_insert_with(|| Container::Array(Vec::new()))
            .insert(lo)
    }

    /// Remove `x`; returns whether it was present.
    pub fn remove(&mut self, x: u32) -> bool {
        let (hi, lo) = split(x);
        if let Some(c) = self.chunks.get_mut(&hi) {
            let removed = c.remove(lo);
            if c.cardinality() == 0 {
                self.chunks.remove(&hi);
            }
            removed
        } else {
            false
        }
    }

    /// Whether `x` is present.
    pub fn contains(&self, x: u32) -> bool {
        let (hi, lo) = split(x);
        self.chunks
            .get(&hi)
            .map(|c| c.contains(lo))
            .unwrap_or(false)
    }

    /// The number of values (cardinality).
    pub fn len(&self) -> usize {
        self.chunks.values().map(|c| c.cardinality()).sum()
    }
    /// Whether the bitmap is empty.
    pub fn is_empty(&self) -> bool {
        self.chunks.is_empty()
    }

    /// All values in ascending order.
    pub fn iter(&self) -> Vec<u32> {
        let mut out = Vec::with_capacity(self.len());
        for (&hi, c) in &self.chunks {
            for lo in c.values() {
                out.push(join(hi, lo));
            }
        }
        out
    }

    /// Combine two bitmaps chunk-by-chunk under a low-16 merge operation.
    fn combine<F: Fn(bool, bool) -> bool + Copy>(
        &self,
        other: &RoaringBitmap,
        op: F,
    ) -> RoaringBitmap {
        let mut chunks = BTreeMap::new();
        let keys: std::collections::BTreeSet<u16> = self
            .chunks
            .keys()
            .chain(other.chunks.keys())
            .copied()
            .collect();
        for k in keys {
            let a = self.chunks.get(&k).map(|c| c.values()).unwrap_or_default();
            let b = other.chunks.get(&k).map(|c| c.values()).unwrap_or_default();
            if let Some(c) = Container::from_values(merge(&a, &b, op)) {
                chunks.insert(k, c);
            }
        }
        RoaringBitmap { chunks }
    }

    /// The union (`self ∪ other`).
    pub fn union(&self, other: &RoaringBitmap) -> RoaringBitmap {
        self.combine(other, |a, b| a || b)
    }
    /// The intersection (`self ∩ other`).
    pub fn intersection(&self, other: &RoaringBitmap) -> RoaringBitmap {
        self.combine(other, |a, b| a && b)
    }
    /// The difference (`self \ other`).
    pub fn difference(&self, other: &RoaringBitmap) -> RoaringBitmap {
        self.combine(other, |a, b| a && !b)
    }
    /// The symmetric difference (`self △ other`).
    pub fn symmetric_difference(&self, other: &RoaringBitmap) -> RoaringBitmap {
        self.combine(other, |a, b| a != b)
    }
}

impl FromIterator<u32> for RoaringBitmap {
    fn from_iter<I: IntoIterator<Item = u32>>(it: I) -> Self {
        let mut b = Self::new();
        for x in it {
            b.insert(x);
        }
        b
    }
}

impl Extend<u32> for RoaringBitmap {
    fn extend<I: IntoIterator<Item = u32>>(&mut self, it: I) {
        for x in it {
            self.insert(x);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;

    #[test]
    fn insert_contains_remove() {
        let mut b = RoaringBitmap::new();
        assert!(b.insert(42));
        assert!(!b.insert(42)); // duplicate
        assert!(b.contains(42));
        assert_eq!(b.len(), 1);
        assert!(b.remove(42));
        assert!(!b.contains(42));
        assert!(b.is_empty());
        assert!(!b.remove(42));
    }

    #[test]
    fn cross_chunk_values() {
        let mut b = RoaringBitmap::new();
        // values in different high-16 chunks.
        for x in [1u32, 70_000, 200_000, 0xFFFF_FFFF] {
            b.insert(x);
        }
        assert_eq!(b.len(), 4);
        assert!(b.contains(0xFFFF_FFFF));
        assert_eq!(b.iter(), vec![1, 70_000, 200_000, 0xFFFF_FFFF]);
    }

    #[test]
    fn iter_is_sorted() {
        let mut b = RoaringBitmap::new();
        for x in [5u32, 1, 100, 70_000, 3, 70_001] {
            b.insert(x);
        }
        assert_eq!(b.iter(), vec![1, 3, 5, 100, 70_000, 70_001]);
    }

    #[test]
    fn dense_chunk_converts_to_bitmap() {
        // > ARRAY_MAX values in one chunk forces a bitmap container.
        let mut b = RoaringBitmap::new();
        for x in 0..10_000u32 {
            b.insert(x);
        }
        assert_eq!(b.len(), 10_000);
        assert!(b.contains(9_999));
        assert!(!b.contains(10_000));
        // removing back below threshold still correct.
        for x in 5_000..10_000u32 {
            b.remove(x);
        }
        assert_eq!(b.len(), 5_000);
        assert!(b.contains(4_999));
        assert!(!b.contains(5_000));
    }

    #[test]
    fn union_matches_reference() {
        let a: Vec<u32> = (0..1000).map(|i| i * 3).collect();
        let b: Vec<u32> = (0..1000).map(|i| i * 5).collect();
        let ra = RoaringBitmap::from_iter(a.iter().copied());
        let rb = RoaringBitmap::from_iter(b.iter().copied());
        let got = ra.union(&rb).iter();
        let want: BTreeSet<u32> = a.iter().chain(&b).copied().collect();
        assert_eq!(got, want.into_iter().collect::<Vec<_>>());
    }

    #[test]
    fn intersection_matches_reference() {
        let a: BTreeSet<u32> = (0..5000u32).filter(|x| x % 2 == 0).collect();
        let b: BTreeSet<u32> = (0..5000u32).filter(|x| x % 3 == 0).collect();
        let ra = RoaringBitmap::from_iter(a.iter().copied());
        let rb = RoaringBitmap::from_iter(b.iter().copied());
        let got = ra.intersection(&rb).iter();
        let want: Vec<u32> = a.intersection(&b).copied().collect();
        assert_eq!(got, want);
    }

    #[test]
    fn difference_and_symmetric() {
        let a = RoaringBitmap::from_iter([1u32, 2, 3, 4, 5]);
        let b = RoaringBitmap::from_iter([4u32, 5, 6, 7]);
        assert_eq!(a.difference(&b).iter(), vec![1, 2, 3]);
        assert_eq!(a.symmetric_difference(&b).iter(), vec![1, 2, 3, 6, 7]);
    }

    #[test]
    fn ops_with_dense_chunks() {
        // both operands dense in the same chunk → bitmap-vs-bitmap path.
        let ra = RoaringBitmap::from_iter(0..8000u32);
        let rb = RoaringBitmap::from_iter(4000..12000u32);
        assert_eq!(ra.intersection(&rb).len(), 4000); // [4000, 8000)
        assert_eq!(ra.union(&rb).len(), 12000); // [0, 12000)
        assert_eq!(ra.difference(&rb).len(), 4000); // [0, 4000)
    }

    #[test]
    fn empty_operand_ops() {
        let a = RoaringBitmap::from_iter([1u32, 2, 3]);
        let empty = RoaringBitmap::new();
        assert_eq!(a.union(&empty).iter(), vec![1, 2, 3]);
        assert!(a.intersection(&empty).is_empty());
        assert_eq!(a.difference(&empty).iter(), vec![1, 2, 3]);
    }

    #[test]
    fn randomized_against_btreeset() {
        // pseudo-random streams; ops must match a BTreeSet reference exactly.
        let mut s = 0x1234_5678u64;
        let mut rng = || {
            s = s.wrapping_mul(6364136223846793005).wrapping_add(1);
            (s >> 33) as u32
        };
        let mut ra = RoaringBitmap::new();
        let mut rb = RoaringBitmap::new();
        let mut sa = BTreeSet::new();
        let mut sb = BTreeSet::new();
        for _ in 0..5000 {
            let x = rng() % 300_000;
            ra.insert(x);
            sa.insert(x);
            let y = rng() % 300_000;
            rb.insert(y);
            sb.insert(y);
        }
        assert_eq!(ra.len(), sa.len());
        assert_eq!(
            ra.intersection(&rb).iter(),
            sa.intersection(&sb).copied().collect::<Vec<_>>()
        );
        assert_eq!(
            ra.union(&rb).iter(),
            sa.union(&sb).copied().collect::<Vec<_>>()
        );
        assert_eq!(
            ra.difference(&rb).iter(),
            sa.difference(&sb).copied().collect::<Vec<_>>()
        );
    }

    #[test]
    fn serde_round_trip() {
        let b = RoaringBitmap::from_iter((0..6000u32).chain([1_000_000, 2_000_000]));
        let j = serde_json::to_string(&b).unwrap();
        let back: RoaringBitmap = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
        assert_eq!(b.len(), back.len());
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
