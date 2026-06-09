//! `sovereign-token-grammar-mask` — drive grammar-constrained decoding on real tokens.
//!
//! A context-free grammar reasons in characters; a language model emits **tokens**,
//! each a short string of characters. To force the model's output to satisfy a
//! grammar, every decoding step must answer: *which tokens, appended to what has
//! been generated, still leave a valid parse reachable?* Those tokens get to keep
//! their logits; the rest are masked to `-inf` so they can never be sampled. This
//! crate computes that mask.
//!
//! Given a [`Grammar`] (from [`sovereign_cfg_grammar`]) and a vocabulary of token
//! strings, [`TokenGrammarMask::mask`] takes the generated prefix and returns, for
//! every token, whether appending it keeps the parse live — plus whether
//! **end-of-sequence** is allowed, which is exactly whether the prefix is already a
//! complete sentence of the grammar.
//!
//! Checking a token means feeding the prefix plus the token's characters through
//! the Earley recognizer and asking whether the result is still a live prefix.
//! Doing that for the whole vocabulary every step would be wasteful, so the mask is
//! computed with a **first-character prefilter**: the grammar's `allowed_next` for
//! the current prefix is found once, and any token whose first character is not
//! among the allowed terminals is rejected immediately, without a full parse. Only
//! the survivors — usually a small fraction of the vocabulary — are validated in
//! full. The empty token and end-of-sequence are handled explicitly.
//!
//! [`TokenGrammarMask::allowed_tokens`] lists the permitted ids;
//! [`TokenGrammarMask::apply`] masks a logit slice in place. The [`Mask`] carries
//! the per-token booleans and the `eos` flag.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

pub use sovereign_cfg_grammar::{Grammar, GrammarBuilder, NextSet, Symbol, Terminal};

/// Schema version of the token-grammar-mask surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A token-level grammar constraint over a fixed vocabulary.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TokenGrammarMask {
    grammar: Grammar,
    /// Token strings, indexed by token id.
    vocab: Vec<String>,
    /// Precomputed first character of each token (None for the empty token).
    first_char: Vec<Option<char>>,
}

/// The result of masking a prefix: per-token permission and the EOS flag.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Mask {
    /// `allowed[id]` = appending token `id` keeps a valid parse reachable.
    pub allowed: Vec<bool>,
    /// Whether end-of-sequence is permitted (the prefix is a complete sentence).
    pub eos: bool,
}

impl Mask {
    /// Whether token `id` is permitted.
    pub fn allows(&self, id: usize) -> bool {
        self.allowed.get(id).copied().unwrap_or(false)
    }
    /// The ids of all permitted tokens.
    pub fn allowed_ids(&self) -> Vec<usize> {
        self.allowed
            .iter()
            .enumerate()
            .filter(|&(_, &ok)| ok)
            .map(|(i, _)| i)
            .collect()
    }
    /// How many tokens are permitted.
    pub fn count_allowed(&self) -> usize {
        self.allowed.iter().filter(|&&ok| ok).count()
    }
}

impl TokenGrammarMask {
    /// Build a constraint from a grammar and a vocabulary of token strings.
    pub fn new(grammar: Grammar, vocab: Vec<String>) -> Self {
        let first_char = vocab.iter().map(|t| t.chars().next()).collect();
        Self {
            grammar,
            vocab,
            first_char,
        }
    }

    /// The vocabulary size.
    pub fn vocab_size(&self) -> usize {
        self.vocab.len()
    }
    /// The underlying grammar.
    pub fn grammar(&self) -> &Grammar {
        &self.grammar
    }
    /// The token string for `id`, if in range.
    pub fn token(&self, id: usize) -> Option<&str> {
        self.vocab.get(id).map(|s| s.as_str())
    }

    /// Compute the token mask for `prefix` (the text generated so far).
    pub fn mask(&self, prefix: &str) -> Mask {
        let next = self.grammar.allowed_next(prefix);
        let eos = next.complete;
        // a buffer reused for prefix+token checks.
        let mut buf = String::with_capacity(prefix.len() + 16);
        let allowed = self
            .vocab
            .iter()
            .zip(&self.first_char)
            .map(|(tok, fc)| self.token_allowed(prefix, tok, *fc, &next, &mut buf))
            .collect();
        Mask { allowed, eos }
    }

    /// Whether a single token may be appended to `prefix`, using the prefilter.
    fn token_allowed(
        &self,
        prefix: &str,
        token: &str,
        first: Option<char>,
        next: &NextSet,
        buf: &mut String,
    ) -> bool {
        match first {
            // the empty token never advances the parse; treat it as not allowed
            // (a generator should use EOS, not an empty token, to stop).
            None => false,
            Some(c) => {
                // cheap rejection: first char must be an allowed next terminal.
                if !next.allows(c) {
                    return false;
                }
                // full check: prefix+token must remain a live prefix.
                buf.clear();
                buf.push_str(prefix);
                buf.push_str(token);
                self.grammar.is_live_prefix(buf)
            }
        }
    }

    /// The ids of tokens permitted after `prefix`.
    pub fn allowed_tokens(&self, prefix: &str) -> Vec<usize> {
        self.mask(prefix).allowed_ids()
    }

