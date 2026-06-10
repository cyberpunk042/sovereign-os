//! `sovereign-embed` — subword embeddings via character n-gram hashing.
//!
//! The lexical retriever matches whole words; this one matches *pieces* of
//! them. It turns text into a fixed-dimension dense vector with the
//! feature-hashing trick over **character n-grams**: each word is wrapped in
//! boundary markers (`^word$`), its overlapping `n`-character grams are
//! hashed into buckets with a `±1` sign, and the vector is L2-normalized. Two
//! strings that share subword structure — `rust` and `rusty`, `run` and
//! `running` — therefore land close in cosine space even though they are not
//! the same token, which exact-overlap retrieval cannot see.
//!
//! [`EmbedStore`] uses these vectors for cosine top-k retrieval. Everything is
//! deterministic (a fixed hash, fixed dimension), so embeddings and rankings
//! are reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the embedding surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Default embedding dimension.
pub const DEFAULT_DIM: usize = 256;

/// Default character n-gram size.
pub const DEFAULT_NGRAM: usize = 3;

/// FNV-1a 64-bit hash.
fn fnv1a(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// Embed `text` into a `dim`-dimensional unit vector via `n`-gram hashing.
///
/// # Panics
/// Panics if `dim == 0` or `n == 0`.
pub fn embed_with(text: &str, dim: usize, n: usize) -> Vec<f32> {
    assert!(dim > 0 && n > 0, "dim and n must be > 0");
    let mut v = vec![0.0f32; dim];

    for word in text
        .split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
    {
        let lowered = word.to_lowercase();
        let padded: Vec<char> = std::iter::once('^')
            .chain(lowered.chars())
            .chain(std::iter::once('$'))
            .collect();
        if padded.len() < n {
            // whole short word as one gram
            accumulate(&mut v, &padded.iter().collect::<String>(), dim);
            continue;
        }
        for gram in padded.windows(n) {
            let s: String = gram.iter().collect();
            accumulate(&mut v, &s, dim);
        }
    }

    l2_normalize(&mut v);
    v
}

/// Embed with the default dimension and n-gram size.
pub fn embed(text: &str) -> Vec<f32> {
    embed_with(text, DEFAULT_DIM, DEFAULT_NGRAM)
}

fn accumulate(v: &mut [f32], gram: &str, dim: usize) {
    let h = fnv1a(gram.as_bytes());
    let idx = (h % dim as u64) as usize;
    // sign from a high bit so it is independent of the bucket index
    let sign = if (h >> 63) & 1 == 0 { 1.0 } else { -1.0 };
    v[idx] += sign;
}

fn l2_normalize(v: &mut [f32]) {
    let norm = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 0.0 {
        for x in v.iter_mut() {
            *x /= norm;
        }
    }
}

/// Cosine similarity of two equal-length vectors (0 if either is zero).
pub fn cosine(a: &[f32], b: &[f32]) -> f32 {
    let dot: f32 = a.iter().zip(b).map(|(x, y)| x * y).sum();
    let na: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if na == 0.0 || nb == 0.0 {
        0.0
    } else {
        dot / (na * nb)
    }
}

/// A document with its embedding.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EmbeddedDoc {
    /// Stable id.
    pub id: String,
    /// Document text.
    pub text: String,
    /// The document's embedding.
    pub vector: Vec<f32>,
}

/// A cosine top-k retrieval hit.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Hit {
    /// Document id.
    pub id: String,
    /// Document text.
    pub text: String,
    /// Cosine similarity to the query.
    pub score: f32,
}

/// An embedding-backed document store for semantic retrieval.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EmbedStore {
    dim: usize,
    n: usize,
    docs: Vec<EmbeddedDoc>,
}

impl EmbedStore {
    /// A store with the default dimension/n-gram size.
    pub fn new() -> Self {
        Self::with_params(DEFAULT_DIM, DEFAULT_NGRAM)
    }

    /// A store with explicit embedding parameters.
    pub fn with_params(dim: usize, n: usize) -> Self {
        assert!(dim > 0 && n > 0, "dim and n must be > 0");
        Self {
            dim,
            n,
            docs: Vec::new(),
        }
    }

