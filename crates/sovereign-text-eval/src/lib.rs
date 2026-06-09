//! `sovereign-text-eval` — score generated text against references.
//!
//! Evaluating a summary, translation, or completion means comparing it to one or
//! more reference texts. This crate implements the two standard families.
//!
//! **BLEU** measures *precision*: what fraction of the candidate's n-grams appear
//! in a reference, for n = 1..N, combined as a geometric mean. Two details make it
//! honest — n-gram counts are *clipped* to the reference's count (so repeating a
//! correct word doesn't inflate the score), and a **brevity penalty** punishes
//! candidates shorter than the reference (precision alone would reward saying
//! almost nothing). [`bleu`] returns a score in `[0, 1]`.
//!
//! **ROUGE** measures *recall*-oriented overlap, the usual choice for
//! summarization. [`rouge_n`] is the n-gram precision/recall/F1 between candidate
//! and reference; [`rouge_l`] uses the longest common subsequence, rewarding
//! in-order overlap without requiring contiguity. Both return an [`Score`] with
//! precision, recall, and F1.
//!
//! Everything works on token slices (`&[&str]`), so you control tokenization;
//! [`whitespace_tokens`] is provided for the common case.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the text-eval surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Precision / recall / F1 triple.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Score {
    /// Precision.
    pub precision: f64,
    /// Recall.
    pub recall: f64,
    /// F1 (harmonic mean).
    pub f1: f64,
}

impl Score {
    fn from_counts(overlap: usize, cand: usize, refr: usize) -> Self {
        let precision = if cand == 0 {
            0.0
        } else {
            overlap as f64 / cand as f64
        };
        let recall = if refr == 0 {
            0.0
        } else {
            overlap as f64 / refr as f64
        };
        let f1 = if precision + recall == 0.0 {
            0.0
        } else {
            2.0 * precision * recall / (precision + recall)
        };
        Self {
            precision,
            recall,
            f1,
        }
    }
}

/// Split text into lowercase whitespace tokens.
pub fn whitespace_tokens(text: &str) -> Vec<String> {
    text.split_whitespace().map(|s| s.to_lowercase()).collect()
}

/// Count the n-grams of `tokens` (as joined strings) into a multiset.
fn ngram_counts(tokens: &[&str], n: usize) -> HashMap<String, usize> {
    let mut m = HashMap::new();
    if tokens.len() < n || n == 0 {
        return m;
    }
    for w in tokens.windows(n) {
        *m.entry(w.join("\u{1f}")).or_insert(0) += 1;
    }
    m
}

/// Clipped n-gram precision: matched n-grams (clipped to reference counts) over
/// candidate n-grams. Returns `(matches, total_candidate_ngrams)`.
fn clipped_match(candidate: &[&str], reference: &[&str], n: usize) -> (usize, usize) {
    let cand = ngram_counts(candidate, n);
    let refr = ngram_counts(reference, n);
    let total: usize = cand.values().sum();
    let mut matched = 0usize;
    for (gram, &c) in &cand {
        let r = refr.get(gram).copied().unwrap_or(0);
        matched += c.min(r);
    }
    (matched, total)
}

/// Sentence BLEU of `candidate` against a single `reference` using n-grams up to
/// `max_n` (typically 4), with uniform weights and a brevity penalty. Score in
/// `[0, 1]`.
pub fn bleu(candidate: &[&str], reference: &[&str], max_n: usize) -> f64 {
    if candidate.is_empty() || max_n == 0 {
        return 0.0;
    }
    let mut log_sum = 0.0;
    let mut used = 0usize;
    for n in 1..=max_n {
        let (m, total) = clipped_match(candidate, reference, n);
        if total == 0 {
            continue; // candidate too short for this n
        }
        used += 1;
        // smoothing: a zero match would send log to -inf; use a tiny floor.
        let p = if m == 0 {
            1.0 / (2.0 * total as f64)
        } else {
            m as f64 / total as f64
        };
        log_sum += p.ln();
    }
    if used == 0 {
        return 0.0;
    }
    let geo_mean = (log_sum / used as f64).exp();

    // brevity penalty
    let c = candidate.len() as f64;
    let r = reference.len() as f64;
    let bp = if c >= r { 1.0 } else { (1.0 - r / c).exp() };

    bp * geo_mean
}

/// ROUGE-N precision/recall/F1 between `candidate` and `reference`.
pub fn rouge_n(candidate: &[&str], reference: &[&str], n: usize) -> Score {
    let cand = ngram_counts(candidate, n);
    let refr = ngram_counts(reference, n);
    let cand_total: usize = cand.values().sum();
    let ref_total: usize = refr.values().sum();
    let mut overlap = 0usize;
    for (gram, &c) in &cand {
        overlap += c.min(refr.get(gram).copied().unwrap_or(0));
    }
    Score::from_counts(overlap, cand_total, ref_total)
}

