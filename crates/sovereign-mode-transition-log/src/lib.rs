//! `sovereign-mode-transition-log` — append-only ExecutionMode transition record.
//!
//! Every mode switch the cockpit issues produces one entry. Each entry
//! carries (from, to, reason, actor, timestamp, trace_id). The validator
//! checks that:
//! - actor + trace_id are non-empty
//! - timestamps monotonically advance
//! - no entry has from == to
//! - dangerous transitions (Replay→Execute, Plan→Execute without a
//!   `direct-shift` reason) are flagged
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_execution_mode_registry::ExecutionMode;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Transition reason.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TransitionReason {
    /// Operator-initiated routine switch (e.g. Plan → DryRun for preview).
    OperatorChose,
    /// Promotion to live execution after review.
    PromoteToLive,
    /// Demotion to safer mode after incident.
    DemoteAfterIncident,
    /// Direct shift (no intermediate mode) — must be explicit.
    DirectShift,
    /// Boot default landing mode.
    BootDefault,
    /// Replay session opened.
    ReplayOpened,
    /// Replay session closed.
    ReplayClosed,
}

/// One transition entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TransitionEntry {
    /// From mode.
    pub from: ExecutionMode,
    /// To mode.
    pub to: ExecutionMode,
    /// Reason.
    pub reason: TransitionReason,
    /// Operator MS003 fingerprint or "boot".
    pub actor: String,
    /// ISO-8601 UTC.
    pub at: String,
    /// M049 trace_id.
    pub trace_id: String,
}

/// Log envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TransitionLog {
    /// Schema version.
    pub schema_version: String,
    /// Entries.
    pub entries: Vec<TransitionEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TransitionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty actor.
    #[error("entry {0} missing actor")]
    MissingActor(usize),
    /// Empty trace_id.
    #[error("entry {0} missing trace_id")]
    MissingTraceId(usize),
    /// Empty timestamp.
    #[error("entry {0} missing timestamp")]
    MissingTimestamp(usize),
    /// from == to.
    #[error("entry {idx} is a no-op: from {mode:?} == to")]
    NoOp {
        /// idx.
        idx: usize,
        /// mode.
        mode: ExecutionMode,
    },
    /// Timestamps regressed.
    #[error("entry {idx} timestamp {at} regresses from {prev}")]
    TimestampRegress {
        /// idx.
        idx: usize,
        /// at.
        at: String,
        /// prev.
        prev: String,
    },
    /// Dangerous direct Plan→Execute without DirectShift reason.
    #[error(
        "entry {idx} dangerous transition Plan→Execute without direct-shift reason ({reason:?})"
    )]
    DangerousTransition {
        /// idx.
        idx: usize,
        /// reason.
        reason: TransitionReason,
    },
}

impl TransitionLog {
    /// New empty log.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
        }
    }

    /// Append a transition. Errors on validation problems.
    pub fn record(
        &mut self,
        from: ExecutionMode,
        to: ExecutionMode,
        reason: TransitionReason,
        actor: &str,
        at: &str,
        trace_id: &str,
    ) -> Result<(), TransitionError> {
        let entry = TransitionEntry {
            from,
            to,
            reason,
            actor: actor.into(),
            at: at.into(),
            trace_id: trace_id.into(),
        };
        self.entries.push(entry);
        // Validate just-appended entry contextually.
        let idx = self.entries.len() - 1;
        if self.entries[idx].actor.is_empty() {
            self.entries.pop();
            return Err(TransitionError::MissingActor(idx));
        }
        if self.entries[idx].trace_id.is_empty() {
            self.entries.pop();
            return Err(TransitionError::MissingTraceId(idx));
        }
        if self.entries[idx].at.is_empty() {
            self.entries.pop();
            return Err(TransitionError::MissingTimestamp(idx));
        }
        if self.entries[idx].from == self.entries[idx].to {
            let m = self.entries[idx].from;
            self.entries.pop();
            return Err(TransitionError::NoOp { idx, mode: m });
        }
        if from == ExecutionMode::Plan
            && to == ExecutionMode::Execute
            && reason != TransitionReason::DirectShift
        {
            self.entries.pop();
            return Err(TransitionError::DangerousTransition { idx, reason });
        }
        // Timestamp regression check.
        if idx > 0 && self.entries[idx].at < self.entries[idx - 1].at {
            let prev = self.entries[idx - 1].at.clone();
            let at_now = self.entries[idx].at.clone();
            self.entries.pop();
            return Err(TransitionError::TimestampRegress {
                idx,
                at: at_now,
                prev,
            });
        }
        Ok(())
    }

    /// Bulk-validate the whole log.
    pub fn validate(&self) -> Result<(), TransitionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TransitionError::SchemaMismatch);
        }
        let mut prev_at: Option<&str> = None;
        for (idx, e) in self.entries.iter().enumerate() {
            if e.actor.is_empty() {
                return Err(TransitionError::MissingActor(idx));
            }
            if e.trace_id.is_empty() {
                return Err(TransitionError::MissingTraceId(idx));
            }
            if e.at.is_empty() {
                return Err(TransitionError::MissingTimestamp(idx));
            }
            if e.from == e.to {
                return Err(TransitionError::NoOp { idx, mode: e.from });
            }
            if e.from == ExecutionMode::Plan
                && e.to == ExecutionMode::Execute
                && e.reason != TransitionReason::DirectShift
            {
                return Err(TransitionError::DangerousTransition {
                    idx,
                    reason: e.reason,
                });
            }
            if let Some(p) = prev_at
                && e.at.as_str() < p
            {
                return Err(TransitionError::TimestampRegress {
                    idx,
                    at: e.at.clone(),
                    prev: p.into(),
                });
            }
            prev_at = Some(&e.at);
        }
        Ok(())
    }

    /// Count transitions ending in a given mode.
    pub fn count_entries_to(&self, mode: ExecutionMode) -> usize {
        self.entries.iter().filter(|e| e.to == mode).count()
    }

    /// Most recent mode the log ended on.
    pub fn current_mode(&self) -> Option<ExecutionMode> {
        self.entries.last().map(|e| e.to)
    }
}

