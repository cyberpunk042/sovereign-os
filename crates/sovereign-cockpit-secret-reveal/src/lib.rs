//! `sovereign-cockpit-secret-reveal` — masked-secret reveal.
//!
//! State{Masked/Revealed}. reveal(now) flips to Revealed and
//! records the timestamp. mask flips to Masked. tick(now)
//! auto-masks once Revealed for >= reveal_ms. masked_display
//! returns the secret with all but last `tail` chars replaced
//! by '•' (when masked) or the actual secret (when revealed).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// Masked.
    Masked,
    /// Revealed.
    Revealed,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SecretReveal {
    /// Schema version.
    pub schema_version: String,
    /// State.
    pub state: State,
    /// Max time Revealed before auto-mask (ms).
    pub reveal_ms: u64,
    /// When entered Revealed.
    pub revealed_at_ms: u64,
    /// Tail chars left visible when masked (0..=8).
    pub tail: u8,
    /// Reveal count.
    pub reveals: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RevealError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad reveal ms.
    #[error("reveal_ms must be >= 1")]
    ZeroReveal,
    /// Bad tail.
    #[error("tail must be 0..=8")]
    BadTail,
}

impl SecretReveal {
    /// New.
    pub fn new(reveal_ms: u64, tail: u8) -> Result<Self, RevealError> {
        if reveal_ms == 0 {
            return Err(RevealError::ZeroReveal);
        }
        if tail > 8 {
            return Err(RevealError::BadTail);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            state: State::Masked,
            reveal_ms,
            revealed_at_ms: 0,
            tail,
            reveals: 0,
        })
    }

    /// Reveal.
    pub fn reveal(&mut self, now_ms: u64) {
        if self.state != State::Revealed {
            self.state = State::Revealed;
            self.revealed_at_ms = now_ms;
            self.reveals = self.reveals.saturating_add(1);
        }
    }

    /// Mask explicitly.
    pub fn mask(&mut self) {
        self.state = State::Masked;
    }

    /// Tick — auto-mask after reveal_ms elapsed.
    pub fn tick(&mut self, now_ms: u64) -> State {
        if self.state == State::Revealed
            && now_ms.saturating_sub(self.revealed_at_ms) >= self.reveal_ms
        {
            self.state = State::Masked;
        }
        self.state
    }

    /// Render display for a given secret.
    pub fn masked_display(&self, secret: &str) -> String {
        match self.state {
            State::Revealed => secret.to_string(),
            State::Masked => {
                let chars: Vec<char> = secret.chars().collect();
                let n = chars.len();
                let t = self.tail as usize;
                if n <= t {
                    return secret.to_string();
                }
                let masked = "•".repeat(n - t);
                let tail: String = chars[n - t..].iter().collect();
                format!("{masked}{tail}")
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RevealError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RevealError::SchemaMismatch);
        }
        if self.reveal_ms == 0 {
            return Err(RevealError::ZeroReveal);
        }
        if self.tail > 8 {
            return Err(RevealError::BadTail);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_is_masked() {
        let s = SecretReveal::new(5000, 4).unwrap();
        assert_eq!(s.state, State::Masked);
    }

    #[test]
    fn reveal_then_auto_mask() {
        let mut s = SecretReveal::new(1000, 4).unwrap();
        s.reveal(0);
        assert_eq!(s.state, State::Revealed);
        assert_eq!(s.tick(500), State::Revealed);
        assert_eq!(s.tick(1500), State::Masked);
    }

    #[test]
    fn explicit_mask() {
        let mut s = SecretReveal::new(5000, 4).unwrap();
        s.reveal(0);
        s.mask();
        assert_eq!(s.state, State::Masked);
    }

    #[test]
    fn masked_shows_tail() {
        let s = SecretReveal::new(5000, 4).unwrap();
        assert_eq!(
            s.masked_display("sk-secret-abcdef1234"),
            "••••••••••••••••1234"
        );
    }

    #[test]
    fn revealed_shows_full() {
        let mut s = SecretReveal::new(5000, 4).unwrap();
        s.reveal(0);
        assert_eq!(s.masked_display("abcd1234"), "abcd1234");
    }

    #[test]
    fn short_secret_unchanged() {
        let s = SecretReveal::new(5000, 4).unwrap();
        // Secret shorter than tail → returned as-is.
        assert_eq!(s.masked_display("abc"), "abc");
    }

    #[test]
    fn reveal_counter_increments_once() {
        let mut s = SecretReveal::new(5000, 4).unwrap();
        s.reveal(0);
        s.reveal(100);
        s.reveal(200);
        assert_eq!(s.reveals, 1);
        s.mask();
        s.reveal(300);
        assert_eq!(s.reveals, 2);
    }

    #[test]
    fn bad_inputs_rejected() {
        assert!(matches!(
            SecretReveal::new(0, 4).unwrap_err(),
            RevealError::ZeroReveal
        ));
        assert!(matches!(
            SecretReveal::new(1000, 9).unwrap_err(),
            RevealError::BadTail
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SecretReveal::new(1000, 4).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            RevealError::SchemaMismatch
        ));
    }

    #[test]
    fn reveal_serde_roundtrip() {
        let mut s = SecretReveal::new(1000, 4).unwrap();
        s.reveal(50);
        let j = serde_json::to_string(&s).unwrap();
        let back: SecretReveal = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
