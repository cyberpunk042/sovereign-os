//! `sovereign-cockpit-input-mask` — formatted-input mask.
//!
//! Given a mask string and the raw character stream the user has
//! typed, `apply()` returns:
//!   * `rendered` — the mask applied (e.g. `"514-555-12  "`),
//!   * `raw` — only the captured user chars (e.g. `"5145551200"`),
//!   * `complete` — true if every mask slot is filled.
//!
//! Mask chars:
//!   * `#` — exactly one ASCII digit `0..=9`
//!   * `A` — exactly one ASCII letter `A..=Z` / `a..=z`
//!   * `*` — exactly one digit OR letter
//!   * any other char — literal placeholder (always rendered)
//!
//! Input chars that don't match the next slot are dropped.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Result of applying a mask.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MaskResult {
    /// Rendered string, including mask literals for unfilled slots.
    pub rendered: String,
    /// Just the captured chars.
    pub raw: String,
    /// All slots filled?
    pub complete: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InputMask {
    /// Schema version.
    pub schema_version: String,
    /// Mask string.
    pub mask: String,
    /// Char placed in unfilled slots when rendering (default space).
    pub placeholder_char: char,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MaskError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty mask.
    #[error("mask empty")]
    EmptyMask,
}

impl InputMask {
    /// New.
    pub fn new(mask: &str, placeholder_char: char) -> Result<Self, MaskError> {
        if mask.is_empty() { return Err(MaskError::EmptyMask); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            mask: mask.into(),
            placeholder_char,
        })
    }

    /// Apply input.
    pub fn apply(&self, input: &str) -> MaskResult {
        let mut input_iter = input.chars().peekable();
        let mut rendered = String::with_capacity(self.mask.len());
        let mut raw = String::new();
        let mut filled_slots = 0usize;
        let mut total_slots = 0usize;
        for mc in self.mask.chars() {
            match mc {
                '#' | 'A' | '*' => {
                    total_slots += 1;
                    let mut placed = false;
                    while let Some(&c) = input_iter.peek() {
                        let ok = match mc {
                            '#' => c.is_ascii_digit(),
                            'A' => c.is_ascii_alphabetic(),
                            '*' => c.is_ascii_alphanumeric(),
                            _ => false,
                        };
                        input_iter.next();
                        if ok {
                            rendered.push(c);
                            raw.push(c);
                            filled_slots += 1;
                            placed = true;
                            break;
                        }
                    }
                    if !placed {
                        rendered.push(self.placeholder_char);
                    }
                }
                literal => {
                    rendered.push(literal);
                    // If user typed the literal verbatim, skip it.
                    if input_iter.peek().copied() == Some(literal) {
                        input_iter.next();
                    }
                }
            }
        }
        MaskResult { rendered, raw, complete: filled_slots == total_slots }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MaskError> {
        if self.schema_version != SCHEMA_VERSION { return Err(MaskError::SchemaMismatch); }
        if self.mask.is_empty() { return Err(MaskError::EmptyMask); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_mask_rejected() {
        assert!(matches!(InputMask::new("", ' ').unwrap_err(), MaskError::EmptyMask));
    }

    #[test]
    fn phone_partial() {
        let m = InputMask::new("###-###-####", ' ').unwrap();
        let r = m.apply("5145");
        assert_eq!(r.rendered, "514-5  -    ");
        assert_eq!(r.raw, "5145");
        assert!(!r.complete);
    }

    #[test]
    fn phone_complete() {
        let m = InputMask::new("###-###-####", ' ').unwrap();
        let r = m.apply("5145551234");
        assert_eq!(r.rendered, "514-555-1234");
        assert_eq!(r.raw, "5145551234");
        assert!(r.complete);
    }

    #[test]
    fn skips_user_typed_literal() {
        let m = InputMask::new("###-###-####", ' ').unwrap();
        let r = m.apply("514-555-1234");
        assert_eq!(r.rendered, "514-555-1234");
        assert!(r.complete);
    }

    #[test]
    fn drops_non_matching_chars() {
        let m = InputMask::new("###-###-####", ' ').unwrap();
        let r = m.apply("abc5145551234");
        assert_eq!(r.raw, "5145551234");
    }

    #[test]
    fn letter_slot() {
        let m = InputMask::new("AA-##", ' ').unwrap();
        let r = m.apply("qc12");
        assert_eq!(r.rendered, "qc-12");
        assert!(r.complete);
    }

    #[test]
    fn star_slot_accepts_either() {
        let m = InputMask::new("***", ' ').unwrap();
        let r = m.apply("a1B");
        assert_eq!(r.rendered, "a1B");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = InputMask::new("##", ' ').unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), MaskError::SchemaMismatch));
    }

    #[test]
    fn mask_serde_roundtrip() {
        let m = InputMask::new("###-###-####", '_').unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: InputMask = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
