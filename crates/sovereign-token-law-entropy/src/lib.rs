//! `sovereign-token-law-entropy` — the **entropy** token-law plane (SDD-513).
//!
//! The M00117 planes to date turn a *structural* text constraint into a per-token
//! allow-list: grammar keeps a parse reachable, regex keeps a match live, the
//! [deny plane] bans the token that *completes* a forbidden substring. Those are
//! exact per-step guarantees because "the token that completes pattern P" is
//! well-defined.
//!
//! Secret leakage is **not** structural: a leaked API key or password is
//! recognized by its *statistics* — a run of characters with high Shannon
//! entropy — not by a fixed substring. The [deny plane's own scope note] is
//! honest that "the token that completes a high-entropy secret is not
//! well-defined", so entropy stayed a post-hoc scanner ([`sovereign-secret-scan`],
//! run on the finished output by the gateway's `StreamGuard`).
//!
//! This crate projects that same detector to the token level as an **explicitly
//! heuristic** plane. It is NOT the exact per-step guarantee the deny plane gives.
//! The rule is **monotone and windowed**: score the trailing `window` characters
//! of `generated + candidate_token` with the SAME
//! [`sovereign_secret_scan::shannon_entropy`] definition and thresholds the
//! post-hoc scanner uses, and **ban** any token that would leave that window at or
//! above the entropy threshold (once the window is long enough to judge). It bans
//! tokens that *extend or form* a secret-shaped run, before the run is emitted —
//! a preventive complement to, never a replacement for, the exact post-hoc scan.
//!
//! [`EntropyConstraint::safe_token_ids`] returns the allow-list — all tokens minus
//! the entropy-raising ones — the same `Vec<usize>` shape
//! `sovereign-token-law-mask`'s `TokenLawPlanes` and `sovereign-token-law-deny`
//! use, so it composes with grammar / regex / denylist / policy planes through the
//! M00117 `token_law_combine` (SDD-501/503).
//!
//! **Honest scope.** Because the threshold is a heuristic cutoff, this plane can
//! (a) miss a low-entropy-but-still-sensitive value, and (b) over-ban legitimate
//! high-entropy text (a base64 blob the operator WANTS). It is opt-in per request,
//! tuned by `(threshold_bits, window, min_len)`, and the post-hoc scanner remains
//! the exact backstop. That trade is the honest v1; a checksum/Luhn-shaped PII
//! projection (well-defined *completion*, unlike entropy) is a natural v2.
//!
//! [deny plane]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-token-law-deny
//! [deny plane's own scope note]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-token-law-deny
//! [`sovereign-secret-scan`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-secret-scan
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_secret_scan::{ENTROPY_THRESHOLD_BITS, MIN_ENTROPY_TOKEN_LEN, shannon_entropy};

/// Schema version of the token-law-entropy surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A heuristic entropy constraint: ban tokens that keep the trailing character
/// window at or above `threshold_bits` of Shannon entropy.
#[derive(Debug, Clone, Copy)]
pub struct EntropyConstraint {
    threshold_bits: f64,
    window: usize,
    min_len: usize,
}

impl Default for EntropyConstraint {
    /// The `sovereign-secret-scan` defaults: 4.0 bits/char over a 20-char window,
    /// judged only once the window holds ≥20 characters — so the plane agrees with
    /// the post-hoc scanner on what counts as a secret-shaped run.
    fn default() -> Self {
        Self {
            threshold_bits: ENTROPY_THRESHOLD_BITS,
            window: MIN_ENTROPY_TOKEN_LEN,
            min_len: MIN_ENTROPY_TOKEN_LEN,
        }
    }
}

impl EntropyConstraint {
    /// A constraint with explicit knobs. `window` is the trailing-character count
    /// scored; `min_len` is the shortest window judged (a short window has
    /// unreliable entropy); `threshold_bits` is the ban cutoff (bits/char).
    /// A non-positive `threshold_bits` or a zero `window` yields a constraint that
    /// bans nothing (an all-safe identity — the plane is effectively off).
    pub fn new(threshold_bits: f64, window: usize, min_len: usize) -> Self {
        Self {
            threshold_bits,
            window,
            min_len,
        }
    }

    /// The active threshold in bits/char.
    pub fn threshold_bits(&self) -> f64 {
        self.threshold_bits
    }

    /// The trailing-window character count.
    pub fn window(&self) -> usize {
        self.window
    }

