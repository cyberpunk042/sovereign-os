//! `sovereign-cockpit-update-prompt` — app-update UX.
//!
//! current_version, available_version (free-form strings).
//! announce(available, now) records snooze=0. snooze(now,
//! snooze_ms) hides until now+snooze_ms. install marks
//! installed (current=available). should_show(now) iff
//! available > current AND past snooze_until_ms.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UpdatePrompt {
    /// Schema version.
    pub schema_version: String,
    /// Current installed version.
    pub current_version: String,
    /// Available version (None when none).
    pub available_version: Option<String>,
    /// Hidden until this ts ms.
    pub snooze_until_ms: u64,
    /// Snoozes recorded.
    pub snoozes: u64,
    /// Installs recorded.
    pub installs: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum UpdateError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("version empty")]
    EmptyVersion,
    /// Nothing available.
    #[error("no update available")]
    NoneAvailable,
}

impl UpdatePrompt {
    /// New.
    pub fn new(current_version: &str) -> Result<Self, UpdateError> {
        if current_version.is_empty() {
            return Err(UpdateError::EmptyVersion);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            current_version: current_version.into(),
            available_version: None,
            snooze_until_ms: 0,
            snoozes: 0,
            installs: 0,
        })
    }

    /// Announce an available version.
    pub fn announce(&mut self, available: &str) -> Result<(), UpdateError> {
        if available.is_empty() {
            return Err(UpdateError::EmptyVersion);
        }
        if available != self.current_version {
            self.available_version = Some(available.into());
            self.snooze_until_ms = 0;
        } else {
            self.available_version = None;
        }
        Ok(())
    }

    /// Should the prompt be shown?
    pub fn should_show(&self, now_ms: u64) -> bool {
        self.available_version.is_some() && now_ms >= self.snooze_until_ms
    }

    /// Snooze for N ms.
    pub fn snooze(&mut self, now_ms: u64, snooze_ms: u64) -> Result<(), UpdateError> {
        if self.available_version.is_none() {
            return Err(UpdateError::NoneAvailable);
        }
        self.snooze_until_ms = now_ms.saturating_add(snooze_ms);
        self.snoozes = self.snoozes.saturating_add(1);
        Ok(())
    }

    /// Mark installed (current = available; clears available).
    pub fn install(&mut self) -> Result<(), UpdateError> {
        let v = self
            .available_version
            .take()
            .ok_or(UpdateError::NoneAvailable)?;
        self.current_version = v;
        self.snooze_until_ms = 0;
        self.installs = self.installs.saturating_add(1);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), UpdateError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(UpdateError::SchemaMismatch);
        }
        if self.current_version.is_empty() {
            return Err(UpdateError::EmptyVersion);
        }
        if let Some(v) = &self.available_version
            && v.is_empty()
        {
            return Err(UpdateError::EmptyVersion);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_update_initially() {
        let p = UpdatePrompt::new("1.0.0").unwrap();
        assert!(!p.should_show(0));
    }

    #[test]
    fn announce_shows() {
        let mut p = UpdatePrompt::new("1.0.0").unwrap();
        p.announce("1.1.0").unwrap();
        assert!(p.should_show(0));
    }

    #[test]
    fn snooze_hides_temporarily() {
        let mut p = UpdatePrompt::new("1.0.0").unwrap();
        p.announce("1.1.0").unwrap();
        p.snooze(0, 1000).unwrap();
        assert!(!p.should_show(500));
        assert!(p.should_show(1500));
    }

    #[test]
    fn install_updates_current() {
        let mut p = UpdatePrompt::new("1.0.0").unwrap();
        p.announce("1.1.0").unwrap();
        p.install().unwrap();
        assert_eq!(p.current_version, "1.1.0");
        assert!(p.available_version.is_none());
        assert!(!p.should_show(0));
    }

    #[test]
    fn announce_same_version_clears() {
        let mut p = UpdatePrompt::new("1.0.0").unwrap();
        p.announce("1.0.0").unwrap();
        assert!(p.available_version.is_none());
    }

    #[test]
    fn snooze_without_announce_rejected() {
        let mut p = UpdatePrompt::new("1.0.0").unwrap();
        assert!(matches!(
            p.snooze(0, 100).unwrap_err(),
            UpdateError::NoneAvailable
        ));
    }

    #[test]
    fn install_without_announce_rejected() {
        let mut p = UpdatePrompt::new("1.0.0").unwrap();
        assert!(matches!(
            p.install().unwrap_err(),
            UpdateError::NoneAvailable
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        assert!(matches!(
            UpdatePrompt::new("").unwrap_err(),
            UpdateError::EmptyVersion
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = UpdatePrompt::new("1.0.0").unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            UpdateError::SchemaMismatch
        ));
    }

    #[test]
    fn prompt_serde_roundtrip() {
        let mut p = UpdatePrompt::new("1.0.0").unwrap();
        p.announce("1.1.0").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: UpdatePrompt = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
