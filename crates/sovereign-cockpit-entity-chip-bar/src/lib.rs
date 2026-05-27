//! `sovereign-cockpit-entity-chip-bar` — removable chips.
//!
//! Chip{id, label, kind}. add appends. remove(id) deletes.
//! visible() returns first `max_visible` chips and the
//! overflow count.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Chip.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Chip {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Kind tag.
    pub kind: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EntityChipBar {
    /// Schema version.
    pub schema_version: String,
    /// Max visible chips.
    pub max_visible: u32,
    /// Chips in insertion order.
    pub chips: Vec<Chip>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Empty.
    #[error("kind empty")]
    EmptyKind,
    /// Zero max.
    #[error("max_visible must be >= 1")]
    ZeroMax,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl EntityChipBar {
    /// New.
    pub fn new(max_visible: u32) -> Result<Self, BarError> {
        if max_visible == 0 {
            return Err(BarError::ZeroMax);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            max_visible,
            chips: Vec::new(),
        })
    }

    /// Append.
    pub fn add(&mut self, id: &str, label: &str, kind: &str) -> Result<(), BarError> {
        if id.is_empty() {
            return Err(BarError::EmptyId);
        }
        if label.is_empty() {
            return Err(BarError::EmptyLabel);
        }
        if kind.is_empty() {
            return Err(BarError::EmptyKind);
        }
        if self.chips.iter().any(|c| c.id == id) {
            return Err(BarError::DuplicateId(id.into()));
        }
        self.chips.push(Chip {
            id: id.into(),
            label: label.into(),
            kind: kind.into(),
        });
        Ok(())
    }

    /// Remove by id.
    pub fn remove(&mut self, id: &str) -> bool {
        if let Some(pos) = self.chips.iter().position(|c| c.id == id) {
            self.chips.remove(pos);
            true
        } else {
            false
        }
    }

    /// Visible chips + overflow count.
    pub fn visible(&self) -> (Vec<&Chip>, u32) {
        let max = self.max_visible as usize;
        if self.chips.len() <= max {
            (self.chips.iter().collect(), 0)
        } else {
            (
                self.chips.iter().take(max).collect(),
                (self.chips.len() - max) as u32,
            )
        }
    }

    /// Count.
    pub fn len(&self) -> usize {
        self.chips.len()
    }

    /// Empty?
    pub fn is_empty(&self) -> bool {
        self.chips.is_empty()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BarError::SchemaMismatch);
        }
        if self.max_visible == 0 {
            return Err(BarError::ZeroMax);
        }
        for c in &self.chips {
            if c.id.is_empty() {
                return Err(BarError::EmptyId);
            }
            if c.label.is_empty() {
                return Err(BarError::EmptyLabel);
            }
            if c.kind.is_empty() {
                return Err(BarError::EmptyKind);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_visible() {
        let mut b = EntityChipBar::new(3).unwrap();
        b.add("u1", "Alice", "user").unwrap();
        b.add("u2", "Bob", "user").unwrap();
        let (vis, over) = b.visible();
        assert_eq!(vis.len(), 2);
        assert_eq!(over, 0);
    }

    #[test]
    fn overflow_truncates() {
        let mut b = EntityChipBar::new(2).unwrap();
        for i in 0..5 {
            b.add(&format!("u{}", i), "X", "user").unwrap();
        }
        let (vis, over) = b.visible();
        assert_eq!(vis.len(), 2);
        assert_eq!(over, 3);
    }

    #[test]
    fn remove_works() {
        let mut b = EntityChipBar::new(3).unwrap();
        b.add("u1", "X", "user").unwrap();
        assert!(b.remove("u1"));
        assert!(!b.remove("u1"));
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut b = EntityChipBar::new(3).unwrap();
        b.add("u1", "X", "user").unwrap();
        assert!(matches!(
            b.add("u1", "Y", "user").unwrap_err(),
            BarError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut b = EntityChipBar::new(3).unwrap();
        assert!(matches!(
            b.add("", "X", "user").unwrap_err(),
            BarError::EmptyId
        ));
        assert!(matches!(
            b.add("i", "", "user").unwrap_err(),
            BarError::EmptyLabel
        ));
        assert!(matches!(
            b.add("i", "X", "").unwrap_err(),
            BarError::EmptyKind
        ));
        assert!(matches!(
            EntityChipBar::new(0).unwrap_err(),
            BarError::ZeroMax
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = EntityChipBar::new(3).unwrap();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            BarError::SchemaMismatch
        ));
    }

    #[test]
    fn bar_serde_roundtrip() {
        let mut b = EntityChipBar::new(3).unwrap();
        b.add("u1", "X", "user").unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: EntityChipBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
