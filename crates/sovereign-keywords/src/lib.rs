//! `sovereign-keywords` — RAKE-style keyphrase extraction.
//!
//! To tag, index, or route a document you need its *salient* phrases, not its
//! word histogram. This crate implements RAKE (Rapid Automatic Keyword
//! Extraction): it splits the text on stopwords and punctuation into candidate
//! phrases (the meaningful runs between function words), scores each content
//! word by its **degree over frequency** — words that co-occur in long phrases
//! and appear often score high — and scores a phrase by summing its words'
//! scores. The top phrases are the keywords.
//!
//! RAKE is unsupervised, deterministic, and dependency-free, and it naturally
//! surfaces multi-word terms (`"rapid keyword extraction"`) rather than isolated
//! words, which is what makes it useful for indexing.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the keywords surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A small English stopword list (function words that delimit keyphrases).
pub const STOPWORDS: &[&str] = &[
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "is", "are", "was", "were", "for",
    "on", "with", "as", "by", "at", "it", "its", "this", "that", "these", "those", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "can", "could", "should", "may",
    "might", "i", "you", "he", "she", "we", "they", "them", "his", "her", "their", "our", "your",
    "from", "into", "than", "then", "so", "if", "not", "no", "yes", "up", "out", "about", "over",
];

fn is_stopword(w: &str) -> bool {
    STOPWORDS.contains(&w)
}

/// A scored keyphrase.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Keyword {
    /// The phrase (lowercased).
    pub phrase: String,
    /// Its RAKE score (sum of member-word degree/frequency scores).
    pub score: f64,
}

/// Extract the top `top_k` keyphrases from `text`.
pub fn extract(text: &str, top_k: usize) -> Vec<Keyword> {
    // work in lowercase so casing doesn't fragment the same word/phrase
    let lower = text.to_lowercase();
    // 1. split into candidate phrases (runs of content words)
    let phrases = candidate_phrases(&lower);
    if phrases.is_empty() {
        return Vec::new();
    }

    // 2. word frequency and degree (co-occurrence including self)
    let mut freq: HashMap<&str, f64> = HashMap::new();
    let mut degree: HashMap<&str, f64> = HashMap::new();
    for phrase in &phrases {
        let len = phrase.len() as f64;
        for &w in phrase {
            *freq.entry(w).or_insert(0.0) += 1.0;
            *degree.entry(w).or_insert(0.0) += len;
        }
    }

    // 3. word score = degree / freq
    let word_score = |w: &str| degree[w] / freq[w];

    // 4. phrase score = sum of word scores; merge duplicate phrases (keep max)
    let mut best: HashMap<String, f64> = HashMap::new();
    for phrase in &phrases {
        let score: f64 = phrase.iter().map(|&w| word_score(w)).sum();
        let key = phrase.join(" ");
        let e = best.entry(key).or_insert(0.0);
        if score > *e {
            *e = score;
        }
    }

    // 5. sort by score desc, ties by phrase asc; take top_k
    let mut out: Vec<Keyword> = best
        .into_iter()
        .map(|(phrase, score)| Keyword { phrase, score })
        .collect();
    out.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.phrase.cmp(&b.phrase))
    });
    out.truncate(top_k);
    out
}

/// Split an already-lowercased `text` into candidate phrases: maximal runs of
/// content (non-stopword) words, broken at stopwords and punctuation.
fn candidate_phrases(text: &str) -> Vec<Vec<&str>> {
    let mut phrases = Vec::new();
    let mut current: Vec<&str> = Vec::new();
    for tok in text.split(|c: char| !c.is_alphanumeric()) {
        if tok.is_empty() || is_stopword(tok) {
            // a stopword or punctuation ends the current phrase
            if !current.is_empty() {
                phrases.push(std::mem::take(&mut current));
            }
        } else {
            current.push(tok);
        }
    }
    if !current.is_empty() {
        phrases.push(current);
    }
    phrases
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_multiword_keyphrases() {
        let text = "Rapid automatic keyword extraction works on documents. \
                    Keyword extraction is useful.";
        let kws = extract(text, 5);
        assert!(!kws.is_empty());
        // a multi-word phrase should surface
        assert!(
            kws.iter().any(|k| k.phrase.split_whitespace().count() >= 2),
            "{kws:?}"
        );
    }

    #[test]
    fn stopwords_are_excluded_from_phrases() {
        let kws = extract("the cat sat on the mat", 10);
        // "the" / "on" are stopwords → never appear as keyphrases
        for k in &kws {
            assert!(!k.phrase.split_whitespace().any(|w| w == "the" || w == "on"));
        }
    }

    #[test]
    fn longer_cooccurring_phrases_score_higher() {
        // "machine learning" co-occurs (degree 2 each) → outscores lone "data"
        let text = "machine learning. machine learning. data.";
        let kws = extract(text, 5);
        assert_eq!(kws[0].phrase, "machine learning");
        assert!(kws[0].score > kws.last().unwrap().score);
    }

    #[test]
    fn punctuation_breaks_phrases() {
        let kws = extract("alpha beta, gamma delta", 5);
        let phrases: Vec<&str> = kws.iter().map(|k| k.phrase.as_str()).collect();
        assert!(phrases.contains(&"alpha beta"));
        assert!(phrases.contains(&"gamma delta"));
        // they were not joined across the comma
        assert!(!phrases.iter().any(|p| p.contains("beta gamma")));
    }

    #[test]
    fn top_k_limits_results() {
        let text = "one. two. three. four. five.";
        assert_eq!(extract(text, 2).len(), 2);
    }

    #[test]
    fn empty_or_stopword_only_text_yields_nothing() {
        assert!(extract("", 5).is_empty());
        assert!(extract("the and of to", 5).is_empty());
    }

    #[test]
    fn scores_are_sorted_descending() {
        let kws = extract("apple banana cherry. apple banana. apple.", 5);
        for w in kws.windows(2) {
            assert!(w[0].score >= w[1].score);
        }
    }

    #[test]
    fn keyword_serde_round_trip() {
        let kws = extract("rust ownership model", 3);
        let j = serde_json::to_string(&kws).unwrap();
        let back: Vec<Keyword> = serde_json::from_str(&j).unwrap();
        assert_eq!(kws, back);
    }
}
