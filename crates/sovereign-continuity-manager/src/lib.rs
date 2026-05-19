//! `sovereign-continuity-manager` — M048 Module 8 sleeper module.
//!
//! Per M048 + E0464 + M00810 + dump 14706-14720. Six primitives + eight
//! lifecycle states form the continuity discipline.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 6 continuity primitives per E0464 dump 14710.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ContinuityPrimitive {
    /// ZFS snapshots.
    ZfsSnapshots,
    /// Podman-CRIU checkpoints.
    PodmanCriu,
    /// Workflow hibernation.
    WorkflowHibernation,
    /// Context compaction.
    ContextCompaction,
    /// Model server warm pools.
    WarmPools,
    /// Session resume.
    SessionResume,
}

/// 8 continuity states per dump 14712.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ContinuityState {
    /// Active (1).
    Active,
    /// Paused (2).
    Paused,
    /// Hibernated (3).
    Hibernated,
    /// Checkpointed (4).
    Checkpointed,
    /// Archived (5).
    Archived,
    /// Quarantined (6).
    Quarantined,
    /// Promoted (7).
    Promoted,
    /// Rolled back (8).
    RolledBack,
}

impl ContinuityState {
    /// 1..8 canonical position.
    pub fn position(self) -> u8 {
        match self {
            ContinuityState::Active => 1,
            ContinuityState::Paused => 2,
            ContinuityState::Hibernated => 3,
            ContinuityState::Checkpointed => 4,
            ContinuityState::Archived => 5,
            ContinuityState::Quarantined => 6,
            ContinuityState::Promoted => 7,
            ContinuityState::RolledBack => 8,
        }
    }
    /// Whether this state allows continuation (resume / re-promote).
    pub fn is_resumable(self) -> bool {
        matches!(
            self,
            ContinuityState::Paused | ContinuityState::Hibernated
            | ContinuityState::Checkpointed | ContinuityState::Archived
        )
    }
}

/// One continuity-managed session record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SessionRecord {
    /// ULID session id.
    pub session_id: String,
    /// Current state.
    pub state: ContinuityState,
    /// Last primitive applied (for audit).
    pub last_primitive: Option<ContinuityPrimitive>,
    /// ISO-8601 UTC last transition timestamp.
    pub last_transition_at: String,
    /// MS003 signature on the latest transition envelope.
    pub signature: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ContinuityError {
    /// Invalid transition from → to.
    #[error("invalid transition {from:?} → {to:?}")]
    InvalidTransition {
        /// From state.
        from: ContinuityState,
        /// To state.
        to: ContinuityState,
    },
    /// Transition unsigned.
    #[error("transition unsigned (MS003 signature required)")]
    Unsigned,
    /// Promotion attempted from a non-resumable state without operator override.
    #[error("promotion from {0:?} requires operator override")]
    PromotionRequiresOverride(ContinuityState),
}

/// Whether a transition is allowed in the lifecycle graph.
pub fn is_allowed_transition(from: ContinuityState, to: ContinuityState) -> bool {
    use ContinuityState::*;
    match (from, to) {
        (Active, Paused | Hibernated | Checkpointed | Archived | Quarantined | Promoted | RolledBack) => true,
        (Paused, Active | Hibernated | Quarantined | Archived) => true,
        (Hibernated, Active | Archived | Quarantined) => true,
        (Checkpointed, Active | Archived | Quarantined) => true,
        (Archived, Active) => true,  // archive→re-activate
        (Quarantined, Active | Archived) => true,  // operator-signed release
        (Promoted, Active) => true,  // already promoted, back to active
        (RolledBack, Active) => true, // post-rollback resume
        _ => false,
    }
}

