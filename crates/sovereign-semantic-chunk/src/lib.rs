//! `sovereign-semantic-chunk` — split text where the *meaning* shifts.
//!
//! Fixed-size character chunking cuts mid-thought: a boundary lands wherever the
//! byte count runs out, often splitting a single idea across two chunks and
//! gluing unrelated ideas into one. **Semantic chunking** instead places
//! boundaries where consecutive sentences stop being about the same thing. Given
//! the sentences and their embeddings, it scores each adjacent pair by cosine
//! similarity and cuts at the *dips* — the low-similarity gaps between
//! topically-coherent runs.
//!
//! Two cut policies are provided. [`chunk_by_threshold`] cuts wherever the
//! neighbour similarity falls below a fixed value — simple when you know what
//! "different topic" looks like for your embeddings. [`chunk_by_percentile`] is
//! adaptive: it cuts at the gaps whose similarity is in the lowest `p` percent of
//! all gaps in *this* document, so it works without tuning across documents of
//! different absolute similarity scales (the standard breakpoint method).
//!
//! Both take the sentences and a parallel slice of embedding vectors and return
//! the chunks as joined strings; they never split a sentence.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the semantic-chunk surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Cosine similarity of two equal-length vectors (0 if either is a zero vector).
pub fn cosine(a: &[f32], b: &[f32]) -> f64 {
    let mut dot = 0.0f64;
    let mut na = 0.0f64;
    let mut nb = 0.0f64;
    for (&x, &y) in a.iter().zip(b.iter()) {
        dot += x as f64 * y as f64;
        na += x as f64 * x as f64;
        nb += y as f64 * y as f64;
    }
    if na == 0.0 || nb == 0.0 {
        0.0
    } else {
        dot / (na.sqrt() * nb.sqrt())
    }
}

/// The adjacent-pair cosine similarities: `gaps[i]` relates sentence `i` and
/// `i+1`. Length is `sentences.len() - 1` (empty for 0 or 1 sentence).
pub fn adjacent_similarities(embeddings: &[Vec<f32>]) -> Vec<f64> {
    embeddings
        .windows(2)
        .map(|w| cosine(&w[0], &w[1]))
        .collect()
}

/// Join sentences into chunks given the boundary indices *after which* to cut
/// (a cut after sentence `i` ends a chunk at `i`).
fn assemble(sentences: &[&str], cut_after: &[bool]) -> Vec<String> {
    let mut chunks = Vec::new();
    let mut current: Vec<&str> = Vec::new();
    for (i, &s) in sentences.iter().enumerate() {
        current.push(s);
        let last = i == sentences.len() - 1;
        if last || cut_after.get(i).copied().unwrap_or(false) {
            chunks.push(current.join(" "));
            current.clear();
        }
    }
    chunks
}

/// Chunk by a fixed similarity `threshold`: cut between two sentences whenever
/// their embedding cosine is *below* `threshold`. `sentences` and `embeddings`
/// must be the same length.
pub fn chunk_by_threshold(
    sentences: &[&str],
    embeddings: &[Vec<f32>],
    threshold: f64,
) -> Vec<String> {
    let n = sentences.len().min(embeddings.len());
    if n == 0 {
        return Vec::new();
    }
    let sims = adjacent_similarities(&embeddings[..n]);
    // cut_after[i] = true means a boundary between sentence i and i+1.
    let cut_after: Vec<bool> = sims.iter().map(|&s| s < threshold).collect();
    assemble(&sentences[..n], &cut_after)
}

/// Chunk by adaptive percentile breakpoints: cut at the gaps whose similarity is
/// in the lowest `percentile` fraction (e.g. `0.1` = the 10% least-similar gaps)
/// of all gaps in this document. `percentile` is clamped to `[0, 1]`; `0` makes a
/// single chunk, `1` splits every sentence.
pub fn chunk_by_percentile(
    sentences: &[&str],
    embeddings: &[Vec<f32>],
    percentile: f64,
) -> Vec<String> {
    let n = sentences.len().min(embeddings.len());
    if n == 0 {
        return Vec::new();
    }
    let p = percentile.clamp(0.0, 1.0);
    let sims = adjacent_similarities(&embeddings[..n]);
    if sims.is_empty() {
        return assemble(&sentences[..n], &[]);
    }
    // number of gaps to cut = round(p * num_gaps); cut exactly those gap indices
    // with the lowest similarity (ties broken by position) so ties never cause
    // over-cutting.
    let num_cuts = (p * sims.len() as f64).round() as usize;
    let num_cuts = num_cuts.min(sims.len());
    let mut order: Vec<usize> = (0..sims.len()).collect();
    order.sort_by(|&i, &j| sims[i].total_cmp(&sims[j]).then(i.cmp(&j)));
    let mut cut_after = vec![false; sims.len()];
    for &gap in order.iter().take(num_cuts) {
        cut_after[gap] = true;
    }
    assemble(&sentences[..n], &cut_after)
}