    /// The shortest window (in characters) that is judged; below it, no token is
    /// banned (short-window entropy is unreliable).
    pub fn min_len(&self) -> usize {
        self.min_len
    }

    /// Whether `text`'s trailing window is already at/above threshold (a post-hoc
    /// check — useful for asserting the plane's intent held).
    pub fn is_high_entropy(&self, text: &str) -> bool {
        let tail = self.trailing_window(text);
        tail.chars().count() >= self.min_len && shannon_entropy(&tail) >= self.threshold_bits
    }

    /// The ids of tokens that are **safe** to append after `generated` — i.e.
    /// appending the token's characters does not leave the trailing window at or
    /// above the entropy threshold. `vocab[i]` is the surface string of token id
    /// `i`. Mirrors [`sovereign_token_law_deny::DenyConstraint::safe_token_ids`]:
    /// the returned `Vec<usize>` is the allow-list a token-law plane consumes.
    ///
    /// Heuristic (see the crate docs): it judges the window AFTER the candidate,
    /// so it bans continuation of a secret-shaped run — it is NOT the exact
    /// completion guarantee the substring deny plane gives.
    ///
    /// [`sovereign_token_law_deny::DenyConstraint::safe_token_ids`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-token-law-deny
    pub fn safe_token_ids(&self, generated: &str, vocab: &[&str]) -> Vec<usize> {
        // Off (identity) when disabled: never ban, so composition is a no-op.
        if self.threshold_bits <= 0.0 || self.window == 0 {
            return (0..vocab.len()).collect();
        }
        let mut safe = Vec::with_capacity(vocab.len());
        for (id, tok) in vocab.iter().enumerate() {
            // The candidate output; only its trailing `window` chars matter, so an
            // empty token (or one that can't lift the window to threshold) is safe.
            let mut candidate = String::with_capacity(generated.len() + tok.len());
            candidate.push_str(generated);
            candidate.push_str(tok);
            let tail = self.trailing_window(&candidate);
            let high = tail.chars().count() >= self.min_len
                && shannon_entropy(&tail) >= self.threshold_bits;
            if !high {
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
    fn low_entropy_text_keeps_every_token_safe() {
        // A short, low-entropy vocab over low-entropy history: nothing is banned.
        let e = EntropyConstraint::default();
        let v = refs(&["a", "the", " ", "cat"]);
        assert_eq!(e.safe_token_ids("the cat sat", &v), vec![0, 1, 2, 3]);
    }

    #[test]
    fn a_token_that_lifts_a_long_window_over_threshold_is_banned() {
        // A 20-char high-entropy prefix already at/above threshold; a token that
        // extends the secret-shaped run keeps the window hot → banned, while a
        // run of a single repeated low-entropy char drops the window's entropy.
        let e = EntropyConstraint::new(4.0, 20, 20);
        let prefix = "aB3xK9zQ7mP2wL5nR8tV"; // 20 distinct-ish chars, high entropy
        assert!(e.is_high_entropy(prefix), "the prefix window must be hot");
        let v = refs(&["Y4", "aaaaaaaaaaaaaaaaaaaaaa"]);
        let safe = e.safe_token_ids(prefix, &v);
        // "Y4" keeps the trailing window high-entropy → banned (id 0 absent);
        // the long run of 'a' makes the trailing window all-'a' (0 bits) → safe.
        assert!(
            !safe.contains(&0),
            "the entropy-extending token must be banned"
        );
        assert!(safe.contains(&1), "a low-entropy run must be safe");
    }

    #[test]
    fn short_window_is_never_judged() {
        // Below min_len characters, entropy is unreliable → never ban.
        let e = EntropyConstraint::new(4.0, 20, 20);
        let v = refs(&["X", "9", "z"]);
        assert_eq!(e.safe_token_ids("aB3", &v), vec![0, 1, 2]);
    }

    #[test]
    fn disabled_constraint_is_an_all_safe_identity() {
        let off = EntropyConstraint::new(0.0, 20, 20);
        let v = refs(&["aB3xK9zQ7mP2wL5nR8tV", "secret"]);
        assert_eq!(off.safe_token_ids("aB3xK9zQ7mP2wL5nR8tV", &v), vec![0, 1]);
    }

    #[test]
    fn defaults_track_the_secret_scanner_thresholds() {
        let e = EntropyConstraint::default();
        assert_eq!(e.threshold_bits(), ENTROPY_THRESHOLD_BITS);
        assert_eq!(e.window(), MIN_ENTROPY_TOKEN_LEN);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
