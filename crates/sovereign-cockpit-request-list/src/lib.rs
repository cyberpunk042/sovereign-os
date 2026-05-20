//! `sovereign-cockpit-request-list` — in-flight UI requests.
//!
//! Request{id, label, status, progress_bp, ts_started}.
//! start(id, label) creates In-Flight. update_progress(id, bp)
//! sets progress (clamped). complete(id) → Done. fail(id, err)
//! → Failed. cancel(id) → Cancelled. inflight() lists
//! In-Flight only.
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
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind", content = "data")]
pub enum Status {
    /// In flight.
    InFlight,
    /// Done.
    Done,
    /// Cancelled.
    Cancelled,
    /// Failed (error string).
    Failed(String),
}

/// Request.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Request {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Status.
    pub status: Status,
    /// Progress 0..=10000 bp.
    pub progress_bp: u32,
    /// Start ts ms.
    pub ts_started_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RequestList {
    /// Schema version.
    pub schema_version: String,
    /// id → request.
    pub requests: BTreeMap<String, Request>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RequestError {
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
    #[error("error empty")]
    EmptyError,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown id: {0}")]
    UnknownId(String),
    /// Not in flight.
    #[error("not in flight")]
    NotInFlight,
}

impl RequestList {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            requests: BTreeMap::new(),
        }
    }

    /// Start a request.
    pub fn start(&mut self, id: &str, label: &str, ts_started_ms: u64) -> Result<(), RequestError> {
        if id.is_empty() { return Err(RequestError::EmptyId); }
        if label.is_empty() { return Err(RequestError::EmptyLabel); }
        if self.requests.contains_key(id) { return Err(RequestError::DuplicateId(id.into())); }
        self.requests.insert(id.into(), Request {
            id: id.into(),
            label: label.into(),
            status: Status::InFlight,
            progress_bp: 0,
            ts_started_ms,
        });
        Ok(())
    }

    /// Update progress.
    pub fn update_progress(&mut self, id: &str, bp: u32) -> Result<(), RequestError> {
        let r = self.requests.get_mut(id).ok_or_else(|| RequestError::UnknownId(id.into()))?;
        if r.status != Status::InFlight { return Err(RequestError::NotInFlight); }
        r.progress_bp = bp.min(10_000);
        Ok(())
    }

    /// Complete.
    pub fn complete(&mut self, id: &str) -> Result<(), RequestError> {
        let r = self.requests.get_mut(id).ok_or_else(|| RequestError::UnknownId(id.into()))?;
        if r.status != Status::InFlight { return Err(RequestError::NotInFlight); }
        r.status = Status::Done;
        r.progress_bp = 10_000;
        Ok(())
    }

    /// Fail with error.
    pub fn fail(&mut self, id: &str, err: &str) -> Result<(), RequestError> {
        if err.is_empty() { return Err(RequestError::EmptyError); }
        let r = self.requests.get_mut(id).ok_or_else(|| RequestError::UnknownId(id.into()))?;
        if r.status != Status::InFlight { return Err(RequestError::NotInFlight); }
        r.status = Status::Failed(err.into());
        Ok(())
    }

    /// Cancel.
    pub fn cancel(&mut self, id: &str) -> Result<(), RequestError> {
        let r = self.requests.get_mut(id).ok_or_else(|| RequestError::UnknownId(id.into()))?;
        if r.status != Status::InFlight { return Err(RequestError::NotInFlight); }
        r.status = Status::Cancelled;
        Ok(())
    }

    /// Currently in-flight.
    pub fn inflight(&self) -> Vec<&Request> {
        self.requests.values().filter(|r| r.status == Status::InFlight).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RequestError> {
        if self.schema_version != SCHEMA_VERSION { return Err(RequestError::SchemaMismatch); }
        for (id, r) in &self.requests {
            if id.is_empty() { return Err(RequestError::EmptyId); }
            if r.label.is_empty() { return Err(RequestError::EmptyLabel); }
        }
        Ok(())
    }
}

impl Default for RequestList {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_then_complete() {
        let mut l = RequestList::new();
        l.start("a", "fetch", 0).unwrap();
        l.update_progress("a", 5000).unwrap();
        l.complete("a").unwrap();
        let r = l.requests.get("a").unwrap();
        assert_eq!(r.status, Status::Done);
        assert_eq!(r.progress_bp, 10_000);
    }

    #[test]
    fn fail_records_error() {
        let mut l = RequestList::new();
        l.start("a", "fetch", 0).unwrap();
        l.fail("a", "timeout").unwrap();
        match &l.requests.get("a").unwrap().status {
            Status::Failed(e) => assert_eq!(e, "timeout"),
            _ => panic!("expected Failed"),
        }
    }

    #[test]
    fn cancel_marks_cancelled() {
        let mut l = RequestList::new();
        l.start("a", "fetch", 0).unwrap();
        l.cancel("a").unwrap();
        assert_eq!(l.requests.get("a").unwrap().status, Status::Cancelled);
    }

    #[test]
    fn inflight_filters() {
        let mut l = RequestList::new();
        l.start("a", "x", 0).unwrap();
        l.start("b", "y", 0).unwrap();
        l.complete("a").unwrap();
        assert_eq!(l.inflight().len(), 1);
    }

    #[test]
    fn update_after_done_rejected() {
        let mut l = RequestList::new();
        l.start("a", "x", 0).unwrap();
        l.complete("a").unwrap();
        assert!(matches!(l.update_progress("a", 100).unwrap_err(), RequestError::NotInFlight));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut l = RequestList::new();
        assert!(matches!(l.start("", "x", 0).unwrap_err(), RequestError::EmptyId));
        assert!(matches!(l.start("a", "", 0).unwrap_err(), RequestError::EmptyLabel));
        l.start("a", "x", 0).unwrap();
        assert!(matches!(l.fail("a", "").unwrap_err(), RequestError::EmptyError));
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut l = RequestList::new();
        l.start("a", "x", 0).unwrap();
        assert!(matches!(l.start("a", "y", 0).unwrap_err(), RequestError::DuplicateId(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = RequestList::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), RequestError::SchemaMismatch));
    }

    #[test]
    fn list_serde_roundtrip() {
        let mut l = RequestList::new();
        l.start("a", "fetch", 0).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: RequestList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
