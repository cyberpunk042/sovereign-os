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
use sovereign_embed::EmbedStore;
use std::collections::HashMap;

/// Schema version of the retrieval surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Anything that can return the texts of the top-`k` documents for a query.
///
/// Implemented for the lexical [`DocStore`] and the embedding-backed
/// [`EmbedStore`], so [`RagResponder`] can be backed by either.
pub trait Retriever {
    /// The texts of the top-`k` documents most relevant to `query`.
    fn retrieve_context(&self, query: &str, k: usize) -> Vec<String>;
}

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

    /// Ingest a long document by chunking it (sentence-aware, with overlap) and
    /// adding each chunk under the id `{id_prefix}#{i}`. Returns the number of
    /// chunks added. Composes [`sovereign-chunker`](sovereign_chunker).
    pub fn add_document(
        &mut self,
        id_prefix: &str,
        text: &str,
        target_chars: usize,
        overlap_chars: usize,
    ) -> usize {
        let chunks = sovereign_chunker::chunk(text, target_chars, overlap_chars);
        for (i, c) in chunks.iter().enumerate() {
            self.add(format!("{id_prefix}#{i}"), c.clone());
        }
        chunks.len()
    }

    /// Ingest a long document like [`add_document`](Self::add_document) but drop
    /// near-duplicate chunks: chunks whose MinHash-estimated Jaccard to an
    /// already-kept chunk is `>= min_jaccard` are skipped. Overlapping or
    /// boilerplate-heavy sources produce chunks that repeat almost the same text;
    /// keeping all of them wastes the retrieval budget and biases ranking, so
    /// this composes [`sovereign-minhash`](sovereign_minhash) signatures and a
    /// [`sovereign-lsh`](sovereign_lsh) index to keep only novel chunks. Returns
    /// the number of chunks actually added (kept chunks get sequential ids
    /// `{id_prefix}#{j}`).
    pub fn add_document_deduped(
        &mut self,
        id_prefix: &str,
        text: &str,
        target_chars: usize,
        overlap_chars: usize,
        min_jaccard: f64,
    ) -> usize {
        use sovereign_lsh::LshIndex;
        use sovereign_minhash::MinHasher;

        let (bands, rows) = (16, 4); // 64-slot signatures, threshold ≈ 0.5
        let hasher = MinHasher::new(bands * rows, 0x5ED_C0DE);
        let mut index = LshIndex::new(bands, rows);

        let chunks = sovereign_chunker::chunk(text, target_chars, overlap_chars);
        let mut kept = 0usize;
        for c in &chunks {
            let sig = hasher.sign_text(c, 3);
            if index.insert_if_novel(sig, min_jaccard).is_ok() {
                self.add(format!("{id_prefix}#{kept}"), c.clone());
                kept += 1;
            }
        }
        kept
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

impl Retriever for DocStore {
    fn retrieve_context(&self, query: &str, k: usize) -> Vec<String> {
        self.retrieve(query, k)
            .into_iter()
            .map(|h| h.text)
            .collect()
    }
}

impl Retriever for EmbedStore {
    fn retrieve_context(&self, query: &str, k: usize) -> Vec<String> {
        self.retrieve(query, k)
            .into_iter()
            .map(|h| h.text)
            .collect()
    }
}

/// A BM25-ranked document store: the same add/retrieve surface as [`DocStore`]
/// but scored with Okapi [`BM25`](sovereign_bm25) — IDF-weighted, tf-saturating,
/// length-normalized — instead of raw term overlap. A stronger lexical backend
/// for [`RagResponder`]; it keeps the document texts alongside the BM25 index so
/// it can return them as context.
#[derive(Debug, Clone, Default)]
pub struct Bm25Store {
    index: sovereign_bm25::Bm25,
    texts: Vec<(String, String)>,
}

impl Bm25Store {
    /// An empty store with the default BM25 parameters.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a document under `id`.
    pub fn add(&mut self, id: impl Into<String>, text: impl Into<String>) {
        let id = id.into();
        let text = text.into();
        self.index.add(id.clone(), &text);
        self.texts.push((id, text));
    }

    /// Number of documents.
    pub fn len(&self) -> usize {
        self.texts.len()
    }

    /// Whether the store is empty.
    pub fn is_empty(&self) -> bool {
        self.texts.is_empty()
    }

    /// Retrieve the top-`k` `(id, text, score)` documents for `query` by BM25.
    pub fn retrieve(&self, query: &str, k: usize) -> Vec<(String, String, f64)> {
        self.index
            .search(query, k)
            .into_iter()
            .filter_map(|hit| {
                self.texts
                    .iter()
                    .find(|(id, _)| *id == hit.id)
                    .map(|(id, text)| (id.clone(), text.clone(), hit.score))
            })
            .collect()
    }
}

impl Retriever for Bm25Store {
    fn retrieve_context(&self, query: &str, k: usize) -> Vec<String> {
        self.retrieve(query, k)
            .into_iter()
            .map(|(_, text, _)| text)
            .collect()
    }
}

/// A [`Responder`] that grounds another responder in retrieved context. Works
/// with any [`Retriever`] — the lexical [`DocStore`] or the embedding-backed
/// [`EmbedStore`].
#[derive(Debug, Clone)]
pub struct RagResponder<R: Responder, Ret: Retriever> {
    inner: R,
    retriever: Ret,
    top_k: usize,
}

impl<R: Responder, Ret: Retriever> RagResponder<R, Ret> {
    /// Wrap `inner`, retrieving up to `top_k` documents per prompt.
    pub fn new(inner: R, retriever: Ret, top_k: usize) -> Self {
        Self {
            inner,
            retriever,
            top_k,
        }
    }

    /// Build the context-augmented prompt for `prompt` (exposed for testing /
    /// inspection). Returns `prompt` unchanged if nothing is retrieved.
    pub fn augment(&self, prompt: &str) -> String {
        let hits = self.retriever.retrieve_context(prompt, self.top_k);
        if hits.is_empty() {
            return prompt.to_string();
        }
        let mut out = String::from("Context:\n");
        for h in &hits {
            out.push_str("- ");
            out.push_str(h);
            out.push('\n');
        }
        out.push('\n');
        out.push_str(prompt);
        out
    }
}

impl<R: Responder, Ret: Retriever> Responder for RagResponder<R, Ret> {
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

    #[test]
    fn add_document_chunks_and_retrieves() {
        let mut s = DocStore::new();
        let doc = "Rust has ownership. Ownership governs memory. \
                   Pasta needs tomato. Tomato is a fruit.";
        let n = s.add_document("doc", doc, 30, 0);
        assert!(n >= 2, "expected multiple chunks, got {n}");
        assert_eq!(s.len(), n);
        // chunk ids are prefixed
        assert!(s.retrieve("ownership memory", 1)[0].id.starts_with("doc#"));
        // a query retrieves the relevant chunk, not the pasta one
        let hit = &s.retrieve("rust ownership", 1)[0];
        assert!(hit.text.to_lowercase().contains("ownership"));
    }

    #[test]
    fn add_document_deduped_drops_repeats() {
        let mut s = DocStore::new();
        // a source where the same paragraph is repeated three times, plus one
        // genuinely different paragraph.
        let para = "Rust ownership governs memory safety without a garbage collector. \
                    The borrow checker enforces these rules at compile time.";
        let other = "Photosynthesis converts sunlight carbon dioxide and water into \
                     glucose and oxygen inside chloroplasts of green plants.";
        let doc = format!("{para} {para} {para} {other}");

        // plain ingest keeps every chunk (duplicates included)
        let mut plain = DocStore::new();
        let all = plain.add_document("p", &doc, 120, 0);

        // deduped ingest drops the repeats
        let kept = s.add_document_deduped("d", &doc, 120, 0, 0.7);
        assert!(kept < all, "dedup should keep fewer: kept {kept} of {all}");
        assert_eq!(s.len(), kept);
        // both distinct topics survive
        assert!(!s.retrieve("ownership memory", 1).is_empty());
        assert!(!s.retrieve("photosynthesis glucose", 1).is_empty());
    }

    #[test]
    fn bm25_store_retrieves_and_drives_rag() {
        let mut bm = Bm25Store::new();
        bm.add(
            "rust",
            "Rust gives memory safety through ownership and borrowing",
        );
        bm.add("python", "Python is a dynamically typed scripting language");
        bm.add("pasta", "boil the pasta then add tomato sauce and basil");
        assert_eq!(bm.len(), 3);
        // a lexical query pulls the rust doc
        let hits = bm.retrieve("rust memory ownership", 2);
        assert_eq!(hits[0].0, "rust");
        assert!(hits[0].2 > 0.0);

        // and it works as a RagResponder backend
        let seen = Rc::new(RefCell::new(Vec::new()));
        let inner = Capture { seen: seen.clone() };
        let mut rag = RagResponder::new(inner, bm, 1);
        rag.respond("rust memory safety", 0).unwrap();
        let prompts = seen.borrow();
        assert!(prompts[0].starts_with("Context:\n"));
        assert!(prompts[0].contains("Rust gives memory safety"));
    }

    #[test]
    fn rag_works_with_an_embedding_retriever() {
        // the same RagResponder, backed by the semantic EmbedStore instead of
        // the lexical DocStore.
        let mut es = EmbedStore::new();
        es.add("rust", "rust ownership and systems programming");
        es.add("cook", "pasta tomato sauce recipe");
        let seen = Rc::new(RefCell::new(Vec::new()));
        let inner = Capture { seen: seen.clone() };
        let mut rag = RagResponder::new(inner, es, 1);
        rag.respond("rusty systems programs", 0).unwrap();
        let prompts = seen.borrow();
        assert!(prompts[0].starts_with("Context:\n"));
        // subword match pulls the rust doc, not the cooking one
        assert!(prompts[0].contains("rust ownership"));
    }
}
