//! `sovereign-tool-invocation-record` — one immutable record per tool call.
//!
//! Each record carries:
//! - `tool` (matches `sovereign-tool-catalog::ToolId`)
//! - `mode` + `bundle` (context at invocation time)
//! - `started_at` + `completed_at` (ISO-8601 UTC)
//! - `exit_kind` (Success / Failure / Timeout / Refused / Aborted)
//! - `bytes_out` (response bytes; capped surrogate)
//! - `trace_id` (M049 link)
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_profile_bundles::BundleName;
use sovereign_tool_catalog::{ToolCatalog, ToolId};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Invocation outcome.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ExitKind {
    /// Tool succeeded.
    Success,
    /// Tool ran but reported failure.
    Failure,
    /// Tool exceeded its deadline.
    Timeout,
    /// Catalog refused the call (mode/bundle gate).
    Refused,
    /// Operator aborted.
    Aborted,
}

/// One immutable invocation record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InvocationRecord {
    /// Schema version.
    pub schema_version: String,
    /// M049 trace_id.
    pub trace_id: String,
    /// Tool id.
    pub tool: ToolId,
    /// Mode at invocation.
    pub mode: ExecutionMode,
    /// Bundle at invocation.
    pub bundle: BundleName,
    /// ISO-8601 UTC.
    pub started_at: String,
    /// ISO-8601 UTC; empty while in-progress.
    pub completed_at: String,
    /// Outcome.
    pub exit_kind: ExitKind,
    /// Bytes of response captured (truncation surrogate).
    pub bytes_out: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RecordError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty trace_id.
    #[error("trace_id missing")]
    MissingTraceId,
    /// Empty started_at.
    #[error("started_at missing")]
    MissingStartedAt,
    /// completed_at precedes started_at.
    #[error("completed_at {completed} precedes started_at {started}")]
    CompletedBeforeStarted {
        /// started.
        started: String,
        /// completed.
        completed: String,
    },
    /// Catalog refused but exit_kind != Refused.
    #[error("tool {tool:?} forbidden in mode {mode:?} bundle {bundle:?} but exit_kind is {exit:?}")]
    GateMismatch {
        /// Tool.
        tool: ToolId,
        /// Mode.
        mode: ExecutionMode,
        /// Bundle.
        bundle: BundleName,
        /// Exit.
        exit: ExitKind,
    },
}

