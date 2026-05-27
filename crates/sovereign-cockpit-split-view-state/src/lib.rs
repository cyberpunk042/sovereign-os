//! `sovereign-cockpit-split-view-state` — split pane state.
//!
//! Orientation Horizontal (top/bottom) or Vertical (left/right).
//! `ratio` in basis points (0..=10000) splits between primary/
//! secondary. `collapsed` hides secondary entirely; min sizes
//! clamp how small either side can shrink.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Orientation.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Orientation {
    /// Horizontal: top/bottom.
    Horizontal,
    /// Vertical: left/right.
    Vertical,
}

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct SplitViewState {
    /// Schema version marker.
    pub schema_version_marker: u32,
    /// Orientation.
    pub orientation: Orientation,
    /// Ratio in basis points (primary share).
    pub ratio_bp: u32,
    /// Collapsed (only primary visible).
    pub collapsed: bool,
    /// Min ratio bp (primary minimum).
    pub min_primary_bp: u32,
    /// Min ratio bp (secondary minimum).
    pub min_secondary_bp: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SplitError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad bp.
    #[error("ratio_bp must be 0..=10000")]
    BadRatio,
    /// Min sum > 10000.
    #[error("min_primary_bp ({p}) + min_secondary_bp ({s}) > 10000")]
    BadMins {
        /// p.
        p: u32,
        /// s.
        s: u32,
    },
}

impl SplitViewState {
    /// New.
    pub fn new(orientation: Orientation, ratio_bp: u32) -> Result<Self, SplitError> {
        if ratio_bp > 10000 {
            return Err(SplitError::BadRatio);
        }
        Ok(Self {
            schema_version_marker: 1,
            orientation,
            ratio_bp,
            collapsed: false,
            min_primary_bp: 1000,
            min_secondary_bp: 1000,
        })
    }

    /// Set ratio, clamped to [min_primary, 10000 - min_secondary].
    pub fn set_ratio(&mut self, ratio_bp: u32) -> Result<(), SplitError> {
        if ratio_bp > 10000 {
            return Err(SplitError::BadRatio);
        }
        let lo = self.min_primary_bp;
        let hi = 10000u32.saturating_sub(self.min_secondary_bp);
        self.ratio_bp = ratio_bp.clamp(lo, hi);
        Ok(())
    }

    /// Set mins. Each is bp; sum must be ≤ 10000.
    pub fn set_mins(&mut self, primary_bp: u32, secondary_bp: u32) -> Result<(), SplitError> {
        if primary_bp.saturating_add(secondary_bp) > 10000 {
            return Err(SplitError::BadMins {
                p: primary_bp,
                s: secondary_bp,
            });
        }
        self.min_primary_bp = primary_bp;
        self.min_secondary_bp = secondary_bp;
        // Re-clamp current ratio.
        let lo = self.min_primary_bp;
        let hi = 10000u32.saturating_sub(self.min_secondary_bp);
        self.ratio_bp = self.ratio_bp.clamp(lo, hi);
        Ok(())
    }

    /// Toggle collapsed.
    pub fn set_collapsed(&mut self, collapsed: bool) {
        self.collapsed = collapsed;
    }

    /// Switch orientation (preserves ratio).
    pub fn set_orientation(&mut self, orientation: Orientation) {
        self.orientation = orientation;
    }

    /// Effective primary bp considering collapsed.
    pub fn effective_primary_bp(&self) -> u32 {
        if self.collapsed { 10000 } else { self.ratio_bp }
    }

    /// Effective secondary bp.
    pub fn effective_secondary_bp(&self) -> u32 {
        10000u32.saturating_sub(self.effective_primary_bp())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SplitError> {
        if self.schema_version_marker != 1 {
            return Err(SplitError::SchemaMismatch);
        }
        if self.ratio_bp > 10000 {
            return Err(SplitError::BadRatio);
        }
        if self.min_primary_bp.saturating_add(self.min_secondary_bp) > 10000 {
            return Err(SplitError::BadMins {
                p: self.min_primary_bp,
                s: self.min_secondary_bp,
            });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_basic() {
        let s = SplitViewState::new(Orientation::Vertical, 5000).unwrap();
        assert_eq!(s.orientation, Orientation::Vertical);
        assert_eq!(s.ratio_bp, 5000);
    }

    #[test]
    fn ratio_clamps_to_mins() {
        let mut s = SplitViewState::new(Orientation::Vertical, 5000).unwrap();
        s.set_ratio(500).unwrap();
        // min_primary_bp default 1000.
        assert_eq!(s.ratio_bp, 1000);
        s.set_ratio(9500).unwrap();
        // hi = 10000 - 1000 = 9000.
        assert_eq!(s.ratio_bp, 9000);
    }

    #[test]
    fn set_mins_reclamps() {
        let mut s = SplitViewState::new(Orientation::Vertical, 5000).unwrap();
        s.set_mins(4000, 4000).unwrap();
        // Now lo=4000, hi=6000; previous ratio 5000 stays.
        s.set_mins(5500, 5500).unwrap_err(); // sum 11000
        s.set_mins(6000, 3000).unwrap();
        // lo=6000, hi=7000; ratio clamps up to 6000.
        assert_eq!(s.ratio_bp, 6000);
    }

    #[test]
    fn collapsed_overrides() {
        let mut s = SplitViewState::new(Orientation::Vertical, 5000).unwrap();
        s.set_collapsed(true);
        assert_eq!(s.effective_primary_bp(), 10000);
        assert_eq!(s.effective_secondary_bp(), 0);
    }

    #[test]
    fn bad_ratio_rejected() {
        let s = SplitViewState::new(Orientation::Vertical, 10001);
        assert!(matches!(s.unwrap_err(), SplitError::BadRatio));
    }

    #[test]
    fn bad_mins_rejected() {
        let mut s = SplitViewState::new(Orientation::Vertical, 5000).unwrap();
        assert!(matches!(
            s.set_mins(6000, 5000).unwrap_err(),
            SplitError::BadMins { .. }
        ));
    }

    #[test]
    fn orientation_change_preserves_ratio() {
        let mut s = SplitViewState::new(Orientation::Vertical, 7000).unwrap();
        s.set_orientation(Orientation::Horizontal);
        assert_eq!(s.ratio_bp, 7000);
        assert_eq!(s.orientation, Orientation::Horizontal);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SplitViewState::new(Orientation::Vertical, 5000).unwrap();
        s.schema_version_marker = 99;
        assert!(matches!(
            s.validate().unwrap_err(),
            SplitError::SchemaMismatch
        ));
    }

    #[test]
    fn split_serde_roundtrip() {
        let s = SplitViewState::new(Orientation::Horizontal, 3000).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SplitViewState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
