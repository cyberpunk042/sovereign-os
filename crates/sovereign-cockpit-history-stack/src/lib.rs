//! `sovereign-cockpit-history-stack` — back/forward nav.
//!
//! Entries indexed by `cursor`. push(entry) drops entries
//! beyond cursor (forward stack), then appends and points
//! cursor at the new entry. back() / forward() move the cursor
//! when possible. Capacity-bounded (oldest dropped).
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
pub struct HistoryStack {
    /// Schema version.
    pub schema_version: String,
    /// Capacity.
    pub capacity: u32,
    /// Entries.
    pub entries: Vec<String>,
    /// Cursor (index into entries; None when empty).
    pub cursor: Option<u32>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HistoryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("entry empty")]
    EmptyEntry,
    /// Zero capacity.
    #[error("capacity must be >= 1")]
    ZeroCapacity,
}

impl HistoryStack {
    /// New.
    pub fn new(capacity: u32) -> Result<Self, HistoryError> {
        if capacity == 0 {
            return Err(HistoryError::ZeroCapacity);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            entries: Vec::new(),
            cursor: None,
        })
    }

    /// Push a new entry; truncates forward stack from cursor.
    pub fn push(&mut self, entry: &str) -> Result<(), HistoryError> {
        if entry.is_empty() {
            return Err(HistoryError::EmptyEntry);
        }
        if let Some(c) = self.cursor {
            self.entries.truncate((c as usize) + 1);
        }
        self.entries.push(entry.into());
        // Cap.
        while (self.entries.len() as u32) > self.capacity {
            self.entries.remove(0);
        }
        self.cursor = Some((self.entries.len() - 1) as u32);
        Ok(())
    }

    /// Current entry.
    pub fn current(&self) -> Option<&str> {
        self.cursor
            .and_then(|c| self.entries.get(c as usize).map(|s| s.as_str()))
    }

    /// Go back.
    pub fn back(&mut self) -> Option<&str> {
        let c = self.cursor?;
        if c == 0 {
            return None;
        }
        self.cursor = Some(c - 1);
        self.current()
    }

    /// Go forward.
    pub fn forward(&mut self) -> Option<&str> {
        let c = self.cursor?;
        if (c as usize + 1) >= self.entries.len() {
            return None;
        }
        self.cursor = Some(c + 1);
        self.current()
    }

    /// Can back?
    pub fn can_back(&self) -> bool {
        self.cursor.map(|c| c > 0).unwrap_or(false)
    }

    /// Can forward?
    pub fn can_forward(&self) -> bool {
        match self.cursor {
            Some(c) => (c as usize + 1) < self.entries.len(),
            None => false,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HistoryError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HistoryError::SchemaMismatch);
        }
        if self.capacity == 0 {
            return Err(HistoryError::ZeroCapacity);
        }
        for e in &self.entries {
            if e.is_empty() {
                return Err(HistoryError::EmptyEntry);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn push_and_current() {
        let mut h = HistoryStack::new(5).unwrap();
        h.push("a").unwrap();
        h.push("b").unwrap();
        assert_eq!(h.current(), Some("b"));
    }

    #[test]
    fn back_and_forward() {
        let mut h = HistoryStack::new(5).unwrap();
        h.push("a").unwrap();
        h.push("b").unwrap();
        h.push("c").unwrap();
        assert_eq!(h.back(), Some("b"));
        assert_eq!(h.back(), Some("a"));
        assert!(!h.can_back());
        assert_eq!(h.forward(), Some("b"));
        assert!(h.can_forward());
    }

    #[test]
    fn push_truncates_forward() {
        let mut h = HistoryStack::new(5).unwrap();
        h.push("a").unwrap();
        h.push("b").unwrap();
        h.push("c").unwrap();
        h.back(); // at b
        h.push("d").unwrap();
        // After push: a, b, d (no c).
        assert_eq!(h.current(), Some("d"));
        assert_eq!(h.entries, vec!["a", "b", "d"]);
        assert!(!h.can_forward());
    }

    #[test]
    fn capacity_drops_oldest() {
        let mut h = HistoryStack::new(3).unwrap();
        h.push("a").unwrap();
        h.push("b").unwrap();
        h.push("c").unwrap();
        h.push("d").unwrap();
        assert_eq!(h.entries, vec!["b", "c", "d"]);
        assert_eq!(h.current(), Some("d"));
    }

    #[test]
    fn empty_history_no_movement() {
        let mut h = HistoryStack::new(5).unwrap();
        assert!(h.current().is_none());
        assert!(h.back().is_none());
        assert!(h.forward().is_none());
    }

    #[test]
    fn bad_inputs_rejected() {
        let mut h = HistoryStack::new(5).unwrap();
        assert!(matches!(h.push("").unwrap_err(), HistoryError::EmptyEntry));
        assert!(matches!(
            HistoryStack::new(0).unwrap_err(),
            HistoryError::ZeroCapacity
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = HistoryStack::new(5).unwrap();
        h.schema_version = "9.9.9".into();
        assert!(matches!(
            h.validate().unwrap_err(),
            HistoryError::SchemaMismatch
        ));
    }

    #[test]
    fn history_serde_roundtrip() {
        let mut h = HistoryStack::new(5).unwrap();
        h.push("a").unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: HistoryStack = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
