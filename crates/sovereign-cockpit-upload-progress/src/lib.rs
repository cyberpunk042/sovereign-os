//! `sovereign-cockpit-upload-progress` — per-file upload state.
//!
//! Upload{phase, bytes_done, bytes_total}. enqueue adds; start
//! Queued→Uploading; progress(bytes_done) updates; complete →
//! Done; fail/cancel transitions. total_progress_bp aggregates.
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
    /// Queued.
    Queued,
    /// Uploading.
    Uploading,
    /// Done.
    Done,
    /// Failed(error).
    Failed(String),
    /// Cancelled.
    Cancelled,
}

/// Upload.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Upload {
    /// Phase.
    pub phase: Phase,
    /// Bytes done.
    pub bytes_done: u64,
    /// Bytes total (>=1).
    pub bytes_total: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UploadProgress {
    /// Schema version.
    pub schema_version: String,
    /// file_id → upload.
    pub uploads: BTreeMap<String, Upload>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum UploadError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("file id empty")]
    EmptyFile,
    /// Empty.
    #[error("error empty")]
    EmptyError,
    /// Zero total.
    #[error("bytes_total must be >= 1")]
    ZeroTotal,
    /// Duplicate.
    #[error("duplicate file id: {0}")]
    DuplicateFile(String),
    /// Unknown.
    #[error("unknown file: {0}")]
    UnknownFile(String),
    /// Invalid phase.
    #[error("invalid phase for operation")]
    InvalidPhase,
}

impl UploadProgress {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            uploads: BTreeMap::new(),
        }
    }

    /// Enqueue.
    pub fn enqueue(&mut self, file_id: &str, bytes_total: u64) -> Result<(), UploadError> {
        if file_id.is_empty() {
            return Err(UploadError::EmptyFile);
        }
        if bytes_total == 0 {
            return Err(UploadError::ZeroTotal);
        }
        if self.uploads.contains_key(file_id) {
            return Err(UploadError::DuplicateFile(file_id.into()));
        }
        self.uploads.insert(
            file_id.into(),
            Upload {
                phase: Phase::Queued,
                bytes_done: 0,
                bytes_total,
            },
        );
        Ok(())
    }

    /// Start (Queued → Uploading).
    pub fn start(&mut self, file_id: &str) -> Result<(), UploadError> {
        let u = self
            .uploads
            .get_mut(file_id)
            .ok_or_else(|| UploadError::UnknownFile(file_id.into()))?;
        if u.phase != Phase::Queued {
            return Err(UploadError::InvalidPhase);
        }
        u.phase = Phase::Uploading;
        Ok(())
    }

    /// Progress.
    pub fn progress(&mut self, file_id: &str, bytes_done: u64) -> Result<(), UploadError> {
        let u = self
            .uploads
            .get_mut(file_id)
            .ok_or_else(|| UploadError::UnknownFile(file_id.into()))?;
        if u.phase != Phase::Uploading {
            return Err(UploadError::InvalidPhase);
        }
        u.bytes_done = bytes_done.min(u.bytes_total);
        Ok(())
    }

    /// Complete.
    pub fn complete(&mut self, file_id: &str) -> Result<(), UploadError> {
        let u = self
            .uploads
            .get_mut(file_id)
            .ok_or_else(|| UploadError::UnknownFile(file_id.into()))?;
        if u.phase != Phase::Uploading {
            return Err(UploadError::InvalidPhase);
        }
        u.phase = Phase::Done;
        u.bytes_done = u.bytes_total;
        Ok(())
    }

    /// Fail.
    pub fn fail(&mut self, file_id: &str, err: &str) -> Result<(), UploadError> {
        if err.is_empty() {
            return Err(UploadError::EmptyError);
        }
        let u = self
            .uploads
            .get_mut(file_id)
            .ok_or_else(|| UploadError::UnknownFile(file_id.into()))?;
        if !matches!(u.phase, Phase::Queued | Phase::Uploading) {
            return Err(UploadError::InvalidPhase);
        }
        u.phase = Phase::Failed(err.into());
        Ok(())
    }

    /// Cancel.
    pub fn cancel(&mut self, file_id: &str) -> Result<(), UploadError> {
        let u = self
            .uploads
            .get_mut(file_id)
            .ok_or_else(|| UploadError::UnknownFile(file_id.into()))?;
        if !matches!(u.phase, Phase::Queued | Phase::Uploading) {
            return Err(UploadError::InvalidPhase);
        }
        u.phase = Phase::Cancelled;
        Ok(())
    }

    /// Aggregate progress in basis points across all uploads
    /// (bytes_done sum / bytes_total sum).
    pub fn total_progress_bp(&self) -> u32 {
        let mut sum_done: u128 = 0;
        let mut sum_total: u128 = 0;
        for u in self.uploads.values() {
            sum_done += u.bytes_done as u128;
            sum_total += u.bytes_total as u128;
        }
        if sum_total == 0 {
            return 0;
        }
        ((sum_done * 10_000) / sum_total) as u32
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), UploadError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(UploadError::SchemaMismatch);
        }
        for (k, u) in &self.uploads {
            if k.is_empty() {
                return Err(UploadError::EmptyFile);
            }
            if u.bytes_total == 0 {
                return Err(UploadError::ZeroTotal);
            }
        }
        Ok(())
    }
}

