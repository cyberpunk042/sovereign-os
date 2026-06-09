//! `sovereign-bm25` — probabilistic lexical ranking for retrieval.
//!
//! Ranking documents by how many query words they contain (raw term overlap)
//! over-rewards long documents and treats every word as equally informative.
//! **BM25** (Okapi BM25) fixes both with three well-understood pieces:
//!
//! - **IDF** weights each query term by how *rare* it is across the collection —
//!   a term in few documents is more discriminating than a common one.
//! - **Saturating term frequency** (`k1`): the contribution of a term grows with
//!   its count in a document but levels off, so the tenth occurrence adds far less
//!   than the first — repetition can't run away with the score.
//! - **Length normalization** (`b`): a term in a short focused document counts
//!   for more than the same term in a long rambling one, scaled by how the
//!   document's length compares to the collection average.
//!
//! The per-term score is `IDF(t) · f(t,d)·(k1+1) / (f(t,d) + k1·(1 − b + b·|d|/avgdl))`,
//! summed over query terms. This crate builds an in-memory index, computes the
//! statistics it needs (document frequencies, lengths, the average length), and
//! ranks documents for a query. Tokenization is lowercase alphanumeric words; the
//! standard `k1 = 1.5`, `b = 0.75` are the defaults.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the BM25 surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Default term-frequency saturation parameter.
pub const DEFAULT_K1: f64 = 1.5;
/// Default length-normalization parameter.
pub const DEFAULT_B: f64 = 0.75;

/// One indexed document.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct Doc {
    id: String,
    /// term → frequency in this document.
    tf: HashMap<String, u32>,
    /// total token count (document length).
    len: u32,
}

/// A BM25 index over a document collection.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Bm25 {
    k1: f64,
    b: f64,
    docs: Vec<Doc>,
    /// term → number of documents containing it.
    df: HashMap<String, usize>,
    total_len: u64,
}

/// A scored search hit.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Hit {
    /// The document id.
    pub id: String,
    /// The BM25 score (higher = more relevant).
    pub score: f64,
}

impl Default for Bm25 {
    fn default() -> Self {
        Self::new(DEFAULT_K1, DEFAULT_B)
    }
}

impl Bm25 {
    /// An empty index with the given `k1` and `b`.
    pub fn new(k1: f64, b: f64) -> Self {
        Self {
            k1,
            b,
            docs: Vec::new(),
            df: HashMap::new(),
            total_len: 0,
        }
    }

    /// The number of indexed documents.
    pub fn len(&self) -> usize {
        self.docs.len()
    }

    /// Whether the index is empty.
    pub fn is_empty(&self) -> bool {
        self.docs.is_empty()
    }

    /// The average document length (0 for an empty index).
    pub fn avgdl(&self) -> f64 {
        if self.docs.is_empty() {
            0.0
        } else {
            self.total_len as f64 / self.docs.len() as f64
        }
    }

    /// Add a document. Re-adding the same id stores a second copy (the caller
    /// controls ids).
    pub fn add(&mut self, id: impl Into<String>, text: &str) {
        let mut tf: HashMap<String, u32> = HashMap::new();
        let mut len = 0u32;
        for tok in tokens(text) {
            *tf.entry(tok).or_insert(0) += 1;
            len += 1;
        }
        for term in tf.keys() {
            *self.df.entry(term.clone()).or_insert(0) += 1;
        }
        self.total_len += len as u64;
        self.docs.push(Doc {
            id: id.into(),
            tf,
            len,
        });
    }

    /// The IDF of `term`: `ln(1 + (N − df + 0.5) / (df + 0.5))`. The `+1` keeps it
    /// non-negative even for very common terms (the robust BM25 IDF).
    pub fn idf(&self, term: &str) -> f64 {
        let n = self.docs.len() as f64;
        let df = *self.df.get(term).unwrap_or(&0) as f64;
        (1.0 + (n - df + 0.5) / (df + 0.5)).ln()
    }

    /// The BM25 score of document index `doc` for the (already tokenized) query
    /// terms.
    fn score_doc(&self, doc: &Doc, query_terms: &[String], avgdl: f64) -> f64 {
        let mut score = 0.0;
        for term in query_terms {
            let f = match doc.tf.get(term) {
                Some(&f) => f as f64,
                None => continue,
            };
            let idf = self.idf(term);
            let denom = f + self.k1 * (1.0 - self.b + self.b * doc.len as f64 / avgdl);
            score += idf * (f * (self.k1 + 1.0)) / denom;
        }
        score
    }

