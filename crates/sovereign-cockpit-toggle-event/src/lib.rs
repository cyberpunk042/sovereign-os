//! `sovereign-cockpit-toggle-event` — append-only toggle audit log.
//!
//! Each `ToggleEvent` records (key, from_value, to_value, actor,
//! trace_id, at). The replay engine applies them in order; the audit
//! ledger pulls them when reconstructing configuration timelines.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One toggle event.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToggleEvent {
    /// Toggle key (operator-readable, dotted: "dash.alerts.show").
    pub key: String,
    /// Previous value.
    pub from_value: bool,
    /// New value.
    pub to_value: bool,
    /// Operator MS003 fingerprint.
    pub actor: String,
    /// M049 trace_id.
    pub trace_id: String,
    /// ISO-8601 UTC.
    pub at: String,
}

/// Log envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToggleEventLog {
    /// Schema version.
    pub schema_version: String,
    /// Entries.
    pub entries: Vec<ToggleEvent>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToggleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty key.
    #[error("toggle key empty")]
    EmptyKey,
    /// Empty actor.
    #[error("entry {0} actor empty")]
    EmptyActor(usize),
    /// Empty trace_id.
    #[error("entry {0} trace_id empty")]
    EmptyTraceId(usize),
    /// Empty timestamp.
    #[error("entry {0} at empty")]
    EmptyTimestamp(usize),
    /// from == to (no-op).
    #[error("entry {idx} no-op flip on key {key} (both {value})")]
    NoOp {
        /// idx.
        idx: usize,
        /// key.
        key: String,
        /// value.
        value: bool,
    },
}

impl ToggleEventLog {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
        }
    }

    /// Append a toggle event.
    pub fn record(&mut self, e: ToggleEvent) -> Result<(), ToggleError> {
        if e.key.is_empty() { return Err(ToggleError::EmptyKey); }
        if e.actor.is_empty() { return Err(ToggleError::EmptyActor(self.entries.len())); }
        if e.trace_id.is_empty() { return Err(ToggleError::EmptyTraceId(self.entries.len())); }
        if e.at.is_empty() { return Err(ToggleError::EmptyTimestamp(self.entries.len())); }
        if e.from_value == e.to_value {
            return Err(ToggleError::NoOp {
                idx: self.entries.len(),
                key: e.key,
                value: e.from_value,
            });
        }
        self.entries.push(e);
        Ok(())
    }

    /// Latest value for a key (None if never toggled).
    pub fn latest(&self, key: &str) -> Option<bool> {
        self.entries.iter().rev().find(|e| e.key == key).map(|e| e.to_value)
    }

    /// Count flips for a key.
    pub fn count_flips(&self, key: &str) -> usize {
        self.entries.iter().filter(|e| e.key == key).count()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToggleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToggleError::SchemaMismatch);
        }
        for (idx, e) in self.entries.iter().enumerate() {
            if e.key.is_empty() { return Err(ToggleError::EmptyKey); }
            if e.actor.is_empty() { return Err(ToggleError::EmptyActor(idx)); }
            if e.trace_id.is_empty() { return Err(ToggleError::EmptyTraceId(idx)); }
            if e.at.is_empty() { return Err(ToggleError::EmptyTimestamp(idx)); }
            if e.from_value == e.to_value {
                return Err(ToggleError::NoOp { idx, key: e.key.clone(), value: e.from_value });
            }
        }
        Ok(())
    }
}

impl Default for ToggleEventLog {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ev(key: &str, from: bool, to: bool) -> ToggleEvent {
        ToggleEvent {
            key: key.into(),
            from_value: from,
            to_value: to,
            actor: "op".into(),
            trace_id: "tr".into(),
            at: "2026-05-19T03:00:00Z".into(),
        }
    }

    #[test]
    fn empty_log_validates() {
        ToggleEventLog::new().validate().unwrap();
    }

    #[test]
    fn record_and_latest() {
        let mut l = ToggleEventLog::new();
        l.record(ev("a", false, true)).unwrap();
        assert_eq!(l.latest("a"), Some(true));
        l.record(ev("a", true, false)).unwrap();
        assert_eq!(l.latest("a"), Some(false));
    }

    #[test]
    fn count_flips() {
        let mut l = ToggleEventLog::new();
        l.record(ev("a", false, true)).unwrap();
        l.record(ev("a", true, false)).unwrap();
        l.record(ev("b", false, true)).unwrap();
        assert_eq!(l.count_flips("a"), 2);
        assert_eq!(l.count_flips("b"), 1);
        assert_eq!(l.count_flips("c"), 0);
    }

    #[test]
    fn no_op_rejected() {
        let mut l = ToggleEventLog::new();
        assert!(matches!(l.record(ev("a", true, true)).unwrap_err(), ToggleError::NoOp { .. }));
    }

    #[test]
    fn empty_key_rejected() {
        let mut l = ToggleEventLog::new();
        assert!(matches!(l.record(ev("", false, true)).unwrap_err(), ToggleError::EmptyKey));
    }

    #[test]
    fn empty_actor_rejected() {
        let mut l = ToggleEventLog::new();
        let mut e = ev("a", false, true);
        e.actor = String::new();
        assert!(matches!(l.record(e).unwrap_err(), ToggleError::EmptyActor(_)));
    }

    #[test]
    fn empty_trace_id_rejected() {
        let mut l = ToggleEventLog::new();
        let mut e = ev("a", false, true);
        e.trace_id = String::new();
        assert!(matches!(l.record(e).unwrap_err(), ToggleError::EmptyTraceId(_)));
    }

    #[test]
    fn latest_returns_none_for_unknown() {
        let l = ToggleEventLog::new();
        assert_eq!(l.latest("x"), None);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = ToggleEventLog::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), ToggleError::SchemaMismatch));
    }

    #[test]
    fn log_serde_roundtrip() {
        let mut l = ToggleEventLog::new();
        l.record(ev("a", false, true)).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: ToggleEventLog = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
