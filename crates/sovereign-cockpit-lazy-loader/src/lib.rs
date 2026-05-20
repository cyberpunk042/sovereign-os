//! `sovereign-cockpit-lazy-loader` — per-resource state.
//!
//! Phase{Idle/Loading/Loaded/Failed}. request(id) Idle/Failed →
//! Loading. complete → Loaded. fail(error) → Failed and bumps
//! attempts. retry(id) Failed → Loading iff attempts <
//! max_attempts. reset(id) → Idle.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "phase", content = "error")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Loading.
    Loading,
    /// Loaded.
    Loaded,
    /// Failed(error).
    Failed(String),
}

/// Resource record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Resource {
    /// Phase.
    pub phase: Phase,
    /// Attempt count.
    pub attempts: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LazyLoader {
    /// Schema version.
    pub schema_version: String,
    /// Max attempts before giving up.
    pub max_attempts: u32,
    /// id → resource.
    pub resources: BTreeMap<String, Resource>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LoaderError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("error empty")]
    EmptyError,
    /// Zero max.
    #[error("max_attempts must be >= 1")]
    ZeroMaxAttempts,
    /// Unknown.
    #[error("unknown resource: {0}")]
    UnknownResource(String),
    /// Invalid phase.
    #[error("invalid phase for operation")]
    InvalidPhase,
    /// Out of attempts.
    #[error("out of attempts")]
    OutOfAttempts,
}

impl LazyLoader {
    /// New.
    pub fn new(max_attempts: u32) -> Result<Self, LoaderError> {
        if max_attempts == 0 { return Err(LoaderError::ZeroMaxAttempts); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            max_attempts,
            resources: BTreeMap::new(),
        })
    }

    /// Request a resource (Idle/Failed → Loading).
    pub fn request(&mut self, id: &str) -> Result<(), LoaderError> {
        if id.is_empty() { return Err(LoaderError::EmptyId); }
        let r = self.resources.entry(id.into()).or_insert(Resource { phase: Phase::Idle, attempts: 0 });
        match &r.phase {
            Phase::Idle | Phase::Failed(_) => {
                r.phase = Phase::Loading;
                r.attempts = r.attempts.saturating_add(1);
                Ok(())
            }
            _ => Err(LoaderError::InvalidPhase),
        }
    }

    /// Complete a load.
    pub fn complete(&mut self, id: &str) -> Result<(), LoaderError> {
        let r = self.resources.get_mut(id).ok_or_else(|| LoaderError::UnknownResource(id.into()))?;
        if !matches!(r.phase, Phase::Loading) { return Err(LoaderError::InvalidPhase); }
        r.phase = Phase::Loaded;
        Ok(())
    }

    /// Fail with error.
    pub fn fail(&mut self, id: &str, err: &str) -> Result<(), LoaderError> {
        if err.is_empty() { return Err(LoaderError::EmptyError); }
        let r = self.resources.get_mut(id).ok_or_else(|| LoaderError::UnknownResource(id.into()))?;
        if !matches!(r.phase, Phase::Loading) { return Err(LoaderError::InvalidPhase); }
        r.phase = Phase::Failed(err.into());
        Ok(())
    }

    /// Retry a failed resource (Failed → Loading iff attempts < max).
    pub fn retry(&mut self, id: &str) -> Result<(), LoaderError> {
        let r = self.resources.get_mut(id).ok_or_else(|| LoaderError::UnknownResource(id.into()))?;
        if !matches!(r.phase, Phase::Failed(_)) { return Err(LoaderError::InvalidPhase); }
        if r.attempts >= self.max_attempts { return Err(LoaderError::OutOfAttempts); }
        r.phase = Phase::Loading;
        r.attempts = r.attempts.saturating_add(1);
        Ok(())
    }

    /// Reset to Idle (clears attempts).
    pub fn reset(&mut self, id: &str) -> Result<(), LoaderError> {
        let r = self.resources.get_mut(id).ok_or_else(|| LoaderError::UnknownResource(id.into()))?;
        r.phase = Phase::Idle;
        r.attempts = 0;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LoaderError> {
        if self.schema_version != SCHEMA_VERSION { return Err(LoaderError::SchemaMismatch); }
        if self.max_attempts == 0 { return Err(LoaderError::ZeroMaxAttempts); }
        for k in self.resources.keys() {
            if k.is_empty() { return Err(LoaderError::EmptyId); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn request_then_complete() {
        let mut l = LazyLoader::new(3).unwrap();
        l.request("a").unwrap();
        l.complete("a").unwrap();
        assert!(matches!(l.resources.get("a").unwrap().phase, Phase::Loaded));
    }

    #[test]
    fn fail_then_retry() {
        let mut l = LazyLoader::new(3).unwrap();
        l.request("a").unwrap();
        l.fail("a", "timeout").unwrap();
        l.retry("a").unwrap();
        assert!(matches!(l.resources.get("a").unwrap().phase, Phase::Loading));
        assert_eq!(l.resources.get("a").unwrap().attempts, 2);
    }

    #[test]
    fn retry_out_of_attempts() {
        let mut l = LazyLoader::new(2).unwrap();
        l.request("a").unwrap();
        l.fail("a", "e").unwrap();
        l.retry("a").unwrap();
        l.fail("a", "e2").unwrap();
        assert!(matches!(l.retry("a").unwrap_err(), LoaderError::OutOfAttempts));
    }

    #[test]
    fn reset_clears() {
        let mut l = LazyLoader::new(2).unwrap();
        l.request("a").unwrap();
        l.fail("a", "e").unwrap();
        l.reset("a").unwrap();
        let r = l.resources.get("a").unwrap();
        assert!(matches!(r.phase, Phase::Idle));
        assert_eq!(r.attempts, 0);
    }

    #[test]
    fn complete_without_loading_rejected() {
        let mut l = LazyLoader::new(2).unwrap();
        l.request("a").unwrap();
        l.complete("a").unwrap();
        assert!(matches!(l.complete("a").unwrap_err(), LoaderError::InvalidPhase));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut l = LazyLoader::new(2).unwrap();
        assert!(matches!(l.request("").unwrap_err(), LoaderError::EmptyId));
        l.request("a").unwrap();
        assert!(matches!(l.fail("a", "").unwrap_err(), LoaderError::EmptyError));
        assert!(matches!(LazyLoader::new(0).unwrap_err(), LoaderError::ZeroMaxAttempts));
    }

    #[test]
    fn unknown_resource_rejected() {
        let mut l = LazyLoader::new(2).unwrap();
        assert!(matches!(l.complete("nope").unwrap_err(), LoaderError::UnknownResource(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = LazyLoader::new(2).unwrap();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), LoaderError::SchemaMismatch));
    }

    #[test]
    fn loader_serde_roundtrip() {
        let mut l = LazyLoader::new(3).unwrap();
        l.request("a").unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: LazyLoader = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
