//! `sovereign-cockpit-audit-trail` — bounded audit records.
//!
//! Record{actor, action, target, ts_ms}. record(...) appends;
//! capacity drops oldest. by_actor / by_target filter.
//! recent(n) returns newest first.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Audit record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Record {
    /// Actor (who).
    pub actor: String,
    /// Action (what).
    pub action: String,
    /// Target (on what).
    pub target: String,
    /// ts ms.
    pub ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuditTrail {
    /// Schema version.
    pub schema_version: String,
    /// Capacity.
    pub capacity: u32,
    /// Records newest-last.
    pub records: Vec<Record>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AuditError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("actor empty")]
    EmptyActor,
    /// Empty.
    #[error("action empty")]
    EmptyAction,
    /// Empty.
    #[error("target empty")]
    EmptyTarget,
    /// Zero capacity.
    #[error("capacity must be >= 1")]
    ZeroCapacity,
}

impl AuditTrail {
    /// New.
    pub fn new(capacity: u32) -> Result<Self, AuditError> {
        if capacity == 0 {
            return Err(AuditError::ZeroCapacity);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            records: Vec::new(),
        })
    }

    /// Record.
    pub fn record(
        &mut self,
        actor: &str,
        action: &str,
        target: &str,
        ts_ms: u64,
    ) -> Result<(), AuditError> {
        if actor.is_empty() {
            return Err(AuditError::EmptyActor);
        }
        if action.is_empty() {
            return Err(AuditError::EmptyAction);
        }
        if target.is_empty() {
            return Err(AuditError::EmptyTarget);
        }
        if (self.records.len() as u32) >= self.capacity {
            self.records.remove(0);
        }
        self.records.push(Record {
            actor: actor.into(),
            action: action.into(),
            target: target.into(),
            ts_ms,
        });
        Ok(())
    }

    /// By actor.
    pub fn by_actor(&self, actor: &str) -> Vec<&Record> {
        self.records.iter().filter(|r| r.actor == actor).collect()
    }

    /// By target.
    pub fn by_target(&self, target: &str) -> Vec<&Record> {
        self.records.iter().filter(|r| r.target == target).collect()
    }

    /// Recent (newest-first).
    pub fn recent(&self, n: usize) -> Vec<&Record> {
        self.records.iter().rev().take(n).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AuditError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(AuditError::SchemaMismatch);
        }
        if self.capacity == 0 {
            return Err(AuditError::ZeroCapacity);
        }
        for r in &self.records {
            if r.actor.is_empty() {
                return Err(AuditError::EmptyActor);
            }
            if r.action.is_empty() {
                return Err(AuditError::EmptyAction);
            }
            if r.target.is_empty() {
                return Err(AuditError::EmptyTarget);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_and_recent() {
        let mut t = AuditTrail::new(5).unwrap();
        t.record("alice", "edit", "doc1", 100).unwrap();
        t.record("bob", "delete", "doc2", 200).unwrap();
        let r = t.recent(2);
        assert_eq!(r[0].actor, "bob");
        assert_eq!(r[1].actor, "alice");
    }

    #[test]
    fn by_actor_filters() {
        let mut t = AuditTrail::new(5).unwrap();
        t.record("alice", "edit", "doc1", 0).unwrap();
        t.record("bob", "edit", "doc1", 0).unwrap();
        t.record("alice", "delete", "doc2", 0).unwrap();
        assert_eq!(t.by_actor("alice").len(), 2);
    }

    #[test]
    fn by_target_filters() {
        let mut t = AuditTrail::new(5).unwrap();
        t.record("alice", "edit", "doc1", 0).unwrap();
        t.record("bob", "edit", "doc1", 0).unwrap();
        assert_eq!(t.by_target("doc1").len(), 2);
    }

    #[test]
    fn capacity_drops_oldest() {
        let mut t = AuditTrail::new(2).unwrap();
        t.record("a", "x", "y", 1).unwrap();
        t.record("b", "x", "y", 2).unwrap();
        t.record("c", "x", "y", 3).unwrap();
        assert_eq!(t.records.len(), 2);
        assert_eq!(t.records[0].actor, "b");
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut t = AuditTrail::new(5).unwrap();
        assert!(matches!(
            t.record("", "a", "b", 0).unwrap_err(),
            AuditError::EmptyActor
        ));
        assert!(matches!(
            t.record("a", "", "b", 0).unwrap_err(),
            AuditError::EmptyAction
        ));
        assert!(matches!(
            t.record("a", "b", "", 0).unwrap_err(),
            AuditError::EmptyTarget
        ));
        assert!(matches!(
            AuditTrail::new(0).unwrap_err(),
            AuditError::ZeroCapacity
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = AuditTrail::new(5).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            AuditError::SchemaMismatch
        ));
    }

    #[test]
    fn trail_serde_roundtrip() {
        let mut t = AuditTrail::new(5).unwrap();
        t.record("a", "x", "y", 0).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: AuditTrail = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
