//! `sovereign-cockpit-sync-status` — sync status indicator.
//!
//! Status{Saved/Saving/Failed/Stale}. begin_save sets Saving;
//! ok(now) sets Saved + last_saved_ms; fail(error) sets Failed
//! + error_text. observe(now) flips Saved → Stale once
//! stale_after_ms elapses.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Saved.
    Saved,
    /// Saving.
    Saving,
    /// Failed.
    Failed,
    /// Stale.
    Stale,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SyncStatus {
    /// Schema version.
    pub schema_version: String,
    /// Status.
    pub status: Status,
    /// Last successful save ts ms.
    pub last_saved_ms: u64,
    /// Stale window after Saved.
    pub stale_after_ms: u64,
    /// Last error text.
    pub error: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SyncError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("error text empty")]
    EmptyError,
    /// Zero.
    #[error("stale_after_ms must be >= 1")]
    ZeroStale,
}

impl SyncStatus {
    /// New.
    pub fn new(stale_after_ms: u64) -> Result<Self, SyncError> {
        if stale_after_ms == 0 { return Err(SyncError::ZeroStale); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            status: Status::Saved,
            last_saved_ms: 0,
            stale_after_ms,
            error: None,
        })
    }

    /// Begin a save.
    pub fn begin_save(&mut self) {
        self.status = Status::Saving;
        self.error = None;
    }

    /// Save succeeded.
    pub fn ok(&mut self, now_ms: u64) {
        self.status = Status::Saved;
        self.last_saved_ms = now_ms;
        self.error = None;
    }

    /// Save failed with text.
    pub fn fail(&mut self, error: &str) -> Result<(), SyncError> {
        if error.is_empty() { return Err(SyncError::EmptyError); }
        self.status = Status::Failed;
        self.error = Some(error.into());
        Ok(())
    }

    /// Observe now — flip Saved → Stale after stale_after_ms.
    pub fn observe(&mut self, now_ms: u64) -> Status {
        if self.status == Status::Saved
            && now_ms.saturating_sub(self.last_saved_ms) >= self.stale_after_ms
        {
            self.status = Status::Stale;
        }
        self.status
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SyncError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SyncError::SchemaMismatch); }
        if self.stale_after_ms == 0 { return Err(SyncError::ZeroStale); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn begin_then_ok_saved() {
        let mut s = SyncStatus::new(10_000).unwrap();
        s.begin_save();
        assert_eq!(s.status, Status::Saving);
        s.ok(100);
        assert_eq!(s.status, Status::Saved);
        assert_eq!(s.last_saved_ms, 100);
    }

    #[test]
    fn fail_sets_error() {
        let mut s = SyncStatus::new(10_000).unwrap();
        s.begin_save();
        s.fail("network down").unwrap();
        assert_eq!(s.status, Status::Failed);
        assert_eq!(s.error.as_deref(), Some("network down"));
    }

    #[test]
    fn observe_flips_to_stale_after_window() {
        let mut s = SyncStatus::new(1000).unwrap();
        s.ok(0);
        assert_eq!(s.observe(500), Status::Saved);
        assert_eq!(s.observe(1500), Status::Stale);
    }

    #[test]
    fn ok_clears_error() {
        let mut s = SyncStatus::new(10_000).unwrap();
        s.fail("oops").unwrap();
        s.ok(100);
        assert!(s.error.is_none());
    }

    #[test]
    fn empty_error_rejected() {
        let mut s = SyncStatus::new(10_000).unwrap();
        assert!(matches!(s.fail("").unwrap_err(), SyncError::EmptyError));
    }

    #[test]
    fn zero_stale_rejected() {
        assert!(matches!(SyncStatus::new(0).unwrap_err(), SyncError::ZeroStale));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SyncStatus::new(10_000).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SyncError::SchemaMismatch));
    }

    #[test]
    fn status_serde_roundtrip() {
        let mut s = SyncStatus::new(10_000).unwrap();
        s.ok(100);
        let j = serde_json::to_string(&s).unwrap();
        let back: SyncStatus = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
