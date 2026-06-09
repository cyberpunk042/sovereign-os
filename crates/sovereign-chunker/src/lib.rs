//! `sovereign-chunker` — sentence-aware chunking for RAG ingestion.
//!
//! Before a document can be retrieved or embedded it has to be cut into pieces
//! small enough to fit a context window and focused enough to match a query.
//! Cutting on a fixed byte boundary slices sentences in half and loses meaning
//! at the seams; this chunker cuts on **sentence boundaries** instead. It
//! splits the text into sentences, greedily packs them into chunks up to a
//! target size, and carries a configurable **overlap** of trailing sentences
//! into the next chunk so a fact spanning a boundary still appears whole in one
//! chunk.
//!
//! It is deterministic and dependency-free, and pairs with the lexical/semantic
//! retrievers: chunk a document, store each chunk, retrieve the relevant ones.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the chunker surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Split `text` into sentence-like units. A unit ends at `.`/`!`/`?` followed by
/// whitespace (or end of input), or at a line break. Empty units are dropped.
pub fn split_sentences(text: &str) -> Vec<String> {
    let chars: Vec<char> = text.chars().collect();
    let mut out = Vec::new();
    let mut buf = String::new();
    let n = chars.len();
    for i in 0..n {
        let c = chars[i];
        if c == '\n' {
            flush(&mut buf, &mut out);
            continue;
        }
        buf.push(c);
        let is_terminator = matches!(c, '.' | '!' | '?');
        let next_is_break = i + 1 >= n || chars[i + 1].is_whitespace();
        if is_terminator && next_is_break {
            flush(&mut buf, &mut out);
        }
    }
    flush(&mut buf, &mut out);
    out
}

fn flush(buf: &mut String, out: &mut Vec<String>) {
    let s = buf.trim();
    if !s.is_empty() {
        out.push(s.to_string());
    }
    buf.clear();
}

/// Chunk `text` into pieces of at most ~`target_chars`, breaking at sentence
/// boundaries, with up to `overlap_chars` of trailing sentences repeated at the
/// start of the next chunk. A single sentence longer than `target_chars` becomes
/// its own (oversized) chunk.
///
/// # Panics
/// Panics if `target_chars == 0`.
pub fn chunk(text: &str, target_chars: usize, overlap_chars: usize) -> Vec<String> {
    assert!(target_chars > 0, "target_chars must be > 0");
    let sentences = split_sentences(text);
    if sentences.is_empty() {
        return Vec::new();
    }

    let mut chunks: Vec<String> = Vec::new();
    let mut current: Vec<String> = Vec::new();
    let mut current_len = 0usize;

    for s in sentences {
        let add = s.chars().count();
        // would adding this sentence overflow a non-empty chunk?
        if !current.is_empty() && current_len + add + 1 > target_chars {
            chunks.push(current.join(" "));
            // seed the next chunk with the trailing overlap sentences
            let overlap = tail_overlap(&current, overlap_chars);
            current_len = overlap.iter().map(|x| x.chars().count() + 1).sum();
            current = overlap;
        }
        current_len += add + 1;
        current.push(s);
    }
    if !current.is_empty() {
        chunks.push(current.join(" "));
    }
    chunks
}

/// The longest suffix of `sentences` whose total length is ≤ `overlap_chars`.
fn tail_overlap(sentences: &[String], overlap_chars: usize) -> Vec<String> {
    if overlap_chars == 0 {
        return Vec::new();
    }
    let mut acc = 0usize;
    let mut start = sentences.len();
    for (i, s) in sentences.iter().enumerate().rev() {
        let len = s.chars().count() + 1;
        if acc + len > overlap_chars {
            break;
        }
        acc += len;
        start = i;
    }
    sentences[start..].to_vec()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splits_into_sentences() {
        let s = split_sentences("Hello world. How are you? I am fine!");
        assert_eq!(s, vec!["Hello world.", "How are you?", "I am fine!"]);
    }

    #[test]
    fn newlines_break_sentences() {
        let s = split_sentences("line one\nline two\n\nline three");
        assert_eq!(s, vec!["line one", "line two", "line three"]);
    }

    #[test]
    fn empty_text_is_no_chunks() {
        assert!(chunk("", 100, 10).is_empty());
        assert!(chunk("   \n  ", 100, 10).is_empty());
    }

    #[test]
    fn short_text_is_one_chunk() {
        let c = chunk("Just a little text.", 100, 10);
        assert_eq!(c.len(), 1);
        assert_eq!(c[0], "Just a little text.");
    }

    #[test]
    fn long_text_splits_into_multiple_chunks() {
        // five ~10-char sentences, target 25 → multiple chunks
        let text = "aaaa bbbb. cccc dddd. eeee ffff. gggg hhhh. iiii jjjj.";
        let chunks = chunk(text, 25, 0);
        assert!(chunks.len() >= 2, "{chunks:?}");
        // each chunk respects the target (allowing a small join slack)
        for ch in &chunks {
            assert!(ch.chars().count() <= 30, "{ch:?}");
        }
    }

    #[test]
    fn chunks_break_on_sentence_boundaries() {
        let text = "First sentence here. Second sentence here. Third sentence here.";
        let chunks = chunk(text, 30, 0);
        // no chunk should start or end mid-word — every chunk is whole sentences
        for ch in &chunks {
            assert!(ch.ends_with('.'), "chunk not sentence-aligned: {ch:?}");
        }
    }

    #[test]
    fn overlap_repeats_trailing_context() {
        let text = "alpha one. bravo two. charlie three. delta four.";
        let chunks = chunk(text, 22, 12);
        assert!(chunks.len() >= 2);
        // the start of chunk 2 should repeat a sentence from the end of chunk 1
        let first_sentences = split_sentences(&chunks[0]);
        let second_sentences = split_sentences(&chunks[1]);
        let last_of_first = first_sentences.last().unwrap();
        assert!(
            second_sentences.iter().any(|s| s == last_of_first),
            "no overlap: {:?} vs {:?}",
            chunks[0],
            chunks[1]
        );
    }

    #[test]
    fn oversized_sentence_becomes_its_own_chunk() {
        let text = "tiny. this is a very long single sentence that exceeds the target size by a lot. tiny.";
        let chunks = chunk(text, 20, 0);
        // the long sentence is preserved whole in some chunk
        assert!(
            chunks
                .iter()
                .any(|c| c.contains("very long single sentence"))
        );
    }

    #[test]
    fn zero_overlap_has_no_repetition() {
        let text = "one. two. three. four. five.";
        let chunks = chunk(text, 12, 0);
        // concatenating all chunk sentences should equal the originals (no dupes)
        let total: usize = chunks.iter().map(|c| split_sentences(c).len()).sum();
        assert_eq!(total, 5);
    }
}