impl InvocationRecord {
    /// New.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        trace_id: &str,
        tool: ToolId,
        mode: ExecutionMode,
        bundle: BundleName,
        started_at: &str,
        completed_at: &str,
        exit_kind: ExitKind,
        bytes_out: u64,
    ) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            trace_id: trace_id.into(),
            tool,
            mode,
            bundle,
            started_at: started_at.into(),
            completed_at: completed_at.into(),
            exit_kind,
            bytes_out,
        }
    }

    /// Validate.
    ///
    /// If `catalog` is provided, validates that the gate-state matches:
    /// if the tool is not available in (mode, bundle), the exit_kind
    /// must be `Refused`.
    pub fn validate(&self, catalog: Option<&ToolCatalog>) -> Result<(), RecordError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RecordError::SchemaMismatch);
        }
        if self.trace_id.is_empty() {
            return Err(RecordError::MissingTraceId);
        }
        if self.started_at.is_empty() {
            return Err(RecordError::MissingStartedAt);
        }
        if !self.completed_at.is_empty() && self.completed_at < self.started_at {
            return Err(RecordError::CompletedBeforeStarted {
                started: self.started_at.clone(),
                completed: self.completed_at.clone(),
            });
        }
        if let Some(cat) = catalog {
            let available = cat.is_available(self.tool, self.mode, self.bundle);
            if !available && self.exit_kind != ExitKind::Refused {
                return Err(RecordError::GateMismatch {
                    tool: self.tool,
                    mode: self.mode,
                    bundle: self.bundle,
                    exit: self.exit_kind,
                });
            }
        }
        Ok(())
    }

    /// True if the invocation produced a result the cockpit can render.
    pub fn rendered(&self) -> bool {
        matches!(self.exit_kind, ExitKind::Success | ExitKind::Failure)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cat() -> ToolCatalog {
        ToolCatalog::canonical()
    }

    #[test]
    fn ok_record_validates() {
        let r = InvocationRecord::new(
            "tr-1",
            ToolId::FsRead,
            ExecutionMode::Plan,
            BundleName::Private,
            "2026-05-19T03:00:00Z",
            "2026-05-19T03:00:01Z",
            ExitKind::Success,
            1024,
        );
        r.validate(Some(&cat())).unwrap();
    }

    #[test]
    fn missing_trace_id_caught() {
        let r = InvocationRecord::new(
            "",
            ToolId::FsRead,
            ExecutionMode::Plan,
            BundleName::Private,
            "t",
            "t",
            ExitKind::Success,
            0,
        );
        assert!(matches!(
            r.validate(None).unwrap_err(),
            RecordError::MissingTraceId
        ));
    }

    #[test]
    fn completed_before_started_caught() {
        let r = InvocationRecord::new(
            "tr-1",
            ToolId::FsRead,
            ExecutionMode::Plan,
            BundleName::Private,
            "2026-05-19T03:00:05Z",
            "2026-05-19T03:00:00Z",
            ExitKind::Success,
            0,
        );
        assert!(matches!(
            r.validate(None).unwrap_err(),
            RecordError::CompletedBeforeStarted { .. }
        ));
    }

    #[test]
    fn gate_mismatch_caught_when_tool_not_available() {
        // FsWrite is not available in Plan mode → if exit_kind is Success, mismatch.
        let r = InvocationRecord::new(
            "tr-1",
            ToolId::FsWrite,
            ExecutionMode::Plan,
            BundleName::Careful,
            "2026-05-19T03:00:00Z",
            "2026-05-19T03:00:01Z",
            ExitKind::Success,
            0,
        );
        match r.validate(Some(&cat())).unwrap_err() {
            RecordError::GateMismatch { tool, mode, .. } => {
                assert_eq!(tool, ToolId::FsWrite);
                assert_eq!(mode, ExecutionMode::Plan);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn refused_in_blocked_context_validates() {
        let r = InvocationRecord::new(
            "tr-1",
            ToolId::FsWrite,
            ExecutionMode::Plan,
            BundleName::Careful,
            "2026-05-19T03:00:00Z",
            "2026-05-19T03:00:00Z",
            ExitKind::Refused,
            0,
        );
        r.validate(Some(&cat())).unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = InvocationRecord::new(
            "tr-1",
            ToolId::FsRead,
            ExecutionMode::Plan,
            BundleName::Private,
            "t",
            "t",
            ExitKind::Success,
            0,
        );
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate(None).unwrap_err(),
            RecordError::SchemaMismatch
        ));
    }

    #[test]
    fn rendered_only_for_success_and_failure() {
        for (ek, expected) in [
            (ExitKind::Success, true),
            (ExitKind::Failure, true),
            (ExitKind::Timeout, false),
            (ExitKind::Refused, false),
            (ExitKind::Aborted, false),
        ] {
            let r = InvocationRecord::new(
                "tr-1",
                ToolId::FsRead,
                ExecutionMode::Plan,
                BundleName::Private,
                "t",
                "t",
                ek,
                0,
            );
            assert_eq!(r.rendered(), expected, "{ek:?}");
        }
    }

    #[test]
    fn exit_kind_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ExitKind::Success).unwrap(),
            "\"success\""
        );
        assert_eq!(
            serde_json::to_string(&ExitKind::Timeout).unwrap(),
            "\"timeout\""
        );
        assert_eq!(
            serde_json::to_string(&ExitKind::Refused).unwrap(),
            "\"refused\""
        );
        assert_eq!(
            serde_json::to_string(&ExitKind::Aborted).unwrap(),
            "\"aborted\""
        );
    }

    #[test]
    fn missing_started_at_caught() {
        let r = InvocationRecord::new(
            "tr-1",
            ToolId::FsRead,
            ExecutionMode::Plan,
            BundleName::Private,
            "",
            "",
            ExitKind::Success,
            0,
        );
        assert!(matches!(
            r.validate(None).unwrap_err(),
            RecordError::MissingStartedAt
        ));
    }

    #[test]
    fn record_serde_roundtrip() {
        let r = InvocationRecord::new(
            "tr-1",
            ToolId::ModelInference,
            ExecutionMode::Execute,
            BundleName::Sovereign,
            "2026-05-19T03:00:00Z",
            "2026-05-19T03:00:05Z",
            ExitKind::Success,
            4096,
        );
        let j = serde_json::to_string(&r).unwrap();
        let back: InvocationRecord = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