/// Length of the longest common subsequence of two token slices.
fn lcs_len(a: &[&str], b: &[&str]) -> usize {
    if a.is_empty() || b.is_empty() {
        return 0;
    }
    let mut prev = vec![0usize; b.len() + 1];
    let mut cur = vec![0usize; b.len() + 1];
    for &ai in a {
        for j in 0..b.len() {
            cur[j + 1] = if ai == b[j] {
                prev[j] + 1
            } else {
                prev[j + 1].max(cur[j])
            };
        }
        std::mem::swap(&mut prev, &mut cur);
        cur.iter_mut().for_each(|x| *x = 0);
    }
    prev[b.len()]
}

/// ROUGE-L precision/recall/F1 based on the longest common subsequence.
pub fn rouge_l(candidate: &[&str], reference: &[&str]) -> Score {
    let lcs = lcs_len(candidate, reference);
    Score::from_counts(lcs, candidate.len(), reference.len())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn toks<'a>(words: &'a [&'a str]) -> Vec<&'a str> {
        words.to_vec()
    }

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn bleu_perfect_match_is_one() {
        let s = ["the", "cat", "sat", "on", "the", "mat"];
        let b = bleu(&toks(&s), &toks(&s), 4);
        assert!(approx(b, 1.0), "bleu {b}");
    }

    #[test]
    fn bleu_penalizes_no_overlap() {
        let refr = ["the", "cat", "sat", "down"];
        let none = ["completely", "different", "words", "here"];
        let partial = ["the", "cat", "ran", "off"]; // shares "the cat"
        let b_none = bleu(&none, &toks(&refr), 4);
        let b_partial = bleu(&partial, &toks(&refr), 4);
        let b_perfect = bleu(&toks(&refr), &toks(&refr), 4);
        // smoothed sentence-BLEU never hits 0 on short texts, but overlap must
        // order the scores: none < partial < perfect.
        assert!(b_none < b_partial, "none {b_none} partial {b_partial}");
        assert!(
            b_partial < b_perfect,
            "partial {b_partial} perfect {b_perfect}"
        );
    }

    #[test]
    fn bleu_brevity_penalty_applies() {
        // candidate is a correct but very short fragment of the reference
        let refr = [
            "the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog",
        ];
        let short = ["the", "quick"];
        let b_short = bleu(&toks(&short), &toks(&refr), 4);
        let b_full = bleu(&toks(&refr), &toks(&refr), 4);
        assert!(b_short < b_full, "short {b_short} full {b_full}");
        assert!(
            b_short < 0.5,
            "brevity penalty should hurt short: {b_short}"
        );
    }

    #[test]
    fn bleu_clips_repeated_ngrams() {
        // candidate repeats "the" many times; clipping caps the credit.
        let cand = ["the", "the", "the", "the"];
        let refr = ["the", "cat"];
        let b = bleu(&toks(&cand), &toks(&refr), 1);
        // unigram precision clipped: only 1 "the" counts of 4 → 0.25, BP=1 (len 4>=2)
        assert!(approx(b, 0.25), "bleu {b}");
    }

    #[test]
    fn rouge_n_unigram_and_bigram() {
        let cand = ["the", "cat", "was", "on", "the", "mat"];
        let refr = ["the", "cat", "sat", "on", "the", "mat"];
        let r1 = rouge_n(&toks(&cand), &toks(&refr), 1);
        // unigram overlap: the(2), cat(1), on(1), mat(1) = 5 of 6 → recall 5/6
        assert!(approx(r1.recall, 5.0 / 6.0), "recall {}", r1.recall);
        let r2 = rouge_n(&toks(&cand), &toks(&refr), 2);
        // bigram overlap is smaller (the cat, on the, the mat match)
        assert!(r2.f1 < r1.f1);
    }

    #[test]
    fn rouge_l_uses_subsequence() {
        // LCS rewards in-order overlap even with a gap
        let cand = ["a", "b", "c", "d", "e"];
        let refr = ["a", "x", "c", "y", "e"]; // LCS = a,c,e = 3
        let r = rouge_l(&toks(&cand), &toks(&refr));
        assert!(approx(r.precision, 3.0 / 5.0));
        assert!(approx(r.recall, 3.0 / 5.0));
    }

    #[test]
    fn rouge_l_perfect_and_disjoint() {
        let s = ["one", "two", "three"];
        let perfect = rouge_l(&toks(&s), &toks(&s));
        assert!(approx(perfect.f1, 1.0));
        let disjoint = rouge_l(&toks(&["a", "b"]), &toks(&["c", "d"]));
        assert!(approx(disjoint.f1, 0.0));
    }

    #[test]
    fn whitespace_tokenizer_lowercases() {
        let t = whitespace_tokens("The  Quick   BROWN fox");
        assert_eq!(t, vec!["the", "quick", "brown", "fox"]);
    }

    #[test]
    fn empty_inputs_are_safe() {
        assert_eq!(bleu(&[], &["a"], 4), 0.0);
        let z = rouge_n(&[], &["a"], 1);
        assert_eq!(z.f1, 0.0);
        assert_eq!(rouge_l(&[], &[]).f1, 0.0);
    }

    #[test]
    fn score_serde_round_trip() {
        let s = rouge_l(&toks(&["a", "b", "c"]), &toks(&["a", "c"]));
        let j = serde_json::to_string(&s).unwrap();
        let back: Score = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
