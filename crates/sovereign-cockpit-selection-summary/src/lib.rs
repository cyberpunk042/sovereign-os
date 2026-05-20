//! `sovereign-cockpit-selection-summary` — selected-items summary.
//!
//! Item{id, value, category}. add records selection.
//! summary() returns Summary{count, total, categories (sorted)}.
//! clear empties.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Item {
    /// Id.
    pub id: String,
    /// Value (numeric for summation).
    pub value: i64,
    /// Category label.
    pub category: String,
}

/// Summary.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Summary {
    /// Count.
    pub count: u32,
    /// Total (sum of values, i128 to avoid overflow).
    pub total: i128,
    /// Sorted unique categories.
    pub categories: Vec<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SelectionSummary {
    /// Schema version.
    pub schema_version: String,
    /// Items.
    pub items: Vec<Item>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SummaryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("category empty")]
    EmptyCategory,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl SelectionSummary {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            items: Vec::new(),
        }
    }

    /// Add item.
    pub fn add(&mut self, id: &str, value: i64, category: &str) -> Result<(), SummaryError> {
        if id.is_empty() { return Err(SummaryError::EmptyId); }
        if category.is_empty() { return Err(SummaryError::EmptyCategory); }
        if self.items.iter().any(|i| i.id == id) {
            return Err(SummaryError::DuplicateId(id.into()));
        }
        self.items.push(Item { id: id.into(), value, category: category.into() });
        Ok(())
    }

    /// Remove by id.
    pub fn remove(&mut self, id: &str) -> bool {
        if let Some(pos) = self.items.iter().position(|i| i.id == id) {
            self.items.remove(pos);
            true
        } else {
            false
        }
    }

    /// Clear.
    pub fn clear(&mut self) { self.items.clear(); }

    /// Summary.
    pub fn summary(&self) -> Summary {
        let categories: BTreeSet<String> = self.items.iter().map(|i| i.category.clone()).collect();
        let total: i128 = self.items.iter().map(|i| i.value as i128).sum();
        Summary {
            count: self.items.len() as u32,
            total,
            categories: categories.into_iter().collect(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SummaryError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SummaryError::SchemaMismatch); }
        for i in &self.items {
            if i.id.is_empty() { return Err(SummaryError::EmptyId); }
            if i.category.is_empty() { return Err(SummaryError::EmptyCategory); }
        }
        Ok(())
    }
}

impl Default for SelectionSummary {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_summary() {
        let s = SelectionSummary::new();
        let sum = s.summary();
        assert_eq!(sum.count, 0);
        assert_eq!(sum.total, 0);
        assert!(sum.categories.is_empty());
    }

    #[test]
    fn add_and_summarize() {
        let mut s = SelectionSummary::new();
        s.add("a", 10, "vip").unwrap();
        s.add("b", 20, "vip").unwrap();
        s.add("c", 30, "regular").unwrap();
        let sum = s.summary();
        assert_eq!(sum.count, 3);
        assert_eq!(sum.total, 60);
        assert_eq!(sum.categories, vec!["regular", "vip"]);
    }

    #[test]
    fn remove() {
        let mut s = SelectionSummary::new();
        s.add("a", 5, "x").unwrap();
        assert!(s.remove("a"));
        assert_eq!(s.summary().count, 0);
    }

    #[test]
    fn clear() {
        let mut s = SelectionSummary::new();
        s.add("a", 5, "x").unwrap();
        s.clear();
        assert_eq!(s.summary().count, 0);
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = SelectionSummary::new();
        s.add("a", 1, "x").unwrap();
        assert!(matches!(s.add("a", 2, "x").unwrap_err(), SummaryError::DuplicateId(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = SelectionSummary::new();
        assert!(matches!(s.add("", 1, "x").unwrap_err(), SummaryError::EmptyId));
        assert!(matches!(s.add("i", 1, "").unwrap_err(), SummaryError::EmptyCategory));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SelectionSummary::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SummaryError::SchemaMismatch));
    }

    #[test]
    fn summary_serde_roundtrip() {
        let mut s = SelectionSummary::new();
        s.add("a", 1, "x").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SelectionSummary = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
