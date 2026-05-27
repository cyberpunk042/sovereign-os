//! `sovereign-tool-catalog` — 8 cockpit-callable tools.
//!
//! Each tool declares:
//! - `side_effect`: None / Read / Write / Network / Model / Subprocess / Replay / Control
//! - `min_mode`:    minimum ExecutionMode required (e.g. fs-write requires
//!   Sandbox / Execute / Debug)
//! - `min_bundle`:  minimum BundleName required (Private/Careful/Fast/Sovereign)
//!
//! The cockpit reads this to decide which tools to surface in the
//! command palette; the dispatcher refuses calls that don't meet the
//! gates.
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

/// 8 canonical tools.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ToolId {
    /// Run a shell subprocess.
    Shell,
    /// Read a file.
    FsRead,
    /// Write a file.
    FsWrite,
    /// Fetch an HTTP(S) resource.
    WebFetch,
    /// Run a model inference call.
    ModelInference,
    /// Bridge to an MCP server.
    McpBridge,
    /// Replay control (start/pause/seek).
    ReplayControl,
    /// Bridge to the selfdef CLI.
    CliBridge,
}

/// Side-effect class.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SideEffect {
    /// No side effect.
    None,
    /// Filesystem read.
    Read,
    /// Filesystem write.
    Write,
    /// Network access.
    Network,
    /// Model invocation (tokens + cost).
    Model,
    /// Subprocess spawn.
    Subprocess,
    /// Replay state mutation.
    Replay,
    /// IPS control plane call.
    Control,
}

/// Per-tool record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToolRecord {
    /// Tool id.
    pub tool: ToolId,
    /// Side-effect class.
    pub side_effect: SideEffect,
    /// Minimum execution mode (set of allowed modes).
    pub allowed_modes: Vec<ExecutionMode>,
    /// Minimum bundle name (set of allowed bundles).
    pub allowed_bundles: Vec<BundleName>,
}

/// Catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToolCatalog {
    /// Schema version.
    pub schema_version: String,
    /// 8 records.
    pub tools: Vec<ToolRecord>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToolError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 8.
    #[error("tool count {0} != 8 canonical")]
    CountInvalid(usize),
    /// Missing tool.
    #[error("missing tool: {0:?}")]
    Missing(ToolId),
    /// allowed_modes empty.
    #[error("tool {0:?} declares no allowed modes")]
    NoModes(ToolId),
    /// allowed_bundles empty.
    #[error("tool {0:?} declares no allowed bundles")]
    NoBundles(ToolId),
    /// Tool unavailable in context.
    #[error("tool {tool:?} not available in mode {mode:?} bundle {bundle:?}")]
    Unavailable {
        /// Tool.
        tool: ToolId,
        /// Mode.
        mode: ExecutionMode,
        /// Bundle.
        bundle: BundleName,
    },
}