    /// Rank the top-`k` documents for `query`, best first (ties by id). Documents
    /// with zero score are excluded.
    pub fn search(&self, query: &str, k: usize) -> Vec<Hit> {
        if self.docs.is_empty() {
            return Vec::new();
        }
        let query_terms: Vec<String> = unique(tokens(query));
        let avgdl = self.avgdl().max(1e-9);
        let mut hits: Vec<Hit> = self
            .docs
            .iter()
            .filter_map(|d| {
                let s = self.score_doc(d, &query_terms, avgdl);
                (s > 0.0).then(|| Hit {
                    id: d.id.clone(),
                    score: s,
                })
            })
            .collect();
        hits.sort_by(|a, b| b.score.total_cmp(&a.score).then(a.id.cmp(&b.id)));
        hits.truncate(k);
        hits
    }
}

/// Lowercase alphanumeric word tokens.
fn tokens(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_lowercase())
        .collect()
}

/// Distinct tokens preserving first-seen order.
fn unique(toks: Vec<String>) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    toks.into_iter()
        .filter(|t| seen.insert(t.clone()))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn index() -> Bm25 {
        let mut bm = Bm25::default();
        bm.add(
            "rust",
            "Rust is a systems programming language focused on memory safety",
        );
        bm.add(
            "python",
            "Python is a high level programming language for general use",
        );
        bm.add(
            "memory",
            "Memory safety in Rust comes from ownership and the borrow checker without a garbage collector",
        );
        bm.add(
            "cooking",
            "A recipe for pasta with tomato sauce and fresh basil",
        );
        bm
    }

    #[test]
    fn ranks_relevant_documents_first() {
        let bm = index();
        let hits = bm.search("rust memory safety", 4);
        assert!(!hits.is_empty());
        // both the "rust" and "memory" docs contain all three query terms, so
        // they take the top two slots (the shorter "rust" doc ranks first under
        // length normalization); the cooking doc shares no terms and is excluded.
        let top2: Vec<&str> = hits.iter().take(2).map(|h| h.id.as_str()).collect();
        assert!(
            top2.contains(&"rust") && top2.contains(&"memory"),
            "top2 {top2:?}"
        );
        assert!(!hits.iter().any(|h| h.id == "cooking"));
    }

    #[test]
    fn rare_terms_outweigh_common_ones() {
        // "programming" appears in 2 docs, "borrow" in 1 → borrow has higher idf
        let bm = index();
        assert!(bm.idf("borrow") > bm.idf("programming"));
        // "a" appears in most docs → low idf
        assert!(bm.idf("programming") > bm.idf("a"));
    }

    #[test]
    fn term_frequency_saturates() {
        // a doc repeating a term many times shouldn't score unboundedly higher
        let mut bm = Bm25::new(1.5, 0.0); // b=0 to isolate tf saturation
        bm.add("once", "alpha beta gamma");
        bm.add(
            "many",
            "alpha alpha alpha alpha alpha alpha alpha alpha beta gamma",
        );
        let once = bm
            .search("alpha", 2)
            .iter()
            .find(|h| h.id == "once")
            .unwrap()
            .score;
        let many = bm
            .search("alpha", 2)
            .iter()
            .find(|h| h.id == "many")
            .unwrap()
            .score;
        // more occurrences scores higher, but far less than 8x
        assert!(many > once);
        assert!(
            many < once * 3.0,
            "tf did not saturate: once {once} many {many}"
        );
    }

    #[test]
    fn length_normalization_favors_focused_docs() {
        let mut bm = Bm25::new(1.5, 0.75);
        bm.add("short", "quantum computing");
        bm.add(
            "long",
            "quantum computing is one of many topics discussed at length across this \
             very long document that rambles about numerous unrelated subjects in detail",
        );
        let hits = bm.search("quantum computing", 2);
        // the short focused doc should outrank the long rambling one
        assert_eq!(hits[0].id, "short", "hits {hits:?}");
    }

    #[test]
    fn empty_index_and_no_match() {
        let empty = Bm25::default();
        assert!(empty.search("anything", 5).is_empty());
        let bm = index();
        assert!(bm.search("zebra quasar bicycle", 5).is_empty());
    }

    #[test]
    fn avgdl_and_len_track_corpus() {
        let bm = index();
        assert_eq!(bm.len(), 4);
        assert!(bm.avgdl() > 0.0);
    }

    #[test]
    fn top_k_limits_results() {
        let bm = index();
        assert_eq!(bm.search("language programming", 1).len(), 1);
    }

    #[test]
    fn serde_round_trip() {
        let bm = index();
        let j = serde_json::to_string(&bm).unwrap();
        let back: Bm25 = serde_json::from_str(&j).unwrap();
        assert_eq!(bm, back);
        assert_eq!(
            back.search("rust memory", 2)[0].id,
            bm.search("rust memory", 2)[0].id
        );
    }
}
