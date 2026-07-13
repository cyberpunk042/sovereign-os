//! `sovereign-context-budget` — keep a prompt within the model's context.
//!
//! Every model has a finite context, and an agent's prompt only grows — history,
//! retrieved documents, observations. This crate is the bookkeeping that keeps
//! it bounded: it measures a text's length *in the runtime's own tokens* (so the
//! count matches what the model will actually see) and trims the text to a token
//! budget, keeping either the **head** (an instruction prefix you must not lose)
//! or the **tail** (the most recent turns).
//!
//! Because the byte-level tokenizer is lossless, trimming to a token subset and
//! decoding it back yields exactly the corresponding slice of the original text
//! — no characters are mangled at the cut. That property is pinned as a test.
//!
//! Composes [`sovereign-tokenizer`].
//!
//! [`sovereign-tokenizer`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-tokenizer
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_tokenizer::Tokenizer;

/// Schema version of the context-budget surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Which end of the text to keep when trimming.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Keep {
    /// Keep the first `max_tokens` tokens (e.g. a system prefix).
    Head,
    /// Keep the last `max_tokens` tokens (e.g. the most recent turns).
    Tail,
}

/// Count `text`'s length in `tokenizer`'s tokens.
pub fn token_count(tokenizer: &Tokenizer, text: &str) -> usize {
    tokenizer.encode(text).len()
}

/// Whether `text` fits within `max_tokens`.
pub fn fits(tokenizer: &Tokenizer, text: &str, max_tokens: usize) -> bool {
    token_count(tokenizer, text) <= max_tokens
}

/// Trim `text` to at most `max_tokens` tokens, keeping the `keep` end. Returns
/// the (decoded) trimmed text; unchanged if it already fits.
pub fn trim(tokenizer: &Tokenizer, text: &str, max_tokens: usize, keep: Keep) -> String {
    let ids = tokenizer.encode(text);
    if ids.len() <= max_tokens {
        return text.to_string();
    }
    let slice = match keep {
        Keep::Head => &ids[..max_tokens],
        Keep::Tail => &ids[ids.len() - max_tokens..],
    };
    // ids came from this tokenizer's own vocab, so decode never fails.
    tokenizer.decode(slice).unwrap_or_default()
}

/// Keep the `head_tokens`-token prefix verbatim and trim the rest to fit the
/// remaining budget from its tail — the common "preserve the system prompt,
/// drop the oldest history" shape. Returns `(head, body_tail)`.
pub fn split_budget(
    tokenizer: &Tokenizer,
    head: &str,
    body: &str,
    total_budget: usize,
) -> (String, String) {
    let head_tokens = token_count(tokenizer, head);
    if head_tokens >= total_budget {
        // the head alone exceeds the budget → trim the head, drop the body
        return (
            trim(tokenizer, head, total_budget, Keep::Head),
            String::new(),
        );
    }
    let body_budget = total_budget - head_tokens;
    (
        head.to_string(),
        trim(tokenizer, body, body_budget, Keep::Tail),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    // byte-level tokenizer: one token per byte → token_count == byte length
    fn tok() -> Tokenizer {
        Tokenizer::default()
    }

    #[test]
    fn token_count_matches_encoding() {
        let t = tok();
        assert_eq!(token_count(&t, "hello"), 5);
        assert_eq!(token_count(&t, ""), 0);
    }

    #[test]
    fn fits_reports_budget() {
        let t = tok();
        assert!(fits(&t, "abc", 5));
        assert!(fits(&t, "abcde", 5));
        assert!(!fits(&t, "abcdef", 5));
    }

    #[test]
    fn under_budget_is_unchanged() {
        let t = tok();
        assert_eq!(trim(&t, "short", 100, Keep::Tail), "short");
    }

    #[test]
    fn trim_tail_keeps_the_end() {
        let t = tok();
        assert_eq!(trim(&t, "abcdefgh", 3, Keep::Tail), "fgh");
    }

    #[test]
    fn trim_head_keeps_the_start() {
        let t = tok();
        assert_eq!(trim(&t, "abcdefgh", 3, Keep::Head), "abc");
    }

    #[test]
    fn trim_result_is_within_budget() {
        let t = tok();
        let trimmed = trim(&t, "a long-ish piece of text here", 10, Keep::Tail);
        assert!(token_count(&t, &trimmed) <= 10);
    }

    #[test]
    fn trim_is_lossless_at_the_cut() {
        // trimming to a token subset == the exact corresponding text slice
        let t = tok();
        let text = "0123456789";
        assert_eq!(trim(&t, text, 4, Keep::Head), "0123");
        assert_eq!(trim(&t, text, 4, Keep::Tail), "6789");
    }

    #[test]
    fn split_budget_preserves_head_and_trims_body_tail() {
        let t = tok();
        // head 4 tokens ("SYS:"), body "0123456789", budget 8 → body gets 4 (tail)
        let (head, body) = split_budget(&t, "SYS:", "0123456789", 8);
        assert_eq!(head, "SYS:");
        assert_eq!(body, "6789");
    }

    #[test]
    fn split_budget_trims_head_when_it_alone_overflows() {
        let t = tok();
        let (head, body) = split_budget(&t, "a very long system header", "body", 5);
        assert_eq!(token_count(&t, &head), 5);
        assert_eq!(body, "");
    }
}
