//! `sovereign-semantic-cache` — return cached completions for similar prompts.
//!
//! The exact-match completion cache only helps if a request is *identical* to a
//! previous one. But models get asked the same thing in different words —
//! paraphrases, typos, reordered clauses. A semantic cache catches those: it
//! stores each completion keyed by its prompt's [`embed`]ding, and on lookup
//! returns the cached completion whose prompt embedding is closest in cosine
//! similarity — provided that similarity clears a configurable threshold.
//!
//! That turns near-duplicate requests into free lookups (more of the `$0`
//! case), at the cost of an embedding comparison. The threshold trades recall
//! (catch more paraphrases) against precision (don't serve a stale answer to a
//! genuinely different question). Embeddings are deterministic, so the cache is
//! reproducible.
//!
//! Composes [`sovereign-embed`].
//!
//! [`embed`]: sovereign_embed::embed
//! [`sovereign-embed`]: https://docs.rs/sovereign-embed
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_embed::{cosine, embed};

/// Schema version of the semantic-cache surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct Entry {
    prompt: String,
    completion: String,
    vector: Vec<f32>,
}

/// A cosine-similarity-thresholded cache of completions.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SemanticCache {
    threshold: f32,
    capacity: usize,
    entries: Vec<Entry>,
    hits: u64,
    misses: u64,
}

/// A semantic cache hit.
#[derive(Debug, Clone, PartialEq)]
pub struct SemanticHit {
    /// The cached completion.
    pub completion: String,
    /// The cached prompt that matched.
    pub matched_prompt: String,
    /// Cosine similarity between the query and the matched prompt.
    pub similarity: f32,
}

impl SemanticCache {
    /// A cache that returns a hit when cosine similarity ≥ `threshold`, holding
    /// up to `capacity` entries.
    ///
    /// # Panics
    /// Panics if `capacity == 0`.
    pub fn new(threshold: f32, capacity: usize) -> Self {
        assert!(capacity > 0, "capacity must be > 0");
        Self {
            threshold,
            capacity,
            entries: Vec::new(),
            hits: 0,
            misses: 0,
        }
    }

    /// Number of cached entries.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the cache is empty.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Cache hits so far.
    pub fn hits(&self) -> u64 {
        self.hits
    }

    /// Cache misses so far.
    pub fn misses(&self) -> u64 {
        self.misses
    }

    /// Store `completion` for `prompt`, evicting the oldest entry if full.
    pub fn put(&mut self, prompt: impl Into<String>, completion: impl Into<String>) {
        let prompt = prompt.into();
        let vector = embed(&prompt);
        if self.entries.len() >= self.capacity {
            self.entries.remove(0); // oldest-first eviction
        }
        self.entries.push(Entry {
            prompt,
            completion: completion.into(),
            vector,
        });
    }

    /// Look up `prompt`: return the most-similar cached completion if its cosine
    /// similarity clears the threshold. Updates hit/miss stats.
    pub fn get(&mut self, prompt: &str) -> Option<SemanticHit> {
        let q = embed(prompt);
        let best = self
            .entries
            .iter()
            .map(|e| (cosine(&q, &e.vector), e))
            .max_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

        match best {
            Some((sim, e)) if sim >= self.threshold => {
                self.hits += 1;
                Some(SemanticHit {
                    completion: e.completion.clone(),
                    matched_prompt: e.prompt.clone(),
                    similarity: sim,
                })
            }
            _ => {
                self.misses += 1;
                None
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_repeat_is_a_hit() {
        let mut c = SemanticCache::new(0.9, 8);
        c.put("what is the capital of france", "Paris");
        let hit = c.get("what is the capital of france").unwrap();
        assert_eq!(hit.completion, "Paris");
        assert!(hit.similarity > 0.99);
        assert_eq!(c.hits(), 1);
    }

    #[test]
    fn paraphrase_within_threshold_hits() {
        // a near-duplicate (extra word / morphology) shares most n-grams
        let mut c = SemanticCache::new(0.6, 8);
        c.put("how do rust ownership rules work", "they govern memory");
        let hit = c.get("how do rust ownership rule work").unwrap(); // typo: rule
        assert_eq!(hit.completion, "they govern memory");
        assert!(hit.similarity >= 0.6);
    }

    #[test]
    fn unrelated_prompt_misses() {
        let mut c = SemanticCache::new(0.6, 8);
        c.put("rust ownership and borrowing", "answer A");
        assert!(c.get("tomato basil pasta recipe").is_none());
        assert_eq!(c.misses(), 1);
    }

    #[test]
    fn threshold_controls_strictness() {
        let mut strict = SemanticCache::new(0.99, 8);
        strict.put("the quick brown fox", "x");
        // a slightly different prompt fails the strict threshold
        assert!(strict.get("the quick brown foxes jumped").is_none());

        let mut loose = SemanticCache::new(0.4, 8);
        loose.put("the quick brown fox", "x");
        assert!(loose.get("the quick brown foxes jumped").is_some());
    }

    #[test]
    fn returns_the_most_similar_entry() {
        let mut c = SemanticCache::new(0.3, 8);
        c.put("rust programming language", "RUST");
        c.put("python programming language", "PY");
        let hit = c.get("rust ownership programming").unwrap();
        assert_eq!(hit.completion, "RUST"); // closer to the rust entry
    }

    #[test]
    fn capacity_evicts_oldest() {
        let mut c = SemanticCache::new(0.9, 2);
        c.put("aaaa", "1");
        c.put("bbbb", "2");
        c.put("cccc", "3"); // evicts "aaaa"
        assert_eq!(c.len(), 2);
        assert!(c.get("aaaa").is_none());
        assert!(c.get("cccc").is_some());
    }

    #[test]
    fn empty_cache_misses() {
        let mut c = SemanticCache::new(0.5, 4);
        assert!(c.get("anything").is_none());
        assert!(c.is_empty());
    }

    #[test]
    fn serde_round_trip() {
        let mut c = SemanticCache::new(0.7, 4);
        c.put("hello", "hi");
        let j = serde_json::to_string(&c).unwrap();
        let back: SemanticCache = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
