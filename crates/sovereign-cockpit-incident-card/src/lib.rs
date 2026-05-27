//! `sovereign-cockpit-incident-card` — incident summary card.
//!
//! Incident{id, title, severity, first_seen_ts_ms, last_seen_ts_ms,
//! occurrence_count, affected_count}. observe(now, affected)
//! increments occurrence_count, advances last_seen, and sets/keeps
//! the maximum affected_count. resolve marks resolved_at_ms; an
//! active card has resolved_at_ms == 0.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Info.
    Info,
    /// Warning.
    Warning,
    /// Error.
    Error,
    /// Critical.
    Critical,
}

/// Card.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct IncidentCard {
    /// Schema version.
    pub schema_version: String,
    /// Stable id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Severity.
    pub severity: Severity,
    /// First-seen ts ms.
    pub first_seen_ts_ms: u64,
    /// Last-seen ts ms.
    pub last_seen_ts_ms: u64,
    /// Occurrence count.
    pub occurrence_count: u64,
    /// Maximum affected count seen.
    pub affected_count: u64,
    /// Resolved-at ts ms (0 = active).
    pub resolved_at_ms: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CardError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
}

impl IncidentCard {
    /// New (active card with one observation).
    pub fn new(
        id: &str,
        title: &str,
        severity: Severity,
        now_ms: u64,
        affected: u64,
    ) -> Result<Self, CardError> {
        if id.is_empty() {
            return Err(CardError::EmptyId);
        }
        if title.is_empty() {
            return Err(CardError::EmptyTitle);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            id: id.into(),
            title: title.into(),
            severity,
            first_seen_ts_ms: now_ms,
            last_seen_ts_ms: now_ms,
            occurrence_count: 1,
            affected_count: affected,
            resolved_at_ms: 0,
        })
    }

    /// Record another occurrence.
    pub fn observe(&mut self, now_ms: u64, affected: u64) {
        self.occurrence_count = self.occurrence_count.saturating_add(1);
        if now_ms > self.last_seen_ts_ms {
            self.last_seen_ts_ms = now_ms;
        }
        if affected > self.affected_count {
            self.affected_count = affected;
        }
        self.resolved_at_ms = 0;
    }

    /// Resolve.
    pub fn resolve(&mut self, now_ms: u64) {
        self.resolved_at_ms = now_ms;
    }

    /// Active?
    pub fn active(&self) -> bool {
        self.resolved_at_ms == 0
    }

    /// Duration so far in ms (until resolved_at or now passed in).
    pub fn duration_ms(&self, now_ms: u64) -> u64 {
        let end = if self.resolved_at_ms == 0 {
            now_ms
        } else {
            self.resolved_at_ms
        };
        end.saturating_sub(self.first_seen_ts_ms)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CardError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CardError::SchemaMismatch);
        }
        if self.id.is_empty() {
            return Err(CardError::EmptyId);
        }
        if self.title.is_empty() {
            return Err(CardError::EmptyTitle);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn observe_updates_count_and_max_affected() {
        let mut c = IncidentCard::new("i1", "DB down", Severity::Critical, 1000, 5).unwrap();
        c.observe(1100, 3);
        c.observe(1200, 10);
        assert_eq!(c.occurrence_count, 3);
        assert_eq!(c.last_seen_ts_ms, 1200);
        assert_eq!(c.affected_count, 10);
    }

    #[test]
    fn resolve_marks_inactive() {
        let mut c = IncidentCard::new("i1", "x", Severity::Warning, 100, 1).unwrap();
        c.resolve(500);
        assert!(!c.active());
        assert_eq!(c.duration_ms(9000), 400);
    }

    #[test]
    fn observe_unresolves() {
        let mut c = IncidentCard::new("i1", "x", Severity::Warning, 100, 1).unwrap();
        c.resolve(200);
        c.observe(300, 5);
        assert!(c.active());
    }

    #[test]
    fn duration_uses_now_when_active() {
        let c = IncidentCard::new("i1", "x", Severity::Warning, 100, 1).unwrap();
        assert_eq!(c.duration_ms(500), 400);
    }

    #[test]
    fn empty_inputs_rejected() {
        assert!(matches!(
            IncidentCard::new("", "t", Severity::Info, 0, 0).unwrap_err(),
            CardError::EmptyId
        ));
        assert!(matches!(
            IncidentCard::new("i", "", Severity::Info, 0, 0).unwrap_err(),
            CardError::EmptyTitle
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = IncidentCard::new("i", "t", Severity::Info, 0, 0).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            CardError::SchemaMismatch
        ));
    }

    #[test]
    fn card_serde_roundtrip() {
        let mut c = IncidentCard::new("i1", "DB", Severity::Critical, 100, 5).unwrap();
        c.observe(200, 7);
        let j = serde_json::to_string(&c).unwrap();
        let back: IncidentCard = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
