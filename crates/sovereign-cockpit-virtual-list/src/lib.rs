//! `sovereign-cockpit-virtual-list` — viewport-window virtualization state.
//!
//! Caller passes (total_items, viewport_height_px, row_height_px,
//! scroll_top_px). Returns (first_visible_index, visible_count). Pure
//! arithmetic — no I/O.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct VirtualListState {
    /// Schema version.
    pub schema_version: String,
    /// Total items in the list.
    pub total_items: u32,
    /// Row height (px).
    pub row_height_px: u16,
    /// Viewport height (px).
    pub viewport_height_px: u16,
    /// Current scroll offset (px).
    pub scroll_top_px: u32,
    /// Overscan rows above + below visible.
    pub overscan_rows: u8,
}

/// Visible range (first_index, count).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct VisibleRange {
    /// First visible item index.
    pub first_index: u32,
    /// Number of items to render.
    pub count: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum VirtualListError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero row height.
    #[error("row_height_px zero")]
    ZeroRowHeight,
    /// Zero viewport height.
    #[error("viewport_height_px zero")]
    ZeroViewport,
}

impl VirtualListState {
    /// Default state.
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            total_items: 0,
            row_height_px: 36,
            viewport_height_px: 600,
            scroll_top_px: 0,
            overscan_rows: 3,
        }
    }

    /// Compute the visible range.
    pub fn visible(&self) -> Result<VisibleRange, VirtualListError> {
        if self.row_height_px == 0 { return Err(VirtualListError::ZeroRowHeight); }
        if self.viewport_height_px == 0 { return Err(VirtualListError::ZeroViewport); }
        let row_h = self.row_height_px as u32;
        let viewport_rows = (self.viewport_height_px as u32 / row_h).max(1);
        let first = (self.scroll_top_px / row_h).min(self.total_items);
        let overscan = self.overscan_rows as u32;
        let first_with_overscan = first.saturating_sub(overscan);
        let last_with_overscan = first + viewport_rows + overscan;
        let last_index = last_with_overscan.min(self.total_items);
        let count = if last_index > first_with_overscan {
            last_index - first_with_overscan
        } else { 0 };
        Ok(VisibleRange { first_index: first_with_overscan, count })
    }

    /// Total height of the list (px).
    pub fn total_height_px(&self) -> u32 {
        self.total_items * self.row_height_px as u32
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), VirtualListError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(VirtualListError::SchemaMismatch);
        }
        if self.row_height_px == 0 { return Err(VirtualListError::ZeroRowHeight); }
        if self.viewport_height_px == 0 { return Err(VirtualListError::ZeroViewport); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        VirtualListState::default_state().validate().unwrap();
    }

    #[test]
    fn empty_list_zero_count() {
        let s = VirtualListState::default_state();
        let v = s.visible().unwrap();
        assert_eq!(v.count, 0);
    }

    #[test]
    fn top_of_list_includes_overscan() {
        let mut s = VirtualListState::default_state();
        s.total_items = 1000;
        // viewport_height=600, row_height=36 → 16 rows visible.
        // scroll_top=0 → first=0, overscan=3 → first_with_overscan=0, last=16+3=19.
        let v = s.visible().unwrap();
        assert_eq!(v.first_index, 0);
        assert!(v.count >= 16 + 3);
    }

    #[test]
    fn middle_of_list_overscan_both_sides() {
        let mut s = VirtualListState::default_state();
        s.total_items = 1000;
        s.scroll_top_px = 360; // 10 rows down
        let v = s.visible().unwrap();
        // first=10, overscan=3 → first_with_overscan=7.
        assert_eq!(v.first_index, 7);
    }

    #[test]
    fn end_of_list_capped() {
        let mut s = VirtualListState::default_state();
        s.total_items = 20;
        s.scroll_top_px = 10_000; // way past end
        let v = s.visible().unwrap();
        assert!(v.first_index <= s.total_items);
    }

    #[test]
    fn total_height_computed() {
        let mut s = VirtualListState::default_state();
        s.total_items = 100;
        // row_h=36 → 3600 px total.
        assert_eq!(s.total_height_px(), 3600);
    }

    #[test]
    fn zero_row_height_rejected() {
        let mut s = VirtualListState::default_state();
        s.row_height_px = 0;
        assert!(matches!(s.validate().unwrap_err(), VirtualListError::ZeroRowHeight));
        assert!(matches!(s.visible().unwrap_err(), VirtualListError::ZeroRowHeight));
    }

    #[test]
    fn zero_viewport_rejected() {
        let mut s = VirtualListState::default_state();
        s.viewport_height_px = 0;
        assert!(matches!(s.validate().unwrap_err(), VirtualListError::ZeroViewport));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = VirtualListState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), VirtualListError::SchemaMismatch));
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = VirtualListState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: VirtualListState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
