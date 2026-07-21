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

pub use sovereign_cfg_grammar::{EarleyChart, Grammar, GrammarBuilder, NextSet, Symbol, Terminal};

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
    ///
    /// Incremental (SDD-502): the prefix is parsed **once** into an
    /// [`EarleyChart`], then each surviving candidate token is validated by
    /// feeding its characters onto that committed chart and rolling back — cost
    /// proportional to the token's length, not the prefix's. The result is
    /// bit-for-bit identical to the previous per-token full re-parse.
    pub fn mask(&self, prefix: &str) -> Mask {
        let mut base = self.grammar.start_chart();
        base.feed_str(&self.grammar, prefix);
        let next = base.next_set(&self.grammar);
        let eos = next.complete;
        let base_len = base.chars_consumed();
        let mut allowed = Vec::with_capacity(self.vocab.len());
        for (tok, fc) in self.vocab.iter().zip(&self.first_char) {
            allowed.push(match *fc {
                // the empty token never advances the parse; treat it as not allowed
                // (a generator should use EOS, not an empty token, to stop).
                None => false,
                // cheap rejection: first char must be an allowed next terminal.
                Some(c) if !next.allows(c) => false,
                Some(_) => {
                    let ok = token_keeps_live(&mut base, &self.grammar, tok);
                    base.rollback_to(base_len);
                    ok
                }
            });
        }
        Mask { allowed, eos }
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

/// Feed `token`'s characters onto a committed [`EarleyChart`] and report whether
/// the extended prefix stays a live prefix — the incremental equivalent of
/// `grammar.is_live_prefix(prefix + token)`. The caller is responsible for
/// rolling the chart back afterwards (this leaves the fed characters in place so
/// a *commit* path can reuse it).
fn token_keeps_live(chart: &mut EarleyChart, grammar: &Grammar, token: &str) -> bool {
    for c in token.chars() {
        if !chart.feed(grammar, c) {
            return false;
        }
    }
    chart.is_live(grammar)
}

/// A grammar token mask that **persists** its Earley state across decode steps.
///
/// [`TokenGrammarMask::mask`] is incremental *within a call* (it parses the
/// prefix once, then validates each token by feed-then-rollback), but it still
/// re-parses the whole prefix every step. This masker goes one step further: it
/// holds the committed [`EarleyChart`] for the accepted text and
/// [`advance`](Self::advance)s it by the newly-accepted characters, so the
/// per-step prefix cost is only the *new* characters — the fully-incremental
/// path (SDD-502).
///
/// It operates in the **character domain** (the grammar's domain). A token-driven
/// decode loop may use it only when the tokenizer is *char-concatenative* —
/// `decode(a) + decode(b) == decode([a, b])` — feeding each accepted token's
/// decoded text via [`advance`](Self::advance). The byte-level BPE path satisfies
/// this; a merge-BPE tokenizer generally does not, which is why the stateless
/// [`TokenGrammarMask::mask`] (also incremental, but per-call — no concatenation
/// assumption) stays the default for the LLM wiring.
#[derive(Debug, Clone)]
pub struct IncrementalGrammarMask {
    grammar: Grammar,
    vocab: Vec<String>,
    first_char: Vec<Option<char>>,
    committed: EarleyChart,
}

impl IncrementalGrammarMask {
    /// Build a stateful constraint from a grammar and a vocabulary of token
    /// strings. The committed chart starts empty (before any generated text).
    pub fn new(grammar: Grammar, vocab: Vec<String>) -> Self {
        let first_char = vocab.iter().map(|t| t.chars().next()).collect();
        let committed = grammar.start_chart();
        Self {
            grammar,
            vocab,
            first_char,
            committed,
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
    /// Characters of accepted text committed so far.
    pub fn chars_consumed(&self) -> usize {
        self.committed.chars_consumed()
    }

    /// The token mask for the currently-committed prefix. Uses the committed
    /// chart as the base for feed-then-rollback, so the committed state is
    /// unchanged on return (hence `&mut self`: the transient feed mutates it).
    /// Identical output to [`TokenGrammarMask::mask`] for the same prefix.
    pub fn mask(&mut self) -> Mask {
        let next = self.committed.next_set(&self.grammar);
        let eos = next.complete;
        let base_len = self.committed.chars_consumed();
        let mut allowed = Vec::with_capacity(self.vocab.len());
        for i in 0..self.vocab.len() {
            let ok = match self.first_char[i] {
                None => false,
                Some(c) if !next.allows(c) => false,
                Some(_) => {
                    let live = token_keeps_live(&mut self.committed, &self.grammar, &self.vocab[i]);
                    self.committed.rollback_to(base_len);
                    live
                }
            };
            allowed.push(ok);
        }
        Mask { allowed, eos }
    }

    /// Permanently extend the committed prefix by `text`'s characters (the
    /// accept path). Returns whether the prefix remains parseable. Feeding text
    /// that kills the parse leaves the chart dead; callers should only advance by
    /// text that a prior [`mask`](Self::mask) permitted.
    pub fn advance(&mut self, text: &str) -> bool {
        self.committed.feed_str(&self.grammar, text)
    }

    /// Permanently extend the committed prefix by token `id`'s string. Returns
    /// whether the prefix remains parseable, or `false` if `id` is out of range.
    pub fn advance_token(&mut self, id: usize) -> bool {
        match self.vocab.get(id) {
            // token_keeps_live leaves the fed characters in place → committed.
            Some(tok) => token_keeps_live(&mut self.committed, &self.grammar, tok),
            None => false,
        }
    }

    /// Whether end-of-sequence is currently permitted (the committed prefix is a
    /// complete sentence).
    pub fn eos_allowed(&self) -> bool {
        self.committed.accepts(&self.grammar)
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
    fn incremental_masker_matches_stateless() {
        // the stateful (across-step) masker must produce the SAME mask as the
        // stateless per-call masker at every step.
        let g = number();
        let v = vocab(&["0", "5", "12", "99", "1x", "", "7", "x"]);
        let stateless = TokenGrammarMask::new(g.clone(), v.clone());
        let mut inc = IncrementalGrammarMask::new(g, v);
        let mut prefix = String::new();
        assert_eq!(inc.mask(), stateless.mask(&prefix)); // empty prefix
        for tok in ["1", "2", "3"] {
            assert!(inc.advance(tok));
            prefix.push_str(tok);
            assert_eq!(inc.mask(), stateless.mask(&prefix), "prefix={prefix:?}");
            assert_eq!(inc.eos_allowed(), stateless.mask(&prefix).eos);
        }
    }

    #[test]
    fn incremental_masker_advance_token_tracks_eos() {
        let g = balanced();
        let v = vocab(&["(", ")", "()"]);
        let mut inc = IncrementalGrammarMask::new(g, v);
        assert!(inc.eos_allowed()); // empty is a complete balanced sentence
        assert!(inc.advance_token(0)); // "("
        assert!(!inc.eos_allowed()); // "(" not complete
        assert!(inc.advance_token(1)); // ")"
        assert!(inc.eos_allowed()); // "()" complete
        assert_eq!(inc.chars_consumed(), 2);
    }

    #[test]
    fn stateless_mask_large_prefix_matches_brute() {
        // a long prefix must still match a brute-force is_live_prefix check for
        // every token — the incremental mask has no length-dependent divergence.
        let g = balanced();
        let prefix = "(".repeat(50);
        let v = vocab(&["(", ")", "()", "((", "x", ""]);
        let m = TokenGrammarMask::new(g.clone(), v.clone());
        let mask = m.mask(&prefix);
        for (id, tok) in v.iter().enumerate() {
            let brute = if tok.is_empty() {
                false
            } else {
                g.is_live_prefix(&format!("{prefix}{tok}"))
            };
            assert_eq!(mask.allows(id), brute, "tok={tok:?}");
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
