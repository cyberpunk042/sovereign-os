//! `sovereign-zfs-commit-gate` — M040 4-stage ZFS commit gate.
//!
//! Per M040 + M00678 + R06729-R06732 + dump 11692-11697.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 4 canonical commit-gate stages per dump 11693-11696.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum GateStage {
    /// 1. Pre-commit ZFS snapshot.
    Snapshot,
    /// 2. Apply patch (atomic write).
    Apply,
    /// 3. Test (eval-gate runs).
    Test,
    /// 4. Commit or rollback (final disposition).
    CommitOrRollback,
}

impl GateStage {
    /// Canonical 1..4 position.
    pub fn position(self) -> u8 {
        match self {
            GateStage::Snapshot => 1,
            GateStage::Apply => 2,
            GateStage::Test => 3,
            GateStage::CommitOrRollback => 4,
        }
    }
    /// Next stage; CommitOrRollback returns None (terminal).
    pub fn next(self) -> Option<Self> {
        match self {
            GateStage::Snapshot => Some(GateStage::Apply),
            GateStage::Apply => Some(GateStage::Test),
            GateStage::Test => Some(GateStage::CommitOrRollback),
            GateStage::CommitOrRollback => None,
        }
    }
}

/// Final disposition.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Disposition {
    /// Committed (kept).
    Committed,
    /// Rolled back to snapshot.
    RolledBack,
    /// In-flight (no final disposition yet).
    InFlight,
}

