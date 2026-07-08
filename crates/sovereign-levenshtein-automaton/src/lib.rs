//! `sovereign-levenshtein-automaton` — recognize everything close to a pattern.
//!
//! Fuzzy search asks: of these thousands of terms, which are within `k` typos of
//! my query? Running an edit-distance DP against every candidate is correct but
//! pays the full table cost per term. The fast route, used by search engines like
//! Lucene/Tantivy, is a **Levenshtein automaton**: a machine that accepts exactly
//! the strings within edit distance `k` of a fixed pattern, so testing a candidate
//! is just feeding its characters through the automaton, and — crucially — it can
//! be driven down a shared trie of the dictionary, pruning an entire subtree the
//! instant no match can still be reached.
//!
//! This implements the nondeterministic Levenshtein automaton by simulating it
//! directly over a set of **positions** `(i, e)` — "matched `i` pattern characters
//! using `e` edits so far". Reading an input character `c` advances the set by the
//! three edit operations — a match or substitution consumes a pattern character, an
//! insertion consumes only the input — and an epsilon closure applies deletions
//! (skip a pattern character for one edit). A position with `i = pattern length` is
//! accepting. The position count is bounded by `pattern_len · (k+1)`, so each step
//! is cheap and independent of how many candidates are tested.
//!
//! [`LevenshteinAutomaton::accepts`] tests a whole candidate;
//! [`LevenshteinAutomaton::distance`] returns the actual edit distance when it is
//! `≤ k`. For trie/dictionary traversal, [`LevenshteinAutomaton::start`] and
//! [`LevenshteinAutomaton::step`] walk a [`State`] character by character, with
//! [`State::can_match`] for pruning and [`State::is_match`] / [`State::distance`]
//! to read off matches. [`LevenshteinAutomaton::fuzzy_filter`] is a convenience
//! over a candidate list.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the Levenshtein-automaton surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A Levenshtein automaton for a fixed pattern and maximum edit distance.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LevenshteinAutomaton {
    pattern: Vec<char>,
    max_edits: usize,
}

/// A live simulation state: the set of reachable `(pattern_index, edits)` positions.
/// Positions are kept sorted and deduplicated.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct State {
    /// `(i, e)` = matched `i` pattern chars using `e` edits. Sorted ascending.
    positions: Vec<(usize, usize)>,
    /// Pattern length and edit cap, carried so [`State`] queries are self-contained.
    pattern_len: usize,
    max_edits: usize,
}

impl State {
    /// Whether this state contains an accepting position (whole pattern matched
    /// within the edit budget) — i.e. the input read so far is a match.
    pub fn is_match(&self) -> bool {
        self.positions.iter().any(|&(i, _)| i == self.pattern_len)
    }

    /// The smallest edit count among accepting positions, if any.
    pub fn distance(&self) -> Option<usize> {
        self.positions
            .iter()
            .filter(|&&(i, _)| i == self.pattern_len)
            .map(|&(_, e)| e)
            .min()
    }

    /// Whether any match is still reachable from here. If false, a dictionary
    /// traversal can prune this branch entirely.
    pub fn can_match(&self) -> bool {
        !self.positions.is_empty()
    }
}

impl LevenshteinAutomaton {
    /// An automaton accepting all strings within `max_edits` of `pattern`.
    pub fn new(pattern: &str, max_edits: usize) -> Self {
        Self {
            pattern: pattern.chars().collect(),
            max_edits,
        }
    }

    /// The pattern length in characters.
    pub fn pattern_len(&self) -> usize {
        self.pattern.len()
    }
    /// The configured maximum edit distance.
    pub fn max_edits(&self) -> usize {
        self.max_edits
    }

    /// Add a position if not already present (keeps the vec sorted/deduped).
    fn insert(positions: &mut Vec<(usize, usize)>, p: (usize, usize)) {
        if let Err(idx) = positions.binary_search(&p) {
            positions.insert(idx, p);
        }
    }

    /// Apply deletions: from `(i, e)` with `e < k` reach `(i+1, e+1)`, repeatedly.
    fn epsilon_closure(&self, positions: &mut Vec<(usize, usize)>) {
        let mut i = 0;
        while i < positions.len() {
            let (pi, pe) = positions[i];
            if pi < self.pattern.len() && pe < self.max_edits {
                Self::insert(positions, (pi + 1, pe + 1));
            }
            i += 1;
        }
    }

