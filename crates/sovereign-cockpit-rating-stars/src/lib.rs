//! `sovereign-cockpit-rating-stars` — star-rating widget state.
//!
//! N-star scale with optional half-star granularity. Value is in
//! half-star units (0..=2N when half_stars, else 0..=N stored as
//! `value_halves`). `allow_clear`: clicking the active star clears
//! the rating. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RatingStars {
    /// Schema version.
    pub schema_version: String,
    /// Star count (3, 5, 7, or 10).
    pub star_count: u8,
    /// Half-star granularity?
    pub half_stars: bool,
    /// Current value in half-star units (0..=2*star_count if half_stars, else even values 0..=2*star_count).
    pub value_halves: u8,
    /// Clicking the active star clears?
    pub allow_clear: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RatingError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad star count.
    #[error("star_count {0} not in {{3,5,7,10}}")]
    BadStarCount(u8),
    /// Value out of range.
    #[error("value {value} out of [0, {max}]")]
    ValueOutOfRange {
        /// value.
        value: u8,
        /// max.
        max: u8,
    },
    /// Odd value with half_stars off.
    #[error("value {0} is odd but half_stars is off")]
    OddValueWithoutHalves(u8),
    /// Out-of-range star index in click.
    #[error("clicked star {clicked} out of [1, {max}]")]
    BadClickStar {
        /// clicked.
        clicked: u8,
        /// max.
        max: u8,
    },
}

impl RatingStars {
    /// New.
    pub fn new(star_count: u8, half_stars: bool, allow_clear: bool) -> Result<Self, RatingError> {
        if !matches!(star_count, 3 | 5 | 7 | 10) {
            return Err(RatingError::BadStarCount(star_count));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            star_count,
            half_stars,
            value_halves: 0,
            allow_clear,
        })
    }

    /// Click star N (1-based). If half_click is true and half_stars enabled,
    /// sets to N-half; else sets to N full. When N equals current full
    /// and `allow_clear`, clears.
    pub fn click(&mut self, star: u8, half_click: bool) -> Result<u8, RatingError> {
        if star == 0 || star > self.star_count {
            return Err(RatingError::BadClickStar {
                clicked: star,
                max: self.star_count,
            });
        }
        let target_halves: u8 = if half_click && self.half_stars {
            star * 2 - 1
        } else {
            star * 2
        };
        if self.allow_clear && self.value_halves == target_halves {
            self.value_halves = 0;
        } else {
            self.value_halves = target_halves;
        }
        Ok(self.value_halves)
    }

    /// Whole-star value (rounds down).
    pub fn whole(&self) -> u8 {
        self.value_halves / 2
    }

    /// Has half-star?
    pub fn has_half(&self) -> bool {
        self.value_halves % 2 == 1
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RatingError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RatingError::SchemaMismatch);
        }
        if !matches!(self.star_count, 3 | 5 | 7 | 10) {
            return Err(RatingError::BadStarCount(self.star_count));
        }
        let max = self.star_count * 2;
        if self.value_halves > max {
            return Err(RatingError::ValueOutOfRange {
                value: self.value_halves,
                max,
            });
        }
        if !self.half_stars && !self.value_halves.is_multiple_of(2) {
            return Err(RatingError::OddValueWithoutHalves(self.value_halves));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bad_star_count_rejected() {
        assert!(matches!(
            RatingStars::new(4, false, false).unwrap_err(),
            RatingError::BadStarCount(4)
        ));
        assert!(matches!(
            RatingStars::new(6, false, false).unwrap_err(),
            RatingError::BadStarCount(6)
        ));
    }

    #[test]
    fn click_sets_full_value() {
        let mut r = RatingStars::new(5, false, false).unwrap();
        r.click(3, false).unwrap();
        assert_eq!(r.whole(), 3);
        assert!(!r.has_half());
    }

    #[test]
    fn click_half_only_when_enabled() {
        let mut r = RatingStars::new(5, true, false).unwrap();
        r.click(3, true).unwrap();
        assert_eq!(r.whole(), 2);
        assert!(r.has_half());
    }

    #[test]
    fn half_click_ignored_when_disabled() {
        let mut r = RatingStars::new(5, false, false).unwrap();
        r.click(3, true).unwrap();
        assert!(!r.has_half());
        assert_eq!(r.whole(), 3);
    }

    #[test]
    fn click_active_clears_when_allowed() {
        let mut r = RatingStars::new(5, false, true).unwrap();
        r.click(3, false).unwrap();
        r.click(3, false).unwrap();
        assert_eq!(r.value_halves, 0);
    }

    #[test]
    fn click_active_no_clear_when_disallowed() {
        let mut r = RatingStars::new(5, false, false).unwrap();
        r.click(3, false).unwrap();
        r.click(3, false).unwrap();
        assert_eq!(r.whole(), 3);
    }

    #[test]
    fn bad_click_star_rejected() {
        let mut r = RatingStars::new(5, false, false).unwrap();
        assert!(matches!(
            r.click(0, false).unwrap_err(),
            RatingError::BadClickStar { .. }
        ));
        assert!(matches!(
            r.click(6, false).unwrap_err(),
            RatingError::BadClickStar { .. }
        ));
    }

    #[test]
    fn validate_value_out_of_range_rejected() {
        let mut r = RatingStars::new(5, true, false).unwrap();
        r.value_halves = 11;
        assert!(matches!(
            r.validate().unwrap_err(),
            RatingError::ValueOutOfRange { .. }
        ));
    }

    #[test]
    fn validate_odd_value_without_halves_rejected() {
        let mut r = RatingStars::new(5, false, false).unwrap();
        r.value_halves = 3;
        assert!(matches!(
            r.validate().unwrap_err(),
            RatingError::OddValueWithoutHalves(3)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = RatingStars::new(5, false, false).unwrap();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RatingError::SchemaMismatch
        ));
    }

    #[test]
    fn rating_serde_roundtrip() {
        let mut r = RatingStars::new(10, true, true).unwrap();
        r.click(7, true).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: RatingStars = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
