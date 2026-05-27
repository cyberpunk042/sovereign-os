//! `sovereign-cockpit-data-grid-sort` — column sort state.
//!
//! Tri-state per column (None / Asc / Desc). Single-column mode:
//! click cycles the clicked column through None→Asc→Desc→None, and
//! clears other columns. Multi-column mode (Shift+click): each
//! click toggles that column's direction within the spec.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Sort direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SortDirection {
    /// Ascending.
    Asc,
    /// Descending.
    Desc,
}

/// One sort entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SortEntry {
    /// Column id.
    pub column_id: String,
    /// Direction.
    pub direction: SortDirection,
}

/// Click mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ClickMode {
    /// Single-column (replaces).
    Single,
    /// Multi-column (Shift+click, appends/toggles).
    Multi,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DataGridSort {
    /// Schema version.
    pub schema_version: String,
    /// Sort spec in priority order.
    pub spec: Vec<SortEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SortError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty column id.
    #[error("column_id empty")]
    EmptyColumnId,
    /// Duplicate column in spec.
    #[error("duplicate column in spec: {0}")]
    DuplicateColumn(String),
}

impl DataGridSort {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            spec: Vec::new(),
        }
    }

    /// Click a column with mode.
    pub fn click_column(&mut self, column_id: &str, mode: ClickMode) -> Result<(), SortError> {
        if column_id.is_empty() {
            return Err(SortError::EmptyColumnId);
        }
        match mode {
            ClickMode::Single => {
                // Cycle: None → Asc → Desc → None; clear others.
                let cur = self
                    .spec
                    .iter()
                    .find(|e| e.column_id == column_id)
                    .map(|e| e.direction);
                self.spec.clear();
                let next = match cur {
                    None => Some(SortDirection::Asc),
                    Some(SortDirection::Asc) => Some(SortDirection::Desc),
                    Some(SortDirection::Desc) => None,
                };
                if let Some(d) = next {
                    self.spec.push(SortEntry {
                        column_id: column_id.into(),
                        direction: d,
                    });
                }
            }
            ClickMode::Multi => {
                // Toggle inside multi-spec.
                if let Some(pos) = self.spec.iter().position(|e| e.column_id == column_id) {
                    let cur = self.spec[pos].direction;
                    match cur {
                        SortDirection::Asc => self.spec[pos].direction = SortDirection::Desc,
                        SortDirection::Desc => {
                            self.spec.remove(pos);
                        }
                    }
                } else {
                    self.spec.push(SortEntry {
                        column_id: column_id.into(),
                        direction: SortDirection::Asc,
                    });
                }
            }
        }
        Ok(())
    }

    /// Direction of a column (None if not sorted).
    pub fn direction_of(&self, column_id: &str) -> Option<SortDirection> {
        self.spec
            .iter()
            .find(|e| e.column_id == column_id)
            .map(|e| e.direction)
    }

    /// Clear all sort.
    pub fn clear(&mut self) {
        self.spec.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SortError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SortError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for e in &self.spec {
            if e.column_id.is_empty() {
                return Err(SortError::EmptyColumnId);
            }
            if !seen.insert(e.column_id.as_str()) {
                return Err(SortError::DuplicateColumn(e.column_id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for DataGridSort {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_click_cycle() {
        let mut s = DataGridSort::new();
        s.click_column("a", ClickMode::Single).unwrap();
        assert_eq!(s.direction_of("a"), Some(SortDirection::Asc));
        s.click_column("a", ClickMode::Single).unwrap();
        assert_eq!(s.direction_of("a"), Some(SortDirection::Desc));
        s.click_column("a", ClickMode::Single).unwrap();
        assert_eq!(s.direction_of("a"), None);
        assert!(s.spec.is_empty());
    }

    #[test]
    fn single_click_replaces_others() {
        let mut s = DataGridSort::new();
        s.click_column("a", ClickMode::Single).unwrap();
        s.click_column("b", ClickMode::Single).unwrap();
        assert_eq!(s.direction_of("a"), None);
        assert_eq!(s.direction_of("b"), Some(SortDirection::Asc));
        assert_eq!(s.spec.len(), 1);
    }

    #[test]
    fn multi_click_appends() {
        let mut s = DataGridSort::new();
        s.click_column("a", ClickMode::Multi).unwrap();
        s.click_column("b", ClickMode::Multi).unwrap();
        assert_eq!(s.spec.len(), 2);
        assert_eq!(s.spec[0].column_id, "a");
        assert_eq!(s.spec[1].column_id, "b");
    }

    #[test]
    fn multi_click_toggles_asc_to_desc() {
        let mut s = DataGridSort::new();
        s.click_column("a", ClickMode::Multi).unwrap();
        s.click_column("a", ClickMode::Multi).unwrap();
        assert_eq!(s.direction_of("a"), Some(SortDirection::Desc));
    }

    #[test]
    fn multi_third_click_removes() {
        let mut s = DataGridSort::new();
        s.click_column("a", ClickMode::Multi).unwrap();
        s.click_column("a", ClickMode::Multi).unwrap();
        s.click_column("a", ClickMode::Multi).unwrap();
        assert_eq!(s.direction_of("a"), None);
    }

    #[test]
    fn clear() {
        let mut s = DataGridSort::new();
        s.click_column("a", ClickMode::Multi).unwrap();
        s.click_column("b", ClickMode::Multi).unwrap();
        s.clear();
        assert!(s.spec.is_empty());
    }

    #[test]
    fn empty_column_rejected() {
        let mut s = DataGridSort::new();
        assert!(matches!(
            s.click_column("", ClickMode::Single).unwrap_err(),
            SortError::EmptyColumnId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = DataGridSort::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SortError::SchemaMismatch
        ));
    }

    #[test]
    fn direction_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&SortDirection::Asc).unwrap(),
            "\"asc\""
        );
        assert_eq!(
            serde_json::to_string(&SortDirection::Desc).unwrap(),
            "\"desc\""
        );
    }

    #[test]
    fn click_mode_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ClickMode::Single).unwrap(),
            "\"single\""
        );
        assert_eq!(
            serde_json::to_string(&ClickMode::Multi).unwrap(),
            "\"multi\""
        );
    }

    #[test]
    fn sort_serde_roundtrip() {
        let mut s = DataGridSort::new();
        s.click_column("a", ClickMode::Multi).unwrap();
        s.click_column("b", ClickMode::Multi).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: DataGridSort = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
