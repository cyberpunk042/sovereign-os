//! `sovereign-cockpit-status-page-list` — external status-page registry.
//!
//! `register(page)`; `update_state(id, new_state, ts)`; `list_all()`
//! returns ordered (insertion); `list_by_state(state)` filters.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// Operational.
    Operational,
    /// Degraded.
    Degraded,
    /// Partial outage.
    PartialOutage,
    /// Major outage.
    MajorOutage,
    /// Maintenance.
    Maintenance,
    /// Unknown.
    Unknown,
}

/// One status-page entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusPage {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Source URL.
    pub url: String,
    /// Current state.
    pub current_state: State,
    /// Last check ts.
    pub last_check_ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusPageList {
    /// Schema version.
    pub schema_version: String,
    /// Ordered pages.
    pub pages: Vec<StatusPage>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StatusError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("status page id empty")]
    EmptyId,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Empty URL.
    #[error("url empty")]
    EmptyUrl,
    /// Duplicate.
    #[error("duplicate status page id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown status page id: {0}")]
    UnknownId(String),
}

impl StatusPageList {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            pages: Vec::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, page: StatusPage) -> Result<(), StatusError> {
        if page.id.is_empty() { return Err(StatusError::EmptyId); }
        if page.label.is_empty() { return Err(StatusError::EmptyLabel); }
        if page.url.is_empty() { return Err(StatusError::EmptyUrl); }
        if self.pages.iter().any(|p| p.id == page.id) {
            return Err(StatusError::DuplicateId(page.id));
        }
        self.pages.push(page);
        Ok(())
    }

    /// Update.
    pub fn update_state(&mut self, id: &str, new_state: State, ts_ms: u64) -> Result<(), StatusError> {
        let p = self.pages.iter_mut().find(|p| p.id == id)
            .ok_or_else(|| StatusError::UnknownId(id.into()))?;
        p.current_state = new_state;
        p.last_check_ts_ms = ts_ms;
        Ok(())
    }

    /// List all in registration order.
    pub fn list_all(&self) -> Vec<StatusPage> {
        self.pages.clone()
    }

    /// List by state.
    pub fn list_by_state(&self, state: State) -> Vec<StatusPage> {
        self.pages.iter().filter(|p| p.current_state == state).cloned().collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StatusError> {
        if self.schema_version != SCHEMA_VERSION { return Err(StatusError::SchemaMismatch); }
        for p in &self.pages {
            if p.id.is_empty() { return Err(StatusError::EmptyId); }
            if p.label.is_empty() { return Err(StatusError::EmptyLabel); }
            if p.url.is_empty() { return Err(StatusError::EmptyUrl); }
        }
        Ok(())
    }
}

impl Default for StatusPageList {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn page(id: &str, label: &str, state: State) -> StatusPage {
        StatusPage {
            id: id.into(),
            label: label.into(),
            url: format!("https://status.example/{id}"),
            current_state: state,
            last_check_ts_ms: 0,
        }
    }

    #[test]
    fn register_and_list() {
        let mut l = StatusPageList::new();
        l.register(page("github", "GitHub", State::Operational)).unwrap();
        l.register(page("aws-us-east-1", "AWS US-EAST-1", State::Operational)).unwrap();
        assert_eq!(l.list_all().len(), 2);
    }

    #[test]
    fn update_state() {
        let mut l = StatusPageList::new();
        l.register(page("github", "GitHub", State::Operational)).unwrap();
        l.update_state("github", State::Degraded, 1000).unwrap();
        assert_eq!(l.list_all()[0].current_state, State::Degraded);
    }

    #[test]
    fn list_by_state() {
        let mut l = StatusPageList::new();
        l.register(page("a", "A", State::Operational)).unwrap();
        l.register(page("b", "B", State::Degraded)).unwrap();
        l.register(page("c", "C", State::Operational)).unwrap();
        assert_eq!(l.list_by_state(State::Operational).len(), 2);
        assert_eq!(l.list_by_state(State::Degraded).len(), 1);
    }

    #[test]
    fn duplicate_rejected() {
        let mut l = StatusPageList::new();
        l.register(page("a", "A", State::Operational)).unwrap();
        assert!(matches!(l.register(page("a", "A", State::Operational)).unwrap_err(), StatusError::DuplicateId(_)));
    }

    #[test]
    fn unknown_id() {
        let mut l = StatusPageList::new();
        assert!(matches!(l.update_state("nope", State::Operational, 0).unwrap_err(), StatusError::UnknownId(_)));
    }

    #[test]
    fn empty_fields_rejected() {
        let mut l = StatusPageList::new();
        let mut bad = page("a", "A", State::Operational);
        bad.id = "".into();
        assert!(matches!(l.register(bad).unwrap_err(), StatusError::EmptyId));
        let mut bad2 = page("a", "A", State::Operational);
        bad2.url = "".into();
        assert!(matches!(l.register(bad2).unwrap_err(), StatusError::EmptyUrl));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = StatusPageList::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), StatusError::SchemaMismatch));
    }

    #[test]
    fn list_serde_roundtrip() {
        let mut l = StatusPageList::new();
        l.register(page("a", "A", State::Operational)).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: StatusPageList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
