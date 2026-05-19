//! `sovereign-cockpit-table-row-selection` — per-row + header-tristate.
//!
//! row_ids visible, selected set (subset). header_state computes
//! Tristate: None (empty)/Some (partial)/All. toggle_header()
//! cycles None↔All. toggle_row(id) flips that row.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Header tristate.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum HeaderState {
    /// No rows selected.
    None,
    /// Some rows selected (partial).
    Some,
    /// All visible rows selected.
    All,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TableRowSelection {
    /// Schema version.
    pub schema_version: String,
    /// Visible row ids (insertion order = display order).
    pub row_ids: Vec<String>,
    /// Selected ids (sorted).
    pub selected: BTreeSet<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SelectionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("row id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate row id: {0}")]
    DuplicateId(String),
    /// Unknown row id (operation).
    #[error("unknown row id: {0}")]
    Unknown(String),
    /// Selected references unknown id.
    #[error("selection references unknown id: {0}")]
    SelectionUnknown(String),
}

impl TableRowSelection {
    /// New.
    pub fn new(row_ids: Vec<String>) -> Result<Self, SelectionError> {
        check_rows(&row_ids)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            row_ids,
            selected: BTreeSet::new(),
        })
    }

    /// Compute header state.
    pub fn header_state(&self) -> HeaderState {
        let n_visible = self.row_ids.len();
        let n_selected = self.row_ids.iter().filter(|id| self.selected.contains(*id)).count();
        if n_selected == 0 { HeaderState::None }
        else if n_selected == n_visible { HeaderState::All }
        else { HeaderState::Some }
    }

    /// Toggle a row.
    pub fn toggle_row(&mut self, id: &str) -> Result<(), SelectionError> {
        if !self.row_ids.iter().any(|x| x == id) {
            return Err(SelectionError::Unknown(id.into()));
        }
        if self.selected.contains(id) {
            self.selected.remove(id);
        } else {
            self.selected.insert(id.into());
        }
        Ok(())
    }

    /// Click the header tristate (None|Some → All, All → None).
    pub fn toggle_header(&mut self) {
        let st = self.header_state();
        match st {
            HeaderState::None | HeaderState::Some => {
                for id in &self.row_ids {
                    self.selected.insert(id.clone());
                }
            }
            HeaderState::All => {
                for id in &self.row_ids {
                    self.selected.remove(id);
                }
            }
        }
    }

    /// Count selected.
    pub fn count(&self) -> usize {
        self.row_ids.iter().filter(|id| self.selected.contains(*id)).count()
    }

    /// Clear all.
    pub fn clear(&mut self) {
        self.selected.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SelectionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SelectionError::SchemaMismatch);
        }
        check_rows(&self.row_ids)?;
        use std::collections::HashSet;
        let ids: HashSet<&str> = self.row_ids.iter().map(String::as_str).collect();
        for s in &self.selected {
            if !ids.contains(s.as_str()) {
                return Err(SelectionError::SelectionUnknown(s.clone()));
            }
        }
        Ok(())
    }
}

fn check_rows(rows: &[String]) -> Result<(), SelectionError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for r in rows {
        if r.is_empty() { return Err(SelectionError::EmptyId); }
        if !seen.insert(r.as_str()) {
            return Err(SelectionError::DuplicateId(r.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rows(ids: &[&str]) -> Vec<String> {
        ids.iter().map(|s| (*s).to_string()).collect()
    }

    #[test]
    fn header_none_initial() {
        let t = TableRowSelection::new(rows(&["a", "b", "c"])).unwrap();
        assert_eq!(t.header_state(), HeaderState::None);
    }

    #[test]
    fn toggle_row_some() {
        let mut t = TableRowSelection::new(rows(&["a", "b", "c"])).unwrap();
        t.toggle_row("a").unwrap();
        assert_eq!(t.header_state(), HeaderState::Some);
    }

    #[test]
    fn toggle_header_selects_all() {
        let mut t = TableRowSelection::new(rows(&["a", "b", "c"])).unwrap();
        t.toggle_header();
        assert_eq!(t.header_state(), HeaderState::All);
        assert_eq!(t.count(), 3);
    }

    #[test]
    fn toggle_header_from_some_selects_all() {
        let mut t = TableRowSelection::new(rows(&["a", "b", "c"])).unwrap();
        t.toggle_row("a").unwrap();
        t.toggle_header();
        assert_eq!(t.header_state(), HeaderState::All);
    }

    #[test]
    fn toggle_header_from_all_clears() {
        let mut t = TableRowSelection::new(rows(&["a", "b", "c"])).unwrap();
        t.toggle_header();
        t.toggle_header();
        assert_eq!(t.header_state(), HeaderState::None);
    }

    #[test]
    fn toggle_row_twice_clears() {
        let mut t = TableRowSelection::new(rows(&["a"])).unwrap();
        t.toggle_row("a").unwrap();
        t.toggle_row("a").unwrap();
        assert_eq!(t.count(), 0);
    }

    #[test]
    fn toggle_unknown_rejected() {
        let mut t = TableRowSelection::new(rows(&["a"])).unwrap();
        assert!(matches!(t.toggle_row("z").unwrap_err(), SelectionError::Unknown(_)));
    }

    #[test]
    fn clear_empties() {
        let mut t = TableRowSelection::new(rows(&["a", "b"])).unwrap();
        t.toggle_header();
        t.clear();
        assert_eq!(t.count(), 0);
    }

    #[test]
    fn duplicate_rejected() {
        assert!(matches!(
            TableRowSelection::new(rows(&["a", "a"])).unwrap_err(),
            SelectionError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        assert!(matches!(
            TableRowSelection::new(rows(&["a", ""])).unwrap_err(),
            SelectionError::EmptyId
        ));
    }

    #[test]
    fn validate_selected_unknown_rejected() {
        let mut t = TableRowSelection::new(rows(&["a"])).unwrap();
        t.selected.insert("ghost".into());
        assert!(matches!(t.validate().unwrap_err(), SelectionError::SelectionUnknown(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TableRowSelection::new(rows(&["a"])).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), SelectionError::SchemaMismatch));
    }

    #[test]
    fn state_serde_kebab() {
        assert_eq!(serde_json::to_string(&HeaderState::Some).unwrap(), "\"some\"");
    }

    #[test]
    fn selection_serde_roundtrip() {
        let mut t = TableRowSelection::new(rows(&["a", "b"])).unwrap();
        t.toggle_row("a").unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: TableRowSelection = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
