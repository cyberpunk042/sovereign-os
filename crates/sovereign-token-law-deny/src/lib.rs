//! `sovereign-token-law-deny` — the **negative** token-law plane.
//!
//! Every constraint to date (grammar, regex, tool-name, schema) is a *positive*
//! allow-list: "the next token must keep some pattern reachable". Safety is the
//! opposite: "the output must **never contain** any of these substrings"
//! (prompt-injection markers, banned phrases). That is a *negative* constraint,
//! and — the crux SDD-503 deferred — a substring ban is **not a per-token
//! property**: a forbidden phrase can span token boundaries, so you cannot simply
//! ban the tokens that contain it.
//!
//! The correct realization is an incremental matcher. This crate compiles the
//! denied substrings into an [`AhoCorasick`] automaton and, from the committed
//! generation's scan state, asks of every candidate token: *would appending its
//! bytes complete a banned match?* If yes, the token is banned; otherwise it is
//! safe. [`DenyConstraint::safe_token_ids`] returns the allow-list — all tokens
//! minus the completers — the same `Vec<usize>` shape
//! `sovereign-token-law-mask`'s `TokenLawPlanes` and `sovereign-regex-constrain`
//! use, so a safety plane composes with grammar / regex / policy planes through
//! the M00117 `token_law_combine` (SDD-501/503).
//!
//! **The guarantee.** Starting from clean text and applying the plane every step,
//! the output can never contain a denied substring: the only way one could appear
//! is at the byte that completes it, and that token is banned at that step. It is
//! an exact, per-step guarantee — not a post-hoc scanner (SDD-504).
//!
//! **Honest scope.** This covers denylists that are literal substrings
//! (`sovereign-injection-detect::PATTERNS`, a toxicity term-list). It does *not*
//! cover structural detectors — entropy-based secret scanning or checksum-based
//! PII (Luhn, SSN shapes) — because "the token that completes a high-entropy
//! secret" is not well-defined; those stay post-hoc scanners, not planes.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub use sovereign_aho_corasick::AcState;
use sovereign_aho_corasick::AhoCorasick;

/// Schema version of the token-law-deny surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A negative (denylist) constraint over a set of forbidden substrings.
#[derive(Debug, Clone)]
pub struct DenyConstraint {
    ac: AhoCorasick,
}

impl DenyConstraint {
    /// Compile the denied substrings into the matcher. Empty patterns are ignored
    /// (they would match everywhere); duplicates are harmless.
    pub fn new<I, P>(patterns: I) -> Self
    where
        I: IntoIterator<Item = P>,
        P: AsRef<[u8]>,
    {
        Self {
            ac: AhoCorasick::new(patterns),
        }
    }

    /// The number of denied patterns.
    pub fn pattern_count(&self) -> usize {
        self.ac.pattern_count()
    }

    /// Whether `text` already contains a denied substring (a post-hoc scan —
    /// useful for asserting the plane's guarantee held).
    pub fn is_denied(&self, text: &str) -> bool {
        self.ac.is_match_str(text)
    }

    /// The ids of tokens that are **safe** to append after `generated` — i.e.
    /// appending the token's bytes does not complete any denied substring.
    /// `vocab[i]` is the surface string of token id `i`. Mirrors
    /// `sovereign_regex_constrain::RegexConstraint::allowed_token_ids`: the
    /// returned `Vec<usize>` is the allow-list a token-law plane consumes.
    ///
    /// Cost is one automaton walk over `generated` (to reach the committed state)
    /// plus, per token, a walk over its bytes — proportional to the token, not the
    /// whole vocabulary's history.
    pub fn safe_token_ids(&self, generated: &str, vocab: &[&str]) -> Vec<usize> {
        // Walk to the committed scan state for the text generated so far, then
        // probe each candidate from there (the incremental primitives below).
        let base = self.advance_state(self.start_state(), generated);
        self.safe_token_ids_from(base, vocab)
    }

