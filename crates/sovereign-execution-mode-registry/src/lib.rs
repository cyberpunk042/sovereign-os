//! `sovereign-execution-mode-registry` — 7 runtime execution modes.
//!
//! The cockpit operates in exactly one mode at a time. Each mode declares
//! a stable capability tuple the dispatcher checks before allowing an
//! operation:
//!
//! | Mode      | writes | network | snapshot | replay-src |
//! |-----------|--------|---------|----------|------------|
//! | Plan      | ✗      | ✗       | ✗        | ✗          |
//! | DryRun    | ✗      | ✓       | ✗        | ✗          |
//! | Shadow    | ✗      | ✓       | ✗        | ✗          |
//! | Sandbox   | ✓ (sb) | ✗       | ✗        | ✗          |
//! | Execute   | ✓      | ✓       | ✓        | ✗          |
//! | Replay    | ✗      | ✗       | ✗        | ✓          |
//! | Debug     | ✓      | ✓       | ✗        | ✗          |
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Execution mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ExecutionMode {
    /// Plan-only — produce plans, no side effects.
    Plan,
    /// Dry-run — go through motions but no host writes.
    DryRun,
    /// Shadow — read-only mirror of a live system.
    Shadow,
    /// Sandbox — writes go to sandbox FS only.
    Sandbox,
    /// Execute — full live execution.
    Execute,
    /// Replay — replay a captured trace.
    Replay,
    /// Debug — full execute + verbose telemetry.
    Debug,
}

/// Capability tuple for a mode.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModeCapabilities {
    /// Host writes allowed.
    pub writes_allowed: bool,
    /// Network egress allowed.
    pub network_allowed: bool,
    /// ZFS snapshot taken before transition into mode.
    pub snapshot_required: bool,
    /// Replay source (trace JSONL) required.
    pub replay_source_required: bool,
}

/// Per-mode capability record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModeRecord {
    /// Mode.
    pub mode: ExecutionMode,
    /// Capabilities.
    pub caps: ModeCapabilities,
}

/// Registry envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExecutionModeRegistry {
    /// Schema version.
    pub schema_version: String,
    /// 7 records (one per mode).
    pub records: Vec<ModeRecord>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ModeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 7.
    #[error("mode count {0} != 7 canonical")]
    CountInvalid(usize),
    /// Missing mode.
    #[error("missing mode: {0:?}")]
    Missing(ExecutionMode),
    /// Replay mode but replay_source_required false (or vice-versa).
    #[error("replay flag mismatch for {0:?}")]
    ReplayFlagMismatch(ExecutionMode),
    /// Operation rejected: mode forbids it.
    #[error("operation {op} not permitted in mode {mode:?}")]
    OperationForbidden {
        /// Mode.
        mode: ExecutionMode,
        /// Op name.
        op: String,
    },
}

impl ExecutionMode {
    /// Canonical capability tuple for this mode.
    pub fn canonical_caps(self) -> ModeCapabilities {
        match self {
            ExecutionMode::Plan => ModeCapabilities {
                writes_allowed: false, network_allowed: false,
                snapshot_required: false, replay_source_required: false,
            },
            ExecutionMode::DryRun => ModeCapabilities {
                writes_allowed: false, network_allowed: true,
                snapshot_required: false, replay_source_required: false,
            },
            ExecutionMode::Shadow => ModeCapabilities {
                writes_allowed: false, network_allowed: true,
                snapshot_required: false, replay_source_required: false,
            },
            ExecutionMode::Sandbox => ModeCapabilities {
                writes_allowed: true, network_allowed: false,
                snapshot_required: false, replay_source_required: false,
            },
            ExecutionMode::Execute => ModeCapabilities {
                writes_allowed: true, network_allowed: true,
                snapshot_required: true, replay_source_required: false,
            },
            ExecutionMode::Replay => ModeCapabilities {
                writes_allowed: false, network_allowed: false,
                snapshot_required: false, replay_source_required: true,
            },
            ExecutionMode::Debug => ModeCapabilities {
                writes_allowed: true, network_allowed: true,
                snapshot_required: false, replay_source_required: false,
            },
        }
    }
}

