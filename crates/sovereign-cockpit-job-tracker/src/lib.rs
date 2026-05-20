//! `sovereign-cockpit-job-tracker` — long-running job progress.
//!
//! Job{id, total, done, started_at, last_update_at}. progress() in
//! basis points; eta_ms(now) extrapolates from average throughput.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Job.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Job {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Total work.
    pub total: u64,
    /// Done work.
    pub done: u64,
    /// Start ts.
    pub started_at_ms: u64,
    /// Last update ts.
    pub last_update_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct JobTracker {
    /// Schema version.
    pub schema_version: String,
    /// id → job.
    pub jobs: BTreeMap<String, Job>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TrackerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate job id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown job: {0}")]
    UnknownJob(String),
}

impl JobTracker {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            jobs: BTreeMap::new(),
        }
    }

    /// Start.
    pub fn start(&mut self, id: &str, label: &str, total: u64, ts_ms: u64) -> Result<(), TrackerError> {
        if id.is_empty() { return Err(TrackerError::EmptyId); }
        if label.is_empty() { return Err(TrackerError::EmptyLabel); }
        if self.jobs.contains_key(id) { return Err(TrackerError::DuplicateId(id.into())); }
        self.jobs.insert(id.into(), Job {
            id: id.into(),
            label: label.into(),
            total,
            done: 0,
            started_at_ms: ts_ms,
            last_update_ms: ts_ms,
        });
        Ok(())
    }

    /// Update done count.
    pub fn update(&mut self, id: &str, done: u64, ts_ms: u64) -> Result<(), TrackerError> {
        let j = self.jobs.get_mut(id).ok_or_else(|| TrackerError::UnknownJob(id.into()))?;
        j.done = done.min(j.total);
        j.last_update_ms = ts_ms;
        Ok(())
    }

    /// Increment done.
    pub fn inc(&mut self, id: &str, delta: u64, ts_ms: u64) -> Result<(), TrackerError> {
        let j = self.jobs.get_mut(id).ok_or_else(|| TrackerError::UnknownJob(id.into()))?;
        j.done = (j.done.saturating_add(delta)).min(j.total);
        j.last_update_ms = ts_ms;
        Ok(())
    }

    /// Progress in bp.
    pub fn progress_bp(&self, id: &str) -> Option<u32> {
        let j = self.jobs.get(id)?;
        if j.total == 0 { return Some(10000); }
        Some(((j.done.saturating_mul(10_000)) / j.total) as u32)
    }

    /// ETA in ms, None if not enough data or done.
    pub fn eta_ms(&self, id: &str, now_ms: u64) -> Option<u64> {
        let j = self.jobs.get(id)?;
        if j.done == 0 || j.done >= j.total { return None; }
        let elapsed = now_ms.saturating_sub(j.started_at_ms);
        if elapsed == 0 { return None; }
        // throughput = done / elapsed → remaining / throughput.
        let remaining = j.total - j.done;
        Some((remaining.saturating_mul(elapsed)) / j.done)
    }

    /// Finish & remove.
    pub fn finish(&mut self, id: &str) -> bool {
        self.jobs.remove(id).is_some()
    }

    /// Active count.
    pub fn active_count(&self) -> usize {
        self.jobs.len()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TrackerError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TrackerError::SchemaMismatch); }
        for (id, j) in &self.jobs {
            if id.is_empty() { return Err(TrackerError::EmptyId); }
            if j.label.is_empty() { return Err(TrackerError::EmptyLabel); }
        }
        Ok(())
    }
}

impl Default for JobTracker {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_and_progress() {
        let mut t = JobTracker::new();
        t.start("j", "Job", 100, 0).unwrap();
        t.update("j", 50, 100).unwrap();
        assert_eq!(t.progress_bp("j"), Some(5000));
    }

    #[test]
    fn inc_clamps_to_total() {
        let mut t = JobTracker::new();
        t.start("j", "J", 100, 0).unwrap();
        t.inc("j", 150, 100).unwrap();
        assert_eq!(t.progress_bp("j"), Some(10000));
    }

    #[test]
    fn eta_linear() {
        let mut t = JobTracker::new();
        t.start("j", "J", 100, 0).unwrap();
        t.update("j", 25, 1000).unwrap();
        // 25 done in 1000ms; 75 remaining at 25/ms → 75 × 1000 / 25 = 3000ms.
        assert_eq!(t.eta_ms("j", 1000), Some(3000));
    }

    #[test]
    fn eta_none_when_done() {
        let mut t = JobTracker::new();
        t.start("j", "J", 100, 0).unwrap();
        t.update("j", 100, 1000).unwrap();
        assert!(t.eta_ms("j", 1000).is_none());
    }

    #[test]
    fn eta_none_when_no_progress() {
        let mut t = JobTracker::new();
        t.start("j", "J", 100, 0).unwrap();
        assert!(t.eta_ms("j", 1000).is_none());
    }

    #[test]
    fn finish_removes() {
        let mut t = JobTracker::new();
        t.start("j", "J", 100, 0).unwrap();
        assert!(t.finish("j"));
        assert_eq!(t.active_count(), 0);
    }

    #[test]
    fn duplicate_rejected() {
        let mut t = JobTracker::new();
        t.start("j", "J", 100, 0).unwrap();
        assert!(matches!(t.start("j", "J", 100, 0).unwrap_err(), TrackerError::DuplicateId(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut t = JobTracker::new();
        assert!(matches!(t.start("", "J", 1, 0).unwrap_err(), TrackerError::EmptyId));
        assert!(matches!(t.start("j", "", 1, 0).unwrap_err(), TrackerError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = JobTracker::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TrackerError::SchemaMismatch));
    }

    #[test]
    fn tracker_serde_roundtrip() {
        let mut t = JobTracker::new();
        t.start("j", "J", 100, 0).unwrap();
        t.update("j", 25, 100).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: JobTracker = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