impl Default for TransitionLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_log_validates() {
        TransitionLog::new().validate().unwrap();
    }

    #[test]
    fn record_legal_transition() {
        let mut l = TransitionLog::new();
        l.record(
            ExecutionMode::Plan,
            ExecutionMode::DryRun,
            TransitionReason::OperatorChose,
            "op",
            "2026-05-19T03:00:00Z",
            "tr-1",
        )
        .unwrap();
        assert_eq!(l.current_mode(), Some(ExecutionMode::DryRun));
    }

    #[test]
    fn no_op_rejected() {
        let mut l = TransitionLog::new();
        let err = l
            .record(
                ExecutionMode::Plan,
                ExecutionMode::Plan,
                TransitionReason::OperatorChose,
                "op",
                "t",
                "tr",
            )
            .unwrap_err();
        assert!(matches!(err, TransitionError::NoOp { .. }));
    }

    #[test]
    fn missing_actor_rejected() {
        let mut l = TransitionLog::new();
        let err = l
            .record(
                ExecutionMode::Plan,
                ExecutionMode::DryRun,
                TransitionReason::OperatorChose,
                "",
                "t",
                "tr",
            )
            .unwrap_err();
        assert!(matches!(err, TransitionError::MissingActor(_)));
    }

    #[test]
    fn missing_trace_rejected() {
        let mut l = TransitionLog::new();
        let err = l
            .record(
                ExecutionMode::Plan,
                ExecutionMode::DryRun,
                TransitionReason::OperatorChose,
                "op",
                "t",
                "",
            )
            .unwrap_err();
        assert!(matches!(err, TransitionError::MissingTraceId(_)));
    }

    #[test]
    fn dangerous_plan_to_execute_rejected_without_direct_shift() {
        let mut l = TransitionLog::new();
        let err = l
            .record(
                ExecutionMode::Plan,
                ExecutionMode::Execute,
                TransitionReason::OperatorChose,
                "op",
                "t",
                "tr",
            )
            .unwrap_err();
        assert!(matches!(err, TransitionError::DangerousTransition { .. }));
    }

    #[test]
    fn plan_to_execute_with_direct_shift_allowed() {
        let mut l = TransitionLog::new();
        l.record(
            ExecutionMode::Plan,
            ExecutionMode::Execute,
            TransitionReason::DirectShift,
            "op",
            "t",
            "tr",
        )
        .unwrap();
    }

    #[test]
    fn timestamp_regression_rejected() {
        let mut l = TransitionLog::new();
        l.record(
            ExecutionMode::Plan,
            ExecutionMode::DryRun,
            TransitionReason::OperatorChose,
            "op",
            "2026-05-19T03:00:00Z",
            "tr-1",
        )
        .unwrap();
        let err = l
            .record(
                ExecutionMode::DryRun,
                ExecutionMode::Execute,
                TransitionReason::PromoteToLive,
                "op",
                "2026-05-19T02:00:00Z",
                "tr-2",
            )
            .unwrap_err();
        assert!(matches!(err, TransitionError::TimestampRegress { .. }));
    }

    #[test]
    fn count_entries_to() {
        let mut l = TransitionLog::new();
        l.record(
            ExecutionMode::Plan,
            ExecutionMode::DryRun,
            TransitionReason::OperatorChose,
            "op",
            "t1",
            "tr",
        )
        .unwrap();
        l.record(
            ExecutionMode::DryRun,
            ExecutionMode::Sandbox,
            TransitionReason::OperatorChose,
            "op",
            "t2",
            "tr",
        )
        .unwrap();
        l.record(
            ExecutionMode::Sandbox,
            ExecutionMode::DryRun,
            TransitionReason::DemoteAfterIncident,
            "op",
            "t3",
            "tr",
        )
        .unwrap();
        assert_eq!(l.count_entries_to(ExecutionMode::DryRun), 2);
        assert_eq!(l.count_entries_to(ExecutionMode::Sandbox), 1);
        assert_eq!(l.count_entries_to(ExecutionMode::Plan), 0);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = TransitionLog::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            TransitionError::SchemaMismatch
        ));
    }

    #[test]
    fn reason_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&TransitionReason::OperatorChose).unwrap(),
            "\"operator-chose\""
        );
        assert_eq!(
            serde_json::to_string(&TransitionReason::PromoteToLive).unwrap(),
            "\"promote-to-live\""
        );
        assert_eq!(
            serde_json::to_string(&TransitionReason::DirectShift).unwrap(),
            "\"direct-shift\""
        );
    }

    #[test]
    fn log_serde_roundtrip() {
        let mut l = TransitionLog::new();
        l.record(
            ExecutionMode::Plan,
            ExecutionMode::DryRun,
            TransitionReason::OperatorChose,
            "op",
            "t1",
            "tr",
        )
        .unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: TransitionLog = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
