//! The Trinity execution cycle — the Pulse → Weaver → Auditor handoff.
//!
//! The manifest in `lib.rs` tracks *which* roles are bound. This module
//! models what the Trinity framework actually *does* (M066): a unit of
//! work flows through the three roles in a fixed order, and the **Auditor
//! is the immutable gatekeeper** — a result reaches `Committed` only by
//! passing the Auditor (E0642). A failure at any stage rejects the cycle.
//!
//! ```text
//! Pulsing ──pulse ok──▶ Weaving ──weave ok──▶ Auditing ──audit pass──▶ Committed
//!    │                     │                      │
//!    └── fail ──▶ Rejected └── fail ──▶ Rejected  └── fail ──▶ Rejected
//! ```
//!
//! Order is enforced: you cannot weave before the Pulse has produced, nor
//! audit before the Weaver has woven. This is the SRP "one role, one
//! responsibility, in sequence" discipline made executable.

use crate::TrinityRole;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Where a Trinity cycle currently is.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CycleStage {
    /// Awaiting the Pulse (compute / bit-plane / ternary).
    Pulsing,
    /// Awaiting the Weaver (orchestration / state transition).
    Weaving,
    /// Awaiting the Auditor (immutable verification gate).
    Auditing,
    /// Passed the Auditor — durable commit.
    Committed,
    /// Rejected at some stage — no commit.
    Rejected,
}

impl CycleStage {
    /// Whether the cycle has finished (committed or rejected).
    pub fn is_terminal(self) -> bool {
        matches!(self, CycleStage::Committed | CycleStage::Rejected)
    }

    /// The role expected to act next, or `None` if terminal.
    pub fn expected_role(self) -> Option<TrinityRole> {
        match self {
            CycleStage::Pulsing => Some(TrinityRole::Pulse),
            CycleStage::Weaving => Some(TrinityRole::Weaver),
            CycleStage::Auditing => Some(TrinityRole::Auditor),
            CycleStage::Committed | CycleStage::Rejected => None,
        }
    }
}

/// A single role's contribution to the cycle.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StageReport {
    /// Which role acted.
    pub role: TrinityRole,
    /// Whether it passed.
    pub passed: bool,
    /// Operator-readable note.
    pub note: String,
}

/// Cycle sequencing errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum CycleError {
    /// A role acted out of turn.
    #[error("out-of-order: stage expected {expected:?} but {got:?} acted")]
    OutOfOrder {
        /// The role the current stage expects.
        expected: TrinityRole,
        /// The role that actually tried to act.
        got: TrinityRole,
    },
    /// A role acted after the cycle had already terminated.
    #[error("cycle already terminal ({0:?}); no further roles may act")]
    AlreadyTerminal(CycleStage),
}

/// A Trinity execution cycle.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TrinityCycle {
    /// Current stage.
    pub stage: CycleStage,
    /// Reports in submission order.
    pub reports: Vec<StageReport>,
}

impl Default for TrinityCycle {
    fn default() -> Self {
        Self::new()
    }
}

impl TrinityCycle {
    /// A fresh cycle awaiting the Pulse.
    pub fn new() -> Self {
        Self {
            stage: CycleStage::Pulsing,
            reports: Vec::new(),
        }
    }

    /// Submit a role's result. The role MUST match the stage's
    /// [`CycleStage::expected_role`]. A pass advances the cycle; a fail
    /// rejects it. Returns the new stage.
    pub fn submit(
        &mut self,
        role: TrinityRole,
        passed: bool,
        note: &str,
    ) -> Result<CycleStage, CycleError> {
        let Some(expected) = self.stage.expected_role() else {
            return Err(CycleError::AlreadyTerminal(self.stage));
        };
        if role != expected {
            return Err(CycleError::OutOfOrder {
                expected,
                got: role,
            });
        }
        self.reports.push(StageReport {
            role,
            passed,
            note: note.to_string(),
        });
        self.stage = if !passed {
            CycleStage::Rejected
        } else {
            match self.stage {
                CycleStage::Pulsing => CycleStage::Weaving,
                CycleStage::Weaving => CycleStage::Auditing,
                CycleStage::Auditing => CycleStage::Committed,
                // Unreachable: expected_role() was Some above.
                terminal => terminal,
            }
        };
        Ok(self.stage)
    }