impl Default for UploadProgress {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_path() {
        let mut p = UploadProgress::new();
        p.enqueue("f", 1000).unwrap();
        p.start("f").unwrap();
        p.progress("f", 500).unwrap();
        p.complete("f").unwrap();
        let u = p.uploads.get("f").unwrap();
        assert_eq!(u.phase, Phase::Done);
        assert_eq!(u.bytes_done, 1000);
    }

    #[test]
    fn fail_path() {
        let mut p = UploadProgress::new();
        p.enqueue("f", 1000).unwrap();
        p.start("f").unwrap();
        p.fail("f", "timeout").unwrap();
        match p.uploads.get("f").unwrap().phase.clone() {
            Phase::Failed(e) => assert_eq!(e, "timeout"),
            _ => panic!("expected Failed"),
        }
    }

    #[test]
    fn cancel_path() {
        let mut p = UploadProgress::new();
        p.enqueue("f", 1000).unwrap();
        p.cancel("f").unwrap();
        assert_eq!(p.uploads.get("f").unwrap().phase, Phase::Cancelled);
    }

    #[test]
    fn total_progress_aggregates() {
        let mut p = UploadProgress::new();
        p.enqueue("a", 1000).unwrap();
        p.enqueue("b", 1000).unwrap();
        p.start("a").unwrap();
        p.progress("a", 500).unwrap();
        // total = 500 / 2000 = 2500 bp.
        assert_eq!(p.total_progress_bp(), 2500);
    }

    #[test]
    fn duplicate_rejected() {
        let mut p = UploadProgress::new();
        p.enqueue("a", 100).unwrap();
        assert!(matches!(
            p.enqueue("a", 200).unwrap_err(),
            UploadError::DuplicateFile(_)
        ));
    }

    #[test]
    fn progress_clamps_to_total() {
        let mut p = UploadProgress::new();
        p.enqueue("a", 100).unwrap();
        p.start("a").unwrap();
        p.progress("a", 9999).unwrap();
        assert_eq!(p.uploads.get("a").unwrap().bytes_done, 100);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut p = UploadProgress::new();
        assert!(matches!(
            p.enqueue("", 100).unwrap_err(),
            UploadError::EmptyFile
        ));
        assert!(matches!(
            p.enqueue("a", 0).unwrap_err(),
            UploadError::ZeroTotal
        ));
    }

    #[test]
    fn invalid_phase_rejected() {
        let mut p = UploadProgress::new();
        p.enqueue("a", 100).unwrap();
        p.start("a").unwrap();
        p.complete("a").unwrap();
        assert!(matches!(
            p.progress("a", 50).unwrap_err(),
            UploadError::InvalidPhase
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = UploadProgress::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            UploadError::SchemaMismatch
        ));
    }

    #[test]
    fn upload_serde_roundtrip() {
        let mut p = UploadProgress::new();
        p.enqueue("a", 100).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: UploadProgress = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
