//! `sovereign-cockpit-frozen-columns` — frozen-column geometry.
//!
//! Column{id, width}. Frozen leading N columns and trailing M
//! columns remain in place during horizontal scroll. position(i)
//! returns Pinned{left_px}, Scrolling{left_px relative to viewport
//! before scroll_x}, or PinnedRight{right_px}. Width computation is
//! deterministic; consumer code applies CSS sticky/transform.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Column.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Column {
    /// Stable id.
    pub id: String,
    /// Width in px (>= 1).
    pub width: u32,
}

/// Position kind.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind", content = "offset_px")]
pub enum Pos {
    /// Pinned to left edge.
    PinnedLeft(u32),
    /// Scrolls with content (left in unscrolled coords).
    Scrolling(u32),
    /// Pinned to right edge.
    PinnedRight(u32),
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FrozenColumns {
    /// Schema version.
    pub schema_version: String,
    /// Columns in display order.
    pub columns: Vec<Column>,
    /// Leading-frozen count.
    pub freeze_lead: u32,
    /// Trailing-frozen count.
    pub freeze_trail: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FrozenError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("column id empty")]
    EmptyId,
    /// Zero width.
    #[error("column width must be >= 1")]
    ZeroWidth,
    /// Bad freeze.
    #[error("freeze counts overlap or exceed columns")]
    BadFreeze,
    /// Out of range.
    #[error("index out of range")]
    OutOfRange,
}

impl FrozenColumns {
    /// New.
    pub fn new(columns: Vec<Column>, freeze_lead: u32, freeze_trail: u32) -> Result<Self, FrozenError> {
        let n = columns.len();
        if freeze_lead as usize + freeze_trail as usize > n {
            return Err(FrozenError::BadFreeze);
        }
        for c in &columns {
            if c.id.is_empty() { return Err(FrozenError::EmptyId); }
            if c.width == 0 { return Err(FrozenError::ZeroWidth); }
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            columns,
            freeze_lead,
            freeze_trail,
        })
    }

    /// Position of column at index i.
    pub fn position(&self, i: usize) -> Result<Pos, FrozenError> {
        if i >= self.columns.len() { return Err(FrozenError::OutOfRange); }
        let lead = self.freeze_lead as usize;
        let trail = self.freeze_trail as usize;
        let n = self.columns.len();
        if i < lead {
            // Pinned left — sum widths of preceding leading-frozen.
            let off: u32 = self.columns[..i].iter().map(|c| c.width).sum();
            return Ok(Pos::PinnedLeft(off));
        }
        if i >= n - trail {
            // Pinned right — sum widths of trailing-frozen after i.
            let off: u32 = self.columns[i+1..].iter().map(|c| c.width).sum();
            return Ok(Pos::PinnedRight(off));
        }
        // Scrolling — left edge in unscrolled coords.
        let left: u32 = self.columns[..i].iter().map(|c| c.width).sum();
        Ok(Pos::Scrolling(left))
    }

    /// Total scrolling width (sum of widths of non-frozen columns).
    pub fn scrolling_width(&self) -> u32 {
        let lead = self.freeze_lead as usize;
        let trail = self.freeze_trail as usize;
        let n = self.columns.len();
        if lead + trail >= n { return 0; }
        self.columns[lead..n - trail].iter().map(|c| c.width).sum()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FrozenError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FrozenError::SchemaMismatch); }
        let n = self.columns.len();
        if self.freeze_lead as usize + self.freeze_trail as usize > n {
            return Err(FrozenError::BadFreeze);
        }
        for c in &self.columns {
            if c.id.is_empty() { return Err(FrozenError::EmptyId); }
            if c.width == 0 { return Err(FrozenError::ZeroWidth); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cols() -> Vec<Column> {
        vec![
            Column { id: "a".into(), width: 80 },
            Column { id: "b".into(), width: 100 },
            Column { id: "c".into(), width: 120 },
            Column { id: "d".into(), width: 60 },
            Column { id: "e".into(), width: 40 },
        ]
    }

    #[test]
    fn no_freeze_all_scrolling() {
        let f = FrozenColumns::new(cols(), 0, 0).unwrap();
        let off = match f.position(2).unwrap() { Pos::Scrolling(x) => x, _ => panic!() };
        assert_eq!(off, 80 + 100);
    }

    #[test]
    fn leading_frozen_pinned_left() {
        let f = FrozenColumns::new(cols(), 2, 0).unwrap();
        assert_eq!(f.position(0).unwrap(), Pos::PinnedLeft(0));
        assert_eq!(f.position(1).unwrap(), Pos::PinnedLeft(80));
        assert!(matches!(f.position(2).unwrap(), Pos::Scrolling(_)));
    }

    #[test]
    fn trailing_frozen_pinned_right() {
        let f = FrozenColumns::new(cols(), 0, 2).unwrap();
        // Last col: nothing after, offset 0.
        assert_eq!(f.position(4).unwrap(), Pos::PinnedRight(0));
        // Penultimate: e (40) after.
        assert_eq!(f.position(3).unwrap(), Pos::PinnedRight(40));
    }

    #[test]
    fn scrolling_width_excludes_frozen() {
        let f = FrozenColumns::new(cols(), 1, 1).unwrap();
        // Scrolling: b, c, d = 100+120+60 = 280.
        assert_eq!(f.scrolling_width(), 280);
    }

    #[test]
    fn bad_freeze_rejected() {
        let r = FrozenColumns::new(cols(), 3, 3).unwrap_err();
        assert!(matches!(r, FrozenError::BadFreeze));
    }

    #[test]
    fn zero_width_rejected() {
        let mut c = cols();
        c[0].width = 0;
        assert!(matches!(FrozenColumns::new(c, 0, 0).unwrap_err(), FrozenError::ZeroWidth));
    }

    #[test]
    fn out_of_range_rejected() {
        let f = FrozenColumns::new(cols(), 0, 0).unwrap();
        assert!(matches!(f.position(99).unwrap_err(), FrozenError::OutOfRange));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = FrozenColumns::new(cols(), 0, 0).unwrap();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FrozenError::SchemaMismatch));
    }

    #[test]
    fn frozen_serde_roundtrip() {
        let f = FrozenColumns::new(cols(), 1, 1).unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: FrozenColumns = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
