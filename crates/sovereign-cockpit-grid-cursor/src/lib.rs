//! `sovereign-cockpit-grid-cursor` — active cell in a grid.
//!
//! row x col bounded by max_row/max_col. set(row, col) clamps.
//! move_by(drow, dcol) shifts within bounds. home() returns to
//! (0, 0); end() to (max_row, max_col).
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
pub struct GridCursor {
    /// Schema version.
    pub schema_version: String,
    /// Max row (>=0).
    pub max_row: u32,
    /// Max col (>=0).
    pub max_col: u32,
    /// Current row.
    pub row: u32,
    /// Current col.
    pub col: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CursorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty grid.
    #[error("grid must have at least 1x1 cell")]
    EmptyGrid,
}

impl GridCursor {
    /// New (positioned at 0,0). max_row/max_col are inclusive bounds.
    pub fn new(max_row: u32, max_col: u32) -> Result<Self, CursorError> {
        // Allow 0,0 (1x1 grid).
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            max_row,
            max_col,
            row: 0,
            col: 0,
        })
    }

    /// Set (clamped).
    pub fn set(&mut self, row: u32, col: u32) {
        self.row = row.min(self.max_row);
        self.col = col.min(self.max_col);
    }

    /// Shift by (drow, dcol) within bounds.
    pub fn move_by(&mut self, drow: i32, dcol: i32) {
        let new_row = (self.row as i64 + drow as i64).clamp(0, self.max_row as i64) as u32;
        let new_col = (self.col as i64 + dcol as i64).clamp(0, self.max_col as i64) as u32;
        self.row = new_row;
        self.col = new_col;
    }

    /// Home (0, 0).
    pub fn home(&mut self) {
        self.row = 0;
        self.col = 0;
    }

    /// End (max_row, max_col).
    pub fn end(&mut self) {
        self.row = self.max_row;
        self.col = self.max_col;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CursorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CursorError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn move_within_bounds() {
        let mut c = GridCursor::new(9, 9).unwrap();
        c.move_by(3, 4);
        assert_eq!((c.row, c.col), (3, 4));
    }

    #[test]
    fn move_clamps_low() {
        let mut c = GridCursor::new(9, 9).unwrap();
        c.set(2, 2);
        c.move_by(-10, -10);
        assert_eq!((c.row, c.col), (0, 0));
    }

    #[test]
    fn move_clamps_high() {
        let mut c = GridCursor::new(5, 5).unwrap();
        c.move_by(100, 100);
        assert_eq!((c.row, c.col), (5, 5));
    }

    #[test]
    fn home_end() {
        let mut c = GridCursor::new(9, 9).unwrap();
        c.set(5, 5);
        c.home();
        assert_eq!((c.row, c.col), (0, 0));
        c.end();
        assert_eq!((c.row, c.col), (9, 9));
    }

    #[test]
    fn set_clamps() {
        let mut c = GridCursor::new(3, 3).unwrap();
        c.set(99, 99);
        assert_eq!((c.row, c.col), (3, 3));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = GridCursor::new(9, 9).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            CursorError::SchemaMismatch
        ));
    }

    #[test]
    fn cursor_serde_roundtrip() {
        let mut c = GridCursor::new(9, 9).unwrap();
        c.set(3, 4);
        let j = serde_json::to_string(&c).unwrap();
        let back: GridCursor = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
