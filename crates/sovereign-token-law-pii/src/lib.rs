//! `sovereign-token-law-pii` — the **PII-completion** token-law plane (SDD-516).
//!
//! The M00117 planes turn a text constraint into a per-token allow-list. The
//! [deny plane] bans the token that *completes* a forbidden substring; the
//! [entropy plane] bans a token that keeps a trailing window *statistically*
//! secret-shaped — an explicitly **heuristic** projection, because "the token
//! that completes a high-entropy secret" is not well-defined at a hard
//! threshold. The entropy plane's own scope note names the fix: a
//! *checksum/Luhn-shaped PII projection* with a **well-defined completion** is
//! the natural v2. This crate is that v2.
//!
//! Unlike entropy, a PII value is a **defined shape**: at any prefix, appending
//! a candidate token either creates a [`sovereign_pii_redact::detect`] match that
//! ends *within the candidate* or it does not — deterministic per step, not a
//! statistical cutoff. This plane bans exactly those completing tokens. It
//! reuses `sovereign-pii-redact::detect` **wholesale** (email / US SSN / IPv4 /
//! Luhn-valid credit card), so the plane and the post-hoc redactor can never
//! disagree on what PII is — the same discipline the entropy plane keeps with the
//! secret scanner.
//!
//! **Honest scope.** The *completion* is exact within the shapes `detect`
//! recognizes, but `detect`'s **recall** is bounded — it is a high-precision
//! heuristic over four kinds; it will not catch a name or a novel identifier
//! format. So, like entropy, this plane is **opt-in per request**, off by
//! default, and the post-hoc `sovereign-pii-redact::redact` (run by the gateway's
//! `StreamGuard`) stays the exact backstop. It is a **preventive complement**,
//! never a replacement. The scan is **windowed** — only the trailing `window`
//! characters of `generated` are considered, so per-step cost is bounded and the
//! stateless and incremental paths agree bit-for-bit; a PII value whose start
//! falls before the window boundary is the documented limitation of the window
//! (mirrors the entropy plane's window).
//!
//! [`PiiConstraint::safe_token_ids`] returns the allow-list — all tokens minus
//! the completing ones — the same `Vec<usize>` shape
//! `sovereign-token-law-mask`'s `TokenLawPlanes`, `sovereign-token-law-deny`, and
//! `sovereign-token-law-entropy` use, so it composes with grammar / regex /
//! denylist / entropy / policy planes through the M00117 `token_law_combine`.
//!
//! [deny plane]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-token-law-deny
//! [entropy plane]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-token-law-entropy
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_pii_redact::detect;

/// Schema version of the token-law-pii surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The default trailing-window character count. Covers the shape-based kinds
/// comfortably — a Luhn card (≤19 digits + separators), an SSN (`###-##-####`),
/// and an IPv4 address are all well under this; a long email whose start falls
/// before the window boundary is the documented windowed limitation.
pub const DEFAULT_PII_WINDOW: usize = 128;

/// A PII-completion constraint: ban the token whose characters *complete* a
/// [`sovereign_pii_redact`] detection ending within the candidate, judged over
/// the trailing `window` characters of the running output.
#[derive(Debug, Clone, Copy)]
pub struct PiiConstraint {
    window: usize,
}

impl Default for PiiConstraint {
    /// A constraint over the [`DEFAULT_PII_WINDOW`] trailing characters.
    fn default() -> Self {
        Self {
            window: DEFAULT_PII_WINDOW,
        }
    }
}

impl PiiConstraint {
    /// A constraint with an explicit trailing-window character count. A `window`
    /// of `0` yields a constraint that bans nothing (an all-safe identity — the
    /// plane is effectively off).
    pub fn new(window: usize) -> Self {
        Self { window }
    }

    /// The trailing-window character count scanned for a PII completion.
    pub fn window(&self) -> usize {
        self.window
    }

    /// Whether `text` *ends with* a PII value — i.e. a detection over the trailing
    /// window ends at the very end of the text (a post-hoc check useful for
    /// asserting the plane's intent held: the value the plane would have blocked
    /// is exactly the one that ends the string).
    pub fn ends_with_pii(&self, text: &str) -> bool {
        if self.window == 0 {
            return false;
        }
        let base = self.trailing_window(text);
        let end = base.len();
        detect(&base).iter().any(|d| d.end == end)
    }

