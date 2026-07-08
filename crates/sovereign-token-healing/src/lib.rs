//! `sovereign-token-healing` — fix the seam between prompt and completion.
//!
//! A subtle bug bites completion and constrained decoding: the prompt is
//! tokenized as a whole, so its *last* token is whatever split the tokenizer
//! chose for the text up to the cut — and that split is often not the one the
//! model would pick if it were generating. Ask for a completion of `"http"` and
//! the model, having been handed the token `http`, can no longer produce `https`
//! as the single token `https` it was trained on; it is stuck extending from a
//! boundary that does not exist in its world. The output degrades right at the
//! seam.
//!
//! **Token healing** fixes this. Trim the trailing token(s) of the prompt, keep
//! their surface text as a *prefix constraint*, and require the first generated
//! token to be consistent with that prefix — either a token that the removed text
//! is a prefix of (so it re-chooses the boundary token and may extend it) or a
//! token that is itself a prefix of the removed text (so healing continues into
//! the next step). The model is then free to pick the natural split.
//!
//! [`TokenHealer`] wraps a vocabulary (token id → surface string).
//! [`heal`](TokenHealer::heal) trims the last token and returns the prefix to
//! re-generate; [`allowed_continuations`](TokenHealer::allowed_continuations)
//! lists the token ids consistent with a prefix (the mask a constrained sampler
//! applies at the first step).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the token-healing surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A token-healing helper over a vocabulary.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TokenHealer {
    /// token id → its surface string.
    vocab: Vec<String>,
}

/// The result of healing a prompt.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Healed {
    /// The prompt with the trailing token(s) removed.
    pub trimmed: Vec<u32>,
    /// The surface text of the removed token(s), which the next generated token
    /// must be consistent with.
    pub prefix: String,
}

impl TokenHealer {
    /// Build from a vocabulary where index `i` is token id `i`'s surface string.
    pub fn new<I, S>(vocab: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        Self {
            vocab: vocab.into_iter().map(Into::into).collect(),
        }
    }

    /// The vocabulary size.
    pub fn vocab_size(&self) -> usize {
        self.vocab.len()
    }

    /// The surface string of a token id, if in range.
    pub fn surface(&self, token: u32) -> Option<&str> {
        self.vocab.get(token as usize).map(String::as_str)
    }

    /// Heal `prompt` by trimming its last token (if any) and returning that token's
    /// surface text as the prefix to re-generate. An empty prompt heals to itself
    /// with an empty prefix (nothing to heal).
    pub fn heal(&self, prompt: &[u32]) -> Healed {
        match prompt.last() {
            Some(&last) => {
                let prefix = self.surface(last).unwrap_or("").to_string();
                Healed {
                    trimmed: prompt[..prompt.len() - 1].to_vec(),
                    prefix,
                }
            }
            None => Healed {
                trimmed: Vec::new(),
                prefix: String::new(),
            },
        }
    }

    /// Heal by trimming up to `max_tokens` trailing tokens, concatenating their
    /// surfaces into the prefix — useful when the boundary spans more than one
    /// token (a multi-token word fragment).
    pub fn heal_n(&self, prompt: &[u32], max_tokens: usize) -> Healed {
        let take = max_tokens.min(prompt.len());
        let cut = prompt.len() - take;
        let prefix: String = prompt[cut..]
            .iter()
            .map(|&t| self.surface(t).unwrap_or(""))
            .collect();
        Healed {
            trimmed: prompt[..cut].to_vec(),
            prefix,
        }
    }

    /// Whether a token is a valid first-step continuation for healing `prefix`:
    /// either the token's surface starts with `prefix` (re-chooses/extends the
    /// boundary), or `prefix` starts with the token's surface (consumes part of
    /// the prefix; healing continues). An empty prefix admits every token.
    pub fn is_continuation(&self, token: u32, prefix: &str) -> bool {
        if prefix.is_empty() {
            return true;
        }
        match self.surface(token) {
            Some(s) if !s.is_empty() => s.starts_with(prefix) || prefix.starts_with(s),
            _ => false,
        }
    }

    /// All token ids that are valid first-step continuations for `prefix`, sorted.
    pub fn allowed_continuations(&self, prefix: &str) -> Vec<u32> {
        (0..self.vocab.len() as u32)
            .filter(|&t| self.is_continuation(t, prefix))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn healer() -> TokenHealer {
        // a toy vocab where "http", "https", "://" exist as distinct tokens.
        TokenHealer::new([
            "http",  // 0
            "https", // 1
            "://",   // 2
            "s",     // 3
            "ht",    // 4
            "world", // 5
            "p",     // 6
        ])
    }

    #[test]
    fn heal_trims_last_token() {
        let h = healer();
        // prompt ends with token 0 ("http")
        let healed = h.heal(&[5, 0]);
        assert_eq!(healed.trimmed, vec![5]);
        assert_eq!(healed.prefix, "http");
    }

    #[test]
    fn allowed_continuations_for_http_prefix() {
        let h = healer();
        let allowed = h.allowed_continuations("http");
        // "http" (0, equal/prefix), "https" (1, starts with http), "ht" (4, prefix
        // of "http"), "p"? no. Let's check membership.
        assert!(allowed.contains(&0)); // http
        assert!(allowed.contains(&1)); // https (extends boundary — the heal!)
        assert!(allowed.contains(&4)); // "ht" is a prefix of "http"
        assert!(!allowed.contains(&5)); // "world" unrelated
        assert!(!allowed.contains(&2)); // "://" unrelated
    }

    #[test]
    fn healing_enables_better_token_choice() {
        // the whole point: after trimming "http", the model may pick "https" (1),
        // which it could NOT have produced if "http" stayed as a fixed token.
        let h = healer();
        let healed = h.heal(&[0]); // prompt was just "http"
        assert_eq!(healed.prefix, "http");
        assert!(h.is_continuation(1, &healed.prefix)); // "https" allowed
    }

    #[test]
    fn empty_prefix_admits_everything() {
        let h = healer();
        let healed = h.heal(&[]); // empty prompt
        assert_eq!(healed.prefix, "");
        assert_eq!(h.allowed_continuations("").len(), h.vocab_size());
    }

    #[test]
    fn partial_prefix_consumption() {
        let h = healer();
        // prefix "ht" → token "http" extends it (allowed), token "ht" equals it,
        // token "h"? not in vocab; "https" starts with "ht"? no ("https" vs "ht":
        // 'h','t' match, "https"[0..2]="ht" yes!). So 1 allowed too.
        let allowed = h.allowed_continuations("ht");
        assert!(allowed.contains(&0)); // http starts with ht
        assert!(allowed.contains(&1)); // https starts with ht
        assert!(allowed.contains(&4)); // ht == ht
    }

    #[test]
    fn heal_n_multiple_tokens() {
        let h = healer();
        // trim last two tokens "ht"+"tp"? use [5,4,6]: "world","ht","p" → trim 2 →
        // prefix "htp", trimmed ["world"].
        let healed = h.heal_n(&[5, 4, 6], 2);
        assert_eq!(healed.trimmed, vec![5]);
        assert_eq!(healed.prefix, "htp");
    }

    #[test]
    fn out_of_range_token_surface() {
        let h = healer();
        assert_eq!(h.surface(999), None);
        // healing a prompt ending in an unknown id yields an empty prefix.
        let healed = h.heal(&[999]);
        assert_eq!(healed.prefix, "");
    }

    #[test]
    fn serde_round_trip() {
        let h = healer();
        let j = serde_json::to_string(&h).unwrap();
        let back: TokenHealer = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
        assert_eq!(back.heal(&[0]).prefix, "http");
    }
}
