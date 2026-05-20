//! `sovereign-cockpit-virtual-tree-window` — virtualized tree.
//!
//! Operates on a flat row index over an externally-flattened tree
//! (depth-first per the consumer). Holds total_rows + visible
//! window (first, count). `set_total(n)` updates row count; if the
//! current window starts past `n`, it snaps. `scroll_to(row)` moves
//! window so row is in view; `scroll_by(delta)` adjusts.
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
pub struct VirtualTreeWindow {
    /// Schema version (encoded in a separate marker).
    pub schema_version_marker: u32,
    /// Total rows.
    pub total_rows: u64,
    /// First visible row.
    pub first_visible: u64,
    /// Window size (visible row count).
    pub window: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum WindowError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero window.
    #[error("window must be >= 1")]
    ZeroWindow,
}

impl VirtualTreeWindow {
    /// New.
    pub fn new(window: u64) -> Result<Self, WindowError> {
        if window == 0 { return Err(WindowError::ZeroWindow); }
        Ok(Self {
            schema_version_marker: 1,
            total_rows: 0,
            first_visible: 0,
            window,
        })
    }

    /// Set total rows.
    pub fn set_total(&mut self, n: u64) {
        self.total_rows = n;
        // Snap if window would extend past end (but keep first ≥ 0).
        if self.first_visible >= n.max(1) {
            self.first_visible = if n == 0 { 0 } else { n.saturating_sub(self.window) };
        }
    }

    /// Scroll so `row` is in view (centred if possible).
    pub fn scroll_to(&mut self, row: u64) {
        if row < self.first_visible {
            self.first_visible = row;
        } else if row >= self.first_visible.saturating_add(self.window) {
            self.first_visible = row.saturating_sub(self.window.saturating_sub(1));
        }
        self.clamp();
    }

    /// Scroll by signed delta.
    pub fn scroll_by(&mut self, delta: i64) {
        if delta >= 0 {
            self.first_visible = self.first_visible.saturating_add(delta as u64);
        } else {
            self.first_visible = self.first_visible.saturating_sub((-delta) as u64);
        }
        self.clamp();
    }

    /// Last visible row (exclusive).
    pub fn end_visible(&self) -> u64 {
        self.first_visible.saturating_add(self.window).min(self.total_rows)
    }

    /// Is row in window?
    pub fn is_visible(&self, row: u64) -> bool {
        row >= self.first_visible && row < self.end_visible()
    }

    /// Window size used (may shrink at the bottom).
    pub fn visible_count(&self) -> u64 {
        self.end_visible().saturating_sub(self.first_visible)
    }

    fn clamp(&mut self) {
        if self.total_rows == 0 {
            self.first_visible = 0;
            return;
        }
        // Allow scrolling such that the last screen-full is visible.
        let max_first = self.total_rows.saturating_sub(1);
        // Prefer to anchor so window fits: max_first = max(0, total - window).
        let pref = self.total_rows.saturating_sub(self.window);
        if self.first_visible > pref {
            self.first_visible = pref.min(max_first);
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), WindowError> {
        if self.schema_version_marker != 1 { return Err(WindowError::SchemaMismatch); }
        if self.window == 0 { return Err(WindowError::ZeroWindow); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scroll_to_brings_into_view() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.set_total(1000);
        w.scroll_to(500);
        assert!(w.is_visible(500));
    }

    #[test]
    fn scroll_to_above_aligns_to_row() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.set_total(1000);
        w.first_visible = 50;
        w.scroll_to(30);
        assert_eq!(w.first_visible, 30);
    }

    #[test]
    fn scroll_to_below_pulls_window_down() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.set_total(1000);
        w.first_visible = 0;
        w.scroll_to(50);
        // Row 50 at bottom of window: first = 50 - 9 = 41.
        assert_eq!(w.first_visible, 41);
    }

    #[test]
    fn set_total_snaps_window() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.set_total(1000);
        w.first_visible = 900;
        w.set_total(50);
        // Should snap so window fits.
        assert_eq!(w.first_visible, 40);
    }

    #[test]
    fn end_visible_clamps_at_total() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.set_total(5);
        assert_eq!(w.end_visible(), 5);
        assert_eq!(w.visible_count(), 5);
    }

    #[test]
    fn scroll_by_negative_clamps_at_zero() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.set_total(1000);
        w.scroll_by(-50);
        assert_eq!(w.first_visible, 0);
    }

    #[test]
    fn empty_tree() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.set_total(0);
        assert_eq!(w.visible_count(), 0);
        assert!(!w.is_visible(0));
    }

    #[test]
    fn zero_window_rejected() {
        assert!(matches!(VirtualTreeWindow::new(0).unwrap_err(), WindowError::ZeroWindow));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.schema_version_marker = 99;
        assert!(matches!(w.validate().unwrap_err(), WindowError::SchemaMismatch));
    }

    #[test]
    fn window_serde_roundtrip() {
        let mut w = VirtualTreeWindow::new(10).unwrap();
        w.set_total(100);
        w.scroll_to(50);
        let j = serde_json::to_string(&w).unwrap();
        let back: VirtualTreeWindow = serde_json::from_str(&j).unwrap();
        assert_eq!(w, back);
    }
}
