//! `sovereign-cockpit-job-progress-card` — multi-stage progress card.
//!
//! Stage{id, label, phase Pending/Running/Done/Failed}. JobCard
//! {job_id, title, stages}. start_stage(id, now) Pending→Running.
//! complete_stage(id, now) Running→Done. fail_stage(id, error)
//! Running→Failed. progress_bp returns weighted progress
//! basis-points (Done stages count, Running counts half).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "phase", content = "error")]
pub enum Phase {
    /// Pending.
    Pending,
    /// Running.
    Running,
    /// Done.
    Done,
    /// Failed(reason).
    Failed(String),
}

/// Stage.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Stage {
    /// Stage id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Phase.
    pub phase: Phase,
    /// Started ts ms.
    pub started_at_ms: u64,
    /// Ended ts ms.
    pub ended_at_ms: u64,
}

/// Card.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct JobCard {
    /// Schema version.
    pub schema_version: String,
    /// Job id.
    pub job_id: String,
    /// Title.
    pub title: String,
    /// Stages in display order.
    pub stages: Vec<Stage>,
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
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate stage id: {0}")]
    Duplicate(String),
    /// Unknown.
    #[error("unknown stage id: {0}")]
    Unknown(String),
    /// Invalid phase.
    #[error("invalid phase for operation")]
    InvalidPhase,
    /// Empty error.
    #[error("error empty")]
    EmptyError,
}

impl JobCard {
    /// New.
    pub fn new(job_id: &str, title: &str) -> Result<Self, CardError> {
        if job_id.is_empty() { return Err(CardError::EmptyId); }
        if title.is_empty() { return Err(CardError::EmptyLabel); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            job_id: job_id.into(),
            title: title.into(),
            stages: Vec::new(),
        })
    }

    /// Add a stage.
    pub fn add_stage(&mut self, id: &str, label: &str) -> Result<(), CardError> {
        if id.is_empty() { return Err(CardError::EmptyId); }
        if label.is_empty() { return Err(CardError::EmptyLabel); }
        if self.stages.iter().any(|s| s.id == id) {
            return Err(CardError::Duplicate(id.into()));
        }
        self.stages.push(Stage {
            id: id.into(), label: label.into(),
            phase: Phase::Pending,
            started_at_ms: 0, ended_at_ms: 0,
        });
        Ok(())
    }

    fn stage_mut(&mut self, id: &str) -> Result<&mut Stage, CardError> {
        self.stages.iter_mut().find(|s| s.id == id)
            .ok_or_else(|| CardError::Unknown(id.into()))
    }

    /// Pending → Running.
    pub fn start_stage(&mut self, id: &str, now_ms: u64) -> Result<(), CardError> {
        let s = self.stage_mut(id)?;
        if s.phase != Phase::Pending { return Err(CardError::InvalidPhase); }
        s.phase = Phase::Running;
        s.started_at_ms = now_ms;
        Ok(())
    }

    /// Running → Done.
    pub fn complete_stage(&mut self, id: &str, now_ms: u64) -> Result<(), CardError> {
        let s = self.stage_mut(id)?;
        if s.phase != Phase::Running { return Err(CardError::InvalidPhase); }
        s.phase = Phase::Done;
        s.ended_at_ms = now_ms;
        Ok(())
    }

    /// Running → Failed.
    pub fn fail_stage(&mut self, id: &str, error: &str, now_ms: u64) -> Result<(), CardError> {
        if error.is_empty() { return Err(CardError::EmptyError); }
        let s = self.stage_mut(id)?;
        if s.phase != Phase::Running { return Err(CardError::InvalidPhase); }
        s.phase = Phase::Failed(error.into());
        s.ended_at_ms = now_ms;
        Ok(())
    }

    /// Progress in basis points (Done full weight, Running half).
    pub fn progress_bp(&self) -> u32 {
        if self.stages.is_empty() { return 0; }
        let n = self.stages.len() as u64;
        let mut points: u64 = 0;
        for s in &self.stages {
            match s.phase {
                Phase::Done => points += 2,
                Phase::Running => points += 1,
                _ => {}
            }
        }
        // points out of 2*n.
        ((points * 10_000) / (2 * n)) as u32
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CardError> {
        if self.schema_version != SCHEMA_VERSION { return Err(CardError::SchemaMismatch); }
        for s in &self.stages {
            if s.id.is_empty() { return Err(CardError::EmptyId); }
            if s.label.is_empty() { return Err(CardError::EmptyLabel); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn progress_no_stages_zero() {
        let c = JobCard::new("j1", "Job").unwrap();
        assert_eq!(c.progress_bp(), 0);
    }

    #[test]
    fn happy_progress_full() {
        let mut c = JobCard::new("j1", "Job").unwrap();
        c.add_stage("s1", "A").unwrap();
        c.add_stage("s2", "B").unwrap();
        c.start_stage("s1", 100).unwrap();
        c.complete_stage("s1", 200).unwrap();
        c.start_stage("s2", 300).unwrap();
        c.complete_stage("s2", 400).unwrap();
        assert_eq!(c.progress_bp(), 10_000);
    }

    #[test]
    fn running_counts_half() {
        let mut c = JobCard::new("j1", "Job").unwrap();
        c.add_stage("s1", "A").unwrap();
        c.add_stage("s2", "B").unwrap();
        c.start_stage("s1", 0).unwrap();
        c.complete_stage("s1", 10).unwrap();
        c.start_stage("s2", 20).unwrap();
        // s1 Done(2) + s2 Running(1) = 3 out of 4 → 7500 bp.
        assert_eq!(c.progress_bp(), 7500);
    }

    #[test]
    fn fail_transitions() {
        let mut c = JobCard::new("j1", "Job").unwrap();
        c.add_stage("s1", "A").unwrap();
        c.start_stage("s1", 0).unwrap();
        c.fail_stage("s1", "boom", 10).unwrap();
        assert!(matches!(c.stages[0].phase, Phase::Failed(_)));
    }

    #[test]
    fn invalid_transitions_rejected() {
        let mut c = JobCard::new("j1", "Job").unwrap();
        c.add_stage("s1", "A").unwrap();
        // Cannot complete a Pending stage.
        assert!(matches!(c.complete_stage("s1", 0).unwrap_err(), CardError::InvalidPhase));
    }

    #[test]
    fn duplicate_stage_rejected() {
        let mut c = JobCard::new("j1", "Job").unwrap();
        c.add_stage("s1", "A").unwrap();
        assert!(matches!(c.add_stage("s1", "A").unwrap_err(), CardError::Duplicate(_)));
    }

    #[test]
    fn empty_error_rejected() {
        let mut c = JobCard::new("j1", "Job").unwrap();
        c.add_stage("s1", "A").unwrap();
        c.start_stage("s1", 0).unwrap();
        assert!(matches!(c.fail_stage("s1", "", 1).unwrap_err(), CardError::EmptyError));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = JobCard::new("j1", "Job").unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), CardError::SchemaMismatch));
    }

    #[test]
    fn card_serde_roundtrip() {
        let mut c = JobCard::new("j1", "Job").unwrap();
        c.add_stage("s1", "A").unwrap();
        c.start_stage("s1", 100).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: JobCard = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