    /// The ids of tokens that are **safe** to append after `generated` — i.e.
    /// appending the token's characters does not *complete* a PII value (create a
    /// [`sovereign_pii_redact::detect`] match ending within the candidate).
    /// `vocab[i]` is the surface string of token id `i`. Mirrors
    /// [`sovereign_token_law_deny::DenyConstraint::safe_token_ids`] and
    /// [`sovereign_token_law_entropy::EntropyConstraint::safe_token_ids`]: the
    /// returned `Vec<usize>` is the allow-list a token-law plane consumes.
    ///
    /// Only the trailing `window` characters of `generated` are considered, so an
    /// empty token (which cannot complete anything new) and any token that does
    /// not close a detection are safe.
    ///
    /// [`sovereign_token_law_deny::DenyConstraint::safe_token_ids`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-token-law-deny
    /// [`sovereign_token_law_entropy::EntropyConstraint::safe_token_ids`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-token-law-entropy
    pub fn safe_token_ids(&self, generated: &str, vocab: &[&str]) -> Vec<usize> {
        // Off (identity) when disabled: never ban, so composition is a no-op.
        if self.window == 0 {
            return (0..vocab.len()).collect();
        }
        // Window the history ONCE; a detection completed by the candidate must end
        // within the appended token, i.e. past this base's byte length.
        let base = self.trailing_window(generated);
        let base_len = base.len();
        let mut safe = Vec::with_capacity(vocab.len());
        for (id, tok) in vocab.iter().enumerate() {
            if tok.is_empty() {
                safe.push(id);
                continue;
            }
            let mut candidate = String::with_capacity(base_len + tok.len());
            candidate.push_str(&base);
            candidate.push_str(tok);
            // The candidate is UNSAFE iff appending `tok` closes a PII detection —
            // a detection whose end falls within the appended region.
            let completes = detect(&candidate).iter().any(|d| d.end > base_len);
            if !completes {
                safe.push(id);
            }
        }
        safe
    }

    /// The trailing `window` characters of `text` (char-, not byte-, bounded so a
    /// multibyte boundary is never split).
    fn trailing_window<'a>(&self, text: &'a str) -> std::borrow::Cow<'a, str> {
        let n = text.chars().count();
        if n <= self.window {
            std::borrow::Cow::Borrowed(text)
        } else {
            std::borrow::Cow::Owned(text.chars().skip(n - self.window).collect())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn refs<'a>(v: &'a [&'a str]) -> Vec<&'a str> {
        v.to_vec()
    }

    #[test]
    fn non_pii_text_keeps_every_token_safe() {
        let p = PiiConstraint::default();
        let v = refs(&["a", "the", " ", "cat"]);
        assert_eq!(p.safe_token_ids("the cat sat", &v), vec![0, 1, 2, 3]);
    }

    #[test]
    fn bans_the_token_that_completes_a_luhn_card() {
        // 4111 1111 1111 1111 is the classic Luhn-valid test Visa. After the first
        // 15 digits, the token that supplies the final Luhn-completing digit is
        // banned; a non-completing digit (that leaves the run Luhn-invalid) is safe.
        let p = PiiConstraint::default();
        let prefix = "card 4111 1111 1111 111"; // 15 digits present
        let v = refs(&["1", " done"]);
        let safe = p.safe_token_ids(prefix, &v);
        // "1" completes 4111111111111111 → Luhn-valid card → banned.
        assert!(
            !safe.contains(&0),
            "the card-completing digit must be banned"
        );
        // " done" adds no digit → no completion → safe.
        assert!(safe.contains(&1), "a non-completing token stays safe");
    }

    #[test]
    fn bans_the_token_that_completes_an_ssn() {
        // `###-##-####` — the last digit completes the SSN shape.
        let p = PiiConstraint::default();
        let v = refs(&["9", " and"]);
        let safe = p.safe_token_ids("ssn 123-45-678", &v);
        assert!(
            !safe.contains(&0),
            "the SSN-completing digit must be banned"
        );
        assert!(safe.contains(&1), "a non-completing token stays safe");
    }

    #[test]
    fn a_token_that_carries_a_whole_pii_value_is_banned() {
        // The candidate itself contains a complete detection (an email).
        let p = PiiConstraint::default();
        let v = refs(&["me@example.com", "hello"]);
        let safe = p.safe_token_ids("contact ", &v);
        assert!(
            !safe.contains(&0),
            "a token containing a full email must be banned"
        );
        assert!(safe.contains(&1), "an ordinary token stays safe");
    }

    #[test]
    fn pii_already_in_history_does_not_ban_a_later_token() {
        // A completed value fully inside `generated` (not extended by the
        // candidate) must not ban an unrelated following token.
        let p = PiiConstraint::default();
        let v = refs(&[" ok", "x"]);
        let safe = p.safe_token_ids("mail me@example.com now", &v);
        assert_eq!(
            safe,
            vec![0, 1],
            "prior PII does not ban non-completing tokens"
        );
    }

    #[test]
    fn empty_token_is_always_safe() {
        let p = PiiConstraint::default();
        let v = refs(&["", "4111 1111 1111 111"]);
        // The empty token completes nothing.
        assert!(p.safe_token_ids("card 4111 1111 1111 111", &v).contains(&0));
    }

    #[test]
    fn disabled_constraint_is_an_all_safe_identity() {
        let off = PiiConstraint::new(0);
        let v = refs(&["1", "me@example.com"]);
        assert_eq!(
            off.safe_token_ids("card 4111 1111 1111 111", &v),
            vec![0, 1]
        );
    }

    #[test]
    fn ends_with_pii_flags_a_completed_value() {
        let p = PiiConstraint::default();
        assert!(p.ends_with_pii("reach me@example.com"));
        assert!(!p.ends_with_pii("reach me@example.com now"));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