    /// Embed and store a document.
    pub fn add(&mut self, id: impl Into<String>, text: impl Into<String>) {
        let text = text.into();
        let vector = embed_with(&text, self.dim, self.n);
        self.docs.push(EmbeddedDoc {
            id: id.into(),
            text,
            vector,
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

    /// Retrieve the top-`k` documents by cosine similarity to `query`.
    /// Zero-similarity documents are excluded; ties break by id ascending.
    pub fn retrieve(&self, query: &str, k: usize) -> Vec<Hit> {
        let q = embed_with(query, self.dim, self.n);
        let mut hits: Vec<Hit> = self
            .docs
            .iter()
            .filter_map(|d| {
                let score = cosine(&q, &d.vector);
                (score > 0.0).then(|| Hit {
                    id: d.id.clone(),
                    text: d.text.clone(),
                    score,
                })
            })
            .collect();
        hits.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.id.cmp(&b.id))
        });
        hits.truncate(k);
        hits
    }

    /// Retrieve the top-`k` documents with **Maximal Marginal Relevance**
    /// re-ranking (Carbonell & Goldstein): greedily pick the document that
    /// maximizes `λ·sim(d, query) − (1−λ)·maxₛ sim(d, s)` over the
    /// already-selected set `s`. `lambda = 1.0` is pure relevance (identical to
    /// [`retrieve`](Self::retrieve)); `lambda = 0.0` is pure diversity. This
    /// avoids returning several near-duplicate chunks — a query budget the plain
    /// top-k wastes when the corpus is redundant. `lambda` is clamped to
    /// `[0, 1]`; only documents with positive query similarity are candidates.
    pub fn retrieve_mmr(&self, query: &str, k: usize, lambda: f32) -> Vec<Hit> {
        let lambda = lambda.clamp(0.0, 1.0);
        let q = embed_with(query, self.dim, self.n);
        // Candidates: (doc, relevance) with positive query similarity.
        let mut candidates: Vec<(&EmbeddedDoc, f32)> = self
            .docs
            .iter()
            .filter_map(|d| {
                let rel = cosine(&q, &d.vector);
                (rel > 0.0).then_some((d, rel))
            })
            .collect();

        // Embeddings of the already-selected docs (for the diversity penalty).
        let mut selected_vecs: Vec<Vec<f32>> = Vec::new();
        let mut selected: Vec<Hit> = Vec::with_capacity(k.min(candidates.len()));
        while selected.len() < k && !candidates.is_empty() {
            // Pick the candidate maximizing the MMR objective; deterministic
            // tie-break by relevance (desc) then id (asc).
            let mut best_idx = 0usize;
            let mut best: Option<(f32, f32, &str)> = None; // (mmr, rel, id)
            for (i, &(d, rel)) in candidates.iter().enumerate() {
                let max_sim = selected_vecs
                    .iter()
                    .map(|sv| cosine(&d.vector, sv))
                    .fold(0.0f32, f32::max);
                let mmr = lambda * rel - (1.0 - lambda) * max_sim;
                let better = match best {
                    None => true,
                    Some((bm, br, bid)) => {
                        mmr > bm + 1e-9
                            || (mmr >= bm - 1e-9
                                && (rel > br + 1e-9 || (rel >= br - 1e-9 && d.id.as_str() < bid)))
                    }
                };
                if better {
                    best = Some((mmr, rel, d.id.as_str()));
                    best_idx = i;
                }
            }
            let (d, rel) = candidates.remove(best_idx);
            selected_vecs.push(d.vector.clone());
            selected.push(Hit {
                id: d.id.clone(),
                text: d.text.clone(),
                score: rel,
            });
        }
        selected
    }
}

impl Default for EmbedStore {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mmr_avoids_near_duplicates() {
        // a1 and a2 are identical text (cosine 1.0); b shares the query term but
        // is otherwise different. Plain top-2 returns the two duplicates; MMR
        // swaps the redundant a2 for the diverse b.
        let mut s = EmbedStore::new();
        s.add("a1", "rust systems programming ownership");
        s.add("a2", "rust systems programming ownership"); // duplicate of a1
        s.add("b", "rust concurrency speed channels");
        let q = "rust systems";

        let plain: Vec<String> = s.retrieve(q, 2).into_iter().map(|h| h.id).collect();
        assert_eq!(plain, vec!["a1", "a2"], "plain top-2 keeps both duplicates");

