//! `sovereign-toxicity` — a content-safety gate that resists obfuscation.
//!
//! Filtering toxic or profane content is a different job from spotting prompt
//! injections, PII, or secrets: it is a *term-list* problem, and the hard part is
//! that people obfuscate — `f4ck`, `$h1t`, `a-s-s` — to slip past a naive list.
//! This crate normalizes the text first (lowercasing, mapping common leetspeak
//! substitutions like `4→a`, `3→e`, `0→o`, `@→a`, `$→s`, and stripping the
//! separators inserted between letters), *then* matches a **severity-tiered** term
//! list in one [`sovereign_aho_corasick`] pass.
//!
//! A [`ToxicityFilter`] holds terms tagged [`Severity::Mild`], [`Severity::Strong`],
//! or [`Severity::Severe`]; you can use the small built-in starter list or supply
//! your own. [`scan`] returns the matched terms and severities, [`score`] a
//! `[0, 1]` toxicity score weighted by severity, and [`is_toxic`] a thresholded
//! verdict. It catches the obvious cases; it is a gate to layer, not a complete
//! moderation system, and a determined adversary can still phrase around it.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_aho_corasick::AhoCorasick;

/// Schema version of the toxicity surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// How serious a flagged term is.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Severity {
    /// Mild profanity / rudeness.
    Mild,
    /// Strong profanity.
    Strong,
    /// Severe (slurs, extreme content).
    Severe,
}

impl Severity {
    /// The weight this severity contributes to the score.
    pub fn weight(self) -> f64 {
        match self {
            Severity::Mild => 0.3,
            Severity::Strong => 0.6,
            Severity::Severe => 1.0,
        }
    }
}

/// A flagged term occurrence.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Flag {
    /// The (normalized) term that matched.
    pub term: String,
    /// Its severity.
    pub severity: Severity,
}

/// A toxicity filter over a severity-tagged term list.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToxicityFilter {
    terms: Vec<(String, Severity)>,
    #[serde(skip)]
    automaton: Option<AhoCorasick>,
}

impl PartialEq for ToxicityFilter {
    fn eq(&self, other: &Self) -> bool {
        self.terms == other.terms
    }
}

impl Default for ToxicityFilter {
    fn default() -> Self {
        Self::with_builtin()
    }
}

impl ToxicityFilter {
    /// An empty filter (no terms).
    pub fn new() -> Self {
        Self {
            terms: Vec::new(),
            automaton: None,
        }
    }

    /// A filter seeded with a small built-in starter list. The list is
    /// intentionally compact and family-friendly-ish placeholders plus a few real
    /// mild words — extend it with [`add_term`](Self::add_term) for your policy.
    pub fn with_builtin() -> Self {
        let mut f = Self::new();
        // mild
        for t in ["damn", "hell", "crap"] {
            f.add_term(t, Severity::Mild);
        }
        // strong (kept tame in source; real deployments add their own)
        for t in ["bastard", "asshole"] {
            f.add_term(t, Severity::Strong);
        }
        // severe placeholder category (callers add jurisdiction-specific terms)
        f.add_term("slur1", Severity::Severe);
        f.build();
        f
    }

    /// Add a term (case/obfuscation-insensitive) at a severity. Call [`build`] (or
    /// any scan, which builds lazily) afterward.
    pub fn add_term(&mut self, term: &str, severity: Severity) {
        self.terms.push((normalize(term), severity));
        self.automaton = None; // invalidate
    }

    /// Number of terms.
    pub fn len(&self) -> usize {
        self.terms.len()
    }

    /// Whether the filter has no terms.
    pub fn is_empty(&self) -> bool {
        self.terms.is_empty()
    }

    /// Build the matching automaton (called lazily by scans).
    pub fn build(&mut self) {
        let patterns: Vec<&str> = self.terms.iter().map(|(t, _)| t.as_str()).collect();
        self.automaton = Some(AhoCorasick::new(patterns));
    }

    fn ensure_built(&self) -> AhoCorasick {
        // Build on demand if not present (scan takes &self for ergonomics).
        match &self.automaton {
            Some(a) => a.clone(),
            None => {
                let patterns: Vec<&str> = self.terms.iter().map(|(t, _)| t.as_str()).collect();
                AhoCorasick::new(patterns)
            }
        }
    }

    /// Flag every term occurrence in `text` (after normalization), de-duplicated by
    /// term, sorted by descending severity then term.
    pub fn scan(&self, text: &str) -> Vec<Flag> {
        if self.terms.is_empty() {
            return Vec::new();
        }
        let normalized = normalize(text);
        let ac = self.ensure_built();
        let mut seen = std::collections::BTreeMap::new();
        for m in ac.matched_patterns(normalized.as_bytes()) {
            let (term, sev) = &self.terms[m];
            seen.insert(term.clone(), *sev);
        }
        let mut flags: Vec<Flag> = seen
            .into_iter()
            .map(|(term, severity)| Flag { term, severity })
            .collect();
        flags.sort_by(|a, b| b.severity.cmp(&a.severity).then(a.term.cmp(&b.term)));
        flags
    }

