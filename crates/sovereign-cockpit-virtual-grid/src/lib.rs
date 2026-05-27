//! `sovereign-cockpit-virtual-grid` — 2D viewport virtualization.
//!
//! Pure arithmetic: given total_rows × total_cols + fixed cell
//! (height, width) px + viewport (w, h, scroll_x, scroll_y) +
//! overscan, compute the rectangular range of visible cells.
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
pub struct VirtualGrid {
    /// Schema version.
    pub schema_version: String,
    /// Total rows.
    pub total_rows: u64,
    /// Total cols.
    pub total_cols: u64,
    /// Cell width in px (≥ 1).
    pub cell_w_px: u32,
    /// Cell height in px (≥ 1).
    pub cell_h_px: u32,
    /// Viewport width in px.
    pub viewport_w_px: u32,
    /// Viewport height in px.
    pub viewport_h_px: u32,
    /// Scroll x in px.
    pub scroll_x_px: u32,
    /// Scroll y in px.
    pub scroll_y_px: u32,
    /// Overscan cells on each side.
    pub overscan: u32,
}

/// Visible range.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct VisibleRange {
    /// First visible row (0-based).
    pub first_row: u64,
    /// First visible col (0-based).
    pub first_col: u64,
    /// Number of visible rows.
    pub row_count: u64,
    /// Number of visible cols.
    pub col_count: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GridError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Cell dim zero.
    #[error("cell dims zero")]
    CellZero,
    /// Viewport dim zero.
    #[error("viewport dims zero")]
    ViewportZero,
}

impl VirtualGrid {
    /// New.
    pub fn new(
        total_rows: u64,
        total_cols: u64,
        cell_w_px: u32,
        cell_h_px: u32,
        viewport_w_px: u32,
        viewport_h_px: u32,
        overscan: u32,
    ) -> Result<Self, GridError> {
        if cell_w_px == 0 || cell_h_px == 0 {
            return Err(GridError::CellZero);
        }
        if viewport_w_px == 0 || viewport_h_px == 0 {
            return Err(GridError::ViewportZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            total_rows,
            total_cols,
            cell_w_px,
            cell_h_px,
            viewport_w_px,
            viewport_h_px,
            scroll_x_px: 0,
            scroll_y_px: 0,
            overscan,
        })
    }

    /// Set scroll.
    pub fn set_scroll(&mut self, x: u32, y: u32) {
        self.scroll_x_px = x;
        self.scroll_y_px = y;
    }

    /// Compute the visible range.
    pub fn visible_range(&self) -> VisibleRange {
        let raw_first_col = (self.scroll_x_px as u64) / self.cell_w_px as u64;
        let raw_first_row = (self.scroll_y_px as u64) / self.cell_h_px as u64;
        let visible_cols_no_overscan =
            (self.viewport_w_px as u64).div_ceil(self.cell_w_px as u64) + 1;
        let visible_rows_no_overscan =
            (self.viewport_h_px as u64).div_ceil(self.cell_h_px as u64) + 1;
        let overscan = self.overscan as u64;
        let first_col = raw_first_col.saturating_sub(overscan).min(self.total_cols);
        let first_row = raw_first_row.saturating_sub(overscan).min(self.total_rows);
        let last_col = (raw_first_col + visible_cols_no_overscan + overscan).min(self.total_cols);
        let last_row = (raw_first_row + visible_rows_no_overscan + overscan).min(self.total_rows);
        VisibleRange {
            first_row,
            first_col,
            row_count: last_row.saturating_sub(first_row),
            col_count: last_col.saturating_sub(first_col),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GridError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GridError::SchemaMismatch);
        }
        if self.cell_w_px == 0 || self.cell_h_px == 0 {
            return Err(GridError::CellZero);
        }
        if self.viewport_w_px == 0 || self.viewport_h_px == 0 {
            return Err(GridError::ViewportZero);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cell_zero_rejected() {
        assert!(matches!(
            VirtualGrid::new(100, 100, 0, 10, 100, 100, 0).unwrap_err(),
            GridError::CellZero
        ));
    }

    #[test]
    fn viewport_zero_rejected() {
        assert!(matches!(
            VirtualGrid::new(100, 100, 10, 10, 0, 100, 0).unwrap_err(),
            GridError::ViewportZero
        ));
    }

    #[test]
    fn top_left_at_origin() {
        let g = VirtualGrid::new(100, 100, 50, 50, 200, 200, 0).unwrap();
        let r = g.visible_range();
        assert_eq!(r.first_row, 0);
        assert_eq!(r.first_col, 0);
        // 200/50 = 4 visible + 1 partial = 5.
        assert_eq!(r.row_count, 5);
        assert_eq!(r.col_count, 5);
    }

    #[test]
    fn scrolled_advances_first() {
        let mut g = VirtualGrid::new(100, 100, 50, 50, 200, 200, 0).unwrap();
        g.set_scroll(100, 150);
        let r = g.visible_range();
        assert_eq!(r.first_col, 2);
        assert_eq!(r.first_row, 3);
    }

    #[test]
    fn overscan_adds_neighbours() {
        let mut g = VirtualGrid::new(100, 100, 50, 50, 200, 200, 2).unwrap();
        g.set_scroll(500, 500);
        let r = g.visible_range();
        // first_col without overscan = 10; with -2 = 8.
        assert_eq!(r.first_col, 8);
        assert_eq!(r.first_row, 8);
    }

    #[test]
    fn capped_at_total() {
        let mut g = VirtualGrid::new(20, 20, 50, 50, 200, 200, 0).unwrap();
        g.set_scroll(100_000, 100_000);
        let r = g.visible_range();
        assert!(r.first_row <= 20);
        assert!(r.first_col <= 20);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = VirtualGrid::new(10, 10, 10, 10, 100, 100, 0).unwrap();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            GridError::SchemaMismatch
        ));
    }

    #[test]
    fn grid_serde_roundtrip() {
        let mut g = VirtualGrid::new(100, 100, 50, 50, 200, 200, 2).unwrap();
        g.set_scroll(150, 100);
        let j = serde_json::to_string(&g).unwrap();
        let back: VirtualGrid = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
