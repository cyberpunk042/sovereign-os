//! `sovereign-cockpit-quick-action-bar` — operator-curated horizontal command bar.
//!
//! Up to 12 slots. Reorderable via swap. Each slot has
//! (command_id, label, icon, shortcut_chord).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max slots.
pub const MAX_SLOTS: usize = 12;

/// One quick-action slot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QuickAction {
    /// Command id (matches palette command id).
    pub command_id: String,
    /// Display label.
    pub label: String,
    /// Icon glyph.
    pub icon: String,
    /// Optional shortcut chord (display-only).
    pub shortcut_chord: String,
}

/// Bar envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QuickActionBar {
    /// Schema version.
    pub schema_version: String,
    /// Slots in display order.
    pub slots: Vec<QuickAction>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum QuickActionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty command_id.
    #[error("command_id empty")]
    EmptyCommandId,
    /// Empty label.
    #[error("slot {0} label empty")]
    EmptyLabel(String),
    /// Duplicate.
    #[error("duplicate command_id: {0}")]
    Duplicate(String),
    /// Bar full.
    #[error("bar full ({MAX_SLOTS} max)")]
    Full,
    /// Out of range.
    #[error("index out of range: {idx}/{len}")]
    OutOfRange {
        /// idx.
        idx: usize,
        /// len.
        len: usize,
    },
    /// Unknown.
    #[error("unknown command_id: {0}")]
    Unknown(String),
}

impl QuickActionBar {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            slots: Vec::new(),
        }
    }

    /// Add slot.
    pub fn add(&mut self, q: QuickAction) -> Result<(), QuickActionError> {
        if q.command_id.is_empty() {
            return Err(QuickActionError::EmptyCommandId);
        }
        if q.label.is_empty() {
            return Err(QuickActionError::EmptyLabel(q.command_id));
        }
        if self.slots.iter().any(|s| s.command_id == q.command_id) {
            return Err(QuickActionError::Duplicate(q.command_id));
        }
        if self.slots.len() >= MAX_SLOTS {
            return Err(QuickActionError::Full);
        }
        self.slots.push(q);
        Ok(())
    }

    /// Remove by command_id.
    pub fn remove(&mut self, command_id: &str) -> Result<(), QuickActionError> {
        let pos = self
            .slots
            .iter()
            .position(|s| s.command_id == command_id)
            .ok_or_else(|| QuickActionError::Unknown(command_id.into()))?;
        self.slots.remove(pos);
        Ok(())
    }

    /// Swap two slots.
    pub fn swap(&mut self, a: usize, b: usize) -> Result<(), QuickActionError> {
        let len = self.slots.len();
        if a >= len || b >= len {
            return Err(QuickActionError::OutOfRange { idx: a.max(b), len });
        }
        self.slots.swap(a, b);
        Ok(())
    }

    /// Move a slot to a new index (with shift).
    pub fn move_to(&mut self, command_id: &str, target_idx: usize) -> Result<(), QuickActionError> {
        let src = self
            .slots
            .iter()
            .position(|s| s.command_id == command_id)
            .ok_or_else(|| QuickActionError::Unknown(command_id.into()))?;
        let len = self.slots.len();
        if target_idx >= len {
            return Err(QuickActionError::OutOfRange {
                idx: target_idx,
                len,
            });
        }
        let item = self.slots.remove(src);
        self.slots.insert(target_idx, item);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), QuickActionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(QuickActionError::SchemaMismatch);
        }
        if self.slots.len() > MAX_SLOTS {
            return Err(QuickActionError::Full);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in &self.slots {
            if s.command_id.is_empty() {
                return Err(QuickActionError::EmptyCommandId);
            }
            if s.label.is_empty() {
                return Err(QuickActionError::EmptyLabel(s.command_id.clone()));
            }
            if !seen.insert(s.command_id.as_str()) {
                return Err(QuickActionError::Duplicate(s.command_id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for QuickActionBar {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn q(id: &str) -> QuickAction {
        QuickAction {
            command_id: id.into(),
            label: format!("Label {id}"),
            icon: "icon".into(),
            shortcut_chord: String::new(),
        }
    }

    #[test]
    fn empty_bar_validates() {
        QuickActionBar::new().validate().unwrap();
    }

    #[test]
    fn add_and_swap() {
        let mut b = QuickActionBar::new();
        b.add(q("a")).unwrap();
        b.add(q("b")).unwrap();
        b.swap(0, 1).unwrap();
        assert_eq!(b.slots[0].command_id, "b");
    }

    #[test]
    fn duplicate_rejected() {
        let mut b = QuickActionBar::new();
        b.add(q("a")).unwrap();
        assert!(matches!(
            b.add(q("a")).unwrap_err(),
            QuickActionError::Duplicate(_)
        ));
    }

    #[test]
    fn full_caught() {
        let mut b = QuickActionBar::new();
        for i in 0..MAX_SLOTS {
            b.add(q(&format!("q{i}"))).unwrap();
        }
        assert!(matches!(
            b.add(q("overflow")).unwrap_err(),
            QuickActionError::Full
        ));
    }

    #[test]
    fn move_to_shifts() {
        let mut b = QuickActionBar::new();
        b.add(q("a")).unwrap();
        b.add(q("b")).unwrap();
        b.add(q("c")).unwrap();
        b.move_to("a", 2).unwrap();
        assert_eq!(b.slots[0].command_id, "b");
        assert_eq!(b.slots[1].command_id, "c");
        assert_eq!(b.slots[2].command_id, "a");
    }

    #[test]
    fn remove_works() {
        let mut b = QuickActionBar::new();
        b.add(q("a")).unwrap();
        b.remove("a").unwrap();
        assert!(b.slots.is_empty());
    }

    #[test]
    fn unknown_remove_rejected() {
        let mut b = QuickActionBar::new();
        assert!(matches!(
            b.remove("none").unwrap_err(),
            QuickActionError::Unknown(_)
        ));
    }

    #[test]
    fn out_of_range_swap_rejected() {
        let mut b = QuickActionBar::new();
        b.add(q("a")).unwrap();
        assert!(matches!(
            b.swap(0, 5).unwrap_err(),
            QuickActionError::OutOfRange { .. }
        ));
    }

    #[test]
    fn empty_command_id_rejected() {
        let mut b = QuickActionBar::new();
        let mut bad = q("a");
        bad.command_id = String::new();
        assert!(matches!(
            b.add(bad).unwrap_err(),
            QuickActionError::EmptyCommandId
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut b = QuickActionBar::new();
        let mut bad = q("a");
        bad.label = String::new();
        assert!(matches!(
            b.add(bad).unwrap_err(),
            QuickActionError::EmptyLabel(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = QuickActionBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            QuickActionError::SchemaMismatch
        ));
    }

    #[test]
    fn bar_serde_roundtrip() {
        let mut b = QuickActionBar::new();
        b.add(q("a")).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: QuickActionBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