    /// A toxicity score in `[0, 1]`: the maximum severity weight among matches
    /// (so one severe term scores high regardless of how many mild ones there are).
    /// `0.0` when nothing matches.
    pub fn score(&self, text: &str) -> f64 {
        self.scan(text)
            .iter()
            .map(|f| f.severity.weight())
            .fold(0.0, f64::max)
    }

    /// Whether `text` is toxic at or above `threshold` (a score in `[0, 1]`).
    pub fn is_toxic(&self, text: &str, threshold: f64) -> bool {
        self.score(text) >= threshold
    }

    /// Whether `text` contains any flagged term.
    pub fn contains_toxicity(&self, text: &str) -> bool {
        !self.scan(text).is_empty()
    }
}

/// Normalize text for obfuscation-resistant matching: lowercase, map common
/// leetspeak digits/symbols to letters, and drop characters commonly inserted
/// between letters to evade filters (spaces, dots, hyphens, asterisks,
/// underscores).
fn normalize(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars().flat_map(|c| c.to_lowercase()) {
        let mapped = match c {
            '4' | '@' => Some('a'),
            '3' => Some('e'),
            '0' => Some('o'),
            '1' => Some('i'),
            '$' | '5' => Some('s'),
            '7' => Some('t'),
            ' ' | '.' | '-' | '*' | '_' | ',' | '|' => None, // separators dropped
            other if other.is_alphanumeric() => Some(other),
            _ => None,
        };
        if let Some(ch) = mapped {
            out.push(ch);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn filter() -> ToxicityFilter {
        let mut f = ToxicityFilter::new();
        f.add_term("damn", Severity::Mild);
        f.add_term("bastard", Severity::Strong);
        f.add_term("slur", Severity::Severe);
        f.build();
        f
    }

    #[test]
    fn detects_plain_term() {
        let f = filter();
        let flags = f.scan("oh damn that hurt");
        assert_eq!(flags.len(), 1);
        assert_eq!(flags[0].term, "damn");
        assert_eq!(flags[0].severity, Severity::Mild);
    }

    #[test]
    fn resists_leetspeak_obfuscation() {
        let f = filter();
        // "d4mn" → normalizes to "damn"
        assert!(f.contains_toxicity("what the d4mn"));
        // "b@st4rd" → "bastard"
        assert!(f.contains_toxicity("you b@st4rd"));
    }

    #[test]
    fn resists_separator_insertion() {
        let f = filter();
        // "d.a.m.n" and "d a m n" → "damn"
        assert!(f.contains_toxicity("d.a.m.n it"));
        assert!(f.contains_toxicity("s l u r"));
    }

    #[test]
    fn score_uses_max_severity() {
        let f = filter();
        // a mild and a severe term → score is the severe weight (1.0)
        let s = f.score("damn slur");
        assert!((s - 1.0).abs() < 1e-9, "score {s}");
        // only mild → 0.3
        assert!((f.score("just a damn") - 0.3).abs() < 1e-9);
        // clean → 0
        assert_eq!(f.score("a perfectly nice sentence"), 0.0);
    }

    #[test]
    fn is_toxic_threshold() {
        let f = filter();
        assert!(f.is_toxic("you bastard", 0.5)); // strong = 0.6 >= 0.5
        assert!(!f.is_toxic("oh damn", 0.5)); // mild = 0.3 < 0.5
    }

    #[test]
    fn flags_sorted_by_severity() {
        let f = filter();
        let flags = f.scan("damn bastard slur");
        // severe first, then strong, then mild
        assert_eq!(flags[0].severity, Severity::Severe);
        assert_eq!(flags[2].severity, Severity::Mild);
    }

    #[test]
    fn clean_text_is_clean() {
        let f = filter();
        assert!(!f.contains_toxicity("the weather is lovely today"));
        assert!(f.scan("hello world").is_empty());
    }

    #[test]
    fn builtin_filter_works() {
        let f = ToxicityFilter::with_builtin();
        assert!(!f.is_empty());
        assert!(f.contains_toxicity("oh hell no"));
    }

    #[test]
    fn empty_filter_flags_nothing() {
        let f = ToxicityFilter::new();
        assert!(f.scan("damn slur bastard").is_empty());
        assert_eq!(f.score("anything"), 0.0);
    }

    #[test]
    fn serde_round_trip() {
        let f = filter();
        let j = serde_json::to_string(&f).unwrap();
        let back: ToxicityFilter = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
        // automaton rebuilt lazily on the deserialized filter
        assert!(back.contains_toxicity("d4mn"));
    }
}
