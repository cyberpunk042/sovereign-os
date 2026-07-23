//! `sovereign-regex-constrain` — force generation onto a regex, token by token.
//!
//! [`sovereign_regex_nfa`] can say which characters a pattern still permits;
//! [`sovereign_logit_mask`] can forbid tokens by setting their logits to `−∞`.
//! This crate joins them into the actual constrained-decoding step: given the text
//! generated so far and the model's token vocabulary, it builds a [`LogitMask`]
//! that allows only the tokens whose characters keep the pattern *viable* — i.e.
//! after appending that token the regex is still on a path to a full match. Apply
//! that mask to the logits before sampling and the model can only ever produce
//! strings the pattern accepts.
//!
//! Viability is checked incrementally: the NFA is advanced once over the prefix to
//! get the live state set, then each candidate token is stepped char-by-char from
//! that set; a token is allowed iff no character kills every state. A token that
//! *completes* the match is allowed too — and [`RegexConstraint::is_satisfied`]
//! reports when the generated text is itself a full match, so a caller knows when
//! it may stop (or permit an end-of-sequence token).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::BTreeSet;

use sovereign_logit_mask::LogitMask;
use sovereign_regex_nfa::Regex;

/// Schema version of the regex-constrain surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A regex-driven decoding constraint.
#[derive(Debug, Clone)]
pub struct RegexConstraint {
    re: Regex,
}

impl RegexConstraint {
    /// Compile `pattern` into a constraint.
    pub fn new(pattern: &str) -> Result<Self, sovereign_regex_nfa::RegexError> {
        Ok(Self {
            re: Regex::new(pattern)?,
        })
    }

    /// Wrap an already-compiled [`Regex`].
    pub fn from_regex(re: Regex) -> Self {
        Self { re }
    }

    /// The underlying regex.
    pub fn regex(&self) -> &Regex {
        &self.re
    }

    /// Whether appending `token` to `generated` leaves the pattern viable — every
    /// character of the token is consumable from the prefix's live state set.
    /// An empty token is always viable (it changes nothing).
    pub fn token_is_viable(&self, generated: &str, token: &str) -> bool {
        let mut set = self.re.start();
        for c in generated.chars() {
            set = self.re.step(&set, c);
            if set.is_empty() {
                return false; // the prefix itself is already off-pattern
            }
        }
        for c in token.chars() {
            set = self.re.step(&set, c);
            if set.is_empty() {
                return false;
            }
        }
        true
    }

    /// The indices into `vocab` of tokens that keep the pattern viable after
    /// `generated`. `vocab[i]` is the surface string of token id `i`.
    pub fn allowed_token_ids(&self, generated: &str, vocab: &[&str]) -> Vec<usize> {
        match self.advance_state(&self.start_state(), generated) {
            Some(base) => self.allowed_token_ids_from(&base, vocab),
            None => Vec::new(), // off-pattern: nothing is viable
        }
    }

    /// The initial live-state set (before any committed text) — the entry point
    /// for the **incremental** API (SDD-514): keep this set across decode steps and
    /// [`advance_state`](Self::advance_state) it by only the newly-committed token,
    /// so the per-step cost is the token, NOT the whole prefix.
    pub fn start_state(&self) -> BTreeSet<usize> {
        self.re.start()
    }

    /// Advance a live-state `base` by `text`'s characters. Returns `None` once the
    /// prefix goes **off-pattern** (the live set empties — a sticky dead state: no
    /// token can ever make it viable again), matching the early-return in
    /// [`allowed_token_ids`](Self::allowed_token_ids).
    pub fn advance_state(&self, base: &BTreeSet<usize>, text: &str) -> Option<BTreeSet<usize>> {
        let mut set = base.clone();
        for c in text.chars() {
            set = self.re.step(&set, c);
            if set.is_empty() {
                return None;
            }
        }
        Some(set)
    }

