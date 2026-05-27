//! `sovereign-cockpit-celebration` — milestone celebration emitter.
//!
//! `fire(scope_id, milestone_id, ts)` records a pending celebration.
//! `should_show(scope_id, milestone_id)` returns the ts when it
//! was fired (only if not yet shown). `mark_shown(scope_id,
//! milestone_id)` clears so it doesn't fire twice.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One pending celebration.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pending {
    /// Fired at.
    pub fired_at_ms: u64,
    /// Whether the chrome has shown it.
    pub shown: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Celebration {
    /// Schema version.
    pub schema_version: String,
    /// scope_id → milestone_id → pending.
    pub by_scope: BTreeMap<String, BTreeMap<String, Pending>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CelebrationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty scope.
    #[error("scope empty")]
    EmptyScope,
    /// Empty milestone.
    #[error("milestone empty")]
    EmptyMilestone,
}

impl Celebration {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            by_scope: BTreeMap::new(),
        }
    }

    /// Fire.
    pub fn fire(
        &mut self,
        scope_id: &str,
        milestone_id: &str,
        ts_ms: u64,
    ) -> Result<bool, CelebrationError> {
        if scope_id.is_empty() {
            return Err(CelebrationError::EmptyScope);
        }
        if milestone_id.is_empty() {
            return Err(CelebrationError::EmptyMilestone);
        }
        let by_milestone = self.by_scope.entry(scope_id.into()).or_default();
        if by_milestone.contains_key(milestone_id) {
            return Ok(false);
        }
        by_milestone.insert(
            milestone_id.into(),
            Pending {
                fired_at_ms: ts_ms,
                shown: false,
            },
        );
        Ok(true)
    }

    /// Should show?
    pub fn should_show(&self, scope_id: &str, milestone_id: &str) -> Option<u64> {
        self.by_scope
            .get(scope_id)?
            .get(milestone_id)
            .filter(|p| !p.shown)
            .map(|p| p.fired_at_ms)
    }

    /// Mark shown.
    pub fn mark_shown(&mut self, scope_id: &str, milestone_id: &str) -> bool {
        if let Some(m) = self.by_scope.get_mut(scope_id)
            && let Some(p) = m.get_mut(milestone_id)
        {
            p.shown = true;
            return true;
        }
        false
    }

    /// Reset (for testing / new session).
    pub fn reset(&mut self) {
        self.by_scope.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CelebrationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CelebrationError::SchemaMismatch);
        }
        for (s, m) in &self.by_scope {
            if s.is_empty() {
                return Err(CelebrationError::EmptyScope);
            }
            for id in m.keys() {
                if id.is_empty() {
                    return Err(CelebrationError::EmptyMilestone);
                }
            }
        }
        Ok(())
    }
}

impl Default for Celebration {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fire_then_show() {
        let mut c = Celebration::new();
        assert!(c.fire("onboarding", "all-done", 100).unwrap());
        assert_eq!(c.should_show("onboarding", "all-done"), Some(100));
    }

    #[test]
    fn second_fire_returns_false() {
        let mut c = Celebration::new();
        c.fire("onboarding", "all-done", 100).unwrap();
        assert!(!c.fire("onboarding", "all-done", 200).unwrap());
    }

    #[test]
    fn mark_shown_silences() {
        let mut c = Celebration::new();
        c.fire("onboarding", "all-done", 100).unwrap();
        c.mark_shown("onboarding", "all-done");
        assert!(c.should_show("onboarding", "all-done").is_none());
    }

    #[test]
    fn mark_shown_unknown_false() {
        let mut c = Celebration::new();
        assert!(!c.mark_shown("missing", "x"));
    }

    #[test]
    fn reset_clears() {
        let mut c = Celebration::new();
        c.fire("onboarding", "all-done", 100).unwrap();
        c.reset();
        assert!(c.should_show("onboarding", "all-done").is_none());
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut c = Celebration::new();
        assert!(matches!(
            c.fire("", "x", 0).unwrap_err(),
            CelebrationError::EmptyScope
        ));
        assert!(matches!(
            c.fire("s", "", 0).unwrap_err(),
            CelebrationError::EmptyMilestone
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = Celebration::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            CelebrationError::SchemaMismatch
        ));
    }

    #[test]
    fn celebration_serde_roundtrip() {
        let mut c = Celebration::new();
        c.fire("onboarding", "all-done", 100).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: Celebration = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
