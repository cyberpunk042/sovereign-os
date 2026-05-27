//! `sovereign-cockpit-column-config` — table column model.
//!
//! Ordered columns with per-column visibility, width, and pin flags.
//! visible_in_render_order returns: pinned_left columns (in base order),
//! then unpinned (in base order), then pinned_right.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One column.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Column {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Visible?
    pub visible: bool,
    /// Width in px.
    pub width_px: u32,
    /// Pinned to left edge?
    pub pinned_left: bool,
    /// Pinned to right edge?
    pub pinned_right: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColumnConfig {
    /// Schema version.
    pub schema_version: String,
    /// Columns in base order.
    pub columns: Vec<Column>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ColumnError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("column id empty")]
    EmptyId,
    /// Empty label.
    #[error("column {0} label empty")]
    EmptyLabel(String),
    /// Width zero.
    #[error("column {0} width zero")]
    WidthZero(String),
    /// Duplicate id.
    #[error("duplicate column id: {0}")]
    DuplicateId(String),
    /// Unknown id.
    #[error("unknown column id: {0}")]
    Unknown(String),
    /// Column pinned to both sides.
    #[error("column {0} pinned to both sides")]
    BothPinned(String),
    /// Move out of bounds.
    #[error("move to {to} out of bounds (len {len})")]
    OutOfBounds {
        /// to.
        to: usize,
        /// len.
        len: usize,
    },
}

impl ColumnConfig {
    /// New.
    pub fn new(columns: Vec<Column>) -> Result<Self, ColumnError> {
        check_columns(&columns)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            columns,
        })
    }

    /// Move a column to a new index.
    pub fn move_to(&mut self, id: &str, to: usize) -> Result<(), ColumnError> {
        let from = self
            .columns
            .iter()
            .position(|c| c.id == id)
            .ok_or_else(|| ColumnError::Unknown(id.into()))?;
        if to >= self.columns.len() {
            return Err(ColumnError::OutOfBounds {
                to,
                len: self.columns.len(),
            });
        }
        let col = self.columns.remove(from);
        self.columns.insert(to, col);
        Ok(())
    }

    /// Resize.
    pub fn resize(&mut self, id: &str, width_px: u32) -> Result<(), ColumnError> {
        if width_px == 0 {
            return Err(ColumnError::WidthZero(id.into()));
        }
        let c = self
            .columns
            .iter_mut()
            .find(|c| c.id == id)
            .ok_or_else(|| ColumnError::Unknown(id.into()))?;
        c.width_px = width_px;
        Ok(())
    }

    /// Toggle visible.
    pub fn toggle_visible(&mut self, id: &str) -> Result<(), ColumnError> {
        let c = self
            .columns
            .iter_mut()
            .find(|c| c.id == id)
            .ok_or_else(|| ColumnError::Unknown(id.into()))?;
        c.visible = !c.visible;
        Ok(())
    }

    /// Visible columns in render order (pinned_left | center | pinned_right).
    pub fn visible_in_render_order(&self) -> Vec<&Column> {
        let mut pinned_left: Vec<&Column> = Vec::new();
        let mut center: Vec<&Column> = Vec::new();
        let mut pinned_right: Vec<&Column> = Vec::new();
        for c in &self.columns {
            if !c.visible {
                continue;
            }
            if c.pinned_left {
                pinned_left.push(c);
            } else if c.pinned_right {
                pinned_right.push(c);
            } else {
                center.push(c);
            }
        }
        pinned_left.extend(center);
        pinned_left.extend(pinned_right);
        pinned_left
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ColumnError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ColumnError::SchemaMismatch);
        }
        check_columns(&self.columns)
    }
}

