//! `sovereign-cockpit-preset-chip-bar` — saved presets bar.
//!
//! Each preset has id + label + payload + display order +
//! application count + last_applied. UI renders chips in declared
//! order with the active chip highlighted. apply(id, ts) bumps
//! counters + sets the active preset.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One preset.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Preset {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Payload (caller-opaque, e.g. encoded filter).
    pub payload: String,
    /// Display order.
    pub order: u32,
    /// Apply count.
    pub apply_count: u64,
    /// Last applied ts.
    pub last_applied_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PresetChipBar {
    /// Schema version.
    pub schema_version: String,
    /// id → preset.
    pub presets: BTreeMap<String, Preset>,
    /// Active preset id.
    pub active: Option<String>,
    /// Next order.
    pub next_order: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PresetError {
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
    #[error("payload empty")]
    EmptyPayload,
    /// Duplicate.
    #[error("duplicate preset id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown preset: {0}")]
    UnknownPreset(String),
}

impl PresetChipBar {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            presets: BTreeMap::new(),
            active: None,
            next_order: 0,
        }
    }

    /// Add preset.
    pub fn add(&mut self, id: &str, label: &str, payload: &str) -> Result<(), PresetError> {
        if id.is_empty() {
            return Err(PresetError::EmptyId);
        }
        if label.is_empty() {
            return Err(PresetError::EmptyLabel);
        }
        if payload.is_empty() {
            return Err(PresetError::EmptyPayload);
        }
        if self.presets.contains_key(id) {
            return Err(PresetError::DuplicateId(id.into()));
        }
        let order = self.next_order;
        self.next_order = self.next_order.saturating_add(1);
        self.presets.insert(
            id.into(),
            Preset {
                id: id.into(),
                label: label.into(),
                payload: payload.into(),
                order,
                apply_count: 0,
                last_applied_ms: 0,
            },
        );
        Ok(())
    }

    /// Apply.
    pub fn apply(&mut self, id: &str, ts_ms: u64) -> Result<String, PresetError> {
        let p = self
            .presets
            .get_mut(id)
            .ok_or_else(|| PresetError::UnknownPreset(id.into()))?;
        p.apply_count = p.apply_count.saturating_add(1);
        p.last_applied_ms = ts_ms;
        self.active = Some(id.into());
        Ok(p.payload.clone())
    }

    /// Clear active.
    pub fn clear_active(&mut self) {
        self.active = None;
    }

    /// Remove preset (clears active if matches).
    pub fn remove(&mut self, id: &str) -> bool {
        let removed = self.presets.remove(id).is_some();
        if self.active.as_deref() == Some(id) {
            self.active = None;
        }
        removed
    }

    /// Presets in display order.
    pub fn ordered(&self) -> Vec<Preset> {
        let mut v: Vec<Preset> = self.presets.values().cloned().collect();
        v.sort_by_key(|p| p.order);
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PresetError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PresetError::SchemaMismatch);
        }
        for (id, p) in &self.presets {
            if id.is_empty() {
                return Err(PresetError::EmptyId);
            }
            if p.label.is_empty() {
                return Err(PresetError::EmptyLabel);
            }
            if p.payload.is_empty() {
                return Err(PresetError::EmptyPayload);
            }
        }
        Ok(())
    }
}

impl Default for PresetChipBar {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_ordered() {
        let mut b = PresetChipBar::new();
        b.add("a", "A", "p1").unwrap();
        b.add("b", "B", "p2").unwrap();
        let v = b.ordered();
        assert_eq!(v[0].id, "a");
        assert_eq!(v[1].id, "b");
    }

    #[test]
    fn apply_returns_payload_and_sets_active() {
        let mut b = PresetChipBar::new();
        b.add("a", "A", "filter:status=open").unwrap();
        let p = b.apply("a", 100).unwrap();
        assert_eq!(p, "filter:status=open");
        assert_eq!(b.active.as_deref(), Some("a"));
        assert_eq!(b.presets["a"].apply_count, 1);
    }

    #[test]
    fn remove_clears_active_when_matching() {
        let mut b = PresetChipBar::new();
        b.add("a", "A", "p").unwrap();
        b.apply("a", 0).unwrap();
        assert!(b.remove("a"));
        assert!(b.active.is_none());
    }

    #[test]
    fn duplicate_rejected() {
        let mut b = PresetChipBar::new();
        b.add("a", "A", "p").unwrap();
        assert!(matches!(
            b.add("a", "A", "p").unwrap_err(),
            PresetError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut b = PresetChipBar::new();
        assert!(matches!(
            b.add("", "A", "p").unwrap_err(),
            PresetError::EmptyId
        ));
        assert!(matches!(
            b.add("a", "", "p").unwrap_err(),
            PresetError::EmptyLabel
        ));
        assert!(matches!(
            b.add("a", "A", "").unwrap_err(),
            PresetError::EmptyPayload
        ));
    }

    #[test]
    fn unknown_apply_rejected() {
        let mut b = PresetChipBar::new();
        assert!(matches!(
            b.apply("nope", 0).unwrap_err(),
            PresetError::UnknownPreset(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = PresetChipBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            PresetError::SchemaMismatch
        ));
    }

    #[test]
    fn preset_serde_roundtrip() {
        let mut b = PresetChipBar::new();
        b.add("a", "A", "p").unwrap();
        b.apply("a", 100).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: PresetChipBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
