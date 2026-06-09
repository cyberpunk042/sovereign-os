//! `sovereign-retrieval` — lexical retrieval to ground the agent.
//!
//! An agent answers better when it can pull in relevant facts instead of
//! relying only on the prompt. This crate is the retrieval half of
//! retrieval-augmented generation: a [`DocStore`] holds documents and ranks
//! them against a query by **term overlap** — for each distinct query term, it
//! sums how often that term appears in a document — returning the top-k. It is
//! deterministic and embedding-free (ties broken by document id), so retrieval
//! is reproducible.
//!
//! [`RagResponder`] wires that into the agent loop: it wraps any
//! [`Responder`], retrieves the top-k documents for each prompt, prepends them
//! as a `Context:` block, and then delegates — so the wrapped model generates
//! *grounded* in the retrieved text. With an empty store it is a transparent
//! pass-through.
//!
//! Composes [`sovereign-agent-loop`].
//!
//! [`sovereign-agent-loop`]: https://docs.rs/sovereign-agent-loop
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_agent_loop::Responder;
use std::collections::HashMap;

/// Schema version of the retrieval surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A stored document.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Document {
    /// Stable identifier.
    pub id: String,
    /// Document text.
    pub text: String,
}

/// A document with its retrieval score.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ScoredDoc {
    /// The document's id.
    pub id: String,
    /// The document's text.
    pub text: String,
    /// Term-overlap score against the query (higher = more relevant).
    pub score: u32,
}

/// A lexical document store.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct DocStore {
    docs: Vec<Document>,
}

impl DocStore {
    /// An empty store.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a document (later additions with the same id are kept as duplicates;
    /// callers control ids).
    pub fn add(&mut self, id: impl Into<String>, text: impl Into<String>) {
        self.docs.push(Document {
            id: id.into(),
            text: text.into(),
        });
    }

    /// Number of documents.
    pub fn len(&self) -> usize {
        self.docs.len()
    }

    /// Whether the store is empty.
    pub fn is_empty(&self) -> bool {
        self.docs.is_empty()
    }

    /// Retrieve the top-`k` documents for `query` by term overlap. Documents
    /// with zero overlap are excluded. Ties (equal score) break by id ascending.
    pub fn retrieve(&self, query: &str, k: usize) -> Vec<ScoredDoc> {
        let q_terms: Vec<String> = unique_tokens(query);
        let mut scored: Vec<ScoredDoc> = self
            .docs
            .iter()
            .filter_map(|d| {
                let counts = token_counts(&d.text);
                let score: u32 = q_terms.iter().map(|t| *counts.get(t).unwrap_or(&0)).sum();
                (score > 0).then(|| ScoredDoc {
                    id: d.id.clone(),
                    text: d.text.clone(),
                    score,
                })
            })
            .collect();
        scored.sort_by(|a, b| b.score.cmp(&a.score).then_with(|| a.id.cmp(&b.id)));
        scored.truncate(k);
        scored
    }
}

/// Lowercased alphanumeric word tokens.
fn tokens(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_lowercase())
        .collect()
}

/// Distinct tokens, order-stable (first occurrence).
fn unique_tokens(text: &str) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    tokens(text)
        .into_iter()
        .filter(|t| seen.insert(t.clone()))
        .collect()
}

/// Per-token counts in a document.
fn token_counts(text: &str) -> HashMap<String, u32> {
    let mut m = HashMap::new();
    for t in tokens(text) {
        *m.entry(t).or_insert(0) += 1;
    }
    m
}

/// A [`Responder`] that grounds another responder in retrieved context.
#[derive(Debug, Clone)]
pub struct RagResponder<R: Responder> {
    inner: R,
    store: DocStore,
    top_k: usize,
}

impl<R: Responder> RagResponder<R> {
    /// Wrap `inner`, retrieving up to `top_k` documents per prompt from `store`.
    pub fn new(inner: R, store: DocStore, top_k: usize) -> Self {
        Self {
            inner,
            store,
            top_k,
        }
    }

