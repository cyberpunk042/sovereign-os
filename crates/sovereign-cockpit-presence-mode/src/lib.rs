//! `sovereign-cockpit-presence-mode` — operator presence/attention modes.
//!
//! Modes:
//!   * `Focus` — only Error severity shows; rest summarized.
//!   * `Standard` — all events shown.
//!   * `Glance` — Warn+Error shown, Info summarized, low-cadence refresh.
//!   * `Off` — UI parked; nothing shown.
//!   * `DoNotDisturb` — everything suppressed (counted, not delivered).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Presence mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Deep focus.
    Focus,
    /// Default work mode.
    Standard,
    /// Casual passive glance.
    Glance,
    /// UI parked.
    Off,
    /// Suppress everything.
    DoNotDisturb,
}

/// Severity (mirrored).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Info.
    Info,
    /// Success.
    Success,
    /// Warn.
    Warn,
    /// Error.
    Error,
}

/// Refresh cadence (mirrored to whatever the renderer uses).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Cadence {
    /// High (≤ 1 Hz cap removed).
    High,
    /// Medium.
    Medium,
    /// Low.
    Low,
    /// Paused.
    Paused,
}

/// Per-event decision.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EventAction {
    /// Show normally.
    Show,
    /// Summarize (badge, no row).
    Summarize,
    /// Suppress.
    Suppress,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PresenceMode {
    /// Schema version.
    pub schema_version: String,
    /// Current mode.
    pub mode: Mode,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PresenceError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl PresenceMode {
    /// New (Standard by default).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: Mode::Standard,
        }
    }

    /// Set.
    pub fn set(&mut self, mode: Mode) {
        self.mode = mode;
    }

    /// Cadence for current mode.
    pub fn cadence(&self) -> Cadence {
        match self.mode {
            Mode::Focus => Cadence::Low,
            Mode::Standard => Cadence::High,
            Mode::Glance => Cadence::Low,
            Mode::Off => Cadence::Paused,
            Mode::DoNotDisturb => Cadence::Paused,
        }
    }

    /// Are animations allowed?
    pub fn animations(&self) -> bool {
        matches!(self.mode, Mode::Standard | Mode::Glance)
    }

    /// Classify an event of given severity.
    pub fn classify_event(&self, sev: Severity) -> EventAction {
        match self.mode {
            Mode::Off | Mode::DoNotDisturb => EventAction::Suppress,
            Mode::Focus => match sev {
                Severity::Error => EventAction::Show,
                _ => EventAction::Summarize,
            },
            Mode::Glance => match sev {
                Severity::Warn | Severity::Error => EventAction::Show,
                Severity::Info | Severity::Success => EventAction::Summarize,
            },
            Mode::Standard => EventAction::Show,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PresenceError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PresenceError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for PresenceMode {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_standard() {
        let p = PresenceMode::new();
        assert_eq!(p.mode, Mode::Standard);
        assert_eq!(p.cadence(), Cadence::High);
        assert!(p.animations());
    }

    #[test]
    fn focus_only_errors_show() {
        let mut p = PresenceMode::new();
        p.set(Mode::Focus);
        assert_eq!(p.classify_event(Severity::Error), EventAction::Show);
        assert_eq!(p.classify_event(Severity::Warn), EventAction::Summarize);
        assert_eq!(p.classify_event(Severity::Info), EventAction::Summarize);
    }

    #[test]
    fn glance_summarizes_info() {
        let mut p = PresenceMode::new();
        p.set(Mode::Glance);
        assert_eq!(p.classify_event(Severity::Warn), EventAction::Show);
        assert_eq!(p.classify_event(Severity::Info), EventAction::Summarize);
    }

    #[test]
    fn off_suppresses_all() {
        let mut p = PresenceMode::new();
        p.set(Mode::Off);
        assert_eq!(p.classify_event(Severity::Error), EventAction::Suppress);
        assert_eq!(p.cadence(), Cadence::Paused);
        assert!(!p.animations());
    }

    #[test]
    fn dnd_suppresses_all() {
        let mut p = PresenceMode::new();
        p.set(Mode::DoNotDisturb);
        assert_eq!(p.classify_event(Severity::Error), EventAction::Suppress);
        assert_eq!(p.cadence(), Cadence::Paused);
    }

    #[test]
    fn focus_low_cadence() {
        let mut p = PresenceMode::new();
        p.set(Mode::Focus);
        assert_eq!(p.cadence(), Cadence::Low);
    }

    #[test]
    fn focus_no_animations() {
        let mut p = PresenceMode::new();
        p.set(Mode::Focus);
        assert!(!p.animations());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = PresenceMode::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PresenceError::SchemaMismatch
        ));
    }

    #[test]
    fn presence_serde_roundtrip() {
        let mut p = PresenceMode::new();
        p.set(Mode::DoNotDisturb);
        let j = serde_json::to_string(&p).unwrap();
        let back: PresenceMode = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
