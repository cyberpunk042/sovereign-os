//! `sovereign-cockpit-multi-sort` — chained sort columns.
//!
//! click(column, extend): if extend=false, replace single
//! Asc on that column (or rotate Asc→Desc→Off on repeat).
//! If extend=true, append/rotate on existing chain.
//! chain() returns the ordered (column, direction) pairs.
//! clear empties.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Direction.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Direction {
    /// Ascending.
    Asc,
    /// Descending.
    Desc,
}

/// Entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Column id.
    pub column: String,
    /// Direction.
    pub direction: Direction,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MultiSort {
    /// Schema version.
    pub schema_version: String,
    /// Ordered sort chain.
    pub chain: Vec<Entry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SortError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("column empty")]
    EmptyColumn,
}

impl MultiSort {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            chain: Vec::new(),
        }
    }

    /// Click a column header.
    /// - extend=false: clear chain, install Asc on column (or rotate Asc→Desc→Off on repeat clicks).
    /// - extend=true: rotate at the column's position in the chain (or append Asc).
    pub fn click(&mut self, column: &str, extend: bool) -> Result<(), SortError> {
        if column.is_empty() { return Err(SortError::EmptyColumn); }
        if !extend {
            // Replace.
            let prev = self.chain.iter().find(|e| e.column == column).cloned();
            self.chain.clear();
            match prev {
                None => self.chain.push(Entry { column: column.into(), direction: Direction::Asc }),
                Some(e) if e.direction == Direction::Asc =>
                    self.chain.push(Entry { column: column.into(), direction: Direction::Desc }),
                Some(_) => {}, // off
            }
            return Ok(());
        }
        // Extend.
        let pos = self.chain.iter().position(|e| e.column == column);
        match pos {
            None => self.chain.push(Entry { column: column.into(), direction: Direction::Asc }),
            Some(i) => {
                match self.chain[i].direction {
                    Direction::Asc => self.chain[i].direction = Direction::Desc,
                    Direction::Desc => { self.chain.remove(i); }
                }
            }
        }
        Ok(())
    }

    /// Chain.
    pub fn chain(&self) -> &[Entry] { &self.chain }

    /// Clear.
    pub fn clear(&mut self) { self.chain.clear(); }

    /// Validate.
    pub fn validate(&self) -> Result<(), SortError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SortError::SchemaMismatch); }
        for e in &self.chain {
            if e.column.is_empty() { return Err(SortError::EmptyColumn); }
        }
        Ok(())
    }
}

impl Default for MultiSort {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn click_no_extend_asc() {
        let mut s = MultiSort::new();
        s.click("a", false).unwrap();
        assert_eq!(s.chain(), &[Entry { column: "a".into(), direction: Direction::Asc }]);
    }

    #[test]
    fn click_repeat_rotates() {
        let mut s = MultiSort::new();
        s.click("a", false).unwrap();
        s.click("a", false).unwrap();
        assert_eq!(s.chain()[0].direction, Direction::Desc);
        s.click("a", false).unwrap();
        assert!(s.chain().is_empty());
    }

    #[test]
    fn extend_appends() {
        let mut s = MultiSort::new();
        s.click("a", true).unwrap();
        s.click("b", true).unwrap();
        assert_eq!(s.chain().len(), 2);
        assert_eq!(s.chain()[0].column, "a");
        assert_eq!(s.chain()[1].column, "b");
    }

    #[test]
    fn extend_rotates_existing() {
        let mut s = MultiSort::new();
        s.click("a", true).unwrap();
        s.click("a", true).unwrap();
        assert_eq!(s.chain()[0].direction, Direction::Desc);
        s.click("a", true).unwrap();
        assert!(s.chain().is_empty());
    }

    #[test]
    fn no_extend_replaces_chain() {
        let mut s = MultiSort::new();
        s.click("a", true).unwrap();
        s.click("b", true).unwrap();
        s.click("c", false).unwrap();
        assert_eq!(s.chain().len(), 1);
        assert_eq!(s.chain()[0].column, "c");
    }

    #[test]
    fn clear_empties() {
        let mut s = MultiSort::new();
        s.click("a", true).unwrap();
        s.clear();
        assert!(s.chain().is_empty());
    }

    #[test]
    fn empty_column_rejected() {
        let mut s = MultiSort::new();
        assert!(matches!(s.click("", false).unwrap_err(), SortError::EmptyColumn));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = MultiSort::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SortError::SchemaMismatch));
    }

    #[test]
    fn sort_serde_roundtrip() {
        let mut s = MultiSort::new();
        s.click("a", false).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: MultiSort = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