/// One-call semantic chunking of raw `text`: split it into sentences with
/// [`sovereign_sentence_split`], embed each with [`sovereign_embed`], and chunk by
/// the adaptive percentile breakpoint. Returns topically-coherent chunks ready
/// for retrieval ingestion — the whole text-to-chunks path in one call.
pub fn chunk_text(text: &str, percentile: f64) -> Vec<String> {
    let sentences = sovereign_sentence_split::split(text);
    if sentences.is_empty() {
        return Vec::new();
    }
    let refs: Vec<&str> = sentences.iter().map(String::as_str).collect();
    let embeddings: Vec<Vec<f32>> = refs.iter().map(|s| sovereign_embed::embed(s)).collect();
    chunk_by_percentile(&refs, &embeddings, percentile)
}

#[cfg(test)]
mod tests {
    use super::*;

    // toy 2-D embeddings: topic A ~ (1,0), topic B ~ (0,1)
    fn a() -> Vec<f32> {
        vec![1.0, 0.0]
    }
    fn b() -> Vec<f32> {
        vec![0.0, 1.0]
    }

    #[test]
    fn threshold_splits_at_topic_change() {
        // two A sentences then two B sentences → one cut in the middle
        let sentences = ["a1", "a2", "b1", "b2"];
        let embs = vec![a(), a(), b(), b()];
        let chunks = chunk_by_threshold(&sentences, &embs, 0.5);
        assert_eq!(chunks, vec!["a1 a2", "b1 b2"]);
    }

    #[test]
    fn threshold_one_chunk_when_coherent() {
        let sentences = ["a1", "a2", "a3"];
        let embs = vec![a(), a(), a()];
        let chunks = chunk_by_threshold(&sentences, &embs, 0.5);
        assert_eq!(chunks, vec!["a1 a2 a3"]);
    }

    #[test]
    fn threshold_splits_every_sentence_when_all_dissimilar() {
        let sentences = ["x", "y", "z"];
        let embs = vec![vec![1.0, 0.0], vec![0.0, 1.0], vec![1.0, 0.0]];
        let chunks = chunk_by_threshold(&sentences, &embs, 0.5);
        assert_eq!(chunks, vec!["x", "y", "z"]);
    }

    #[test]
    fn adjacent_similarities_values() {
        let embs = vec![a(), a(), b()];
        let sims = adjacent_similarities(&embs);
        assert_eq!(sims.len(), 2);
        assert!((sims[0] - 1.0).abs() < 1e-9); // a,a
        assert!(sims[1].abs() < 1e-9); // a,b orthogonal
    }

    #[test]
    fn percentile_cuts_the_weakest_gaps() {
        // gaps similarities: high, LOW, high → 1/3 percentile cuts the one low gap
        let sentences = ["a1", "a2", "b1", "b2"];
        let embs = vec![a(), a(), b(), b()];
        // gaps: (a,a)=1, (a,b)=0, (b,b)=1 → lowest is the middle
        let chunks = chunk_by_percentile(&sentences, &embs, 0.34);
        assert_eq!(chunks, vec!["a1 a2", "b1 b2"]);
    }

    #[test]
    fn percentile_zero_is_single_chunk() {
        let sentences = ["a", "b", "c"];
        let embs = vec![a(), b(), a()];
        let chunks = chunk_by_percentile(&sentences, &embs, 0.0);
        assert_eq!(chunks, vec!["a b c"]);
    }

    #[test]
    fn percentile_one_splits_all() {
        let sentences = ["a", "b", "c"];
        let embs = vec![a(), a(), a()];
        let chunks = chunk_by_percentile(&sentences, &embs, 1.0);
        assert_eq!(chunks, vec!["a", "b", "c"]);
    }

    #[test]
    fn single_sentence_and_empty() {
        assert_eq!(chunk_by_threshold(&["only"], &[a()], 0.5), vec!["only"]);
        let empty: Vec<&str> = Vec::new();
        assert!(chunk_by_threshold(&empty, &[], 0.5).is_empty());
        assert!(chunk_by_percentile(&empty, &[], 0.5).is_empty());
    }

    #[test]
    fn chunk_text_end_to_end() {
        // two clearly different topics; semantic chunking should produce >1 chunk
        // and every sentence must survive somewhere in the output.
        let text = "Rust gives memory safety. Ownership prevents data races. \
                    Pasta needs boiling water. Add salt and tomato sauce.";
        let chunks = chunk_text(text, 0.34);
        assert!(!chunks.is_empty());
        let joined = chunks.join(" ");
        assert!(joined.contains("memory safety"));
        assert!(joined.contains("tomato sauce"));
    }

    #[test]
    fn chunk_text_empty_is_empty() {
        assert!(chunk_text("", 0.3).is_empty());
        assert!(chunk_text("   ", 0.3).is_empty());
    }

    #[test]
    fn chunks_concatenate_back_to_all_sentences() {
        let sentences = ["one", "two", "three", "four", "five"];
        let embs = vec![a(), b(), a(), b(), a()];
        let chunks = chunk_by_threshold(&sentences, &embs, 0.5);
        let rejoined: Vec<&str> = chunks.iter().flat_map(|c| c.split(' ')).collect();
        assert_eq!(rejoined, sentences);
    }
}
