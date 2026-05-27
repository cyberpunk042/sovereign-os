//! `sovereign-cockpit-collapsible-region` — single-region collapse.
//!
//! Distinct from accordion (multi-region group). Single region with
//! optional auto-expand-on-content-arrival behavior.
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
pub struct CollapsibleRegion {
    /// Schema version.
    pub schema_version: String,
    /// Stable id.
    pub id: String,
    /// Currently expanded?
    pub expanded: bool,
    /// Auto-expand when content arrives?
    pub prefer_expanded_when_filled: bool,
    /// Last observed content height (used to detect newly-filled).
    pub content_height_px: u32,
    /// Operator manually toggled? (sticky against auto-expand).
    pub manual_override: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RegionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("region id empty")]
    EmptyId,
}

impl CollapsibleRegion {
    /// New.
    pub fn new(id: &str, prefer_expanded_when_filled: bool) -> Result<Self, RegionError> {
        if id.is_empty() {
            return Err(RegionError::EmptyId);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            id: id.into(),
            expanded: false,
            prefer_expanded_when_filled,
            content_height_px: 0,
            manual_override: false,
        })
    }

    /// Operator toggle (sets manual_override).
    pub fn toggle(&mut self) {
        self.expanded = !self.expanded;
        self.manual_override = true;
    }

    /// Set content height. May auto-expand if prefer + no manual override.
    pub fn set_content_height(&mut self, h_px: u32) {
        let was_empty = self.content_height_px == 0;
        self.content_height_px = h_px;
        if was_empty && h_px > 0 && self.prefer_expanded_when_filled && !self.manual_override {
            self.expanded = true;
        }
    }

    /// Reset manual_override flag (e.g., when route changes).
    pub fn reset_override(&mut self) {
        self.manual_override = false;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RegionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RegionError::SchemaMismatch);
        }
        if self.id.is_empty() {
            return Err(RegionError::EmptyId);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_id_rejected() {
        assert!(matches!(
            CollapsibleRegion::new("", false).unwrap_err(),
            RegionError::EmptyId
        ));
    }

    #[test]
    fn initial_collapsed() {
        let r = CollapsibleRegion::new("a", false).unwrap();
        assert!(!r.expanded);
    }

    #[test]
    fn toggle_flips_and_marks_override() {
        let mut r = CollapsibleRegion::new("a", true).unwrap();
        r.toggle();
        assert!(r.expanded);
        assert!(r.manual_override);
        r.toggle();
        assert!(!r.expanded);
    }

    #[test]
    fn auto_expand_when_filled() {
        let mut r = CollapsibleRegion::new("a", true).unwrap();
        r.set_content_height(100);
        assert!(r.expanded);
    }

    #[test]
    fn auto_expand_only_first_fill() {
        let mut r = CollapsibleRegion::new("a", true).unwrap();
        r.set_content_height(100);
        r.toggle(); // collapse manually
        r.set_content_height(200);
        // No auto-re-expand because was already non-empty.
        assert!(!r.expanded);
    }

    #[test]
    fn manual_override_blocks_auto_expand() {
        let mut r = CollapsibleRegion::new("a", true).unwrap();
        r.toggle();
        r.toggle(); // back to collapsed but manual_override = true
        r.set_content_height(100);
        // Manual override blocks auto expand.
        assert!(!r.expanded);
    }

    #[test]
    fn no_auto_expand_when_prefer_off() {
        let mut r = CollapsibleRegion::new("a", false).unwrap();
        r.set_content_height(100);
        assert!(!r.expanded);
    }

    #[test]
    fn reset_override_allows_future_auto() {
        let mut r = CollapsibleRegion::new("a", true).unwrap();
        r.toggle();
        r.toggle(); // manual_override on but collapsed
        r.reset_override();
        // Reset content to 0 then refill.
        r.content_height_px = 0;
        r.set_content_height(100);
        assert!(r.expanded);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = CollapsibleRegion::new("a", false).unwrap();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RegionError::SchemaMismatch
        ));
    }

    #[test]
    fn region_serde_roundtrip() {
        let r = CollapsibleRegion::new("a", true).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: CollapsibleRegion = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