    /// Build the context-augmented prompt for `prompt` (exposed for testing /
    /// inspection). Returns `prompt` unchanged if nothing is retrieved.
    pub fn augment(&self, prompt: &str) -> String {
        let hits = self.store.retrieve(prompt, self.top_k);
        if hits.is_empty() {
            return prompt.to_string();
        }
        let mut out = String::from("Context:\n");
        for h in &hits {
            out.push_str("- ");
            out.push_str(&h.text);
            out.push('\n');
        }
        out.push('\n');
        out.push_str(prompt);
        out
    }
}

impl<R: Responder> Responder for RagResponder<R> {
    fn respond(&mut self, prompt: &str, seed: u64) -> Result<String, String> {
        let augmented = self.augment(prompt);
        self.inner.respond(&augmented, seed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn store() -> DocStore {
        let mut s = DocStore::new();
        s.add(
            "rust",
            "Rust is a systems programming language with ownership.",
        );
        s.add("python", "Python is a high-level interpreted language.");
        s.add(
            "ownership",
            "Ownership in Rust governs memory without a garbage collector.",
        );
        s
    }

    #[test]
    fn retrieves_by_term_overlap() {
        let s = store();
        let hits = s.retrieve("rust ownership memory", 3);
        // both rust-related docs match; the one mentioning more query terms ranks first
        assert!(!hits.is_empty());
        assert_eq!(hits[0].id, "ownership"); // contains rust + ownership + memory
        assert!(hits.iter().all(|h| h.score > 0));
    }

    #[test]
    fn top_k_limits_results() {
        let s = store();
        let hits = s.retrieve("language", 1);
        assert_eq!(hits.len(), 1);
    }

    #[test]
    fn no_overlap_returns_nothing() {
        let s = store();
        assert!(s.retrieve("quantum biology zebra", 5).is_empty());
    }

    #[test]
    fn ties_break_by_id() {
        let mut s = DocStore::new();
        s.add("b", "apple");
        s.add("a", "apple");
        let hits = s.retrieve("apple", 5);
        assert_eq!(hits.len(), 2);
        assert_eq!(hits[0].id, "a"); // equal score → id ascending
        assert_eq!(hits[1].id, "b");
    }

    #[test]
    fn score_counts_term_frequency() {
        let mut s = DocStore::new();
        s.add("once", "rust");
        s.add("thrice", "rust rust rust");
        let hits = s.retrieve("rust", 2);
        assert_eq!(hits[0].id, "thrice"); // 3 > 1
        assert_eq!(hits[0].score, 3);
    }

    // --- RagResponder ---

    use std::cell::RefCell;
    use std::rc::Rc;

    struct Capture {
        seen: Rc<RefCell<Vec<String>>>,
    }
    impl Responder for Capture {
        fn respond(&mut self, prompt: &str, _seed: u64) -> Result<String, String> {
            self.seen.borrow_mut().push(prompt.to_string());
            Ok("ok".to_string())
        }
    }

    #[test]
    fn rag_injects_retrieved_context() {
        let seen = Rc::new(RefCell::new(Vec::new()));
        let inner = Capture { seen: seen.clone() };
        let mut rag = RagResponder::new(inner, store(), 2);
        rag.respond("tell me about rust ownership", 0).unwrap();
        let prompts = seen.borrow();
        assert_eq!(prompts.len(), 1);
        assert!(prompts[0].starts_with("Context:\n"));
        assert!(prompts[0].contains("Ownership in Rust"));
        // the original prompt is preserved after the context
        assert!(prompts[0].ends_with("tell me about rust ownership"));
    }

    #[test]
    fn rag_passes_through_when_nothing_retrieved() {
        let seen = Rc::new(RefCell::new(Vec::new()));
        let inner = Capture { seen: seen.clone() };
        let mut rag = RagResponder::new(inner, store(), 2);
        rag.respond("zebra quantum biology", 0).unwrap();
        // no overlap → prompt unchanged
        assert_eq!(seen.borrow()[0], "zebra quantum biology");
    }

    #[test]
    fn rag_augment_is_inspectable() {
        let rag = RagResponder::new(
            Capture {
                seen: Rc::new(RefCell::new(Vec::new())),
            },
            store(),
            1,
        );
        let aug = rag.augment("python language");
        assert!(aug.contains("Context:"));
        assert!(aug.contains("Python is"));
    }

    #[test]
    fn store_serde_round_trip() {
        let s = store();
        let j = serde_json::to_string(&s).unwrap();
        let back: DocStore = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