impl ToolCatalog {
    /// Canonical catalog.
    pub fn canonical() -> Self {
        use BundleName::*;
        use ExecutionMode::*;
        let tools = vec![
            ToolRecord {
                tool: ToolId::Shell,
                side_effect: SideEffect::Subprocess,
                allowed_modes: vec![Sandbox, Execute, Debug],
                allowed_bundles: vec![Careful, Fast, Sovereign],
            },
            ToolRecord {
                tool: ToolId::FsRead,
                side_effect: SideEffect::Read,
                allowed_modes: vec![Plan, DryRun, Shadow, Sandbox, Execute, Replay, Debug],
                allowed_bundles: vec![Private, Careful, Fast, Sovereign],
            },
            ToolRecord {
                tool: ToolId::FsWrite,
                side_effect: SideEffect::Write,
                allowed_modes: vec![Sandbox, Execute, Debug],
                allowed_bundles: vec![Careful, Fast, Sovereign],
            },
            ToolRecord {
                tool: ToolId::WebFetch,
                side_effect: SideEffect::Network,
                allowed_modes: vec![DryRun, Shadow, Execute, Debug],
                allowed_bundles: vec![Careful, Fast, Sovereign],
            },
            ToolRecord {
                tool: ToolId::ModelInference,
                side_effect: SideEffect::Model,
                allowed_modes: vec![Plan, DryRun, Shadow, Sandbox, Execute, Replay, Debug],
                allowed_bundles: vec![Private, Careful, Fast, Sovereign],
            },
            ToolRecord {
                tool: ToolId::McpBridge,
                side_effect: SideEffect::Network,
                allowed_modes: vec![DryRun, Shadow, Execute, Debug],
                allowed_bundles: vec![Careful, Fast, Sovereign],
            },
            ToolRecord {
                tool: ToolId::ReplayControl,
                side_effect: SideEffect::Replay,
                allowed_modes: vec![Replay, Debug],
                allowed_bundles: vec![Careful, Fast, Sovereign],
            },
            ToolRecord {
                tool: ToolId::CliBridge,
                side_effect: SideEffect::Control,
                allowed_modes: vec![Plan, DryRun, Shadow, Sandbox, Execute, Replay, Debug],
                allowed_bundles: vec![Careful, Fast, Sovereign],
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tools,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToolError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToolError::SchemaMismatch);
        }
        if self.tools.len() != 8 {
            return Err(ToolError::CountInvalid(self.tools.len()));
        }
        for t in [
            ToolId::Shell,
            ToolId::FsRead,
            ToolId::FsWrite,
            ToolId::WebFetch,
            ToolId::ModelInference,
            ToolId::McpBridge,
            ToolId::ReplayControl,
            ToolId::CliBridge,
        ] {
            if !self.tools.iter().any(|r| r.tool == t) {
                return Err(ToolError::Missing(t));
            }
        }
        for r in &self.tools {
            if r.allowed_modes.is_empty() {
                return Err(ToolError::NoModes(r.tool));
            }
            if r.allowed_bundles.is_empty() {
                return Err(ToolError::NoBundles(r.tool));
            }
        }
        Ok(())
    }

    /// Lookup by tool id.
    pub fn get(&self, t: ToolId) -> Option<&ToolRecord> {
        self.tools.iter().find(|r| r.tool == t)
    }

    /// Is this tool available given (mode, bundle)?
    pub fn is_available(&self, t: ToolId, mode: ExecutionMode, bundle: BundleName) -> bool {
        match self.get(t) {
            Some(r) => r.allowed_modes.contains(&mode) && r.allowed_bundles.contains(&bundle),
            None => false,
        }
    }

    /// Refuse tool with descriptive error if unavailable.
    pub fn require_available(
        &self,
        t: ToolId,
        mode: ExecutionMode,
        bundle: BundleName,
    ) -> Result<(), ToolError> {
        if self.is_available(t, mode, bundle) {
            Ok(())
        } else {
            Err(ToolError::Unavailable {
                tool: t,
                mode,
                bundle,
            })
        }
    }

    /// Names of tools available in the given (mode, bundle) context.
    pub fn available_tools(&self, mode: ExecutionMode, bundle: BundleName) -> Vec<ToolId> {
        self.tools
            .iter()
            .filter(|r| r.allowed_modes.contains(&mode) && r.allowed_bundles.contains(&bundle))
            .map(|r| r.tool)
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        ToolCatalog::canonical().validate().unwrap();
    }

    #[test]
    fn eight_tools_present() {
        let c = ToolCatalog::canonical();
        for t in [
            ToolId::Shell,
            ToolId::FsRead,
            ToolId::FsWrite,
            ToolId::WebFetch,
            ToolId::ModelInference,
            ToolId::McpBridge,
            ToolId::ReplayControl,
            ToolId::CliBridge,
        ] {
            assert!(c.get(t).is_some(), "missing {t:?}");
        }
    }

    #[test]
    fn fs_read_universally_available_in_curated_bundles() {
        let c = ToolCatalog::canonical();
        for mode in [
            ExecutionMode::Plan,
            ExecutionMode::DryRun,
            ExecutionMode::Shadow,
            ExecutionMode::Sandbox,
            ExecutionMode::Execute,
            ExecutionMode::Replay,
            ExecutionMode::Debug,
        ] {
            for bundle in [
                BundleName::Private,
                BundleName::Careful,
                BundleName::Fast,
                BundleName::Sovereign,
            ] {
                assert!(c.is_available(ToolId::FsRead, mode, bundle));
            }
        }
    }

