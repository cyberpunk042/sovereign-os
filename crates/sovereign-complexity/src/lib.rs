//! `sovereign-complexity` — estimate request difficulty for routing.
//!
//! The sovereign runtime's premise is *complexity-routed*, `$0`-target
//! inference: a trivial request ("hi", "what time is it") should never wake the
//! big expensive model, while a hard one ("prove this, step by step, then
//! refactor the code") should. The router needs a cheap, deterministic signal
//! of how hard a request is *before* running it. This crate is that estimator.
//!
//! It scores a prompt from five interpretable signals — length, lexical
//! diversity, reasoning markers ("why", "explain", "step by step"), technical
//! markers (code fences, symbols, definitions), and question count — combines
//! them into a `[0, 1]` score, and maps that to a [`Tier`]. The heuristics are
//! deliberately transparent and dependency-free, so the routing decision is
//! explainable and reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Schema version of the complexity surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phrases that signal multi-step reasoning.
const REASONING_MARKERS: &[&str] = &[
    "why",
    "how",
    "explain",
    "prove",
    "analyze",
    "compare",
    "step by step",
    "reason",
    "derive",
    "because",
    "therefore",
    "evaluate",
    "design",
];

/// A request-complexity tier, cheapest first.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Tier {
    /// Greetings, acknowledgements — the cheapest path.
    Trivial,
    /// Short, direct questions.
    Simple,
    /// Multi-sentence or lightly technical requests.
    Moderate,
    /// Long, reasoning-heavy, or technical requests — the expensive path.
    Complex,
}

/// The breakdown of a complexity estimate.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Complexity {
    /// Word count.
    pub words: usize,
    /// Distinct words ÷ total words (0 for empty).
    pub lexical_diversity: f64,
    /// Number of reasoning-marker hits.
    pub reasoning_hits: usize,
    /// Number of technical-marker hits.
    pub technical_hits: usize,
    /// Number of `?` characters.
    pub question_count: usize,
    /// Aggregate score in `[0, 1]`.
    pub score: f64,
}

impl Complexity {
    /// The routing tier implied by the score.
    pub fn tier(&self) -> Tier {
        match self.score {
            s if s < 0.20 => Tier::Trivial,
            s if s < 0.45 => Tier::Simple,
            s if s < 0.70 => Tier::Moderate,
            _ => Tier::Complex,
        }
    }
}

/// Estimate the complexity of `text`.
pub fn estimate(text: &str) -> Complexity {
    let lower = text.to_lowercase();
    let words: Vec<&str> = lower
        .split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .collect();
    let n = words.len();

    let unique: HashSet<&str> = words.iter().copied().collect();
    let lexical_diversity = if n == 0 {
        0.0
    } else {
        unique.len() as f64 / n as f64
    };

    let reasoning_hits = REASONING_MARKERS
        .iter()
        .filter(|m| lower.contains(*m))
        .count();

    let technical_hits = count_technical(text);
    let question_count = text.matches('?').count();

    // interpretable, saturating factors in [0, 1]
    let length_f = (n as f64 / 50.0).min(1.0);
    let reasoning_f = (reasoning_hits as f64 / 3.0).min(1.0);
    let technical_f = (technical_hits as f64 / 3.0).min(1.0);
    let question_f = (question_count as f64 / 2.0).min(1.0);

    let score = 0.25 * length_f + 0.40 * reasoning_f + 0.25 * technical_f + 0.10 * question_f;

    Complexity {
        words: n,
        lexical_diversity,
        reasoning_hits,
        technical_hits,
        question_count,
        score: score.clamp(0.0, 1.0),
    }
}

/// Count technical markers: code fences, common code keywords, and dense
/// symbol/operator usage.
fn count_technical(text: &str) -> usize {
    let mut hits = 0;
    if text.contains("```") {
        hits += 2; // a code block is a strong signal
    }
    for kw in [
        "function", "def ", "fn ", "class ", "import ", "select ", "{", "}", "=>", "->",
    ] {
        if text.contains(kw) {
            hits += 1;
        }
    }
    // a high density of operator/symbol characters suggests math/code
    let symbols = text
        .chars()
        .filter(|c| "+-*/=<>(){}[]^%".contains(*c))
        .count();
    if !text.is_empty() && symbols * 10 >= text.len() {
        hits += 1;
    }
    hits
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn greeting_is_trivial() {
        let c = estimate("hi there");
        assert_eq!(c.tier(), Tier::Trivial);
        assert!(c.score < 0.2);
    }

    #[test]
    fn short_question_is_simple_or_trivial() {
        let c = estimate("what is the capital of France?");
        assert!(matches!(c.tier(), Tier::Trivial | Tier::Simple));
        assert_eq!(c.question_count, 1);
    }

    #[test]
    fn reasoning_prompt_scores_higher() {
        let simple = estimate("list three colors");
        let reasoning =
            estimate("explain step by step why the sky is blue and analyze the physics");
        assert!(reasoning.score > simple.score);
        assert!(reasoning.reasoning_hits >= 2);
        assert!(matches!(reasoning.tier(), Tier::Moderate | Tier::Complex));
    }

    #[test]
    fn technical_markers_are_detected() {
        let c = estimate("refactor this:\n```rust\nfn main() { let x = 1 + 2; }\n```");
        assert!(c.technical_hits >= 2, "hits {}", c.technical_hits);
        assert!(c.score > estimate("refactor this please").score);
    }

    #[test]
    fn long_complex_request_is_complex() {
        let text = "Design and prove correct a step-by-step algorithm, then explain why it \
                    works, analyze its complexity, compare alternatives, and derive the \
                    recurrence. Provide code: ```fn solve() {}``` and evaluate edge cases.";
        let c = estimate(text);
        assert_eq!(c.tier(), Tier::Complex, "score {}", c.score);
    }

    #[test]
    fn empty_text_is_trivial() {
        let c = estimate("");
        assert_eq!(c.words, 0);
        assert_eq!(c.lexical_diversity, 0.0);
        assert_eq!(c.tier(), Tier::Trivial);
    }

    #[test]
    fn score_is_bounded() {
        let c = estimate(&"prove explain why analyze ".repeat(100));
        assert!((0.0..=1.0).contains(&c.score));
    }

    #[test]
    fn lexical_diversity_is_computed() {
        // "a a a" → 1 unique / 3 total
        let c = estimate("a a a");
        assert!((c.lexical_diversity - (1.0 / 3.0)).abs() < 1e-9);
    }

    #[test]
    fn tier_ordering_is_cost_ascending() {
        // sanity: more demanding prompts never route cheaper
        let trivial = estimate("ok").score;
        let complex = estimate(
            "explain step by step and prove why, then analyze and derive the code ```fn x(){}```",
        )
        .score;
        assert!(complex > trivial);
    }

    #[test]
    fn serde_round_trip() {
        let c = estimate("why is this complex? explain.");
        let j = serde_json::to_string(&c).unwrap();
        let back: Complexity = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
