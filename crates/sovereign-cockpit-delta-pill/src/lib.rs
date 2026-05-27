//! `sovereign-cockpit-delta-pill` — colored delta pill.
//!
//! Given current + prior values, render a Pill{direction, label,
//! magnitude_bp}. direction = Up if delta > flat_threshold,
//! Down if delta < -flat_threshold, else Flat. magnitude_bp is
//! abs(delta)/prior in basis points (0 if prior == 0).
//!
//! Direction-color reflects "higher = better" by default;
//! invert_polarity flips Up/Down semantics for metrics where
//! "higher = worse" (e.g. error-rate).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Direction.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Direction {
    /// Up.
    Up,
    /// Flat.
    Flat,
    /// Down.
    Down,
}

/// Sentiment.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Sentiment {
    /// Positive (green).
    Positive,
    /// Neutral.
    Neutral,
    /// Negative (red).
    Negative,
}

/// Pill.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pill {
    /// Direction.
    pub direction: Direction,
    /// Sentiment (post-polarity).
    pub sentiment: Sentiment,
    /// Display label e.g. "+12%" or "-3%".
    pub label: String,
    /// Magnitude in basis points (0..=10000).
    pub magnitude_bp: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DeltaError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// Compute pill from current/prior i64.
pub fn render(current: i64, prior: i64, flat_threshold: i64, invert_polarity: bool) -> Pill {
    let delta = current - prior;
    let direction = if delta > flat_threshold {
        Direction::Up
    } else if delta < -flat_threshold {
        Direction::Down
    } else {
        Direction::Flat
    };
    let sentiment = match (direction, invert_polarity) {
        (Direction::Up, false) => Sentiment::Positive,
        (Direction::Down, false) => Sentiment::Negative,
        (Direction::Up, true) => Sentiment::Negative,
        (Direction::Down, true) => Sentiment::Positive,
        (Direction::Flat, _) => Sentiment::Neutral,
    };
    let magnitude_bp = if prior == 0 {
        0
    } else {
        let abs = (delta.unsigned_abs() as u128) * 10_000 / (prior.unsigned_abs() as u128);
        abs.min(u32::MAX as u128) as u32
    };
    let label = if delta > 0 {
        format!("+{}", delta)
    } else {
        format!("{}", delta)
    };
    Pill {
        direction,
        sentiment,
        label,
        magnitude_bp,
    }
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), DeltaError> {
    if s != SCHEMA_VERSION {
        return Err(DeltaError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn up_no_invert_positive() {
        let p = render(120, 100, 0, false);
        assert_eq!(p.direction, Direction::Up);
        assert_eq!(p.sentiment, Sentiment::Positive);
        assert_eq!(p.magnitude_bp, 2000);
        assert_eq!(p.label, "+20");
    }

    #[test]
    fn down_no_invert_negative() {
        let p = render(80, 100, 0, false);
        assert_eq!(p.direction, Direction::Down);
        assert_eq!(p.sentiment, Sentiment::Negative);
        assert_eq!(p.magnitude_bp, 2000);
    }

    #[test]
    fn flat_within_threshold() {
        let p = render(102, 100, 5, false);
        assert_eq!(p.direction, Direction::Flat);
        assert_eq!(p.sentiment, Sentiment::Neutral);
    }

    #[test]
    fn invert_polarity_flips_sentiment() {
        let p = render(120, 100, 0, true);
        // Up but inverted = bad (error-rate ↑).
        assert_eq!(p.sentiment, Sentiment::Negative);
        let p2 = render(80, 100, 0, true);
        assert_eq!(p2.sentiment, Sentiment::Positive);
    }

    #[test]
    fn prior_zero_no_magnitude() {
        let p = render(10, 0, 0, false);
        assert_eq!(p.magnitude_bp, 0);
        assert_eq!(p.direction, Direction::Up);
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            DeltaError::SchemaMismatch
        ));
    }

    #[test]
    fn pill_serde_roundtrip() {
        let p = render(120, 100, 0, false);
        let j = serde_json::to_string(&p).unwrap();
        let back: Pill = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
