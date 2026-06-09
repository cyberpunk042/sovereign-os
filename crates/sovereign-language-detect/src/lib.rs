//! `sovereign-language-detect` — which language is this text?
//!
//! Routing, filtering, or tagging text often needs to know its language first.
//! The classic, model-free way (Cavnar & Trenkle) is character n-grams: every
//! language has a characteristic distribution of short character sequences — the
//! `the`/`ing`/`th` of English, the `ent`/`ion`/`es ` of French — and that
//! distribution is a fingerprint. This crate learns a fingerprint per language
//! from sample text and classifies new text by comparing fingerprints.
//!
//! A [`LanguageDetector`] is *trained*: [`add_language`] folds a sample into that
//! language's character-trigram frequency profile (lowercased, including spaces so
//! word-edge patterns count). [`detect`] then computes the query's trigram profile
//! and returns the language whose profile is most **cosine-similar** — robust to
//! length, since both vectors are normalized. [`rank`] returns the full ordering
//! with scores, useful when two languages are close.
//!
//! It is self-contained: no bundled models, so you train it on whatever languages
//! and registers you care about, and the result is deterministic.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the language-detect surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The character n-gram order used for profiles (trigrams).
pub const NGRAM: usize = 3;

/// A trained per-language character-n-gram profile.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LanguageProfile {
    /// The language name/tag.
    pub name: String,
    /// n-gram → raw count, accumulated over training samples.
    counts: HashMap<String, u64>,
    /// Total n-grams seen (for reference; cosine uses the raw counts directly).
    total: u64,
}

impl LanguageProfile {
    /// The number of distinct n-grams in the profile.
    pub fn distinct_ngrams(&self) -> usize {
        self.counts.len()
    }
}

/// A trainable language detector over character-trigram profiles.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LanguageDetector {
    profiles: Vec<LanguageProfile>,
}

impl LanguageDetector {
    /// An empty detector.
    pub fn new() -> Self {
        Self::default()
    }

    /// Train: fold `sample` into the named language's profile (creating it if new).
    /// Call repeatedly to accumulate more data for a language.
    pub fn add_language(&mut self, name: &str, sample: &str) {
        let grams = ngram_counts(sample);
        if let Some(p) = self.profiles.iter_mut().find(|p| p.name == name) {
            for (g, c) in grams {
                *p.counts.entry(g).or_insert(0) += c;
                p.total += c;
            }
        } else {
            let total = grams.values().sum();
            self.profiles.push(LanguageProfile {
                name: name.to_string(),
                counts: grams,
                total,
            });
        }
    }

    /// The number of trained languages.
    pub fn len(&self) -> usize {
        self.profiles.len()
    }

    /// Whether the detector has no languages.
    pub fn is_empty(&self) -> bool {
        self.profiles.is_empty()
    }

    /// The most likely language for `text` with its cosine score in `[0, 1]`, or
    /// `None` if untrained or `text` has no usable n-grams.
    pub fn detect(&self, text: &str) -> Option<(String, f64)> {
        self.rank(text).into_iter().next()
    }

    /// All languages ranked by descending cosine similarity to `text`.
    pub fn rank(&self, text: &str) -> Vec<(String, f64)> {
        if self.profiles.is_empty() {
            return Vec::new();
        }
        let query = ngram_counts(text);
        if query.is_empty() {
            return Vec::new();
        }
        let qnorm = norm(query.values().map(|&c| c as f64));
        let mut scored: Vec<(String, f64)> = self
            .profiles
            .iter()
            .map(|p| {
                let sim = cosine(&query, &p.counts, qnorm);
                (p.name.clone(), sim)
            })
            .collect();
        scored.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
        scored
    }
}

