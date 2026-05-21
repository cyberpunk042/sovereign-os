//! `sovereign-cockpit-text-truncation` — char-aware text truncation.
//!
//! Every cockpit row that surfaces a long string (titles, paths,
//! error messages, identifiers) in a narrow column needs the same
//! decision: where does the ellipsis go?
//!
//! Three strategies:
//!   - End:    "the quick brown fox..." (default; preserves start)
//!   - Middle: "the…brown fox" (preserves both ends; good for paths)
//!   - Start:  "...brown fox" (preserves end; good for tail-watching)
//!
//! All strategies operate on CHARS, not bytes — Unicode-safe.
//! The ellipsis itself is a configurable string (default "…");
//! its char count is included in the max-length budget.
//!
//! Standing rule: we do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Truncation strategy.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Strategy {
    /// Truncate the end. Preserves the start.
    End,
    /// Truncate the middle. Preserves both ends.
    Middle,
    /// Truncate the start. Preserves the end.
    Start,
}

/// Errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum TruncationError {
    /// `max_chars` was 0.
    #[error("max_chars must be ≥ 1")]
    InvalidMaxChars,
    /// `ellipsis` itself is longer than `max_chars`.
    #[error("ellipsis longer than max_chars; truncation impossible")]
    EllipsisTooLong,
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// Default ellipsis used when `truncate` is called without one.
pub const DEFAULT_ELLIPSIS: &str = "…";

/// Truncate `input` to at most `max_chars` characters using the
/// given `strategy`, inserting `ellipsis` at the truncation point.
/// If `input.chars().count() <= max_chars`, returns the input
/// unchanged.
///
/// Returns `Err` if `max_chars == 0` or the ellipsis itself
/// exceeds `max_chars`.
pub fn truncate(
    input: &str,
    max_chars: usize,
    strategy: Strategy,
    ellipsis: &str,
) -> Result<String, TruncationError> {
    if max_chars == 0 {
        return Err(TruncationError::InvalidMaxChars);
    }
    let ellipsis_len = ellipsis.chars().count();
    if ellipsis_len >= max_chars {
        return Err(TruncationError::EllipsisTooLong);
    }
    let input_chars: Vec<char> = input.chars().collect();
    if input_chars.len() <= max_chars {
        return Ok(input.to_string());
    }
    let budget = max_chars - ellipsis_len;
    let out = match strategy {
        Strategy::End => {
            let kept: String = input_chars.iter().take(budget).collect();
            format!("{kept}{ellipsis}")
        }
        Strategy::Start => {
            let skip = input_chars.len() - budget;
            let kept: String = input_chars.iter().skip(skip).collect();
            format!("{ellipsis}{kept}")
        }
        Strategy::Middle => {
            let head_len = budget / 2 + (budget % 2);  // bias to head
            let tail_len = budget - head_len;
            let head: String = input_chars.iter().take(head_len).collect();
            let tail: String = input_chars
                .iter()
                .skip(input_chars.len() - tail_len)
                .collect();
            format!("{head}{ellipsis}{tail}")
        }
    };
    Ok(out)
}

/// Truncate with the default ellipsis ("…").
pub fn truncate_default(
    input: &str,
    max_chars: usize,
    strategy: Strategy,
) -> Result<String, TruncationError> {
    truncate(input, max_chars, strategy, DEFAULT_ELLIPSIS)
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), TruncationError> {
    if s != SCHEMA_VERSION {
        return Err(TruncationError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn input_within_budget_passes_through() {
        let r = truncate_default("hello", 10, Strategy::End).unwrap();
        assert_eq!(r, "hello");
    }

    #[test]
    fn input_at_exact_budget_passes_through() {
        let r = truncate_default("hello", 5, Strategy::End).unwrap();
        assert_eq!(r, "hello");
    }

    #[test]
    fn end_strategy_keeps_start_appends_ellipsis() {
        let r = truncate_default("the quick brown fox", 10, Strategy::End).unwrap();
        // budget = 10 - 1 (ellipsis) = 9 chars from start
        assert_eq!(r, "the quick…");
        assert_eq!(r.chars().count(), 10);
    }

    #[test]
    fn start_strategy_keeps_end_prepends_ellipsis() {
        let r = truncate_default("the quick brown fox", 10, Strategy::Start).unwrap();
        // budget = 9 chars from end of 19-char input: skip 10 chars
        // → "rown fox " — wait let me count: "the quick brown fox" has
        // 19 chars; skip 19-9 = 10 chars → starts at char index 10
        // ("brown fox" = 9 chars) → result "…brown fox"
        assert_eq!(r, "…brown fox");
        assert_eq!(r.chars().count(), 10);
    }

    #[test]
    fn middle_strategy_keeps_both_ends() {
        let r = truncate_default("the quick brown fox", 11, Strategy::Middle).unwrap();
        // budget = 11 - 1 = 10; head = 5 (bias), tail = 5
        // "the q" + "…" + "n fox" = "the q…n fox"
        assert_eq!(r, "the q…n fox");
        assert_eq!(r.chars().count(), 11);
    }

    #[test]
    fn unicode_aware_chars_not_bytes() {
        // "héllo" is 5 chars but 6 bytes (é = 2 bytes UTF-8).
        let r = truncate_default("héllo world", 6, Strategy::End).unwrap();
        // budget = 6 - 1 = 5 chars → "héllo" + "…"
        assert_eq!(r, "héllo…");
        assert_eq!(r.chars().count(), 6);
    }

    #[test]
    fn custom_ellipsis_three_dots() {
        let r = truncate("the quick brown fox", 10, Strategy::End, "...").unwrap();
        // budget = 10 - 3 = 7 chars
        assert_eq!(r, "the qui...");
        assert_eq!(r.chars().count(), 10);
    }

    #[test]
    fn zero_max_chars_is_invalid() {
        let r = truncate_default("hello", 0, Strategy::End);
        assert_eq!(r.unwrap_err(), TruncationError::InvalidMaxChars);
    }

    #[test]
    fn ellipsis_longer_than_budget_is_invalid() {
        let r = truncate("hello", 2, Strategy::End, "...");
        assert_eq!(r.unwrap_err(), TruncationError::EllipsisTooLong);
    }

    #[test]
    fn ellipsis_equal_to_budget_is_invalid() {
        // ellipsis length must be STRICTLY less than max_chars.
        let r = truncate("hello", 3, Strategy::End, "...");
        assert_eq!(r.unwrap_err(), TruncationError::EllipsisTooLong);
    }

    #[test]
    fn empty_input_passes_through() {
        let r = truncate_default("", 10, Strategy::End).unwrap();
        assert_eq!(r, "");
    }

    #[test]
    fn middle_with_odd_budget_biases_to_head() {
        // budget=5: head=3, tail=2 — head bias makes prefix more
        // recognizable at-a-glance.
        let r = truncate_default("abcdefghij", 6, Strategy::Middle).unwrap();
        // head=3, ellipsis=1, tail=2: "abc…ij"
        assert_eq!(r, "abc…ij");
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            TruncationError::SchemaMismatch
        ));
    }

    #[test]
    fn strategy_serde_roundtrip() {
        for s in [Strategy::End, Strategy::Middle, Strategy::Start] {
            let j = serde_json::to_string(&s).unwrap();
            let back: Strategy = serde_json::from_str(&j).unwrap();
            assert_eq!(s, back);
        }
    }
}
