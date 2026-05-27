//! `sovereign-cockpit-context-panel` — sidebar context envelope.
//!
//! Single source of truth for the cockpit's sidebar: which conversation
//! is active, which bundle, mode, workspace folder, branch_id. The
//! sidebar reads this on every render; updates are operator-driven.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_profile_bundles::BundleName;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Context panel state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContextPanel {
    /// Schema version.
    pub schema_version: String,
    /// Active conversation thread id (non-empty when one is open).
    pub conversation_id: String,
    /// Active bundle.
    pub bundle: BundleName,
    /// Active execution mode.
    pub mode: ExecutionMode,
    /// Active workspace folder label (matches workspace-folder-registry).
    pub workspace_label: String,
    /// Active branch id (matches conversation-thread branch ids).
    pub branch_id: String,
    /// ISO-8601 UTC of last refresh.
    pub refreshed_at: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ContextError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// refreshed_at empty.
    #[error("refreshed_at missing")]
    MissingTimestamp,
    /// branch_id empty.
    #[error("branch_id missing")]
    MissingBranchId,
    /// Inconsistent: mode is Replay but no conversation_id set.
    #[error("Replay mode requires conversation_id")]
    ReplayWithoutConversation,
}

impl ContextPanel {
    /// New panel.
    pub fn new(
        bundle: BundleName,
        mode: ExecutionMode,
        workspace_label: &str,
        branch_id: &str,
        conversation_id: &str,
        refreshed_at: &str,
    ) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            conversation_id: conversation_id.into(),
            bundle,
            mode,
            workspace_label: workspace_label.into(),
            branch_id: branch_id.into(),
            refreshed_at: refreshed_at.into(),
        }
    }

    /// Validate cross-field constraints.
    pub fn validate(&self) -> Result<(), ContextError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ContextError::SchemaMismatch);
        }
        if self.refreshed_at.is_empty() {
            return Err(ContextError::MissingTimestamp);
        }
        if self.branch_id.is_empty() {
            return Err(ContextError::MissingBranchId);
        }
        if self.mode == ExecutionMode::Replay && self.conversation_id.is_empty() {
            return Err(ContextError::ReplayWithoutConversation);
        }
        Ok(())
    }

    /// True if there's an active conversation.
    pub fn has_conversation(&self) -> bool {
        !self.conversation_id.is_empty()
    }

    /// True if a workspace is set.
    pub fn has_workspace(&self) -> bool {
        !self.workspace_label.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn typical_panel_validates() {
        ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::DryRun,
            "repo",
            "main",
            "th-1",
            "2026-05-19T03:00:00Z",
        )
        .validate()
        .unwrap();
    }

    #[test]
    fn missing_timestamp_caught() {
        let mut p = ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Plan,
            "repo",
            "main",
            "",
            "",
        );
        let _ = p.conversation_id;
        p.refreshed_at = String::new();
        assert!(matches!(
            p.validate().unwrap_err(),
            ContextError::MissingTimestamp
        ));
    }

    #[test]
    fn missing_branch_caught() {
        let p = ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Plan,
            "repo",
            "",
            "",
            "t",
        );
        assert!(matches!(
            p.validate().unwrap_err(),
            ContextError::MissingBranchId
        ));
    }

    #[test]
    fn replay_without_conversation_caught() {
        let p = ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Replay,
            "repo",
            "main",
            "",
            "t",
        );
        assert!(matches!(
            p.validate().unwrap_err(),
            ContextError::ReplayWithoutConversation
        ));
    }

    #[test]
    fn replay_with_conversation_ok() {
        ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Replay,
            "repo",
            "main",
            "th-1",
            "t",
        )
        .validate()
        .unwrap();
    }

    #[test]
    fn has_conversation_flag() {
        let p_empty = ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Plan,
            "repo",
            "main",
            "",
            "t",
        );
        assert!(!p_empty.has_conversation());
        let p_full = ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Plan,
            "repo",
            "main",
            "th-1",
            "t",
        );
        assert!(p_full.has_conversation());
    }

    #[test]
    fn has_workspace_flag() {
        let p_empty = ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Plan,
            "",
            "main",
            "",
            "t",
        );
        assert!(!p_empty.has_workspace());
        let p_full = ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Plan,
            "repo",
            "main",
            "",
            "t",
        );
        assert!(p_full.has_workspace());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Plan,
            "",
            "main",
            "",
            "t",
        );
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            ContextError::SchemaMismatch
        ));
    }

    #[test]
    fn panel_serde_roundtrip() {
        let p = ContextPanel::new(
            BundleName::Sovereign,
            ExecutionMode::Execute,
            "repo",
            "main",
            "th-1",
            "2026-05-19T03:00:00Z",
        );
        let j = serde_json::to_string(&p).unwrap();
        let back: ContextPanel = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
