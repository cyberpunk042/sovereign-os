//! `sovereign-cockpit-alert-acknowledge` — alert ack tracker.
//!
//! Ack{acker, ts_ms, note}. acknowledge(alert, acker, now, note)
//! records. unack(alert) clears. is_acknowledged returns bool.
//! unacked() lists alert ids without an Ack (registered via
//! register).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Ack.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Ack {
    /// Acker (operator id).
    pub acker: String,
    /// ts ms.
    pub ts_ms: u64,
    /// Note.
    pub note: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AlertAcknowledge {
    /// Schema version.
    pub schema_version: String,
    /// alert id → ack (None = unacked).
    pub alerts: BTreeMap<String, Option<Ack>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AckError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("alert id empty")]
    EmptyAlert,
    /// Empty.
    #[error("acker empty")]
    EmptyAcker,
    /// Empty.
    #[error("note empty")]
    EmptyNote,
    /// Unknown.
    #[error("unknown alert: {0}")]
    UnknownAlert(String),
}

impl AlertAcknowledge {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            alerts: BTreeMap::new(),
        }
    }

    /// Register an alert (initially unacked).
    pub fn register(&mut self, alert: &str) -> Result<(), AckError> {
        if alert.is_empty() {
            return Err(AckError::EmptyAlert);
        }
        self.alerts.entry(alert.into()).or_insert(None);
        Ok(())
    }

    /// Acknowledge.
    pub fn acknowledge(
        &mut self,
        alert: &str,
        acker: &str,
        now_ms: u64,
        note: &str,
    ) -> Result<(), AckError> {
        if alert.is_empty() {
            return Err(AckError::EmptyAlert);
        }
        if acker.is_empty() {
            return Err(AckError::EmptyAcker);
        }
        if note.is_empty() {
            return Err(AckError::EmptyNote);
        }
        let entry = self.alerts.entry(alert.into()).or_insert(None);
        *entry = Some(Ack {
            acker: acker.into(),
            ts_ms: now_ms,
            note: note.into(),
        });
        Ok(())
    }

    /// Un-acknowledge.
    pub fn unack(&mut self, alert: &str) -> Result<(), AckError> {
        let e = self
            .alerts
            .get_mut(alert)
            .ok_or_else(|| AckError::UnknownAlert(alert.into()))?;
        *e = None;
        Ok(())
    }

    /// Is alert acked?
    pub fn is_acknowledged(&self, alert: &str) -> bool {
        matches!(self.alerts.get(alert), Some(Some(_)))
    }

    /// Unacked alerts.
    pub fn unacked(&self) -> Vec<&str> {
        self.alerts
            .iter()
            .filter(|(_, v)| v.is_none())
            .map(|(k, _)| k.as_str())
            .collect()
    }

    /// Acked alerts.
    pub fn acked(&self) -> Vec<&str> {
        self.alerts
            .iter()
            .filter(|(_, v)| v.is_some())
            .map(|(k, _)| k.as_str())
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AckError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(AckError::SchemaMismatch);
        }
        for (k, v) in &self.alerts {
            if k.is_empty() {
                return Err(AckError::EmptyAlert);
            }
            if let Some(a) = v {
                if a.acker.is_empty() {
                    return Err(AckError::EmptyAcker);
                }
                if a.note.is_empty() {
                    return Err(AckError::EmptyNote);
                }
            }
        }
        Ok(())
    }
}

impl Default for AlertAcknowledge {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_then_ack() {
        let mut a = AlertAcknowledge::new();
        a.register("alert1").unwrap();
        assert!(!a.is_acknowledged("alert1"));
        a.acknowledge("alert1", "alice", 100, "investigating")
            .unwrap();
        assert!(a.is_acknowledged("alert1"));
    }

    #[test]
    fn unack_clears() {
        let mut a = AlertAcknowledge::new();
        a.acknowledge("alert1", "alice", 100, "x").unwrap();
        a.unack("alert1").unwrap();
        assert!(!a.is_acknowledged("alert1"));
    }

    #[test]
    fn unack_unknown_rejected() {
        let mut a = AlertAcknowledge::new();
        assert!(matches!(
            a.unack("nope").unwrap_err(),
            AckError::UnknownAlert(_)
        ));
    }

    #[test]
    fn unacked_and_acked() {
        let mut a = AlertAcknowledge::new();
        a.register("a1").unwrap();
        a.register("a2").unwrap();
        a.acknowledge("a2", "alice", 100, "x").unwrap();
        assert_eq!(a.unacked(), vec!["a1"]);
        assert_eq!(a.acked(), vec!["a2"]);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut a = AlertAcknowledge::new();
        assert!(matches!(
            a.acknowledge("", "u", 0, "n").unwrap_err(),
            AckError::EmptyAlert
        ));
        assert!(matches!(
            a.acknowledge("a", "", 0, "n").unwrap_err(),
            AckError::EmptyAcker
        ));
        assert!(matches!(
            a.acknowledge("a", "u", 0, "").unwrap_err(),
            AckError::EmptyNote
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut a = AlertAcknowledge::new();
        a.schema_version = "9.9.9".into();
        assert!(matches!(
            a.validate().unwrap_err(),
            AckError::SchemaMismatch
        ));
    }

    #[test]
    fn ack_serde_roundtrip() {
        let mut a = AlertAcknowledge::new();
        a.acknowledge("a1", "alice", 100, "x").unwrap();
        let j = serde_json::to_string(&a).unwrap();
        let back: AlertAcknowledge = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
