//! `sovereign-cockpit-status-badge` — top-bar status chips.
//!
//! Operator picks which of 8 canonical badges to render + can override
//! the label. Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 8 canonical badges.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum BadgeId {
    /// Active mode (e.g. "EXECUTE").
    ActiveMode,
    /// Active profile.
    ActiveProfile,
    /// Active bundle.
    ActiveBundle,
    /// Replay session running.
    Replay,
    /// Recording.
    Recording,
    /// Dry-run.
    DryRun,
    /// Sandbox tier.
    SandboxTier,
    /// Open alerts count.
    OpenAlerts,
}

/// Per-badge preference.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BadgePref {
    /// Badge id.
    pub id: BadgeId,
    /// Operator wants this badge shown.
    pub visible: bool,
    /// Optional label override (empty = use default).
    pub label_override: String,
}

/// Preferences envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusBadgePreferences {
    /// Schema version.
    pub schema_version: String,
    /// 8 prefs.
    pub prefs: Vec<BadgePref>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BadgeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 8.
    #[error("pref count {0} != 8 canonical")]
    CountInvalid(usize),
    /// Missing.
    #[error("missing badge: {0:?}")]
    Missing(BadgeId),
    /// Label override too long (> 20).
    #[error("badge {0:?} label override length {1} > 20")]
    LabelTooLong(BadgeId, usize),
}

const REQUIRED: [BadgeId; 8] = [
    BadgeId::ActiveMode, BadgeId::ActiveProfile, BadgeId::ActiveBundle,
    BadgeId::Replay, BadgeId::Recording, BadgeId::DryRun,
    BadgeId::SandboxTier, BadgeId::OpenAlerts,
];

impl StatusBadgePreferences {
    /// Canonical defaults — mode/profile/alerts visible, rest hidden.
    pub fn canonical() -> Self {
        let prefs = REQUIRED.iter().map(|b| BadgePref {
            id: *b,
            visible: matches!(b, BadgeId::ActiveMode | BadgeId::ActiveProfile | BadgeId::OpenAlerts),
            label_override: String::new(),
        }).collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            prefs,
        }
    }

    /// Lookup.
    pub fn get(&self, id: BadgeId) -> Option<&BadgePref> {
        self.prefs.iter().find(|p| p.id == id)
    }

    /// Toggle visibility.
    pub fn set_visible(&mut self, id: BadgeId, visible: bool) -> Result<(), BadgeError> {
        let p = self.prefs.iter_mut().find(|p| p.id == id).ok_or(BadgeError::Missing(id))?;
        p.visible = visible;
        Ok(())
    }

    /// Set label override.
    pub fn set_label(&mut self, id: BadgeId, label: &str) -> Result<(), BadgeError> {
        if label.chars().count() > 20 {
            return Err(BadgeError::LabelTooLong(id, label.chars().count()));
        }
        let p = self.prefs.iter_mut().find(|p| p.id == id).ok_or(BadgeError::Missing(id))?;
        p.label_override = label.into();
        Ok(())
    }

    /// Visible badges in canonical order.
    pub fn visible(&self) -> Vec<&BadgePref> {
        let mut v: Vec<&BadgePref> = self.prefs.iter().filter(|p| p.visible).collect();
        // Stable order by canonical position.
        v.sort_by_key(|p| REQUIRED.iter().position(|x| *x == p.id).unwrap_or(usize::MAX));
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BadgeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BadgeError::SchemaMismatch);
        }
        if self.prefs.len() != 8 {
            return Err(BadgeError::CountInvalid(self.prefs.len()));
        }
        for b in REQUIRED {
            if !self.prefs.iter().any(|p| p.id == b) {
                return Err(BadgeError::Missing(b));
            }
        }
        for p in &self.prefs {
            let n = p.label_override.chars().count();
            if n > 20 {
                return Err(BadgeError::LabelTooLong(p.id, n));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        StatusBadgePreferences::canonical().validate().unwrap();
    }

    #[test]
    fn eight_badges_present() {
        let p = StatusBadgePreferences::canonical();
        for b in REQUIRED { assert!(p.get(b).is_some(), "missing {b:?}"); }
    }

    #[test]
    fn default_visibility_subset() {
        let p = StatusBadgePreferences::canonical();
        assert!(p.get(BadgeId::ActiveMode).unwrap().visible);
        assert!(p.get(BadgeId::ActiveProfile).unwrap().visible);
        assert!(p.get(BadgeId::OpenAlerts).unwrap().visible);
        assert!(!p.get(BadgeId::Replay).unwrap().visible);
        assert!(!p.get(BadgeId::Recording).unwrap().visible);
    }

    #[test]
    fn set_visible_updates() {
        let mut p = StatusBadgePreferences::canonical();
        p.set_visible(BadgeId::Replay, true).unwrap();
        assert!(p.get(BadgeId::Replay).unwrap().visible);
    }

    #[test]
    fn set_label_updates() {
        let mut p = StatusBadgePreferences::canonical();
        p.set_label(BadgeId::ActiveMode, "EXEC").unwrap();
        assert_eq!(p.get(BadgeId::ActiveMode).unwrap().label_override, "EXEC");
    }

    #[test]
    fn label_too_long_rejected() {
        let mut p = StatusBadgePreferences::canonical();
        let long = "x".repeat(21);
        assert!(matches!(p.set_label(BadgeId::ActiveMode, &long).unwrap_err(), BadgeError::LabelTooLong(_, 21)));
    }

    #[test]
    fn visible_returns_subset() {
        let p = StatusBadgePreferences::canonical();
        let v = p.visible();
        assert_eq!(v.len(), 3);
    }

    #[test]
    fn count_invalid_caught() {
        let mut p = StatusBadgePreferences::canonical();
        p.prefs.pop();
        assert!(matches!(p.validate().unwrap_err(), BadgeError::CountInvalid(7)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = StatusBadgePreferences::canonical();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), BadgeError::SchemaMismatch));
    }

    #[test]
    fn badge_serde_kebab() {
        assert_eq!(serde_json::to_string(&BadgeId::ActiveMode).unwrap(), "\"active-mode\"");
        assert_eq!(serde_json::to_string(&BadgeId::OpenAlerts).unwrap(), "\"open-alerts\"");
        assert_eq!(serde_json::to_string(&BadgeId::DryRun).unwrap(), "\"dry-run\"");
    }

    #[test]
    fn preferences_serde_roundtrip() {
        let p = StatusBadgePreferences::canonical();
        let j = serde_json::to_string(&p).unwrap();
        let back: StatusBadgePreferences = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