/// Lowercased character-trigram counts of `text` (whitespace runs collapsed to a
/// single space so word-boundary n-grams are consistent).
fn ngram_counts(text: &str) -> HashMap<String, u64> {
    let normalized: String = {
        let mut s = String::with_capacity(text.len());
        let mut last_space = false;
        for c in text.chars().flat_map(|c| c.to_lowercase()) {
            if c.is_whitespace() {
                if !last_space {
                    s.push(' ');
                    last_space = true;
                }
            } else {
                s.push(c);
                last_space = false;
            }
        }
        s.trim().to_string()
    };
    let chars: Vec<char> = normalized.chars().collect();
    let mut m = HashMap::new();
    if chars.len() < NGRAM {
        if !chars.is_empty() {
            *m.entry(chars.iter().collect::<String>()).or_insert(0) += 1;
        }
        return m;
    }
    for w in chars.windows(NGRAM) {
        *m.entry(w.iter().collect::<String>()).or_insert(0) += 1;
    }
    m
}

fn norm<I: Iterator<Item = f64>>(values: I) -> f64 {
    values.map(|v| v * v).sum::<f64>().sqrt()
}

/// Cosine similarity between a query count map and a profile count map, given the
/// query's precomputed norm.
fn cosine(query: &HashMap<String, u64>, profile: &HashMap<String, u64>, qnorm: f64) -> f64 {
    let pnorm = norm(profile.values().map(|&c| c as f64));
    if qnorm == 0.0 || pnorm == 0.0 {
        return 0.0;
    }
    let mut dot = 0.0;
    for (g, &qc) in query {
        if let Some(&pc) = profile.get(g) {
            dot += qc as f64 * pc as f64;
        }
    }
    dot / (qnorm * pnorm)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn trained() -> LanguageDetector {
        let mut d = LanguageDetector::new();
        d.add_language(
            "english",
            "the quick brown fox jumps over the lazy dog and the cat sat on the mat \
             while the children were playing in the garden near the old house",
        );
        d.add_language(
            "spanish",
            "el rapido zorro marron salta sobre el perro perezoso y el gato se sento \
             en la alfombra mientras los ninos jugaban en el jardin cerca de la casa",
        );
        d.add_language(
            "french",
            "le renard brun rapide saute par dessus le chien paresseux et le chat \
             etait assis sur le tapis pendant que les enfants jouaient dans le jardin",
        );
        d
    }

    #[test]
    fn detects_trained_languages() {
        let d = trained();
        assert_eq!(
            d.detect("the dog and the cat in the house").unwrap().0,
            "english"
        );
        assert_eq!(
            d.detect("el gato y el perro en la casa").unwrap().0,
            "spanish"
        );
        assert_eq!(
            d.detect("le chat et le chien dans le jardin").unwrap().0,
            "french"
        );
    }

    #[test]
    fn rank_returns_all_with_scores() {
        let d = trained();
        let ranked = d.rank("the quick brown dog");
        assert_eq!(ranked.len(), 3);
        // top is english and scores are descending in [0,1]
        assert_eq!(ranked[0].0, "english");
        assert!(ranked.windows(2).all(|w| w[0].1 >= w[1].1));
        assert!(ranked.iter().all(|(_, s)| (0.0..=1.0).contains(s)));
    }

    #[test]
    fn identical_text_scores_near_one() {
        let mut d = LanguageDetector::new();
        let sample = "hello world this is a test of the detector";
        d.add_language("x", sample);
        let (_, score) = d.detect(sample).unwrap();
        assert!(score > 0.99, "score {score}");
    }

    #[test]
    fn accumulates_training() {
        let mut d = LanguageDetector::new();
        d.add_language("en", "the cat");
        d.add_language("en", "the dog");
        assert_eq!(d.len(), 1); // same language merged
        assert!(d.profiles[0].distinct_ngrams() > 0);
    }

    #[test]
    fn untrained_or_empty_query() {
        let d = LanguageDetector::new();
        assert!(d.detect("anything").is_none());
        let t = trained();
        assert!(t.detect("").is_none());
    }

    #[test]
    fn case_insensitive() {
        let d = trained();
        let lower = d.detect("the dog and the cat").unwrap().0;
        let upper = d.detect("THE DOG AND THE CAT").unwrap().0;
        assert_eq!(lower, upper);
    }

    #[test]
    fn serde_round_trip() {
        let d = trained();
        let j = serde_json::to_string(&d).unwrap();
        let back: LanguageDetector = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
        assert_eq!(
            back.detect("the cat").unwrap().0,
            d.detect("the cat").unwrap().0
        );
    }
}