    /// The initial state before any input is read.
    pub fn start(&self) -> State {
        let mut positions = vec![(0usize, 0usize)];
        self.epsilon_closure(&mut positions);
        State {
            positions,
            pattern_len: self.pattern.len(),
            max_edits: self.max_edits,
        }
    }

    /// Advance `state` by reading input character `c`.
    pub fn step(&self, state: &State, c: char) -> State {
        let mut next: Vec<(usize, usize)> = Vec::new();
        for &(i, e) in &state.positions {
            // match: consume input and pattern char with no edit.
            if i < self.pattern.len() && self.pattern[i] == c {
                Self::insert(&mut next, (i + 1, e));
            }
            if e < self.max_edits {
                // substitution: consume input and pattern char, +1 edit.
                if i < self.pattern.len() {
                    Self::insert(&mut next, (i + 1, e + 1));
                }
                // insertion: consume input only (extra char), +1 edit.
                Self::insert(&mut next, (i, e + 1));
            }
        }
        // deletions (skip pattern chars) close the set.
        self.epsilon_closure(&mut next);
        State {
            positions: next,
            pattern_len: self.pattern.len(),
            max_edits: self.max_edits,
        }
    }

    /// Whether `candidate` is within `max_edits` of the pattern.
    pub fn accepts(&self, candidate: &str) -> bool {
        let mut state = self.start();
        for c in candidate.chars() {
            state = self.step(&state, c);
            if !state.can_match() {
                return false;
            }
        }
        state.is_match()
    }

    /// The edit distance to `candidate` if it is `≤ max_edits`, else `None`.
    pub fn distance(&self, candidate: &str) -> Option<usize> {
        let mut state = self.start();
        for c in candidate.chars() {
            state = self.step(&state, c);
            if !state.can_match() {
                return None;
            }
        }
        state.distance()
    }