    /// The initial scan state (before any committed text) — the entry point for
    /// the **incremental** API (SDD-514): keep this state across decode steps and
    /// [`advance_state`](Self::advance_state) it by only the newly-committed token,
    /// so the per-step cost is the token, NOT the whole prefix (removes the O(n²)
    /// re-walk `safe_token_ids` does).
    pub fn start_state(&self) -> AcState {
        self.ac.start()
    }

    /// Advance a committed scan `state` by `text`'s bytes.
    pub fn advance_state(&self, mut state: AcState, text: &str) -> AcState {
        for &b in text.as_bytes() {
            state = self.ac.advance(state, b);
        }
        state
    }

    /// The safe token ids from an already-committed `base` state — probes each
    /// candidate token from `base` without re-walking the prefix. Identical result
    /// to [`safe_token_ids`](Self::safe_token_ids) when `base` is the state reached
    /// by walking the same `generated`.
    pub fn safe_token_ids_from(&self, base: AcState, vocab: &[&str]) -> Vec<usize> {
        let mut safe = Vec::with_capacity(vocab.len());
        for (id, tok) in vocab.iter().enumerate() {
            let mut state = base;
            let mut completes = false;
            for &b in tok.as_bytes() {
                state = self.ac.advance(state, b);
                if self.ac.hits(state) {
                    completes = true;
                    break;
                }
            }
            if !completes {
                safe.push(id);
            }
        }
        safe
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vocab(words: &[&str]) -> Vec<String> {
        words.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn bans_the_token_that_completes_a_cross_token_ban() {
        // Forbidden "ab". After "a", the token "b" completes it → banned;
        // "a" and "c" are safe. The completion spans the token boundary — the
        // case a per-token containment check would miss.
        let d = DenyConstraint::new(["ab"]);
        let v = vocab(&["a", "b", "c"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        assert_eq!(d.safe_token_ids("a", &refs), vec![0, 2]);
    }

    #[test]
    fn bans_a_multichar_token_that_contains_the_ban() {
        // From empty text, a token whose OWN bytes contain "ab" is banned even
        // though single chars are fine.
        let d = DenyConstraint::new(["ab"]);
        let v = vocab(&["ab", "x", "ba"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        // "ab"(0) completes; "x"(1) safe; "ba"(2) does not form "ab" → safe.
        assert_eq!(d.safe_token_ids("", &refs), vec![1, 2]);
    }

    #[test]
    fn breaks_on_the_first_completing_byte_of_a_token() {
        // Committed "a"; forbidden "ab". "b" and "bc" both complete "ab" at the
        // first byte → banned; "x" is safe.
        let d = DenyConstraint::new(["ab"]);
        let v = vocab(&["b", "bc", "x"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        assert_eq!(d.safe_token_ids("a", &refs), vec![2]);
    }

    #[test]
    fn a_single_byte_ban_excludes_any_token_containing_it() {
        let d = DenyConstraint::new(["a"]);
        let v = vocab(&["a", "ba", "xy", "za"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        // every token containing 'a' is unsafe → only "xy"(2) survives.
        assert_eq!(d.safe_token_ids("", &refs), vec![2]);
    }

    #[test]
    fn no_patterns_allows_everything() {
        let d = DenyConstraint::new(Vec::<&str>::new());
        let v = vocab(&["a", "b", "c"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        assert_eq!(d.safe_token_ids("anything", &refs), vec![0, 1, 2]);
        assert_eq!(d.pattern_count(), 0);
    }

    #[test]
    fn overlapping_patterns_all_ban() {
        // "he" and "she": after "s", "he" completes both a plain "he" and the
        // suffix of "she" → banned.
        let d = DenyConstraint::new(["he", "she"]);
        let v = vocab(&["he", "e", "x"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        // committed "s": "he"(0) → 'h','e' completes "she"/"he" → banned;
        // "e"(1) → from "s", 'e' → root-ish, no hit → safe; "x"(2) safe.
        assert_eq!(d.safe_token_ids("s", &refs), vec![1, 2]);
    }

    #[test]
    fn is_denied_scans_finished_text() {
        let d = DenyConstraint::new(["jailbreak", "ignore previous"]);
        assert!(d.is_denied("please ignore previous rules"));
        assert!(!d.is_denied("a normal sentence"));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