/// One commit-gate cycle record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GateCycle {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// ZFS dataset path (e.g. "rpool/sovereign-os").
    pub dataset: String,
    /// Snapshot id (e.g. "rpool/sovereign-os@pre-2026-05-19T03:00").
    pub snapshot_id: String,
    /// Current stage.
    pub stage: GateStage,
    /// Final disposition.
    pub disposition: Disposition,
    /// Test eval score (0..=100); >= 80 required to advance to commit.
    pub test_score: u8,
    /// MS003 signature on the commit envelope.
    pub signature: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GateError {
    /// Stage skip.
    #[error("stage skip {from:?} → {to:?} not allowed")]
    StageSkip {
        /// From.
        from: GateStage,
        /// To.
        to: GateStage,
    },
    /// Past-terminal advance.
    #[error("past-terminal CommitOrRollback advance refused")]
    PastTerminal,
    /// Empty fields.
    #[error("required field empty: {0}")]
    FieldEmpty(&'static str),
    /// Test score below 80 — refuse commit (must rollback).
    #[error("test_score {0} below 80 — must rollback")]
    TestGateFailed(u8),
    /// Snapshot id format invalid (must contain '@').
    #[error("snapshot_id missing @ separator: {0}")]
    SnapshotIdInvalid(String),
}

impl GateCycle {
    /// Validate envelope structural invariants.
    pub fn validate(&self) -> Result<(), GateError> {
        if self.dataset.is_empty() {
            return Err(GateError::FieldEmpty("dataset"));
        }
        if self.snapshot_id.is_empty() {
            return Err(GateError::FieldEmpty("snapshot_id"));
        }
        if !self.snapshot_id.contains('@') {
            return Err(GateError::SnapshotIdInvalid(self.snapshot_id.clone()));
        }
        if self.signature.is_empty() {
            return Err(GateError::FieldEmpty("signature"));
        }
        Ok(())
    }

    /// Advance stage. CommitOrRollback enforces test_score >= 80 unless rolling back.
    pub fn advance(&mut self, target: GateStage) -> Result<(), GateError> {
        let next = self.stage.next().ok_or(GateError::PastTerminal)?;
        if next != target {
            return Err(GateError::StageSkip {
                from: self.stage,
                to: target,
            });
        }
        if target == GateStage::CommitOrRollback
            && self.test_score < 80
            && self.disposition != Disposition::RolledBack
        {
            return Err(GateError::TestGateFailed(self.test_score));
        }
        self.stage = target;
        Ok(())
    }

    /// Set final disposition (Commit only allowed if test_score >= 80).
    pub fn finalize(&mut self, disposition: Disposition) -> Result<(), GateError> {
        if disposition == Disposition::Committed && self.test_score < 80 {
            return Err(GateError::TestGateFailed(self.test_score));
        }
        self.disposition = disposition;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cycle() -> GateCycle {
        GateCycle {
            schema_version: SCHEMA_VERSION.into(),
            dataset: "rpool/sovereign-os".into(),
            snapshot_id: "rpool/sovereign-os@pre-2026-05-19T03:00".into(),
            stage: GateStage::Snapshot,
            disposition: Disposition::InFlight,
            test_score: 85,
            signature: "ms003-sig".into(),
        }
    }

    #[test]
    fn four_stages_positioned_1_to_4() {
        for (s, p) in [
            (GateStage::Snapshot, 1),
            (GateStage::Apply, 2),
            (GateStage::Test, 3),
            (GateStage::CommitOrRollback, 4),
        ] {
            assert_eq!(s.position(), p);
        }
    }

    #[test]
    fn next_chain_terminates_at_commit_or_rollback() {
        let mut s = GateStage::Snapshot;
        let mut count = 1;
        while let Some(n) = s.next() {
            s = n;
            count += 1;
        }
        assert_eq!(count, 4);
        assert_eq!(s, GateStage::CommitOrRollback);
    }

    #[test]
    fn ok_cycle_validates() {
        cycle().validate().unwrap();
    }

    #[test]
    fn empty_dataset_rejected() {
        let mut c = cycle();
        c.dataset = String::new();
        assert!(matches!(
            c.validate().unwrap_err(),
            GateError::FieldEmpty("dataset")
        ));
    }

    #[test]
    fn snapshot_without_at_rejected() {
        let mut c = cycle();
        c.snapshot_id = "no-at-separator".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            GateError::SnapshotIdInvalid(_)
        ));
    }

    #[test]
    fn advance_full_chain_succeeds() {
        let mut c = cycle();
        c.advance(GateStage::Apply).unwrap();
        c.advance(GateStage::Test).unwrap();
        c.advance(GateStage::CommitOrRollback).unwrap();
    }

    #[test]
    fn stage_skip_refused() {
        let mut c = cycle();
        assert!(matches!(
            c.advance(GateStage::CommitOrRollback).unwrap_err(),
            GateError::StageSkip { .. }
        ));
    }

    #[test]
    fn past_terminal_refused() {
        let mut c = cycle();
        c.stage = GateStage::CommitOrRollback;
        assert!(matches!(
            c.advance(GateStage::Snapshot).unwrap_err(),
            GateError::PastTerminal
        ));
    }

    #[test]
    fn test_gate_below_80_refused_for_commit() {
        let mut c = cycle();
        c.test_score = 70;
        c.stage = GateStage::Test;
        assert!(matches!(
            c.advance(GateStage::CommitOrRollback).unwrap_err(),
            GateError::TestGateFailed(70)
        ));
    }

    #[test]
    fn test_gate_below_80_allowed_for_rollback() {
        let mut c = cycle();
        c.test_score = 70;
        c.stage = GateStage::Test;
        c.disposition = Disposition::RolledBack;
        c.advance(GateStage::CommitOrRollback).unwrap();
    }

    #[test]
    fn finalize_commit_requires_80() {
        let mut c = cycle();
        c.test_score = 70;
        assert!(matches!(
            c.finalize(Disposition::Committed).unwrap_err(),
            GateError::TestGateFailed(70)
        ));
        // Rollback is allowed regardless of score
        c.finalize(Disposition::RolledBack).unwrap();
    }

    #[test]
    fn stage_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&GateStage::CommitOrRollback).unwrap(),
            "\"commit-or-rollback\""
        );
        assert_eq!(
            serde_json::to_string(&GateStage::Snapshot).unwrap(),
            "\"snapshot\""
        );
    }

    #[test]
    fn disposition_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Disposition::RolledBack).unwrap(),
            "\"rolled-back\""
        );
        assert_eq!(
            serde_json::to_string(&Disposition::InFlight).unwrap(),
            "\"in-flight\""
        );
    }

    #[test]
    fn cycle_serde_roundtrip() {
        let c = cycle();
        let j = serde_json::to_string(&c).unwrap();
        let back: GateCycle = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