    /// The viable token ids from an already-advanced live-state `base` — probes
    /// each candidate from `base` without re-advancing the prefix. Identical result
    /// to [`allowed_token_ids`](Self::allowed_token_ids) for the matching prefix.
    pub fn allowed_token_ids_from(&self, base: &BTreeSet<usize>, vocab: &[&str]) -> Vec<usize> {
        let mut allowed = Vec::new();
        for (id, tok) in vocab.iter().enumerate() {
            let mut set = base.clone();
            let mut ok = true;
            for c in tok.chars() {
                set = self.re.step(&set, c);
                if set.is_empty() {
                    ok = false;
                    break;
                }
            }
            if ok {
                allowed.push(id);
            }
        }
        allowed
    }

    /// A [`LogitMask`] that allows only the viable token ids for `generated`. If
    /// no token is viable the mask bans everything (every logit → `−∞`), which a
    /// caller should treat as "stop".
    pub fn mask(&self, generated: &str, vocab: &[&str]) -> LogitMask {
        let allowed = self.allowed_token_ids(generated, vocab);
        if allowed.is_empty() {
            // ban every vocab token explicitly.
            LogitMask::new().ban_all(0..vocab.len())
        } else {
            LogitMask::new().allow_only(allowed)
        }
    }

    /// Whether `generated` is itself a complete match (a caller may stop / emit
    /// end-of-sequence).
    pub fn is_satisfied(&self, generated: &str) -> bool {
        self.re.is_match(generated)
    }
}

/// A regex-driven **negative** constraint: forbid a running model from ever
/// emitting text that MATCHES `pattern` anywhere — a *negated* regex (an SSN
/// shape `\d\d\d-\d\d-\d\d\d\d`, a forbidden id format). The positive
/// [`RegexConstraint`] forces output *onto* a pattern; this keeps it *off* one.
///
/// Like the literal-substring safety plane (`sovereign-token-law-deny`), a
/// forbidden match can span token boundaries, so it drives the **unanchored**
/// NFA ([`Regex::step_unanchored`]) from the committed generation and bans
/// exactly the tokens whose characters would **complete** a match.
/// [`safe_token_ids`](Self::safe_token_ids) returns the allow-list — the same
/// `Vec<usize>` shape a token-law plane consumes (SDD-506). The guarantee is
/// exact and per-step: a forbidden match can only appear at the character that
/// completes it, and that token is banned at that step.
///
/// A pattern that matches the empty string forbids everything; don't use one.
#[derive(Debug, Clone)]
pub struct RegexDenyConstraint {
    re: Regex,
}

impl RegexDenyConstraint {
    /// Compile a forbidden `pattern`.
    pub fn new(pattern: &str) -> Result<Self, sovereign_regex_nfa::RegexError> {
        Ok(Self {
            re: Regex::new(pattern)?,
        })
    }

    /// Wrap an already-compiled forbidden [`Regex`].
    pub fn from_regex(re: Regex) -> Self {
        Self { re }
    }

    /// The underlying forbidden regex.
    pub fn regex(&self) -> &Regex {
        &self.re
    }

    /// Whether `text` already contains a match of the forbidden pattern anywhere
    /// (a post-hoc scan — useful for asserting the plane's guarantee held).
    pub fn is_denied(&self, text: &str) -> bool {
        self.re.matches_anywhere(text)
    }

    /// The ids of tokens that are **safe** to append after `generated` — i.e.
    /// appending the token's characters does not complete a match of the
    /// forbidden pattern anywhere. `vocab[i]` is the surface string of token id
    /// `i`. Mirrors [`RegexConstraint::allowed_token_ids`]: the returned
    /// `Vec<usize>` is the allow-list a token-law plane consumes.
    pub fn safe_token_ids(&self, generated: &str, vocab: &[&str]) -> Vec<usize> {
        let base = self.advance_state(&self.start_state(), generated);
        self.safe_token_ids_from(&base, vocab)
    }

