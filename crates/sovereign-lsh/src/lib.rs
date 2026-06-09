//! `sovereign-lsh` — banded locality-sensitive hashing over MinHash signatures.
//!
//! [`sovereign_minhash`] turns a set into a fixed-length signature and lets you
//! estimate the Jaccard similarity of *one pair* in `O(signature length)`. But to
//! deduplicate a corpus you would still have to compare every pair — `O(n²)`,
//! which is hopeless at scale. Banded LSH fixes that: split each signature of
//! `r * b` slots into `b` *bands* of `r` rows, hash each band, and index items by
//! their band hashes. Two items are *candidates* if they collide in **at least
//! one** band. The probability of colliding in a given band is `s^r` (where `s`
//! is their true Jaccard), so the probability of being a candidate is
//! `1 - (1 - s^r)^b` — an S-curve with a tunable threshold near `(1/b)^(1/r)`.
//! Pick `r` and `b` to put that knee where you want it: similar items almost
//! always collide, dissimilar items almost never do, and you only ever run the
//! exact Jaccard check on the few candidate pairs.
//!
//! [`LshIndex`] stores band buckets and answers two questions: *what existing
//! items are candidate-similar to this one?* ([`LshIndex::query`]) and, while
//! deduplicating a stream, *have I already seen something like this?*
//! ([`LshIndex::insert_if_novel`]).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_minhash::Signature;
use std::collections::{HashMap, HashSet};

/// Schema version of the LSH surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A banded LSH index over MinHash signatures of dimension `bands * rows`.
///
/// Items are identified by an opaque `usize` id assigned in insertion order.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LshIndex {
    bands: usize,
    rows: usize,
    /// One bucket map per band: band-hash → ids that landed in it.
    buckets: Vec<HashMap<u64, Vec<usize>>>,
    /// Stored signatures, indexed by id, for the exact post-filter.
    signatures: Vec<Signature>,
}

impl LshIndex {
    /// An empty index using `bands` bands of `rows` rows each; signatures must
    /// have exactly `bands * rows` slots.
    ///
    /// # Panics
    /// Panics if `bands == 0` or `rows == 0`.
    pub fn new(bands: usize, rows: usize) -> Self {
        assert!(bands > 0 && rows > 0, "bands and rows must be > 0");
        Self {
            bands,
            rows,
            buckets: vec![HashMap::new(); bands],
            signatures: Vec::new(),
        }
    }

    /// The required signature length (`bands * rows`).
    pub fn signature_len(&self) -> usize {
        self.bands * self.rows
    }

    /// Number of indexed items.
    pub fn len(&self) -> usize {
        self.signatures.len()
    }

    /// Whether the index is empty.
    pub fn is_empty(&self) -> bool {
        self.signatures.is_empty()
    }

    /// The approximate similarity threshold — the Jaccard at which an item has a
    /// 50%-ish chance of becoming a candidate, `(1/bands)^(1/rows)`. A handle for
    /// choosing `bands`/`rows`, not an exact cutoff.
    pub fn threshold(&self) -> f64 {
        (1.0 / self.bands as f64).powf(1.0 / self.rows as f64)
    }

    /// Hash one band (a slice of `rows` slots) to a bucket key.
    fn band_hash(slots: &[u64]) -> u64 {
        // FNV-1a over the band's bytes — distinct band contents → distinct keys.
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        for &slot in slots {
            for byte in slot.to_le_bytes() {
                h ^= byte as u64;
                h = h.wrapping_mul(0x0000_0100_0000_01b3);
            }
        }
        h
    }

    /// The per-band bucket keys of `sig`.
    fn band_keys(&self, sig: &Signature) -> Vec<u64> {
        let slots = sig.slots();
        (0..self.bands)
            .map(|band| {
                let start = band * self.rows;
                Self::band_hash(&slots[start..start + self.rows])
            })
            .collect()
    }

    /// Candidate ids that share at least one band bucket with `sig`, without
    /// inserting it. Ids are returned sorted and de-duplicated.
    ///
    /// # Panics
    /// Panics if `sig.len() != self.signature_len()`.
    pub fn query(&self, sig: &Signature) -> Vec<usize> {
        assert_eq!(
            sig.len(),
            self.signature_len(),
            "signature length must equal bands * rows"
        );
        let mut found: HashSet<usize> = HashSet::new();
        for (band, key) in self.band_keys(sig).into_iter().enumerate() {
            if let Some(ids) = self.buckets[band].get(&key) {
                found.extend(ids.iter().copied());
            }
        }
        let mut out: Vec<usize> = found.into_iter().collect();
        out.sort_unstable();
        out
    }

    /// Candidate ids whose *exact* (signature-estimated) Jaccard to `sig` is at
    /// least `min_jaccard`. This is the LSH candidate set filtered by the cheap
    /// signature comparison — the two-stage recipe that makes LSH precise.
    pub fn query_similar(&self, sig: &Signature, min_jaccard: f64) -> Vec<(usize, f64)> {
        let mut out: Vec<(usize, f64)> = self
            .query(sig)
            .into_iter()
            .map(|id| (id, self.signatures[id].jaccard(sig)))
            .filter(|&(_, s)| s >= min_jaccard)
            .collect();
        // most similar first
        out.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
        out
    }