    /// Keep the candidates within `max_edits`, each paired with its distance,
    /// sorted by distance then input order.
    pub fn fuzzy_filter<'a>(&self, candidates: &[&'a str]) -> Vec<(&'a str, usize)> {
        let mut out: Vec<(&'a str, usize)> = candidates
            .iter()
            .filter_map(|&c| self.distance(c).map(|d| (c, d)))
            .collect();
        out.sort_by(|a, b| a.1.cmp(&b.1));
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Reference edit distance by the standard DP, for cross-checking.
    fn dp_distance(a: &str, b: &str) -> usize {
        let a: Vec<char> = a.chars().collect();
        let b: Vec<char> = b.chars().collect();
        let mut prev: Vec<usize> = (0..=b.len()).collect();
        for (i, &ca) in a.iter().enumerate() {
            let mut cur = vec![i + 1; b.len() + 1];
            for (j, &cb) in b.iter().enumerate() {
                let cost = usize::from(ca != cb);
                cur[j + 1] = (prev[j] + cost).min(prev[j + 1] + 1).min(cur[j] + 1);
            }
            prev = cur;
        }
        prev[b.len()]
    }

    #[test]
    fn accepts_exact_match() {
        let a = LevenshteinAutomaton::new("hello", 0);
        assert!(a.accepts("hello"));
        assert!(!a.accepts("hell"));
        assert!(!a.accepts("hallo"));
    }

    #[test]
    fn accepts_within_one_edit() {
        let a = LevenshteinAutomaton::new("hello", 1);
        assert!(a.accepts("hello")); // 0
        assert!(a.accepts("hallo")); // substitution
        assert!(a.accepts("hell")); // deletion
        assert!(a.accepts("helllo")); // insertion
        assert!(a.accepts("ello")); // deletion at front
        assert!(!a.accepts("hallo2")); // 2 edits
        assert!(!a.accepts("world"));
    }

    #[test]
    fn distance_reports_actual() {
        let a = LevenshteinAutomaton::new("kitten", 3);
        // classic: kitten -> sitting is distance 3.
        assert_eq!(a.distance("sitting"), Some(3));
        assert_eq!(a.distance("kitten"), Some(0));
        assert_eq!(a.distance("kittens"), Some(1));
    }

    #[test]
    fn distance_none_beyond_budget() {
        let a = LevenshteinAutomaton::new("kitten", 2);
        assert_eq!(a.distance("sitting"), None); // distance 3 > 2
    }

    #[test]
    fn matches_dp_on_many_pairs() {
        let words = [
            "cat", "cart", "card", "dog", "do", "category", "kitten", "sitting", "", "a", "ab",
            "abc", "abcd", "banana", "bananas", "ananab",
        ];
        for k in 0..=4 {
            for &p in &words {
                let auto = LevenshteinAutomaton::new(p, k);
                for &c in &words {
                    let dp = dp_distance(p, c);
                    let expected_accept = dp <= k;
                    assert_eq!(
                        auto.accepts(c),
                        expected_accept,
                        "pattern={p:?} cand={c:?} k={k} dp={dp}"
                    );
                    if dp <= k {
                        assert_eq!(auto.distance(c), Some(dp), "p={p:?} c={c:?} k={k}");
                    } else {
                        assert_eq!(auto.distance(c), None);
                    }
                }
            }
        }
    }

    #[test]
    fn empty_pattern() {
        let a = LevenshteinAutomaton::new("", 2);
        assert!(a.accepts("")); // 0
        assert!(a.accepts("ab")); // 2 insertions
        assert!(!a.accepts("abc")); // 3 insertions > 2
    }

    #[test]
    fn incremental_step_prunes() {
        // walking a candidate that diverges early should become un-matchable.
        let a = LevenshteinAutomaton::new("apple", 1);
        let mut s = a.start();
        for c in "xyz".chars() {
            s = a.step(&s, c);
        }
        // "xyz" is already > 1 edit from any prefix of "apple".
        assert!(!s.can_match());
    }

    #[test]
    fn step_matches_accepts() {
        let a = LevenshteinAutomaton::new("graph", 2);
        for cand in ["graph", "grph", "graph", "graff", "gra"] {
            let mut s = a.start();
            let mut alive = true;
            for c in cand.chars() {
                s = a.step(&s, c);
                if !s.can_match() {
                    alive = false;
                    break;
                }
            }
            let via_step = alive && s.is_match();
            assert_eq!(via_step, a.accepts(cand), "cand {cand}");
        }
    }

    #[test]
    fn fuzzy_filter_sorts_by_distance() {
        let a = LevenshteinAutomaton::new("color", 2);
        let dict = ["color", "colour", "colon", "dolor", "valor", "flavor"];
        let got = a.fuzzy_filter(&dict);
        // color(0), colon(1)/dolor(1)/colour(1), valor(2)... flavor is >2 (excluded).
        assert_eq!(got[0], ("color", 0));
        assert!(got.iter().all(|&(_, d)| d <= 2));
        assert!(!got.iter().any(|&(w, _)| w == "flavor"));
        // distances are non-decreasing.
        for w in got.windows(2) {
            assert!(w[0].1 <= w[1].1);
        }
    }

    #[test]
    fn unicode_pattern() {
        let a = LevenshteinAutomaton::new("café", 1);
        assert!(a.accepts("café"));
        assert!(a.accepts("cafe")); // é -> e substitution
        assert!(a.accepts("cafés")); // insertion
        assert!(!a.accepts("coffee"));
    }

    #[test]
    fn state_position_bound() {
        // the position set never exceeds pattern_len*(k+1)+ a few.
        let a = LevenshteinAutomaton::new("abcdefgh", 3);
        let mut s = a.start();
        let bound = (a.pattern_len() + 1) * (a.max_edits() + 1);
        assert!(s.positions.len() <= bound);
        for c in "abXdefYh".chars() {
            s = a.step(&s, c);
            assert!(s.positions.len() <= bound, "len {}", s.positions.len());
        }
    }

    #[test]
    fn serde_round_trip() {
        let a = LevenshteinAutomaton::new("router", 2);
        let j = serde_json::to_string(&a).unwrap();
        let back: LevenshteinAutomaton = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
        assert!(back.accepts("route"));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
