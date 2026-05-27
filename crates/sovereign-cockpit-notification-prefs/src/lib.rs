//! `sovereign-cockpit-notification-prefs` — notification prefs.
//!
//! Per channel (e.g. "email", "desktop", "mobile"), an `enabled`
//! flag + min severity. Global DND window [dnd_start_ms,
//! dnd_end_ms) blanks everything when active. `should_deliver(
//! channel, severity, now)` answers.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity (ordered).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Info.
    Info,
    /// Notice.
    Notice,
    /// Warn.
    Warn,
    /// Error.
    Error,
    /// Critical.
    Critical,
}

/// Per-channel.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChannelPrefs {
    /// Enabled?
    pub enabled: bool,
    /// Minimum severity.
    pub min_severity: Severity,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct NotificationPrefs {
    /// Schema version.
    pub schema_version: String,
    /// channel → prefs.
    pub channels: BTreeMap<String, ChannelPrefs>,
    /// DND start (None = no DND).
    pub dnd_start_ms: Option<u64>,
    /// DND end.
    pub dnd_end_ms: Option<u64>,
    /// Critical bypasses DND.
    pub critical_bypasses_dnd: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PrefsError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("channel name empty")]
    EmptyChannel,
    /// Inverted DND.
    #[error("dnd_start ({s}) >= dnd_end ({e})")]
    InvertedDnd {
        /// s.
        s: u64,
        /// e.
        e: u64,
    },
}

impl NotificationPrefs {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            channels: BTreeMap::new(),
            dnd_start_ms: None,
            dnd_end_ms: None,
            critical_bypasses_dnd: true,
        }
    }

    /// Set channel.
    pub fn set_channel(
        &mut self,
        name: &str,
        enabled: bool,
        min_severity: Severity,
    ) -> Result<(), PrefsError> {
        if name.is_empty() {
            return Err(PrefsError::EmptyChannel);
        }
        self.channels.insert(
            name.into(),
            ChannelPrefs {
                enabled,
                min_severity,
            },
        );
        Ok(())
    }

    /// Set DND.
    pub fn set_dnd(&mut self, start_ms: u64, end_ms: u64) -> Result<(), PrefsError> {
        if start_ms >= end_ms {
            return Err(PrefsError::InvertedDnd {
                s: start_ms,
                e: end_ms,
            });
        }
        self.dnd_start_ms = Some(start_ms);
        self.dnd_end_ms = Some(end_ms);
        Ok(())
    }

    /// Clear DND.
    pub fn clear_dnd(&mut self) {
        self.dnd_start_ms = None;
        self.dnd_end_ms = None;
    }

    /// In DND window?
    pub fn in_dnd(&self, now_ms: u64) -> bool {
        match (self.dnd_start_ms, self.dnd_end_ms) {
            (Some(s), Some(e)) => now_ms >= s && now_ms < e,
            _ => false,
        }
    }

    /// Should deliver?
    pub fn should_deliver(&self, channel: &str, severity: Severity, now_ms: u64) -> bool {
        let in_dnd = self.in_dnd(now_ms);
        if in_dnd && !(self.critical_bypasses_dnd && severity == Severity::Critical) {
            return false;
        }
        let Some(c) = self.channels.get(channel) else {
            return false;
        };
        c.enabled && severity >= c.min_severity
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PrefsError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PrefsError::SchemaMismatch);
        }
        for k in self.channels.keys() {
            if k.is_empty() {
                return Err(PrefsError::EmptyChannel);
            }
        }
        if let (Some(s), Some(e)) = (self.dnd_start_ms, self.dnd_end_ms)
            && s >= e
        {
            return Err(PrefsError::InvertedDnd { s, e });
        }
        Ok(())
    }
}

impl Default for NotificationPrefs {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enabled_channel_delivers_at_or_above_min() {
        let mut p = NotificationPrefs::new();
        p.set_channel("desktop", true, Severity::Warn).unwrap();
        assert!(!p.should_deliver("desktop", Severity::Info, 0));
        assert!(p.should_deliver("desktop", Severity::Warn, 0));
        assert!(p.should_deliver("desktop", Severity::Critical, 0));
    }

    #[test]
    fn disabled_channel_blocks() {
        let mut p = NotificationPrefs::new();
        p.set_channel("desktop", false, Severity::Info).unwrap();
        assert!(!p.should_deliver("desktop", Severity::Critical, 0));
    }

    #[test]
    fn unknown_channel_blocks() {
        let p = NotificationPrefs::new();
        assert!(!p.should_deliver("nope", Severity::Critical, 0));
    }

    #[test]
    fn dnd_blocks_non_critical() {
        let mut p = NotificationPrefs::new();
        p.set_channel("desktop", true, Severity::Info).unwrap();
        p.set_dnd(1000, 2000).unwrap();
        assert!(!p.should_deliver("desktop", Severity::Warn, 1500));
        // Critical bypasses.
        assert!(p.should_deliver("desktop", Severity::Critical, 1500));
    }

    #[test]
    fn critical_bypass_off() {
        let mut p = NotificationPrefs::new();
        p.set_channel("desktop", true, Severity::Info).unwrap();
        p.set_dnd(1000, 2000).unwrap();
        p.critical_bypasses_dnd = false;
        assert!(!p.should_deliver("desktop", Severity::Critical, 1500));
    }

    #[test]
    fn outside_dnd_delivers() {
        let mut p = NotificationPrefs::new();
        p.set_channel("desktop", true, Severity::Info).unwrap();
        p.set_dnd(1000, 2000).unwrap();
        assert!(p.should_deliver("desktop", Severity::Warn, 500));
    }

    #[test]
    fn clear_dnd() {
        let mut p = NotificationPrefs::new();
        p.set_dnd(1000, 2000).unwrap();
        p.clear_dnd();
        assert!(!p.in_dnd(1500));
    }

    #[test]
    fn inverted_dnd_rejected() {
        let mut p = NotificationPrefs::new();
        assert!(matches!(
            p.set_dnd(2000, 1000).unwrap_err(),
            PrefsError::InvertedDnd { .. }
        ));
    }

    #[test]
    fn empty_channel_rejected() {
        let mut p = NotificationPrefs::new();
        assert!(matches!(
            p.set_channel("", true, Severity::Info).unwrap_err(),
            PrefsError::EmptyChannel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = NotificationPrefs::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PrefsError::SchemaMismatch
        ));
    }

    #[test]
    fn prefs_serde_roundtrip() {
        let mut p = NotificationPrefs::new();
        p.set_channel("desktop", true, Severity::Warn).unwrap();
        p.set_dnd(1000, 2000).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: NotificationPrefs = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
