//! `sovereign-cockpit-row-hover-affordance` — reveal row actions.
//!
//! Two independent inputs each select at most one row: pointer hover
//! and keyboard focus. visible(row) returns true if EITHER selects
//! the row OR sticky_pinned_row equals it. sticky_pin allows a
//! "pin this row's actions" interaction (e.g. menu opened).
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
pub struct RowHoverAffordance {
    /// Schema version.
    pub schema_version: String,
    /// Row currently hovered by pointer, if any.
    pub hovered_row: Option<String>,
    /// Row currently focused, if any.
    pub focused_row: Option<String>,
    /// Row pinned (e.g. menu open), if any.
    pub pinned_row: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HoverError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("row id empty")]
    EmptyRow,
}

impl RowHoverAffordance {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            hovered_row: None,
            focused_row: None,
            pinned_row: None,
        }
    }

    /// Pointer entered a row.
    pub fn hover(&mut self, row: &str) -> Result<(), HoverError> {
        if row.is_empty() {
            return Err(HoverError::EmptyRow);
        }
        self.hovered_row = Some(row.into());
        Ok(())
    }

    /// Pointer left all rows.
    pub fn unhover(&mut self) {
        self.hovered_row = None;
    }

    /// Focus moved into a row.
    pub fn focus(&mut self, row: &str) -> Result<(), HoverError> {
        if row.is_empty() {
            return Err(HoverError::EmptyRow);
        }
        self.focused_row = Some(row.into());
        Ok(())
    }

    /// Focus moved out.
    pub fn blur(&mut self) {
        self.focused_row = None;
    }

    /// Pin a row's affordances visible (e.g. opened action menu).
    pub fn pin(&mut self, row: &str) -> Result<(), HoverError> {
        if row.is_empty() {
            return Err(HoverError::EmptyRow);
        }
        self.pinned_row = Some(row.into());
        Ok(())
    }

    /// Unpin.
    pub fn unpin(&mut self) {
        self.pinned_row = None;
    }

    /// Should affordance be visible for this row?
    pub fn visible(&self, row: &str) -> bool {
        self.hovered_row.as_deref() == Some(row)
            || self.focused_row.as_deref() == Some(row)
            || self.pinned_row.as_deref() == Some(row)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HoverError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HoverError::SchemaMismatch);
        }
        for r in [&self.hovered_row, &self.focused_row, &self.pinned_row] {
            if let Some(s) = r
                && s.is_empty()
            {
                return Err(HoverError::EmptyRow);
            }
        }
        Ok(())
    }
}

impl Default for RowHoverAffordance {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hover_shows() {
        let mut s = RowHoverAffordance::new();
        s.hover("r1").unwrap();
        assert!(s.visible("r1"));
        assert!(!s.visible("r2"));
    }

    #[test]
    fn focus_shows() {
        let mut s = RowHoverAffordance::new();
        s.focus("r2").unwrap();
        assert!(s.visible("r2"));
    }

    #[test]
    fn pin_persists_across_unhover() {
        let mut s = RowHoverAffordance::new();
        s.hover("r1").unwrap();
        s.pin("r1").unwrap();
        s.unhover();
        assert!(s.visible("r1"));
    }

    #[test]
    fn multiple_rows_independent() {
        let mut s = RowHoverAffordance::new();
        s.hover("r1").unwrap();
        s.focus("r2").unwrap();
        assert!(s.visible("r1"));
        assert!(s.visible("r2"));
        assert!(!s.visible("r3"));
    }

    #[test]
    fn unpin_clears() {
        let mut s = RowHoverAffordance::new();
        s.pin("r1").unwrap();
        s.unpin();
        assert!(!s.visible("r1"));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = RowHoverAffordance::new();
        assert!(matches!(s.hover("").unwrap_err(), HoverError::EmptyRow));
        assert!(matches!(s.focus("").unwrap_err(), HoverError::EmptyRow));
        assert!(matches!(s.pin("").unwrap_err(), HoverError::EmptyRow));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = RowHoverAffordance::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            HoverError::SchemaMismatch
        ));
    }

    #[test]
    fn affordance_serde_roundtrip() {
        let mut s = RowHoverAffordance::new();
        s.hover("r1").unwrap();
        s.pin("r2").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: RowHoverAffordance = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
