//! `sovereign-cockpit-haptic-cue-policy` — haptic cues.
//!
//! Each named channel (e.g. "tap", "success", "error", "long-press")
//! has an `intensity` (Off/Light/Medium/Strong) and a per-channel
//! mute flag. The operator sets a global `master_intensity` cap;
//! the effective intensity for a cue is min(master, channel).
//!
//! `cue_for(channel)` returns the effective intensity; `Off` means
//! suppress.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Intensity tier (ordered).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Intensity {
    /// Off.
    Off,
    /// Light.
    Light,
    /// Medium.
    Medium,
    /// Strong.
    Strong,
}

/// One channel's settings.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Channel {
    /// Configured intensity.
    pub intensity: Intensity,
    /// Muted (overrides intensity).
    pub muted: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HapticCuePolicy {
    /// Schema version.
    pub schema_version: String,
    /// Global cap.
    pub master_intensity: Intensity,
    /// channel → settings.
    pub channels: BTreeMap<String, Channel>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HapticError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty channel.
    #[error("channel name empty")]
    EmptyChannel,
}

impl HapticCuePolicy {
    /// New (master Strong, no channels).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            master_intensity: Intensity::Strong,
            channels: BTreeMap::new(),
        }
    }

    /// Set master cap.
    pub fn set_master(&mut self, master_intensity: Intensity) {
        self.master_intensity = master_intensity;
    }

    /// Register / update a channel.
    pub fn set_channel(
        &mut self,
        name: &str,
        intensity: Intensity,
        muted: bool,
    ) -> Result<(), HapticError> {
        if name.is_empty() {
            return Err(HapticError::EmptyChannel);
        }
        self.channels
            .insert(name.into(), Channel { intensity, muted });
        Ok(())
    }

    /// Toggle mute.
    pub fn set_muted(&mut self, name: &str, muted: bool) -> Result<(), HapticError> {
        if name.is_empty() {
            return Err(HapticError::EmptyChannel);
        }
        let c = self.channels.entry(name.into()).or_insert(Channel {
            intensity: Intensity::Light,
            muted,
        });
        c.muted = muted;
        Ok(())
    }

    /// Effective intensity for a channel.
    pub fn cue_for(&self, name: &str) -> Intensity {
        let Some(c) = self.channels.get(name) else {
            return Intensity::Off;
        };
        if c.muted {
            return Intensity::Off;
        }
        // min(master, channel).
        if self.master_intensity < c.intensity {
            self.master_intensity
        } else {
            c.intensity
        }
    }

    /// All channels (sorted by name).
    pub fn channel_names(&self) -> Vec<String> {
        self.channels.keys().cloned().collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HapticError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HapticError::SchemaMismatch);
        }
        for k in self.channels.keys() {
            if k.is_empty() {
                return Err(HapticError::EmptyChannel);
            }
        }
        Ok(())
    }
}

impl Default for HapticCuePolicy {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unknown_channel_off() {
        let p = HapticCuePolicy::new();
        assert_eq!(p.cue_for("tap"), Intensity::Off);
    }

    #[test]
    fn channel_returns_intensity() {
        let mut p = HapticCuePolicy::new();
        p.set_channel("tap", Intensity::Light, false).unwrap();
        assert_eq!(p.cue_for("tap"), Intensity::Light);
    }

    #[test]
    fn master_caps_channel() {
        let mut p = HapticCuePolicy::new();
        p.set_master(Intensity::Light);
        p.set_channel("error", Intensity::Strong, false).unwrap();
        // Capped down to Light.
        assert_eq!(p.cue_for("error"), Intensity::Light);
    }

    #[test]
    fn mute_overrides() {
        let mut p = HapticCuePolicy::new();
        p.set_channel("tap", Intensity::Strong, true).unwrap();
        assert_eq!(p.cue_for("tap"), Intensity::Off);
    }

    #[test]
    fn master_off_silences_all() {
        let mut p = HapticCuePolicy::new();
        p.set_channel("tap", Intensity::Strong, false).unwrap();
        p.set_master(Intensity::Off);
        assert_eq!(p.cue_for("tap"), Intensity::Off);
    }

    #[test]
    fn set_muted_creates_if_missing() {
        let mut p = HapticCuePolicy::new();
        p.set_muted("tap", true).unwrap();
        assert_eq!(p.cue_for("tap"), Intensity::Off);
    }

    #[test]
    fn channel_names_sorted() {
        let mut p = HapticCuePolicy::new();
        p.set_channel("z", Intensity::Light, false).unwrap();
        p.set_channel("a", Intensity::Light, false).unwrap();
        assert_eq!(p.channel_names(), vec!["a", "z"]);
    }

    #[test]
    fn empty_channel_rejected() {
        let mut p = HapticCuePolicy::new();
        assert!(matches!(
            p.set_channel("", Intensity::Light, false).unwrap_err(),
            HapticError::EmptyChannel
        ));
        assert!(matches!(
            p.set_muted("", true).unwrap_err(),
            HapticError::EmptyChannel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = HapticCuePolicy::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            HapticError::SchemaMismatch
        ));
    }

    #[test]
    fn haptic_serde_roundtrip() {
        let mut p = HapticCuePolicy::new();
        p.set_channel("tap", Intensity::Medium, false).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: HapticCuePolicy = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