/// Apply a transition to a session record.
pub fn transition(
    rec: &mut SessionRecord,
    to: ContinuityState,
    primitive: Option<ContinuityPrimitive>,
    signature: &str,
    at: &str,
) -> Result<(), ContinuityError> {
    if signature.is_empty() {
        return Err(ContinuityError::Unsigned);
    }
    if !is_allowed_transition(rec.state, to) {
        return Err(ContinuityError::InvalidTransition { from: rec.state, to });
    }
    rec.state = to;
    rec.last_primitive = primitive;
    rec.last_transition_at = at.into();
    rec.signature = signature.into();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec() -> SessionRecord {
        SessionRecord {
            session_id: "sess-001".into(),
            state: ContinuityState::Active,
            last_primitive: None,
            last_transition_at: "2026-05-19T00:00:00Z".into(),
            signature: "ms003".into(),
        }
    }

    #[test]
    fn eight_states_positioned_1_to_8() {
        for (s, p) in [
            (ContinuityState::Active, 1), (ContinuityState::Paused, 2),
            (ContinuityState::Hibernated, 3), (ContinuityState::Checkpointed, 4),
            (ContinuityState::Archived, 5), (ContinuityState::Quarantined, 6),
            (ContinuityState::Promoted, 7), (ContinuityState::RolledBack, 8),
        ] {
            assert_eq!(s.position(), p);
        }
    }

    #[test]
    fn resumable_states() {
        for s in [
            ContinuityState::Paused, ContinuityState::Hibernated,
            ContinuityState::Checkpointed, ContinuityState::Archived,
        ] {
            assert!(s.is_resumable(), "{s:?} should be resumable");
        }
        assert!(!ContinuityState::Active.is_resumable());
        assert!(!ContinuityState::Quarantined.is_resumable());
        assert!(!ContinuityState::Promoted.is_resumable());
        assert!(!ContinuityState::RolledBack.is_resumable());
    }

    #[test]
    fn allowed_transitions_from_active() {
        for to in [
            ContinuityState::Paused, ContinuityState::Hibernated,
            ContinuityState::Checkpointed, ContinuityState::Archived,
            ContinuityState::Quarantined, ContinuityState::Promoted,
            ContinuityState::RolledBack,
        ] {
            assert!(is_allowed_transition(ContinuityState::Active, to), "Active → {to:?}");
        }
    }

    #[test]
    fn disallowed_transitions_caught() {
        // Promoted → Quarantined would skip the active intermediate.
        assert!(!is_allowed_transition(ContinuityState::Promoted, ContinuityState::Quarantined));
        // RolledBack → Hibernated must go through Active first.
        assert!(!is_allowed_transition(ContinuityState::RolledBack, ContinuityState::Hibernated));
    }

    #[test]
    fn transition_unsigned_rejected() {
        let mut r = rec();
        assert!(matches!(
            transition(&mut r, ContinuityState::Paused, None, "", "ts").unwrap_err(),
            ContinuityError::Unsigned
        ));
    }

    #[test]
    fn transition_invalid_rejected() {
        let mut r = rec();
        r.state = ContinuityState::Promoted;
        assert!(matches!(
            transition(&mut r, ContinuityState::Quarantined, None, "sig", "ts").unwrap_err(),
            ContinuityError::InvalidTransition { .. }
        ));
    }

    #[test]
    fn transition_applies_primitive_and_signature() {
        let mut r = rec();
        transition(&mut r, ContinuityState::Hibernated, Some(ContinuityPrimitive::PodmanCriu),
                   "sig-xyz", "2026-05-19T03:00:00Z").unwrap();
        assert_eq!(r.state, ContinuityState::Hibernated);
        assert_eq!(r.last_primitive, Some(ContinuityPrimitive::PodmanCriu));
        assert_eq!(r.signature, "sig-xyz");
        assert_eq!(r.last_transition_at, "2026-05-19T03:00:00Z");
    }

    #[test]
    fn six_primitives_enumerated() {
        let all = [
            ContinuityPrimitive::ZfsSnapshots, ContinuityPrimitive::PodmanCriu,
            ContinuityPrimitive::WorkflowHibernation, ContinuityPrimitive::ContextCompaction,
            ContinuityPrimitive::WarmPools, ContinuityPrimitive::SessionResume,
        ];
        assert_eq!(all.len(), 6);
    }

    #[test]
    fn continuity_state_serde_kebab() {
        assert_eq!(serde_json::to_string(&ContinuityState::Hibernated).unwrap(), "\"hibernated\"");
        assert_eq!(serde_json::to_string(&ContinuityState::RolledBack).unwrap(), "\"rolled-back\"");
        assert_eq!(serde_json::to_string(&ContinuityState::Quarantined).unwrap(), "\"quarantined\"");
    }

    #[test]
    fn continuity_primitive_serde_kebab() {
        assert_eq!(serde_json::to_string(&ContinuityPrimitive::PodmanCriu).unwrap(), "\"podman-criu\"");
        assert_eq!(serde_json::to_string(&ContinuityPrimitive::WorkflowHibernation).unwrap(), "\"workflow-hibernation\"");
        assert_eq!(serde_json::to_string(&ContinuityPrimitive::ZfsSnapshots).unwrap(), "\"zfs-snapshots\"");
    }

    #[test]
    fn session_serde_roundtrip() {
        let r = rec();
        let j = serde_json::to_string(&r).unwrap();
        let back: SessionRecord = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
