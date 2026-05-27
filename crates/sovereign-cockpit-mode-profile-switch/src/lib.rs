//! `sovereign-cockpit-mode-profile-switch` — mode/profile switch.
//!
//! Registered profiles by id + label. switch(id, ts) sets active
//! and appends to history (bounded). previous() returns most recent
//! prior profile (for "go back" UX).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, VecDeque};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One profile.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Profile {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
}

/// Switch event.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Switch {
    /// Profile id.
    pub to: String,
    /// Ts.
    pub ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModeProfileSwitch {
    /// Schema version.
    pub schema_version: String,
    /// id → profile.
    pub profiles: BTreeMap<String, Profile>,
    /// Active id.
    pub active: Option<String>,
    /// History capacity.
    pub history_capacity: usize,
    /// History (newest at back).
    pub history: VecDeque<Switch>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SwitchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate profile: {0}")]
    DuplicateProfile(String),
    /// Unknown.
    #[error("unknown profile: {0}")]
    UnknownProfile(String),
    /// Zero capacity.
    #[error("history_capacity must be > 0")]
    ZeroCapacity,
}

impl ModeProfileSwitch {
    /// New.
    pub fn new(history_capacity: usize) -> Result<Self, SwitchError> {
        if history_capacity == 0 {
            return Err(SwitchError::ZeroCapacity);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            profiles: BTreeMap::new(),
            active: None,
            history_capacity,
            history: VecDeque::with_capacity(history_capacity),
        })
    }

    /// Register.
    pub fn register(&mut self, id: &str, label: &str) -> Result<(), SwitchError> {
        if id.is_empty() {
            return Err(SwitchError::EmptyId);
        }
        if label.is_empty() {
            return Err(SwitchError::EmptyLabel);
        }
        if self.profiles.contains_key(id) {
            return Err(SwitchError::DuplicateProfile(id.into()));
        }
        self.profiles.insert(
            id.into(),
            Profile {
                id: id.into(),
                label: label.into(),
            },
        );
        Ok(())
    }

    /// Switch.
    pub fn switch(&mut self, id: &str, ts_ms: u64) -> Result<(), SwitchError> {
        if !self.profiles.contains_key(id) {
            return Err(SwitchError::UnknownProfile(id.into()));
        }
        self.active = Some(id.into());
        if self.history.len() == self.history_capacity {
            self.history.pop_front();
        }
        self.history.push_back(Switch {
            to: id.into(),
            ts_ms,
        });
        Ok(())
    }

    /// Previous profile (just before active).
    pub fn previous(&self) -> Option<String> {
        // Need the entry before the last (the active).
        let n = self.history.len();
        if n < 2 {
            return None;
        }
        self.history.get(n - 2).map(|s| s.to.clone())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SwitchError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SwitchError::SchemaMismatch);
        }
        if self.history_capacity == 0 {
            return Err(SwitchError::ZeroCapacity);
        }
        for (id, p) in &self.profiles {
            if id.is_empty() {
                return Err(SwitchError::EmptyId);
            }
            if p.label.is_empty() {
                return Err(SwitchError::EmptyLabel);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_and_switch() {
        let mut m = ModeProfileSwitch::new(10).unwrap();
        m.register("dev", "Developer").unwrap();
        m.switch("dev", 0).unwrap();
        assert_eq!(m.active.as_deref(), Some("dev"));
    }

    #[test]
    fn previous_returns_prior() {
        let mut m = ModeProfileSwitch::new(10).unwrap();
        m.register("a", "A").unwrap();
        m.register("b", "B").unwrap();
        m.switch("a", 0).unwrap();
        m.switch("b", 100).unwrap();
        assert_eq!(m.previous().as_deref(), Some("a"));
    }

    #[test]
    fn previous_none_at_start() {
        let mut m = ModeProfileSwitch::new(10).unwrap();
        m.register("a", "A").unwrap();
        m.switch("a", 0).unwrap();
        assert!(m.previous().is_none());
    }

    #[test]
    fn history_capacity_drops_oldest() {
        let mut m = ModeProfileSwitch::new(2).unwrap();
        m.register("a", "A").unwrap();
        m.register("b", "B").unwrap();
        m.register("c", "C").unwrap();
        m.switch("a", 0).unwrap();
        m.switch("b", 1).unwrap();
        m.switch("c", 2).unwrap();
        assert_eq!(m.history.len(), 2);
    }

    #[test]
    fn unknown_switch_rejected() {
        let mut m = ModeProfileSwitch::new(10).unwrap();
        assert!(matches!(
            m.switch("nope", 0).unwrap_err(),
            SwitchError::UnknownProfile(_)
        ));
    }

    #[test]
    fn duplicate_register_rejected() {
        let mut m = ModeProfileSwitch::new(10).unwrap();
        m.register("a", "A").unwrap();
        assert!(matches!(
            m.register("a", "A").unwrap_err(),
            SwitchError::DuplicateProfile(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut m = ModeProfileSwitch::new(10).unwrap();
        assert!(matches!(
            m.register("", "A").unwrap_err(),
            SwitchError::EmptyId
        ));
        assert!(matches!(
            m.register("a", "").unwrap_err(),
            SwitchError::EmptyLabel
        ));
    }

    #[test]
    fn zero_capacity_rejected() {
        assert!(matches!(
            ModeProfileSwitch::new(0).unwrap_err(),
            SwitchError::ZeroCapacity
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = ModeProfileSwitch::new(10).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            SwitchError::SchemaMismatch
        ));
    }

    #[test]
    fn switch_serde_roundtrip() {
        let mut m = ModeProfileSwitch::new(10).unwrap();
        m.register("a", "A").unwrap();
        m.switch("a", 0).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: ModeProfileSwitch = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