    #[test]
    fn fs_write_blocked_in_plan_mode() {
        let c = ToolCatalog::canonical();
        assert!(!c.is_available(ToolId::FsWrite, ExecutionMode::Plan, BundleName::Sovereign));
        assert!(!c.is_available(
            ToolId::FsWrite,
            ExecutionMode::DryRun,
            BundleName::Sovereign
        ));
        assert!(c.is_available(ToolId::FsWrite, ExecutionMode::Sandbox, BundleName::Careful));
        assert!(c.is_available(ToolId::FsWrite, ExecutionMode::Execute, BundleName::Careful));
    }

    #[test]
    fn replay_control_only_in_replay_or_debug() {
        let c = ToolCatalog::canonical();
        assert!(c.is_available(
            ToolId::ReplayControl,
            ExecutionMode::Replay,
            BundleName::Careful
        ));
        assert!(c.is_available(
            ToolId::ReplayControl,
            ExecutionMode::Debug,
            BundleName::Careful
        ));
        assert!(!c.is_available(
            ToolId::ReplayControl,
            ExecutionMode::Execute,
            BundleName::Careful
        ));
    }

    #[test]
    fn shell_blocked_in_private_bundle() {
        let c = ToolCatalog::canonical();
        assert!(!c.is_available(ToolId::Shell, ExecutionMode::Execute, BundleName::Private));
        assert!(c.is_available(ToolId::Shell, ExecutionMode::Execute, BundleName::Careful));
    }

    #[test]
    fn web_fetch_blocked_in_private() {
        let c = ToolCatalog::canonical();
        assert!(!c.is_available(
            ToolId::WebFetch,
            ExecutionMode::Execute,
            BundleName::Private
        ));
    }

    #[test]
    fn require_available_returns_error_on_block() {
        let c = ToolCatalog::canonical();
        let err = c
            .require_available(ToolId::FsWrite, ExecutionMode::Plan, BundleName::Sovereign)
            .unwrap_err();
        match err {
            ToolError::Unavailable { tool, mode, bundle } => {
                assert_eq!(tool, ToolId::FsWrite);
                assert_eq!(mode, ExecutionMode::Plan);
                assert_eq!(bundle, BundleName::Sovereign);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn available_tools_in_plan_private() {
        let c = ToolCatalog::canonical();
        let v = c.available_tools(ExecutionMode::Plan, BundleName::Private);
        // FsRead + ModelInference universally allowed in Private; CliBridge not in Private.
        assert!(v.contains(&ToolId::FsRead));
        assert!(v.contains(&ToolId::ModelInference));
        assert!(!v.contains(&ToolId::FsWrite));
        assert!(!v.contains(&ToolId::Shell));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ToolCatalog::canonical();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            ToolError::SchemaMismatch
        ));
    }

    #[test]
    fn count_invalid_caught() {
        let mut c = ToolCatalog::canonical();
        c.tools.pop();
        assert!(matches!(
            c.validate().unwrap_err(),
            ToolError::CountInvalid(7)
        ));
    }

    #[test]
    fn no_modes_caught() {
        let mut c = ToolCatalog::canonical();
        c.tools[0].allowed_modes.clear();
        match c.validate().unwrap_err() {
            ToolError::NoModes(t) => assert_eq!(t, c.tools[0].tool),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn tool_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ToolId::FsRead).unwrap(),
            "\"fs-read\""
        );
        assert_eq!(
            serde_json::to_string(&ToolId::ModelInference).unwrap(),
            "\"model-inference\""
        );
        assert_eq!(
            serde_json::to_string(&ToolId::CliBridge).unwrap(),
            "\"cli-bridge\""
        );
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let c = ToolCatalog::canonical();
        let j = serde_json::to_string(&c).unwrap();
        let back: ToolCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