fn check_columns(c: &[Column]) -> Result<(), ColumnError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for col in c {
        if col.id.is_empty() {
            return Err(ColumnError::EmptyId);
        }
        if col.label.is_empty() {
            return Err(ColumnError::EmptyLabel(col.id.clone()));
        }
        if col.width_px == 0 {
            return Err(ColumnError::WidthZero(col.id.clone()));
        }
        if !seen.insert(col.id.as_str()) {
            return Err(ColumnError::DuplicateId(col.id.clone()));
        }
        if col.pinned_left && col.pinned_right {
            return Err(ColumnError::BothPinned(col.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn c(id: &str, visible: bool, pl: bool, pr: bool) -> Column {
        Column {
            id: id.into(),
            label: format!("L-{id}"),
            visible,
            width_px: 100,
            pinned_left: pl,
            pinned_right: pr,
        }
    }

    #[test]
    fn render_order_pinned_left_first() {
        let cc = ColumnConfig::new(vec![
            c("c", true, false, false),
            c("a", true, true, false),
            c("b", true, false, false),
        ])
        .unwrap();
        let order: Vec<&str> = cc
            .visible_in_render_order()
            .iter()
            .map(|c| c.id.as_str())
            .collect();
        assert_eq!(order, vec!["a", "c", "b"]);
    }

    #[test]
    fn render_order_pinned_right_last() {
        let cc = ColumnConfig::new(vec![
            c("a", true, false, true),
            c("b", true, false, false),
            c("c", true, false, false),
        ])
        .unwrap();
        let order: Vec<&str> = cc
            .visible_in_render_order()
            .iter()
            .map(|c| c.id.as_str())
            .collect();
        assert_eq!(order, vec!["b", "c", "a"]);
    }

    #[test]
    fn invisible_omitted() {
        let cc = ColumnConfig::new(vec![
            c("a", true, false, false),
            c("b", false, false, false),
            c("c", true, false, false),
        ])
        .unwrap();
        let order: Vec<&str> = cc
            .visible_in_render_order()
            .iter()
            .map(|c| c.id.as_str())
            .collect();
        assert_eq!(order, vec!["a", "c"]);
    }

    #[test]
    fn toggle_visible() {
        let mut cc = ColumnConfig::new(vec![c("a", true, false, false)]).unwrap();
        cc.toggle_visible("a").unwrap();
        assert!(!cc.columns[0].visible);
    }

    #[test]
    fn move_to_repositions() {
        let mut cc = ColumnConfig::new(vec![
            c("a", true, false, false),
            c("b", true, false, false),
            c("c", true, false, false),
        ])
        .unwrap();
        cc.move_to("a", 2).unwrap();
        let order: Vec<&str> = cc.columns.iter().map(|c| c.id.as_str()).collect();
        assert_eq!(order, vec!["b", "c", "a"]);
    }

    #[test]
    fn resize_sets_width() {
        let mut cc = ColumnConfig::new(vec![c("a", true, false, false)]).unwrap();
        cc.resize("a", 200).unwrap();
        assert_eq!(cc.columns[0].width_px, 200);
    }

    #[test]
    fn resize_zero_rejected() {
        let mut cc = ColumnConfig::new(vec![c("a", true, false, false)]).unwrap();
        assert!(matches!(
            cc.resize("a", 0).unwrap_err(),
            ColumnError::WidthZero(_)
        ));
    }

    #[test]
    fn both_pinned_rejected() {
        assert!(matches!(
            ColumnConfig::new(vec![c("a", true, true, true)]).unwrap_err(),
            ColumnError::BothPinned(_)
        ));
    }

    #[test]
    fn duplicate_rejected() {
        assert!(matches!(
            ColumnConfig::new(vec![c("a", true, false, false), c("a", true, false, false)])
                .unwrap_err(),
            ColumnError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = c("a", true, false, false);
        x.id = String::new();
        assert!(matches!(
            ColumnConfig::new(vec![x]).unwrap_err(),
            ColumnError::EmptyId
        ));
    }

    #[test]
    fn move_out_of_bounds_rejected() {
        let mut cc = ColumnConfig::new(vec![c("a", true, false, false)]).unwrap();
        assert!(matches!(
            cc.move_to("a", 99).unwrap_err(),
            ColumnError::OutOfBounds { .. }
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut cc = ColumnConfig::new(vec![c("a", true, false, false)]).unwrap();
        cc.schema_version = "9.9.9".into();
        assert!(matches!(
            cc.validate().unwrap_err(),
            ColumnError::SchemaMismatch
        ));
    }

    #[test]
    fn config_serde_roundtrip() {
        let cc =
            ColumnConfig::new(vec![c("a", true, true, false), c("b", true, false, false)]).unwrap();
        let j = serde_json::to_string(&cc).unwrap();
        let back: ColumnConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(cc, back);
    }
}
