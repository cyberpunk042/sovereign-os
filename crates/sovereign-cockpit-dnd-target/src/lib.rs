//! `sovereign-cockpit-dnd-target` — drag-drop receptor registry.
//!
//! Each Target declares which ObjectKinds it accepts + an active
//! flag. dispatch_drop matches and returns the typed outcome.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Object kind (mirror of sovereign-cockpit-drag-drop).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ObjectKind {
    /// Tab.
    Tab,
    /// PinCard.
    PinCard,
    /// QuickActionSlot.
    QuickActionSlot,
    /// Bookmark.
    Bookmark,
    /// DashboardWidget.
    DashboardWidget,
}

/// One target.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Target {
    /// Stable id.
    pub id: String,
    /// Accepted kinds.
    pub accepts: Vec<ObjectKind>,
    /// Active (can receive drops)?
    pub active: bool,
}

/// Dispatch outcome.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum DropOutcome {
    /// Accepted.
    Accepted {
        /// target id.
        target_id: String,
    },
    /// Target exists but doesn't accept this kind.
    RejectedKind {
        /// target id.
        target_id: String,
        /// kind.
        offered_kind: ObjectKind,
    },
    /// Target inactive.
    Inactive {
        /// target id.
        target_id: String,
    },
    /// Unknown target.
    Unknown,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DndTargets {
    /// Schema version.
    pub schema_version: String,
    /// Targets.
    pub targets: Vec<Target>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DndError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("target id empty")]
    EmptyId,
    /// Duplicate.
    #[error("duplicate target id: {0}")]
    DuplicateId(String),
    /// Empty accepts.
    #[error("target {0} accepts empty")]
    EmptyAccepts(String),
}

impl DndTargets {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            targets: Vec::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, t: Target) -> Result<(), DndError> {
        if t.id.is_empty() {
            return Err(DndError::EmptyId);
        }
        if t.accepts.is_empty() {
            return Err(DndError::EmptyAccepts(t.id));
        }
        if self.targets.iter().any(|x| x.id == t.id) {
            return Err(DndError::DuplicateId(t.id));
        }
        self.targets.push(t);
        Ok(())
    }

    /// Dispatch drop.
    pub fn dispatch_drop(&self, source_kind: ObjectKind, target_id: &str) -> DropOutcome {
        let t = match self.targets.iter().find(|t| t.id == target_id) {
            Some(t) => t,
            None => return DropOutcome::Unknown,
        };
        if !t.active {
            return DropOutcome::Inactive {
                target_id: target_id.into(),
            };
        }
        if !t.accepts.contains(&source_kind) {
            return DropOutcome::RejectedKind {
                target_id: target_id.into(),
                offered_kind: source_kind,
            };
        }
        DropOutcome::Accepted {
            target_id: target_id.into(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DndError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DndError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.targets {
            if t.id.is_empty() {
                return Err(DndError::EmptyId);
            }
            if t.accepts.is_empty() {
                return Err(DndError::EmptyAccepts(t.id.clone()));
            }
            if !seen.insert(t.id.as_str()) {
                return Err(DndError::DuplicateId(t.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for DndTargets {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tgt(id: &str, accepts: &[ObjectKind], active: bool) -> Target {
        Target {
            id: id.into(),
            accepts: accepts.to_vec(),
            active,
        }
    }

    #[test]
    fn unknown_target() {
        let d = DndTargets::new();
        assert!(matches!(
            d.dispatch_drop(ObjectKind::Tab, "none"),
            DropOutcome::Unknown
        ));
    }

    #[test]
    fn accepted_kind() {
        let mut d = DndTargets::new();
        d.register(tgt("trash", &[ObjectKind::Tab, ObjectKind::Bookmark], true))
            .unwrap();
        let v = d.dispatch_drop(ObjectKind::Tab, "trash");
        assert!(matches!(v, DropOutcome::Accepted { .. }));
    }

    #[test]
    fn rejected_kind() {
        let mut d = DndTargets::new();
        d.register(tgt("tab-bar", &[ObjectKind::Tab], true))
            .unwrap();
        assert!(matches!(
            d.dispatch_drop(ObjectKind::PinCard, "tab-bar"),
            DropOutcome::RejectedKind { .. }
        ));
    }

    #[test]
    fn inactive_target() {
        let mut d = DndTargets::new();
        d.register(tgt("trash", &[ObjectKind::Tab], false)).unwrap();
        assert!(matches!(
            d.dispatch_drop(ObjectKind::Tab, "trash"),
            DropOutcome::Inactive { .. }
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut d = DndTargets::new();
        assert!(matches!(
            d.register(tgt("", &[ObjectKind::Tab], true)).unwrap_err(),
            DndError::EmptyId
        ));
    }

    #[test]
    fn empty_accepts_rejected() {
        let mut d = DndTargets::new();
        assert!(matches!(
            d.register(tgt("a", &[], true)).unwrap_err(),
            DndError::EmptyAccepts(_)
        ));
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut d = DndTargets::new();
        d.register(tgt("a", &[ObjectKind::Tab], true)).unwrap();
        assert!(matches!(
            d.register(tgt("a", &[ObjectKind::Tab], true)).unwrap_err(),
            DndError::DuplicateId(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DndTargets::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DndError::SchemaMismatch
        ));
    }

    #[test]
    fn outcome_serde_kebab() {
        let o = DropOutcome::Unknown;
        assert!(
            serde_json::to_string(&o)
                .unwrap()
                .contains("\"kind\":\"unknown\"")
        );
    }

    #[test]
    fn targets_serde_roundtrip() {
        let mut d = DndTargets::new();
        d.register(tgt("trash", &[ObjectKind::Tab], true)).unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: DndTargets = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