    /// Whether the cycle committed (passed the Auditor gate).
    pub fn committed(&self) -> bool {
        self.stage == CycleStage::Committed
    }

    /// Run a full cycle in one call, short-circuiting on the first failure.
    /// Each tuple is `(passed, note)` for Pulse, Weaver, Auditor in order.
    pub fn run(pulse: (bool, &str), weave: (bool, &str), audit: (bool, &str)) -> TrinityCycle {
        let mut c = TrinityCycle::new();
        // Ordered submission can never be OutOfOrder; stop if a stage rejects.
        let _ = c.submit(TrinityRole::Pulse, pulse.0, pulse.1);
        if !c.stage.is_terminal() {
            let _ = c.submit(TrinityRole::Weaver, weave.0, weave.1);
        }
        if !c.stage.is_terminal() {
            let _ = c.submit(TrinityRole::Auditor, audit.0, audit.1);
        }
        c
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_path_commits_through_the_auditor() {
        let mut c = TrinityCycle::new();
        assert_eq!(
            c.submit(TrinityRole::Pulse, true, "computed").unwrap(),
            CycleStage::Weaving
        );
        assert_eq!(
            c.submit(TrinityRole::Weaver, true, "woven").unwrap(),
            CycleStage::Auditing
        );
        assert_eq!(
            c.submit(TrinityRole::Auditor, true, "verified").unwrap(),
            CycleStage::Committed
        );
        assert!(c.committed());
        assert_eq!(c.reports.len(), 3);
    }

    #[test]
    fn auditor_is_the_gatekeeper() {
        // Pulse + Weaver pass, but the Auditor rejects → no commit.
        let c = TrinityCycle::run((true, "ok"), (true, "ok"), (false, "tampered"));
        assert_eq!(c.stage, CycleStage::Rejected);
        assert!(!c.committed());
        assert_eq!(c.reports.len(), 3);
    }

    #[test]
    fn pulse_failure_halts_before_weaver() {
        let c = TrinityCycle::run((false, "bad iron"), (true, "x"), (true, "y"));
        assert_eq!(c.stage, CycleStage::Rejected);
        // Only the Pulse report exists — Weaver/Auditor never acted.
        assert_eq!(c.reports.len(), 1);
        assert_eq!(c.reports[0].role, TrinityRole::Pulse);
    }

    #[test]
    fn weave_failure_halts_before_auditor() {
        let c = TrinityCycle::run((true, "ok"), (false, "sandbox escape"), (true, "y"));
        assert_eq!(c.stage, CycleStage::Rejected);
        assert_eq!(c.reports.len(), 2);
    }

    #[test]
    fn out_of_order_is_refused() {
        let mut c = TrinityCycle::new();
        // Weaver tries to act before the Pulse.
        let err = c
            .submit(TrinityRole::Weaver, true, "premature")
            .unwrap_err();
        assert_eq!(
            err,
            CycleError::OutOfOrder {
                expected: TrinityRole::Pulse,
                got: TrinityRole::Weaver
            }
        );
        // State unchanged.
        assert_eq!(c.stage, CycleStage::Pulsing);
    }

    #[test]
    fn acting_after_terminal_is_refused() {
        let mut c = TrinityCycle::run((true, "a"), (true, "b"), (true, "c"));
        assert_eq!(c.stage, CycleStage::Committed);
        let err = c.submit(TrinityRole::Auditor, true, "again").unwrap_err();
        assert_eq!(err, CycleError::AlreadyTerminal(CycleStage::Committed));
    }

    #[test]
    fn expected_role_tracks_stage() {
        assert_eq!(
            CycleStage::Pulsing.expected_role(),
            Some(TrinityRole::Pulse)
        );
        assert_eq!(
            CycleStage::Weaving.expected_role(),
            Some(TrinityRole::Weaver)
        );
        assert_eq!(
            CycleStage::Auditing.expected_role(),
            Some(TrinityRole::Auditor)
        );
        assert_eq!(CycleStage::Committed.expected_role(), None);
        assert!(CycleStage::Rejected.is_terminal());
    }
}
