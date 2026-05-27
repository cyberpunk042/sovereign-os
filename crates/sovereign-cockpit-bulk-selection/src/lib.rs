//! `sovereign-cockpit-bulk-selection` — multi-item selection.
//!
//! Holds an ordered universe of item ids + a set of selected ids
//! + an anchor (last single click). click/ctrl_click/shift_click
//! drive selection state.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BulkSelection {
    /// Schema version.
    pub schema_version: String,
    /// Item universe in order.
    pub items: Vec<String>,
    /// Selected set.
    pub selected: BTreeSet<String>,
    /// Anchor item (last simple click).
    pub anchor: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SelectionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Unknown.
    #[error("unknown item: {0}")]
    UnknownItem(String),
}

impl BulkSelection {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            items: Vec::new(),
            selected: BTreeSet::new(),
            anchor: None,
        }
    }

    /// Set universe (clears selection + anchor).
    pub fn set_items(&mut self, items: &[&str]) -> Result<(), SelectionError> {
        for i in items {
            if i.is_empty() {
                return Err(SelectionError::EmptyId);
            }
        }
        self.items = items.iter().map(|s| (*s).into()).collect();
        self.selected.clear();
        self.anchor = None;
        Ok(())
    }

    /// Single click: selects only this item, sets anchor.
    pub fn click(&mut self, id: &str) -> Result<(), SelectionError> {
        if !self.items.iter().any(|i| i == id) {
            return Err(SelectionError::UnknownItem(id.into()));
        }
        self.selected.clear();
        self.selected.insert(id.into());
        self.anchor = Some(id.into());
        Ok(())
    }

    /// Ctrl click: toggles this item in selection (anchor unchanged unless new selection).
    pub fn ctrl_click(&mut self, id: &str) -> Result<(), SelectionError> {
        if !self.items.iter().any(|i| i == id) {
            return Err(SelectionError::UnknownItem(id.into()));
        }
        if self.selected.contains(id) {
            self.selected.remove(id);
        } else {
            self.selected.insert(id.into());
            self.anchor = Some(id.into());
        }
        Ok(())
    }

    /// Shift click: selects range from anchor to this item.
    pub fn shift_click(&mut self, id: &str) -> Result<(), SelectionError> {
        if !self.items.iter().any(|i| i == id) {
            return Err(SelectionError::UnknownItem(id.into()));
        }
        let anchor = self.anchor.clone().unwrap_or_else(|| id.to_string());
        let a = self.items.iter().position(|i| *i == anchor).unwrap();
        let b = self.items.iter().position(|i| *i == id).unwrap();
        let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
        self.selected.clear();
        for item in &self.items[lo..=hi] {
            self.selected.insert(item.clone());
        }
        Ok(())
    }

    /// Select all.
    pub fn select_all(&mut self) {
        self.selected = self.items.iter().cloned().collect();
    }

    /// Clear selection.
    pub fn clear(&mut self) {
        self.selected.clear();
        self.anchor = None;
    }

    /// Selected count.
    pub fn count(&self) -> usize {
        self.selected.len()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SelectionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SelectionError::SchemaMismatch);
        }
        for i in &self.items {
            if i.is_empty() {
                return Err(SelectionError::EmptyId);
            }
        }
        Ok(())
    }
}

impl Default for BulkSelection {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn loaded() -> BulkSelection {
        let mut s = BulkSelection::new();
        s.set_items(&["a", "b", "c", "d", "e"]).unwrap();
        s
    }

    #[test]
    fn click_selects_one() {
        let mut s = loaded();
        s.click("b").unwrap();
        assert_eq!(s.count(), 1);
        assert!(s.selected.contains("b"));
    }

    #[test]
    fn ctrl_click_toggles() {
        let mut s = loaded();
        s.click("b").unwrap();
        s.ctrl_click("d").unwrap();
        assert_eq!(s.count(), 2);
        s.ctrl_click("b").unwrap();
        assert_eq!(s.count(), 1);
    }

    #[test]
    fn shift_click_range() {
        let mut s = loaded();
        s.click("b").unwrap();
        s.shift_click("d").unwrap();
        assert_eq!(s.count(), 3);
        assert!(s.selected.contains("b"));
        assert!(s.selected.contains("c"));
        assert!(s.selected.contains("d"));
    }

    #[test]
    fn shift_click_backward() {
        let mut s = loaded();
        s.click("d").unwrap();
        s.shift_click("b").unwrap();
        assert_eq!(s.count(), 3);
    }

    #[test]
    fn select_all() {
        let mut s = loaded();
        s.select_all();
        assert_eq!(s.count(), 5);
    }

    #[test]
    fn clear() {
        let mut s = loaded();
        s.click("a").unwrap();
        s.clear();
        assert_eq!(s.count(), 0);
        assert!(s.anchor.is_none());
    }

    #[test]
    fn unknown_item_rejected() {
        let mut s = loaded();
        assert!(matches!(
            s.click("nope").unwrap_err(),
            SelectionError::UnknownItem(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = BulkSelection::new();
        assert!(matches!(
            s.set_items(&[""]).unwrap_err(),
            SelectionError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = loaded();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SelectionError::SchemaMismatch
        ));
    }

    #[test]
    fn selection_serde_roundtrip() {
        let mut s = loaded();
        s.click("a").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: BulkSelection = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