    /// Insert `sig`, returning its assigned id.
    ///
    /// # Panics
    /// Panics if `sig.len() != self.signature_len()`.
    pub fn insert(&mut self, sig: Signature) -> usize {
        assert_eq!(
            sig.len(),
            self.signature_len(),
            "signature length must equal bands * rows"
        );
        let id = self.signatures.len();
        for (band, key) in self.band_keys(&sig).into_iter().enumerate() {
            self.buckets[band].entry(key).or_default().push(id);
        }
        self.signatures.push(sig);
        id
    }

    /// Insert `sig` only if no already-indexed item has signature-estimated
    /// Jaccard `>= min_jaccard`. Returns `Ok(new_id)` if it was novel and
    /// inserted, or `Err((existing_id, similarity))` for the most-similar
    /// existing item that made it a duplicate. The core dedup primitive.
    pub fn insert_if_novel(
        &mut self,
        sig: Signature,
        min_jaccard: f64,
    ) -> Result<usize, (usize, f64)> {
        if let Some(&(id, s)) = self.query_similar(&sig, min_jaccard).first() {
            return Err((id, s));
        }
        Ok(self.insert(sig))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_minhash::MinHasher;

    fn hasher(bands: usize, rows: usize) -> MinHasher {
        MinHasher::new(bands * rows, 2024)
    }

    #[test]
    fn threshold_matches_formula() {
        let idx = LshIndex::new(16, 4); // (1/16)^(1/4) = 0.5
        assert!((idx.threshold() - 0.5).abs() < 1e-9);
    }

    #[test]
    fn finds_near_duplicate_text() {
        let (bands, rows) = (32, 4);
        let mh = hasher(bands, rows);
        let mut idx = LshIndex::new(bands, rows);

        let a = "the quick brown fox jumps over the lazy dog in the yard";
        let b = "the quick brown fox leaps over the lazy dog in the yard"; // 1 word
        let c = "macroeconomic policy shifts dominated the financial headlines";

        let id_a = idx.insert(mh.sign_text(a, 2));
        let _id_c = idx.insert(mh.sign_text(c, 2));

        // b should surface a as a candidate, c should not be similar to b
        let cands = idx.query(&mh.sign_text(b, 2));
        assert!(
            cands.contains(&id_a),
            "near-dup A should be a candidate of B"
        );

        let sim = idx.query_similar(&mh.sign_text(b, 2), 0.4);
        assert_eq!(sim[0].0, id_a, "A should be the top similar to B");
        assert!(
            sim.iter().all(|&(id, _)| id != 1),
            "unrelated C must not match"
        );
    }

    #[test]
    fn dedup_stream_rejects_duplicates() {
        let (bands, rows) = (32, 4);
        let mh = hasher(bands, rows);
        let mut idx = LshIndex::new(bands, rows);

        let first = mh.sign_text("install the package then run the tests", 2);
        let again = mh.sign_text("install the package then run the tests", 2); // identical
        let other = mh.sign_text("a completely different sentence about cats", 2);

        assert!(idx.insert_if_novel(first, 0.8).is_ok());
        // identical → rejected as duplicate
        let dup = idx.insert_if_novel(again, 0.8);
        assert!(dup.is_err());
        assert!((dup.unwrap_err().1 - 1.0).abs() < 1e-9);
        // novel → accepted
        assert!(idx.insert_if_novel(other, 0.8).is_ok());
        assert_eq!(idx.len(), 2);
    }

    #[test]
    fn dissimilar_items_rarely_collide() {
        let (bands, rows) = (20, 5); // threshold (1/20)^(1/5) ≈ 0.55
        let mh = hasher(bands, rows);
        let mut idx = LshIndex::new(bands, rows);

        // 30 genuinely unrelated sentences: every token is globally unique
        // (`w{n}`), so no two sentences share a word or a shingle. With a 0.55
        // threshold their near-zero Jaccard should almost never make candidates.
        let sentences: Vec<String> = (0..30)
            .map(|i| {
                let b = i * 4;
                format!("w{} w{} w{} w{}", b, b + 1, b + 2, b + 3)
            })
            .collect();
        let mut collisions = 0;
        for s in &sentences {
            let sig = mh.sign_text(s, 2);
            collisions += idx.query(&sig).len();
            idx.insert(sig);
        }
        // with a 0.55 threshold these near-disjoint sets should almost never
        // be candidates; allow a tiny number of incidental collisions
        assert!(collisions <= 2, "too many false candidates: {collisions}");
    }

    #[test]
    fn query_requires_matching_length() {
        let idx = LshIndex::new(4, 4); // needs 16-slot signatures
        let mh = MinHasher::new(8, 1); // produces 8-slot signatures
        let sig = mh.sign(["x"]);
        assert!(std::panic::catch_unwind(|| idx.query(&sig)).is_err());
    }

    #[test]
    fn serde_round_trip() {
        let (bands, rows) = (8, 2);
        let mh = hasher(bands, rows);
        let mut idx = LshIndex::new(bands, rows);
        idx.insert(mh.sign_text("hello there general", 2));
        let j = serde_json::to_string(&idx).unwrap();
        let back: LshIndex = serde_json::from_str(&j).unwrap();
        assert_eq!(back.len(), 1);
        assert_eq!(back.signature_len(), idx.signature_len());
    }
}
