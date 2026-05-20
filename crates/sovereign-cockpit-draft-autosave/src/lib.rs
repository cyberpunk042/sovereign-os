//! `sovereign-cockpit-draft-autosave` — periodic draft snapshots.
//!
//! Per field id, the cockpit records text edits over time. The
//! autosave engine decides when a snapshot is due based on:
//!   * `min_interval_ms` since the last snapshot AND
//!   * either `idle_ms` since the last edit OR `max_age_ms` since
//!     the last snapshot.
//!
//! `update(field_id, text, ts_ms)` records an edit.
//! `snapshot_due(field_id, now_ms)` → bool.
//! `mark_snapshotted(field_id, now_ms)` records that a snapshot was
//! taken. `clear(field_id)` drops a field. `latest(field_id)` returns
//! the current text.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Autosave config.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct AutosaveConfig {
    /// Minimum time between snapshots.
    pub min_interval_ms: u64,
    /// Idle time after last edit that triggers a snapshot.
    pub idle_ms: u64,
    /// Max age since last snapshot (forces snapshot even mid-typing).
    pub max_age_ms: u64,
}

impl Default for AutosaveConfig {
    fn default() -> Self {
        Self { min_interval_ms: 1_000, idle_ms: 2_000, max_age_ms: 30_000 }
    }
}

/// Per-field draft state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DraftField {
    /// Current text.
    pub text: String,
    /// Last edit ts.
    pub last_edit_ms: u64,
    /// Last snapshot ts (0 if never).
    pub last_snapshot_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DraftAutosave {
    /// Schema version.
    pub schema_version: String,
    /// Config.
    pub config: AutosaveConfig,
    /// field_id → draft.
    pub fields: BTreeMap<String, DraftField>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AutosaveError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty field id.
    #[error("field id empty")]
    EmptyField,
    /// Non-monotonic.
    #[error("non-monotonic ts: prev {prev} > new {new}")]
    NonMonotonic {
        /// prev.
        prev: u64,
        /// new.
        new: u64,
    },
}

