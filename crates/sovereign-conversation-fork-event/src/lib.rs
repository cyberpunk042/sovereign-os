//! `sovereign-conversation-fork-event` — operator-initiated branch fork log.
//!
//! Each `ForkEvent` records: thread_id, parent_branch_id, new_branch_id,
//! fork_at_turn (turn index in parent at fork point), actor, trace_id, at.
//!
//! Validator rejects: empty fields, fork_at_turn >= parent.turns.len(),
//! parent == new branch.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_conversation_thread::ConversationThread;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One fork event.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForkEvent {
    /// Thread id.
    pub thread_id: String,
    /// Branch we forked from.
    pub parent_branch_id: String,
    /// New branch id.
    pub new_branch_id: String,
    /// Turn index in parent where the fork happened.
    pub fork_at_turn: u32,
    /// Operator MS003 fingerprint.
    pub actor: String,
    /// M049 trace_id.
    pub trace_id: String,
    /// ISO-8601 UTC.
    pub at: String,
}

/// Fork log.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForkLog {
    /// Schema version.
    pub schema_version: String,
    /// Entries.
    pub entries: Vec<ForkEvent>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ForkError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty thread_id.
    #[error("thread_id missing")]
    MissingThreadId,
    /// Empty branch id.
    #[error("branch id empty")]
    EmptyBranch,
    /// new_branch == parent_branch.
    #[error("new_branch_id same as parent_branch_id: {0}")]
    SelfFork(String),
    /// Empty actor.
    #[error("actor missing")]
    MissingActor,
    /// Empty trace_id.
    #[error("trace_id missing")]
    MissingTraceId,
    /// Empty timestamp.
    #[error("at missing")]
    MissingTimestamp,
    /// fork_at_turn out of range.
    #[error("fork_at_turn {idx} >= turn count {total}")]
    TurnOutOfRange {
        /// idx.
        idx: u32,
        /// total.
        total: u32,
    },
}

impl ForkLog {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
        }
    }

    /// Record a fork against a thread (validates against thread's turn count).
    pub fn record(&mut self, e: ForkEvent, thread: &ConversationThread) -> Result<(), ForkError> {
        check_shape(&e)?;
        if e.thread_id == thread.thread_id && e.fork_at_turn >= thread.turns.len() as u32 {
            return Err(ForkError::TurnOutOfRange {
                idx: e.fork_at_turn,
                total: thread.turns.len() as u32,
            });
        }
        self.entries.push(e);
        Ok(())
    }

    /// Forks for a specific branch.
    pub fn descendants_of(&self, parent: &str) -> Vec<&ForkEvent> {
        self.entries
            .iter()
            .filter(|e| e.parent_branch_id == parent)
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ForkError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ForkError::SchemaMismatch);
        }
        for e in &self.entries {
            check_shape(e)?;
        }
        Ok(())
    }
}

fn check_shape(e: &ForkEvent) -> Result<(), ForkError> {
    if e.thread_id.is_empty() {
        return Err(ForkError::MissingThreadId);
    }
    if e.parent_branch_id.is_empty() || e.new_branch_id.is_empty() {
        return Err(ForkError::EmptyBranch);
    }
    if e.parent_branch_id == e.new_branch_id {
        return Err(ForkError::SelfFork(e.parent_branch_id.clone()));
    }
    if e.actor.is_empty() {
        return Err(ForkError::MissingActor);
    }
    if e.trace_id.is_empty() {
        return Err(ForkError::MissingTraceId);
    }
    if e.at.is_empty() {
        return Err(ForkError::MissingTimestamp);
    }
    Ok(())
}

impl Default for ForkLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_conversation_thread::{Turn, TurnRole};

    fn thread_3() -> ConversationThread {
        let mut t = ConversationThread::new("th-1", "t");
        for _ in 0..3 {
            t.append(Turn {
                index: 0,
                role: TurnRole::Operator,
                tokens_in: 0,
                tokens_out: 0,
                provider: "p".into(),
                started_at: "t".into(),
                completed_at: "t".into(),
                branch_id: "main".into(),
                text: String::new(),
            });
        }
        t
    }

    fn ev(parent: &str, new: &str, at_turn: u32) -> ForkEvent {
        ForkEvent {
            thread_id: "th-1".into(),
            parent_branch_id: parent.into(),
            new_branch_id: new.into(),
            fork_at_turn: at_turn,
            actor: "op".into(),
            trace_id: "tr".into(),
            at: "2026-05-19T03:00:00Z".into(),
        }
    }

    #[test]
    fn empty_log_validates() {
        ForkLog::new().validate().unwrap();
    }

    #[test]
    fn record_fork() {
        let mut l = ForkLog::new();
        let t = thread_3();
        l.record(ev("main", "experiment", 1), &t).unwrap();
        assert_eq!(l.entries.len(), 1);
    }

    #[test]
    fn out_of_range_rejected() {
        let mut l = ForkLog::new();
        let t = thread_3();
        let err = l.record(ev("main", "experiment", 99), &t).unwrap_err();
        assert!(matches!(err, ForkError::TurnOutOfRange { .. }));
    }

    #[test]
    fn self_fork_rejected() {
        let mut l = ForkLog::new();
        let t = thread_3();
        let err = l.record(ev("main", "main", 0), &t).unwrap_err();
        assert!(matches!(err, ForkError::SelfFork(_)));
    }

    #[test]
    fn empty_branch_rejected() {
        let mut l = ForkLog::new();
        let t = thread_3();
        let err = l.record(ev("", "experiment", 0), &t).unwrap_err();
        assert!(matches!(err, ForkError::EmptyBranch));
    }

    #[test]
    fn missing_actor_rejected() {
        let mut l = ForkLog::new();
        let t = thread_3();
        let mut e = ev("main", "experiment", 0);
        e.actor = String::new();
        let err = l.record(e, &t).unwrap_err();
        assert!(matches!(err, ForkError::MissingActor));
    }

    #[test]
    fn missing_trace_id_rejected() {
        let mut l = ForkLog::new();
        let t = thread_3();
        let mut e = ev("main", "experiment", 0);
        e.trace_id = String::new();
        let err = l.record(e, &t).unwrap_err();
        assert!(matches!(err, ForkError::MissingTraceId));
    }

    #[test]
    fn descendants_filters_by_parent() {
        let mut l = ForkLog::new();
        let t = thread_3();
        l.record(ev("main", "experiment-1", 1), &t).unwrap();
        l.record(ev("main", "experiment-2", 2), &t).unwrap();
        l.record(ev("experiment-1", "deeper", 1), &t).unwrap();
        assert_eq!(l.descendants_of("main").len(), 2);
        assert_eq!(l.descendants_of("experiment-1").len(), 1);
        assert_eq!(l.descendants_of("none").len(), 0);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = ForkLog::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            ForkError::SchemaMismatch
        ));
    }

    #[test]
    fn log_serde_roundtrip() {
        let mut l = ForkLog::new();
        let t = thread_3();
        l.record(ev("main", "experiment", 1), &t).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: ForkLog = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