    /// Mask a logit slice in place: any disallowed token's logit becomes `-inf`.
    /// The slice length should equal the vocabulary size. Returns the EOS flag so
    /// the caller can gate the end-of-sequence logit separately.
    pub fn apply(&self, logits: &mut [f32], prefix: &str) -> bool {
        let m = self.mask(prefix);
        for (l, &ok) in logits.iter_mut().zip(&m.allowed) {
            if !ok {
                *l = f32::NEG_INFINITY;
            }
        }
        m.eos
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// S -> '(' S ')' S | ε  (balanced parentheses).
    fn balanced() -> Grammar {
        let mut b = GrammarBuilder::new();
        let s = b.nonterminal();
        b.rule(
            s,
            vec![
                Symbol::ch('('),
                Symbol::nt(s),
                Symbol::ch(')'),
                Symbol::nt(s),
            ],
        );
        b.rule(s, vec![]);
        b.build(s)
    }

    /// Number -> Digit Rest ; Rest -> Digit Rest | ε ; Digit -> [0-9]
    fn number() -> Grammar {
        let mut b = GrammarBuilder::new();
        let num = b.nonterminal();
        let rest = b.nonterminal();
        let digit = b.nonterminal();
        b.rule(num, vec![Symbol::nt(digit), Symbol::nt(rest)]);
        b.rule(rest, vec![Symbol::nt(digit), Symbol::nt(rest)]);
        b.rule(rest, vec![]);
        b.rule(digit, vec![Symbol::range('0', '9')]);
        b.build(num)
    }

    fn vocab(words: &[&str]) -> Vec<String> {
        words.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn balanced_masks_invalid_tokens() {
        let v = vocab(&["(", ")", "()", "(())", "x", ""]);
        let m = TokenGrammarMask::new(balanced(), v);
        let mask = m.mask("");
        // at the start: "(" ok, "()" ok, "(())" ok; ")" not, "x" not, "" not.
        assert!(mask.allows(0)); // "("
        assert!(!mask.allows(1)); // ")"
        assert!(mask.allows(2)); // "()"
        assert!(mask.allows(3)); // "(())"
        assert!(!mask.allows(4)); // "x"
        assert!(!mask.allows(5)); // ""
        // empty string is a complete balanced sentence → EOS allowed.
        assert!(mask.eos);
    }

    #[test]
    fn balanced_after_open_paren() {
        let v = vocab(&["(", ")", "()", "x"]);
        let m = TokenGrammarMask::new(balanced(), v);
        let mask = m.mask("(");
        // after "(": "(" ok, ")" ok (closes), "()" ok; "x" not.
        assert!(mask.allows(0));
        assert!(mask.allows(1));
        assert!(mask.allows(2));
        assert!(!mask.allows(3));
        // "(" alone is not complete → no EOS.
        assert!(!mask.eos);
    }

    #[test]
    fn number_multichar_tokens() {
        let v = vocab(&["12", "1a", "9", "007", "x"]);
        let m = TokenGrammarMask::new(number(), v);
        let mask = m.mask("");
        assert!(mask.allows(0)); // "12"
        assert!(!mask.allows(1)); // "1a" — 'a' breaks the parse
        assert!(mask.allows(2)); // "9"
        assert!(mask.allows(3)); // "007"
        assert!(!mask.allows(4)); // "x"
        // empty is not a valid number → no EOS yet.
        assert!(!mask.eos);
    }

    #[test]
    fn number_eos_after_digits() {
        let v = vocab(&["3", "z"]);
        let m = TokenGrammarMask::new(number(), v);
        let mask = m.mask("42");
        assert!(mask.allows(0)); // can append another digit
        assert!(!mask.allows(1));
        // "42" is a complete number → EOS allowed.
        assert!(mask.eos);
    }

    #[test]
    fn allowed_tokens_lists_ids() {
        let v = vocab(&["(", ")", "()", "x"]);
        let m = TokenGrammarMask::new(balanced(), v);
        let ids = m.allowed_tokens("");
        assert_eq!(ids, vec![0, 2]); // "(" and "()"
    }

    #[test]
    fn apply_masks_logits() {
        let v = vocab(&["(", ")", "()", "x"]);
        let m = TokenGrammarMask::new(balanced(), v);
        let mut logits = vec![1.0f32; 4];
        let eos = m.apply(&mut logits, "");
        assert!(logits[0].is_finite()); // "("
        assert_eq!(logits[1], f32::NEG_INFINITY); // ")"
        assert!(logits[2].is_finite()); // "()"
        assert_eq!(logits[3], f32::NEG_INFINITY); // "x"
        assert!(eos);
    }

    #[test]
    fn prefilter_matches_full_check() {
        // the mask must equal a brute-force is_live_prefix check for every token.
        let g = number();
        let v = vocab(&["0", "5", "12", "99", "1x", "", "abc", "7", "x9"]);
        let m = TokenGrammarMask::new(g.clone(), v.clone());
        for prefix in ["", "1", "42", "9"] {
            let mask = m.mask(prefix);
            for (id, tok) in v.iter().enumerate() {
                let brute = if tok.is_empty() {
                    false
                } else {
                    g.is_live_prefix(&format!("{prefix}{tok}"))
                };
                assert_eq!(mask.allows(id), brute, "prefix={prefix:?} tok={tok:?}");
            }
        }
    }

    #[test]
    fn count_allowed_reports_size() {
        let v = vocab(&["(", ")", "()", "(())", "x"]);
        let m = TokenGrammarMask::new(balanced(), v);
        assert_eq!(m.mask("").count_allowed(), 3); // "(", "()", "(())"
    }

    #[test]
    fn token_accessors() {
        let v = vocab(&["a", "bc"]);
        let m = TokenGrammarMask::new(number(), v);
        assert_eq!(m.vocab_size(), 2);
        assert_eq!(m.token(1), Some("bc"));
        assert_eq!(m.token(9), None);
    }

    #[test]
    fn serde_round_trip() {
        let v = vocab(&["(", ")", "()"]);
        let m = TokenGrammarMask::new(balanced(), v);
        let j = serde_json::to_string(&m).unwrap();
        let back: TokenGrammarMask = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
        assert_eq!(m.mask("("), back.mask("("));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