impl DraftAutosave {
    /// New with default config.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            config: AutosaveConfig::default(),
            fields: BTreeMap::new(),
        }
    }

    /// New with config.
    pub fn with_config(config: AutosaveConfig) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            config,
            fields: BTreeMap::new(),
        }
    }

    /// Record an edit.
    pub fn update(&mut self, field_id: &str, text: &str, ts_ms: u64) -> Result<(), AutosaveError> {
        if field_id.is_empty() { return Err(AutosaveError::EmptyField); }
        if let Some(existing) = self.fields.get(field_id) {
            if ts_ms < existing.last_edit_ms {
                return Err(AutosaveError::NonMonotonic { prev: existing.last_edit_ms, new: ts_ms });
            }
        }
        let entry = self.fields.entry(field_id.into()).or_insert(DraftField {
            text: String::new(),
            last_edit_ms: ts_ms,
            last_snapshot_ms: 0,
        });
        entry.text = text.into();
        entry.last_edit_ms = ts_ms;
        Ok(())
    }

    /// Is a snapshot due for this field?
    pub fn snapshot_due(&self, field_id: &str, now_ms: u64) -> bool {
        let Some(f) = self.fields.get(field_id) else { return false; };
        let since_snap = now_ms.saturating_sub(f.last_snapshot_ms);
        if since_snap < self.config.min_interval_ms {
            return false;
        }
        // Max-age path: snapshot is overdue even if typing continues.
        if since_snap >= self.config.max_age_ms {
            return true;
        }
        // Idle path: user paused.
        let idle = now_ms.saturating_sub(f.last_edit_ms);
        idle >= self.config.idle_ms
    }

    /// Record that a snapshot was taken.
    pub fn mark_snapshotted(&mut self, field_id: &str, now_ms: u64) -> bool {
        match self.fields.get_mut(field_id) {
            Some(f) => { f.last_snapshot_ms = now_ms; true }
            None => false,
        }
    }

    /// All fields currently due for snapshot.
    pub fn due_fields(&self, now_ms: u64) -> Vec<String> {
        self.fields.keys()
            .filter(|id| self.snapshot_due(id, now_ms))
            .cloned()
            .collect()
    }

    /// Current text.
    pub fn latest(&self, field_id: &str) -> Option<&str> {
        self.fields.get(field_id).map(|f| f.text.as_str())
    }

    /// Drop a field (e.g. saved permanently or discarded).
    pub fn clear(&mut self, field_id: &str) -> bool {
        self.fields.remove(field_id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AutosaveError> {
        if self.schema_version != SCHEMA_VERSION { return Err(AutosaveError::SchemaMismatch); }
        for k in self.fields.keys() {
            if k.is_empty() { return Err(AutosaveError::EmptyField); }
        }
        Ok(())
    }
}

impl Default for DraftAutosave {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg() -> AutosaveConfig {
        AutosaveConfig { min_interval_ms: 1_000, idle_ms: 2_000, max_age_ms: 10_000 }
    }

    #[test]
    fn not_due_immediately_after_edit() {
        let mut d = DraftAutosave::with_config(cfg());
        d.update("body", "hi", 0).unwrap();
        // Just edited — not idle yet.
        assert!(!d.snapshot_due("body", 500));
    }

    #[test]
    fn due_after_idle_window() {
        let mut d = DraftAutosave::with_config(cfg());
        d.update("body", "hi", 0).unwrap();
        // 3s elapsed, idle threshold is 2s, min_interval 1s — due.
        assert!(d.snapshot_due("body", 3_000));
    }

    #[test]
    fn not_due_under_min_interval() {
        let mut d = DraftAutosave::with_config(cfg());
        d.update("body", "hi", 0).unwrap();
        d.mark_snapshotted("body", 100);
        // 500ms since snapshot < min_interval 1000 — never due.
        assert!(!d.snapshot_due("body", 600));
    }

    #[test]
    fn due_after_max_age_even_while_typing() {
        let mut d = DraftAutosave::with_config(cfg());
        d.update("body", "hi", 0).unwrap();
        // Continuously typing — last_edit keeps moving.
        d.update("body", "hi!", 9_500).unwrap();
        // 15s since last snapshot (0) > max_age 10s. Due despite recent edit.
        assert!(d.snapshot_due("body", 15_000));
    }

    #[test]
    fn mark_snapshotted_resets_clock() {
        let mut d = DraftAutosave::with_config(cfg());
        d.update("body", "hi", 0).unwrap();
        assert!(d.snapshot_due("body", 3_000));
        d.mark_snapshotted("body", 3_000);
        // Right after, not due again.
        assert!(!d.snapshot_due("body", 3_100));
    }

    #[test]
    fn unknown_field_not_due() {
        let d = DraftAutosave::new();
        assert!(!d.snapshot_due("nope", 999_999));
    }

    #[test]
    fn due_fields_lists_them() {
        let mut d = DraftAutosave::with_config(cfg());
        d.update("a", "x", 0).unwrap();
        d.update("b", "y", 100).unwrap();
        let due = d.due_fields(5_000);
        assert!(due.contains(&"a".to_string()));
        assert!(due.contains(&"b".to_string()));
    }

    #[test]
    fn clear_drops_field() {
        let mut d = DraftAutosave::new();
        d.update("a", "x", 0).unwrap();
        assert!(d.clear("a"));
        assert!(d.latest("a").is_none());
    }

    #[test]
    fn nonmonotonic_rejected() {
        let mut d = DraftAutosave::new();
        d.update("a", "x", 200).unwrap();
        assert!(matches!(d.update("a", "y", 100).unwrap_err(), AutosaveError::NonMonotonic { .. }));
    }

    #[test]
    fn empty_field_rejected() {
        let mut d = DraftAutosave::new();
        assert!(matches!(d.update("", "x", 0).unwrap_err(), AutosaveError::EmptyField));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DraftAutosave::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(d.validate().unwrap_err(), AutosaveError::SchemaMismatch));
    }

    #[test]
    fn autosave_serde_roundtrip() {
        let mut d = DraftAutosave::new();
        d.update("body", "hi", 0).unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: DraftAutosave = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
