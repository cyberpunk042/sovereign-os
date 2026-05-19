//! `sovereign-cockpit-filter-chip-bar` — chip list for active filters.
//!
//! Each Chip is (id, label, value, removable). The bar supports
//! add/remove/clear_all_removable. Non-removable chips survive
//! clear_all to reflect always-on filters (e.g., scope=current-tab).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One chip.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Chip {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Optional value (e.g., "status=active").
    pub value: String,
    /// Operator can dismiss?
    pub removable: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FilterChipBar {
    /// Schema version.
    pub schema_version: String,
    /// Chips in render order.
    pub chips: Vec<Chip>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ChipBarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("chip id empty")]
    EmptyId,
    /// Empty label.
    #[error("chip {0} label empty")]
    EmptyLabel(String),
    /// Duplicate.
    #[error("duplicate chip id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown chip id: {0}")]
    Unknown(String),
    /// Chip not removable.
    #[error("chip {0} is not removable")]
    NotRemovable(String),
}

impl FilterChipBar {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            chips: Vec::new(),
        }
    }

    /// Add a chip.
    pub fn add(&mut self, chip: Chip) -> Result<(), ChipBarError> {
        if chip.id.is_empty() { return Err(ChipBarError::EmptyId); }
        if chip.label.is_empty() { return Err(ChipBarError::EmptyLabel(chip.id.clone())); }
        if self.chips.iter().any(|c| c.id == chip.id) {
            return Err(ChipBarError::DuplicateId(chip.id));
        }
        self.chips.push(chip);
        Ok(())
    }

    /// Remove by id; fails if chip not removable.
    pub fn remove(&mut self, id: &str) -> Result<(), ChipBarError> {
        let pos = self.chips.iter().position(|c| c.id == id)
            .ok_or_else(|| ChipBarError::Unknown(id.into()))?;
        if !self.chips[pos].removable {
            return Err(ChipBarError::NotRemovable(id.into()));
        }
        self.chips.remove(pos);
        Ok(())
    }

    /// Clear all removable chips (non-removable survive).
    pub fn clear_all_removable(&mut self) {
        self.chips.retain(|c| !c.removable);
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ChipBarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ChipBarError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for c in &self.chips {
            if c.id.is_empty() { return Err(ChipBarError::EmptyId); }
            if c.label.is_empty() { return Err(ChipBarError::EmptyLabel(c.id.clone())); }
            if !seen.insert(c.id.as_str()) {
                return Err(ChipBarError::DuplicateId(c.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for FilterChipBar {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn chip(id: &str, removable: bool) -> Chip {
        Chip {
            id: id.into(),
            label: format!("L-{id}"),
            value: format!("v-{id}"),
            removable,
        }
    }

    #[test]
    fn add_remove_basic() {
        let mut b = FilterChipBar::new();
        b.add(chip("a", true)).unwrap();
        assert_eq!(b.chips.len(), 1);
        b.remove("a").unwrap();
        assert!(b.chips.is_empty());
    }

    #[test]
    fn remove_unknown_rejected() {
        let mut b = FilterChipBar::new();
        assert!(matches!(b.remove("z").unwrap_err(), ChipBarError::Unknown(_)));
    }

    #[test]
    fn remove_non_removable_rejected() {
        let mut b = FilterChipBar::new();
        b.add(chip("a", false)).unwrap();
        assert!(matches!(b.remove("a").unwrap_err(), ChipBarError::NotRemovable(_)));
    }

    #[test]
    fn clear_all_removable_preserves_pinned() {
        let mut b = FilterChipBar::new();
        b.add(chip("p", false)).unwrap();
        b.add(chip("r1", true)).unwrap();
        b.add(chip("r2", true)).unwrap();
        b.clear_all_removable();
        assert_eq!(b.chips.len(), 1);
        assert_eq!(b.chips[0].id, "p");
    }

    #[test]
    fn duplicate_rejected() {
        let mut b = FilterChipBar::new();
        b.add(chip("a", true)).unwrap();
        assert!(matches!(b.add(chip("a", true)).unwrap_err(), ChipBarError::DuplicateId(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut b = FilterChipBar::new();
        let mut c = chip("a", true);
        c.id = String::new();
        assert!(matches!(b.add(c).unwrap_err(), ChipBarError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut b = FilterChipBar::new();
        let mut c = chip("a", true);
        c.label = String::new();
        assert!(matches!(b.add(c).unwrap_err(), ChipBarError::EmptyLabel(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = FilterChipBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), ChipBarError::SchemaMismatch));
    }

    #[test]
    fn bar_serde_roundtrip() {
        let mut b = FilterChipBar::new();
        b.add(chip("a", true)).unwrap();
        b.add(chip("b", false)).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: FilterChipBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
