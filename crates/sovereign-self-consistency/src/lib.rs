//! `sovereign-self-consistency` — majority-vote decoding for reliability.
//!
//! A single sampled answer can be a fluke; *self-consistency* trades compute
//! for reliability by drawing several answers (each with a different seed),
//! normalizing them, and returning the one the samples agree on most. On
//! reasoning tasks the majority answer is markedly more reliable than any
//! single draw — and the agreement fraction is a free confidence signal.
//!
//! This crate is generic over an answer *generator* — a closure mapping a seed
//! to an answer — so it wraps the real runtime in production or a scripted
//! generator in tests. Normalization (trim + lowercase) decides which answers
//! count as "the same"; the returned answer keeps the original surface form of
//! the winning group's first occurrence.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version of the self-consistency surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong.
#[derive(Debug, Error, PartialEq)]
pub enum ConsistencyError {
    /// `samples` was zero.
    #[error("samples must be >= 1")]
    ZeroSamples,
    /// Every generation failed, so there is nothing to vote on.
    #[error("all {0} generations failed; last error: {1}")]
    AllFailed(usize, String),
}

/// The outcome of a self-consistency vote.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Vote {
    /// The winning answer (original surface form of its first occurrence).
    pub answer: String,
    /// How many samples agreed with the winner (after normalization).
    pub count: usize,
    /// How many samples were collected (successful generations).
    pub total: usize,
    /// `count / total` — the agreement fraction in `[0, 1]`.
    pub agreement: f64,
}

/// A self-consistency decoder: draw `samples` answers and take the majority.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct SelfConsistency {
    /// Number of answers to draw.
    pub samples: usize,
}

impl SelfConsistency {
    /// A decoder that draws `samples` answers per query.
    pub fn new(samples: usize) -> Self {
        Self { samples }
    }

    /// Draw answers with `generate` (called with `base_seed + i` for each of
    /// the `samples` draws), normalize, and return the majority vote.
    ///
    /// Failed generations are skipped; if *all* fail, an error is returned.
    /// Ties are broken toward the lexicographically smallest normalized answer
    /// for determinism.
    pub fn run<F>(&self, base_seed: u64, mut generate: F) -> Result<Vote, ConsistencyError>
    where
        F: FnMut(u64) -> Result<String, String>,
    {
        if self.samples == 0 {
            return Err(ConsistencyError::ZeroSamples);
        }

        // normalized form → (count, first original form)
        let mut groups: HashMap<String, (usize, String)> = HashMap::new();
        let mut total = 0usize;
        let mut last_err = String::new();

        for i in 0..self.samples {
            match generate(base_seed + i as u64) {
                Ok(answer) => {
                    total += 1;
                    let norm = normalize(&answer);
                    let entry = groups.entry(norm).or_insert((0, answer));
                    entry.0 += 1;
                }
                Err(e) => last_err = e,
            }
        }

        if total == 0 {
            return Err(ConsistencyError::AllFailed(self.samples, last_err));
        }

        // pick max count; tie → smallest normalized key
        let (_, count, answer) = groups
            .iter()
            .map(|(norm, (count, original))| (norm.clone(), *count, original.clone()))
            .max_by(|a, b| a.1.cmp(&b.1).then_with(|| b.0.cmp(&a.0)))
            .expect("non-empty");

        Ok(Vote {
            answer,
            count,
            total,
            agreement: count as f64 / total as f64,
        })
    }
}

/// Normalize an answer for equality: trim, lowercase, collapse inner runs of
/// whitespace to a single space.
fn normalize(s: &str) -> String {
    s.split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A generator replaying a fixed list (indexed by seed - base).
    fn scripted(answers: Vec<&str>) -> impl FnMut(u64) -> Result<String, String> {
        let answers: Vec<String> = answers.into_iter().map(String::from).collect();
        let base = 100u64;
        move |seed| {
            answers
                .get((seed - base) as usize)
                .cloned()
                .ok_or_else(|| "out of range".to_string())
        }
    }

    #[test]
    fn zero_samples_errors() {
        let sc = SelfConsistency::new(0);
        assert_eq!(
            sc.run(0, |_| Ok("x".to_string())).unwrap_err(),
            ConsistencyError::ZeroSamples
        );
    }

    #[test]
    fn picks_the_majority_answer() {
        let sc = SelfConsistency::new(5);
        let v = sc
            .run(100, scripted(vec!["42", "42", "7", "42", "7"]))
            .unwrap();
        assert_eq!(v.answer, "42");
        assert_eq!(v.count, 3);
        assert_eq!(v.total, 5);
        assert!((v.agreement - 0.6).abs() < 1e-9);
    }

    #[test]
    fn normalization_groups_equivalent_answers() {
        // "Paris", "paris", " PARIS " all count together
        let sc = SelfConsistency::new(3);
        let v = sc
            .run(100, scripted(vec!["Paris", "paris", " PARIS "]))
            .unwrap();
        assert_eq!(v.count, 3);
        assert!(["Paris", "paris", " PARIS "].contains(&v.answer.as_str()));
    }

    #[test]
    fn ties_break_lexicographically() {
        // "a" and "b" each twice → tie → smallest normalized ("a") wins
        let sc = SelfConsistency::new(4);
        let v = sc.run(100, scripted(vec!["a", "b", "a", "b"])).unwrap();
        assert_eq!(v.answer, "a");
        assert_eq!(v.count, 2);
    }

    #[test]
    fn failed_generations_are_skipped() {
        let sc = SelfConsistency::new(4);
        let v = sc
            .run(0, |seed| {
                if seed % 2 == 0 {
                    Ok("ok".to_string())
                } else {
                    Err("boom".to_string())
                }
            })
            .unwrap();
        assert_eq!(v.answer, "ok");
        assert_eq!(v.total, 2); // only the even seeds succeeded
    }

    #[test]
    fn all_failed_is_an_error() {
        let sc = SelfConsistency::new(3);
        let err = sc.run(0, |_| Err("nope".to_string())).unwrap_err();
        assert_eq!(err, ConsistencyError::AllFailed(3, "nope".to_string()));
    }

    #[test]
    fn distinct_seeds_are_used() {
        let sc = SelfConsistency::new(3);
        let mut seeds = Vec::new();
        let _ = sc.run(50, |seed| {
            seeds.push(seed);
            Ok("x".to_string())
        });
        assert_eq!(seeds, vec![50, 51, 52]);
    }

    #[test]
    fn unanimous_has_full_agreement() {
        let sc = SelfConsistency::new(3);
        let v = sc.run(100, scripted(vec!["yes", "yes", "yes"])).unwrap();
        assert_eq!(v.agreement, 1.0);
    }

    #[test]
    fn serde_round_trip() {
        let sc = SelfConsistency::new(5);
        let j = serde_json::to_string(&sc).unwrap();
        let back: SelfConsistency = serde_json::from_str(&j).unwrap();
        assert_eq!(sc, back);
    }
}