    /// The initial unanchored live-state set — the entry point for the
    /// **incremental** API (SDD-514): keep it across decode steps and
    /// [`advance_state`](Self::advance_state) it by only the newly-committed token.
    /// (Unanchored search is never a dead state — the start position is always
    /// live — so this returns the set directly, no `Option`.)
    pub fn start_state(&self) -> BTreeSet<usize> {
        self.re.start_unanchored()
    }

    /// Advance an unanchored live-state `base` by `text`'s characters.
    pub fn advance_state(&self, base: &BTreeSet<usize>, text: &str) -> BTreeSet<usize> {
        let mut set = base.clone();
        for c in text.chars() {
            set = self.re.step_unanchored(&set, c);
        }
        set
    }

    /// The safe token ids from an already-advanced unanchored live-state `base` —
    /// probes each candidate from `base` without re-advancing the prefix. Identical
    /// result to [`safe_token_ids`](Self::safe_token_ids) for the matching prefix.
    pub fn safe_token_ids_from(&self, base: &BTreeSet<usize>, vocab: &[&str]) -> Vec<usize> {
        let mut safe = Vec::with_capacity(vocab.len());
        for (id, tok) in vocab.iter().enumerate() {
            let mut set = base.clone();
            let mut completes = false;
            for c in tok.chars() {
                set = self.re.step_unanchored(&set, c);
                if self.re.is_accepting(&set) {
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

    #[test]
    fn allows_only_pattern_consistent_tokens() {
        // pattern: a 4-digit year. vocab mixes digits and letters.
        let c = RegexConstraint::new(r"\d\d\d\d").unwrap();
        let vocab = ["0", "1", "9", "a", "x", "12"];
        // from empty prefix, only single/multi digit tokens that fit are viable
        let allowed = c.allowed_token_ids("", &vocab);
        let allowed_strs: Vec<&str> = allowed.iter().map(|&i| vocab[i]).collect();
        assert!(allowed_strs.contains(&"0"));
        assert!(allowed_strs.contains(&"12")); // two digits, still viable
        assert!(!allowed_strs.contains(&"a"));
        assert!(!allowed_strs.contains(&"x"));
    }

    #[test]
    fn viability_tracks_the_prefix() {
        let c = RegexConstraint::new(r"\d\d\d\d").unwrap();
        // after 3 digits, only a single digit completes it; "12" would overflow
        assert!(c.token_is_viable("202", "6"));
        assert!(!c.token_is_viable("202", "66")); // 5 digits exceeds the pattern
        assert!(!c.token_is_viable("202", "a"));
    }

    #[test]
    fn off_pattern_prefix_allows_nothing() {
        let c = RegexConstraint::new(r"\d+").unwrap();
        // "ab" is already off-pattern → no token is viable
        assert!(c.allowed_token_ids("ab", &["1", "2"]).is_empty());
    }

    #[test]
    fn mask_restricts_logits_to_viable_tokens() {
        let c = RegexConstraint::new("(yes|no)").unwrap();
        let vocab = ["y", "n", "z"];
        let mask = c.mask("", &vocab);
        // 'y' (id 0) and 'n' (id 1) start valid words; 'z' (id 2) does not.
        assert!(mask.is_eligible(0));
        assert!(mask.is_eligible(1));
        assert!(!mask.is_eligible(2));

        // applying the mask sends the disallowed token to -inf
        let mut logits = [1.0f32, 1.0, 1.0];
        mask.apply(&mut logits);
        assert!(logits[0].is_finite() && logits[1].is_finite());
        assert_eq!(logits[2], f32::NEG_INFINITY);
    }

    #[test]
    fn mask_after_partial_word() {
        let c = RegexConstraint::new("(yes|no)").unwrap();
        let vocab = ["e", "o", "x"];
        // after "y", only "es" continues → 'e' viable, 'o'/'x' not
        let mask = c.mask("y", &vocab);
        assert!(mask.is_eligible(0)); // e
        assert!(!mask.is_eligible(1)); // o
        assert!(!mask.is_eligible(2)); // x
    }

    #[test]
    fn is_satisfied_reports_full_match() {
        let c = RegexConstraint::new(r"\d\d\d\d").unwrap();
        assert!(!c.is_satisfied("202"));
        assert!(c.is_satisfied("2026"));
        assert!(!c.is_satisfied("20266"));
    }

    #[test]
    fn dead_end_mask_bans_everything() {
        let c = RegexConstraint::new("ab").unwrap();
        // after "ab" the pattern is complete; no further token is viable
        let vocab = ["a", "b", "c"];
        let mask = c.mask("ab", &vocab);
        for id in 0..vocab.len() {
            assert!(!mask.is_eligible(id), "token {id} should be banned");
        }
        // but the generation is satisfied
        assert!(c.is_satisfied("ab"));
    }

    #[test]
    fn end_to_end_constrained_generation() {
        // greedily build a string allowed by the pattern using only the mask.
        let c = RegexConstraint::new(r"[a-c]+!").unwrap();
        let vocab = ["a", "b", "c", "!", "z"];
        let mut out = String::new();
        for _ in 0..5 {
            let allowed = c.allowed_token_ids(&out, &vocab);
            if allowed.is_empty() {
                break;
            }
            // prefer a token that completes the match; otherwise take the first
            // viable one. (A real sampler would pick by probability among these.)
            let pick = allowed
                .iter()
                .copied()
                .find(|&id| c.is_satisfied(&format!("{out}{}", vocab[id])))
                .unwrap_or(allowed[0]);
            out.push_str(vocab[pick]);
            if c.is_satisfied(&out) {
                break;
            }
        }
        assert!(c.is_satisfied(&out), "built '{out}' which doesn't match");
        // every char is in the allowed alphabet
        assert!(out.chars().all(|ch| "abc!".contains(ch)));
    }

    // ── RegexDenyConstraint (SDD-506: the negated-regex plane) ─────────────

    fn vocab(words: &[&str]) -> Vec<String> {
        words.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn deny_bans_the_token_completing_a_regex_match() {
        // forbidden "ab": after committed "a", the token "b" completes it →
        // banned; "c"/"x" are safe. The match spans the token boundary.
        let d = RegexDenyConstraint::new("ab").unwrap();
        let v = vocab(&["b", "c", "x"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        assert_eq!(d.safe_token_ids("a", &refs), vec![1, 2]);
    }

    #[test]
    fn deny_bans_a_token_whose_own_chars_match() {
        // forbidden two digits: a token that is itself two digits is banned.
        let d = RegexDenyConstraint::new(r"\d\d").unwrap();
        let v = vocab(&["12", "1a", "ab"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        assert_eq!(d.safe_token_ids("", &refs), vec![1, 2]);
    }

    #[test]
    fn deny_catches_a_cross_token_digit_pair() {
        // forbidden \d\d; committed "1"; the token "2" completes "12" → banned.
        let d = RegexDenyConstraint::new(r"\d\d").unwrap();
        let v = vocab(&["2", "a", "x"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        assert_eq!(d.safe_token_ids("1", &refs), vec![1, 2]);
    }

    #[test]
    fn deny_forbids_a_pattern_matched_mid_token() {
        // an alternation forbidden anywhere: a token containing "dog" is banned
        // even embedded, from a clean prefix.
        let d = RegexDenyConstraint::new("cat|dog").unwrap();
        let v = vocab(&["xdogy", "fish", "ok"]);
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        assert_eq!(d.safe_token_ids("", &refs), vec![1, 2]);
    }

    #[test]
    fn deny_is_denied_scans_for_a_match_anywhere() {
        let d = RegexDenyConstraint::new(r"\d\d\d").unwrap();
        assert!(d.is_denied("order 427 shipped")); // "427" inside
        assert!(!d.is_denied("order forty-two"));
    }
}
