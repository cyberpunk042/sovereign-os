//! `sovereign-cockpit-checklist` — ordered operator checklist.
//!
//! `register(item)` appends. `complete(id, ts)` marks complete;
//! `uncomplete(id)` reopens. `progress()` returns (done, total)
//! and `percent()` returns 0..=100 (integer floor).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Item {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Completed-at ts (None = open).
    pub completed_at_ms: Option<u64>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Checklist {
    /// Schema version.
    pub schema_version: String,
    /// Items in registered order.
    pub items: Vec<Item>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ChecklistError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("item id empty")]
    EmptyId,
    /// Empty label.
    #[error("item label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate item id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown item id: {0}")]
    UnknownId(String),
}

impl Checklist {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            items: Vec::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, item: Item) -> Result<(), ChecklistError> {
        if item.id.is_empty() {
            return Err(ChecklistError::EmptyId);
        }
        if item.label.is_empty() {
            return Err(ChecklistError::EmptyLabel);
        }
        if self.items.iter().any(|i| i.id == item.id) {
            return Err(ChecklistError::DuplicateId(item.id));
        }
        self.items.push(item);
        Ok(())
    }

    /// Complete.
    pub fn complete(&mut self, id: &str, ts_ms: u64) -> Result<(), ChecklistError> {
        let it = self
            .items
            .iter_mut()
            .find(|i| i.id == id)
            .ok_or_else(|| ChecklistError::UnknownId(id.into()))?;
        it.completed_at_ms = Some(ts_ms);
        Ok(())
    }

    /// Reopen.
    pub fn uncomplete(&mut self, id: &str) -> Result<(), ChecklistError> {
        let it = self
            .items
            .iter_mut()
            .find(|i| i.id == id)
            .ok_or_else(|| ChecklistError::UnknownId(id.into()))?;
        it.completed_at_ms = None;
        Ok(())
    }

    /// Progress (done, total).
    pub fn progress(&self) -> (usize, usize) {
        let total = self.items.len();
        let done = self
            .items
            .iter()
            .filter(|i| i.completed_at_ms.is_some())
            .count();
        (done, total)
    }

    /// Percent complete (0..=100).
    pub fn percent(&self) -> u8 {
        let (done, total) = self.progress();
        if total == 0 {
            0
        } else {
            ((done * 100) / total) as u8
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ChecklistError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ChecklistError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for i in &self.items {
            if i.id.is_empty() {
                return Err(ChecklistError::EmptyId);
            }
            if i.label.is_empty() {
                return Err(ChecklistError::EmptyLabel);
            }
            if !seen.insert(i.id.as_str()) {
                return Err(ChecklistError::DuplicateId(i.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for Checklist {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(id: &str) -> Item {
        Item {
            id: id.into(),
            label: id.into(),
            completed_at_ms: None,
        }
    }

    #[test]
    fn register_and_progress() {
        let mut c = Checklist::new();
        c.register(item("a")).unwrap();
        c.register(item("b")).unwrap();
        c.complete("a", 100).unwrap();
        assert_eq!(c.progress(), (1, 2));
        assert_eq!(c.percent(), 50);
    }

    #[test]
    fn empty_progress_zero() {
        let c = Checklist::new();
        assert_eq!(c.progress(), (0, 0));
        assert_eq!(c.percent(), 0);
    }

    #[test]
    fn duplicate_rejected() {
        let mut c = Checklist::new();
        c.register(item("a")).unwrap();
        assert!(matches!(
            c.register(item("a")).unwrap_err(),
            ChecklistError::DuplicateId(_)
        ));
    }

    #[test]
    fn uncomplete_reopens() {
        let mut c = Checklist::new();
        c.register(item("a")).unwrap();
        c.complete("a", 100).unwrap();
        c.uncomplete("a").unwrap();
        assert_eq!(c.progress(), (0, 1));
    }

    #[test]
    fn unknown_id_rejected() {
        let mut c = Checklist::new();
        assert!(matches!(
            c.complete("nope", 0).unwrap_err(),
            ChecklistError::UnknownId(_)
        ));
        assert!(matches!(
            c.uncomplete("nope").unwrap_err(),
            ChecklistError::UnknownId(_)
        ));
    }

    #[test]
    fn empty_id_or_label_rejected() {
        let mut c = Checklist::new();
        let mut bad = item("a");
        bad.id = "".into();
        assert!(matches!(
            c.register(bad).unwrap_err(),
            ChecklistError::EmptyId
        ));
        let mut bad2 = item("a");
        bad2.label = "".into();
        assert!(matches!(
            c.register(bad2).unwrap_err(),
            ChecklistError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = Checklist::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            ChecklistError::SchemaMismatch
        ));
    }

    #[test]
    fn checklist_serde_roundtrip() {
        let mut c = Checklist::new();
        c.register(item("a")).unwrap();
        c.complete("a", 100).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: Checklist = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