        let mmr: Vec<String> = s
            .retrieve_mmr(q, 2, 0.5)
            .into_iter()
            .map(|h| h.id)
            .collect();
        assert!(mmr.contains(&"a1".to_string()));
        assert!(
            mmr.contains(&"b".to_string()),
            "MMR must pick the diverse b: {mmr:?}"
        );
        assert!(
            !mmr.contains(&"a2".to_string()),
            "MMR must drop the duplicate: {mmr:?}"
        );
    }

    #[test]
    fn mmr_lambda_one_equals_plain_retrieve() {
        let mut s = EmbedStore::new();
        s.add("x", "alpha beta gamma");
        s.add("y", "beta gamma delta");
        s.add("z", "gamma delta epsilon");
        let q = "beta gamma";
        let plain: Vec<String> = s.retrieve(q, 3).into_iter().map(|h| h.id).collect();
        let mmr: Vec<String> = s
            .retrieve_mmr(q, 3, 1.0)
            .into_iter()
            .map(|h| h.id)
            .collect();
        assert_eq!(plain, mmr, "λ=1 is pure relevance");
    }

    #[test]
    fn mmr_empty_store_and_no_match() {
        assert!(EmbedStore::new().retrieve_mmr("q", 3, 0.5).is_empty());
        let mut s = EmbedStore::new();
        s.add("a", "totally unrelated text");
        assert!(s.retrieve_mmr("xyzzy nonexistent", 3, 0.5).is_empty());
    }

    #[test]
    fn embedding_is_unit_norm() {
        let v = embed("hello world");
        let norm: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
        assert!((norm - 1.0).abs() < 1e-5, "norm {norm}");
        assert_eq!(v.len(), DEFAULT_DIM);
    }

    #[test]
    fn embedding_is_deterministic() {
        assert_eq!(embed("reproducible text"), embed("reproducible text"));
    }

    #[test]
    fn empty_text_is_a_zero_vector() {
        let v = embed("   !!!  ");
        assert!(v.iter().all(|&x| x == 0.0));
        assert_eq!(cosine(&v, &embed("anything")), 0.0);
    }

    #[test]
    fn identical_text_has_cosine_one() {
        let a = embed("the quick brown fox");
        assert!((cosine(&a, &a) - 1.0).abs() < 1e-5);
    }

    #[test]
    fn subword_relatives_beat_unrelated() {
        // morphological neighbors share n-grams → higher cosine than unrelated.
        let rust = embed("rust");
        let rusty = embed("rusty");
        let banana = embed("banana");
        assert!(
            cosine(&rust, &rusty) > cosine(&rust, &banana),
            "rust~rusty {} should beat rust~banana {}",
            cosine(&rust, &rusty),
            cosine(&rust, &banana)
        );
    }

    #[test]
    fn shared_stem_is_detected() {
        let run = embed("running");
        let runner = embed("runner");
        let ocean = embed("ocean");
        assert!(cosine(&run, &runner) > cosine(&run, &ocean));
    }

    #[test]
    fn store_retrieves_semantically_closest() {
        let mut s = EmbedStore::new();
        s.add("a", "programming in rust and systems");
        s.add("b", "cooking pasta and tomato sauce");
        s.add("c", "rusty old systems and programs");
        let hits = s.retrieve("rust programming systems", 3);
        assert!(!hits.is_empty());
        // the cooking doc should rank below the rust-related ones
        let cooking = hits.iter().position(|h| h.id == "b");
        let rusty = hits.iter().position(|h| h.id == "c");
        if let (Some(c), Some(r)) = (cooking, rusty) {
            assert!(r < c, "rusty doc should outrank cooking doc");
        }
    }

    #[test]
    fn ties_break_by_id_and_topk_limits() {
        let mut s = EmbedStore::new();
        s.add("b", "apple banana");
        s.add("a", "apple banana");
        let hits = s.retrieve("apple banana", 1);
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].id, "a"); // equal score → id ascending
    }

    #[test]
    fn no_overlap_returns_nothing() {
        let mut s = EmbedStore::new();
        s.add("a", "zzzzz qqqqq");
        // a query with no shared n-grams
        assert!(s.retrieve("0000 1111", 3).is_empty());
    }

    #[test]
    fn store_serde_round_trip() {
        let mut s = EmbedStore::new();
        s.add("x", "hello");
        let j = serde_json::to_string(&s).unwrap();
        let back: EmbedStore = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