impl ExecutionModeRegistry {
    /// Canonical registry — all 7 modes with declared capability tuples.
    pub fn canonical() -> Self {
        let records = [
            ExecutionMode::Plan, ExecutionMode::DryRun, ExecutionMode::Shadow,
            ExecutionMode::Sandbox, ExecutionMode::Execute, ExecutionMode::Replay,
            ExecutionMode::Debug,
        ].into_iter().map(|m| ModeRecord {
            mode: m,
            caps: m.canonical_caps(),
        }).collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            records,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ModeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ModeError::SchemaMismatch);
        }
        if self.records.len() != 7 {
            return Err(ModeError::CountInvalid(self.records.len()));
        }
        for m in [
            ExecutionMode::Plan, ExecutionMode::DryRun, ExecutionMode::Shadow,
            ExecutionMode::Sandbox, ExecutionMode::Execute, ExecutionMode::Replay,
            ExecutionMode::Debug,
        ] {
            if !self.records.iter().any(|r| r.mode == m) {
                return Err(ModeError::Missing(m));
            }
        }
        // Cross-check: Replay must require replay source; nothing else may.
        for r in &self.records {
            let canonical_replay = r.mode == ExecutionMode::Replay;
            if r.caps.replay_source_required != canonical_replay {
                return Err(ModeError::ReplayFlagMismatch(r.mode));
            }
        }
        Ok(())
    }

    /// Lookup by mode.
    pub fn get(&self, m: ExecutionMode) -> Option<&ModeRecord> {
        self.records.iter().find(|r| r.mode == m)
    }

    /// Check whether a write operation is permitted in the given mode.
    pub fn check_write(&self, mode: ExecutionMode) -> Result<(), ModeError> {
        let r = self.get(mode).ok_or(ModeError::Missing(mode))?;
        if !r.caps.writes_allowed {
            return Err(ModeError::OperationForbidden { mode, op: "write".into() });
        }
        Ok(())
    }

    /// Check whether a network operation is permitted in the given mode.
    pub fn check_network(&self, mode: ExecutionMode) -> Result<(), ModeError> {
        let r = self.get(mode).ok_or(ModeError::Missing(mode))?;
        if !r.caps.network_allowed {
            return Err(ModeError::OperationForbidden { mode, op: "network".into() });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        ExecutionModeRegistry::canonical().validate().unwrap();
    }

    #[test]
    fn seven_modes_present() {
        let r = ExecutionModeRegistry::canonical();
        assert_eq!(r.records.len(), 7);
        for m in [ExecutionMode::Plan, ExecutionMode::DryRun, ExecutionMode::Shadow,
                  ExecutionMode::Sandbox, ExecutionMode::Execute, ExecutionMode::Replay,
                  ExecutionMode::Debug] {
            assert!(r.get(m).is_some(), "missing {m:?}");
        }
    }

    #[test]
    fn plan_forbids_writes_and_network() {
        let r = ExecutionModeRegistry::canonical();
        assert!(r.check_write(ExecutionMode::Plan).is_err());
        assert!(r.check_network(ExecutionMode::Plan).is_err());
    }

    #[test]
    fn execute_permits_writes_and_network() {
        let r = ExecutionModeRegistry::canonical();
        r.check_write(ExecutionMode::Execute).unwrap();
        r.check_network(ExecutionMode::Execute).unwrap();
    }

    #[test]
    fn sandbox_writes_but_no_network() {
        let r = ExecutionModeRegistry::canonical();
        r.check_write(ExecutionMode::Sandbox).unwrap();
        assert!(r.check_network(ExecutionMode::Sandbox).is_err());
    }

    #[test]
    fn replay_requires_source_only_for_replay() {
        let r = ExecutionModeRegistry::canonical();
        assert!(r.get(ExecutionMode::Replay).unwrap().caps.replay_source_required);
        for m in [ExecutionMode::Plan, ExecutionMode::DryRun, ExecutionMode::Shadow,
                  ExecutionMode::Sandbox, ExecutionMode::Execute, ExecutionMode::Debug] {
            assert!(!r.get(m).unwrap().caps.replay_source_required, "{m:?} should not require replay src");
        }
    }

    #[test]
    fn execute_requires_snapshot() {
        let r = ExecutionModeRegistry::canonical();
        assert!(r.get(ExecutionMode::Execute).unwrap().caps.snapshot_required);
    }

    #[test]
    fn replay_flag_mismatch_caught() {
        let mut r = ExecutionModeRegistry::canonical();
        for rec in r.records.iter_mut() {
            if rec.mode == ExecutionMode::Replay {
                rec.caps.replay_source_required = false;
            }
        }
        assert!(matches!(r.validate().unwrap_err(), ModeError::ReplayFlagMismatch(ExecutionMode::Replay)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = ExecutionModeRegistry::canonical();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), ModeError::SchemaMismatch));
    }

    #[test]
    fn count_invalid_caught() {
        let mut r = ExecutionModeRegistry::canonical();
        r.records.pop();
        assert!(matches!(r.validate().unwrap_err(), ModeError::CountInvalid(6)));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(serde_json::to_string(&ExecutionMode::Plan).unwrap(), "\"plan\"");
        assert_eq!(serde_json::to_string(&ExecutionMode::DryRun).unwrap(), "\"dry-run\"");
        assert_eq!(serde_json::to_string(&ExecutionMode::Sandbox).unwrap(), "\"sandbox\"");
    }

    #[test]
    fn registry_serde_roundtrip() {
        let r = ExecutionModeRegistry::canonical();
        let j = serde_json::to_string(&r).unwrap();
        let back: ExecutionModeRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
