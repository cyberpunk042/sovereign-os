//! `sovereign-cockpit-cell-range-select` — cell-range selection.
//!
//! Cell{row, col}. anchor + focus form the selection rectangle.
//! click(cell) sets both to the cell. drag(cell) moves focus
//! only (extends selection). cells() yields all cells in the
//! rectangle (inclusive) in row-major order. contains(cell)
//! tests membership.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Cell coordinate.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Cell {
    /// Row (0-based).
    pub row: u32,
    /// Column (0-based).
    pub col: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CellRangeSelect {
    /// Schema version.
    pub schema_version: String,
    /// Anchor cell (None = nothing selected).
    pub anchor: Option<Cell>,
    /// Focus cell.
    pub focus: Option<Cell>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SelectError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// No selection.
    #[error("no active selection")]
    NoSelection,
}

impl CellRangeSelect {
    /// New (empty).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            anchor: None,
            focus: None,
        }
    }

    /// Click a cell — sets both anchor + focus.
    pub fn click(&mut self, cell: Cell) {
        self.anchor = Some(cell);
        self.focus = Some(cell);
    }

    /// Drag (or shift-click) — moves focus only.
    pub fn drag(&mut self, cell: Cell) -> Result<(), SelectError> {
        if self.anchor.is_none() {
            return Err(SelectError::NoSelection);
        }
        self.focus = Some(cell);
        Ok(())
    }

    /// Clear.
    pub fn clear(&mut self) {
        self.anchor = None;
        self.focus = None;
    }

    /// Rectangle (lo_row, lo_col, hi_row, hi_col), inclusive.
    pub fn rect(&self) -> Option<(u32, u32, u32, u32)> {
        let a = self.anchor?;
        let f = self.focus?;
        Some((
            a.row.min(f.row),
            a.col.min(f.col),
            a.row.max(f.row),
            a.col.max(f.col),
        ))
    }

    /// All cells in row-major order.
    pub fn cells(&self) -> Vec<Cell> {
        let Some((lo_r, lo_c, hi_r, hi_c)) = self.rect() else {
            return Vec::new();
        };
        let mut out = Vec::with_capacity(((hi_r - lo_r + 1) * (hi_c - lo_c + 1)) as usize);
        for r in lo_r..=hi_r {
            for c in lo_c..=hi_c {
                out.push(Cell { row: r, col: c });
            }
        }
        out
    }

    /// Is cell inside the selection?
    pub fn contains(&self, cell: Cell) -> bool {
        let Some((lo_r, lo_c, hi_r, hi_c)) = self.rect() else {
            return false;
        };
        cell.row >= lo_r && cell.row <= hi_r && cell.col >= lo_c && cell.col <= hi_c
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SelectError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SelectError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for CellRangeSelect {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_yields_no_rect() {
        let s = CellRangeSelect::new();
        assert!(s.rect().is_none());
        assert_eq!(s.cells(), Vec::<Cell>::new());
    }

    #[test]
    fn click_selects_one_cell() {
        let mut s = CellRangeSelect::new();
        s.click(Cell { row: 2, col: 3 });
        let cs = s.cells();
        assert_eq!(cs.len(), 1);
        assert_eq!(cs[0], Cell { row: 2, col: 3 });
    }

    #[test]
    fn drag_extends_selection() {
        let mut s = CellRangeSelect::new();
        s.click(Cell { row: 2, col: 3 });
        s.drag(Cell { row: 4, col: 5 }).unwrap();
        assert_eq!(s.rect(), Some((2, 3, 4, 5)));
        assert_eq!(s.cells().len(), 9);
    }

    #[test]
    fn rectangle_normalizes_corners() {
        let mut s = CellRangeSelect::new();
        s.click(Cell { row: 5, col: 5 });
        s.drag(Cell { row: 2, col: 2 }).unwrap();
        assert_eq!(s.rect(), Some((2, 2, 5, 5)));
    }

    #[test]
    fn contains_inside_and_outside() {
        let mut s = CellRangeSelect::new();
        s.click(Cell { row: 0, col: 0 });
        s.drag(Cell { row: 2, col: 2 }).unwrap();
        assert!(s.contains(Cell { row: 1, col: 1 }));
        assert!(!s.contains(Cell { row: 3, col: 0 }));
    }

    #[test]
    fn drag_without_anchor_rejected() {
        let mut s = CellRangeSelect::new();
        assert!(matches!(
            s.drag(Cell { row: 0, col: 0 }).unwrap_err(),
            SelectError::NoSelection
        ));
    }

    #[test]
    fn clear_resets() {
        let mut s = CellRangeSelect::new();
        s.click(Cell { row: 0, col: 0 });
        s.clear();
        assert!(s.rect().is_none());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = CellRangeSelect::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SelectError::SchemaMismatch
        ));
    }

    #[test]
    fn select_serde_roundtrip() {
        let mut s = CellRangeSelect::new();
        s.click(Cell { row: 1, col: 2 });
        s.drag(Cell { row: 3, col: 4 }).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: CellRangeSelect = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
