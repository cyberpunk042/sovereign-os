//! `sovereign-cockpit-presence-roster` — collaborator presence indicators.
//!
//! Each entry: `(operator_id, label, status, last_seen_ts)`. `set/
//! observe` updates the entry. `mark_idle_if_older(now, threshold_ms)`
//! flips `Online → Idle` for any entry whose `last_seen_ts` is too
//! old. Distinct from sovereign-cockpit-presence-mode (operator's own
//! presence) — this is the collaborator-display lane.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Online.
    Online,
    /// Idle.
    Idle,
    /// Busy.
    Busy,
    /// Offline.
    Offline,
}

/// One entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Operator id.
    pub operator_id: String,
    /// Label.
    pub label: String,
    /// Status.
    pub status: Status,
    /// Last seen ts.
    pub last_seen_ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PresenceRoster {
    /// Schema version.
    pub schema_version: String,
    /// operator_id → entry.
    pub roster: BTreeMap<String, Entry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RosterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty operator id.
    #[error("operator id empty")]
    EmptyOperator,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
}

impl PresenceRoster {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            roster: BTreeMap::new(),
        }
    }

    /// Set / replace.
    pub fn set(&mut self, entry: Entry) -> Result<(), RosterError> {
        if entry.operator_id.is_empty() {
            return Err(RosterError::EmptyOperator);
        }
        if entry.label.is_empty() {
            return Err(RosterError::EmptyLabel);
        }
        self.roster.insert(entry.operator_id.clone(), entry);
        Ok(())
    }

    /// Observe a heartbeat (just updates last_seen + may flip Idle → Online).
    pub fn observe(&mut self, operator_id: &str, now_ms: u64) -> bool {
        if let Some(e) = self.roster.get_mut(operator_id) {
            e.last_seen_ts_ms = now_ms;
            if e.status == Status::Idle {
                e.status = Status::Online;
            }
            return true;
        }
        false
    }

    /// Remove.
    pub fn remove(&mut self, operator_id: &str) -> bool {
        self.roster.remove(operator_id).is_some()
    }

    /// Flip Online → Idle for stale entries.
    pub fn mark_idle_if_older(&mut self, now_ms: u64, threshold_ms: u64) -> usize {
        let mut flipped = 0;
        for e in self.roster.values_mut() {
            if e.status == Status::Online && now_ms.saturating_sub(e.last_seen_ts_ms) > threshold_ms
            {
                e.status = Status::Idle;
                flipped += 1;
            }
        }
        flipped
    }

    /// Status for an operator.
    pub fn status_of(&self, operator_id: &str) -> Option<Status> {
        self.roster.get(operator_id).map(|e| e.status)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RosterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RosterError::SchemaMismatch);
        }
        for e in self.roster.values() {
            if e.operator_id.is_empty() {
                return Err(RosterError::EmptyOperator);
            }
            if e.label.is_empty() {
                return Err(RosterError::EmptyLabel);
            }
        }
        Ok(())
    }
}

impl Default for PresenceRoster {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entry(id: &str, status: Status, ts: u64) -> Entry {
        Entry {
            operator_id: id.into(),
            label: id.into(),
            status,
            last_seen_ts_ms: ts,
        }
    }

    #[test]
    fn set_and_status() {
        let mut r = PresenceRoster::new();
        r.set(entry("alice", Status::Online, 100)).unwrap();
        assert_eq!(r.status_of("alice"), Some(Status::Online));
    }

    #[test]
    fn observe_returns_false_for_unknown() {
        let mut r = PresenceRoster::new();
        assert!(!r.observe("bob", 100));
    }

    #[test]
    fn observe_flips_idle_to_online() {
        let mut r = PresenceRoster::new();
        r.set(entry("alice", Status::Idle, 100)).unwrap();
        r.observe("alice", 200);
        assert_eq!(r.status_of("alice"), Some(Status::Online));
    }

    #[test]
    fn mark_idle_if_older() {
        let mut r = PresenceRoster::new();
        r.set(entry("alice", Status::Online, 100)).unwrap();
        r.set(entry("bob", Status::Online, 100_000)).unwrap();
        let n = r.mark_idle_if_older(120_000, 5_000);
        // alice's last_seen is 100, so age=119_900 → over threshold → flip.
        // bob's last_seen is 100_000, age=20_000 → also over 5_000 → flip.
        assert_eq!(n, 2);
    }

    #[test]
    fn mark_idle_busy_unchanged() {
        let mut r = PresenceRoster::new();
        r.set(entry("alice", Status::Busy, 0)).unwrap();
        r.mark_idle_if_older(99_999, 1_000);
        assert_eq!(r.status_of("alice"), Some(Status::Busy));
    }

    #[test]
    fn remove_returns_true_once() {
        let mut r = PresenceRoster::new();
        r.set(entry("alice", Status::Online, 0)).unwrap();
        assert!(r.remove("alice"));
        assert!(!r.remove("alice"));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut r = PresenceRoster::new();
        assert!(matches!(
            r.set(entry("", Status::Online, 0)).unwrap_err(),
            RosterError::EmptyOperator
        ));
        let mut bad = entry("alice", Status::Online, 0);
        bad.label = "".into();
        assert!(matches!(r.set(bad).unwrap_err(), RosterError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = PresenceRoster::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RosterError::SchemaMismatch
        ));
    }

    #[test]
    fn roster_serde_roundtrip() {
        let mut r = PresenceRoster::new();
        r.set(entry("alice", Status::Online, 0)).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: PresenceRoster = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
