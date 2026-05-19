//! `sovereign-cockpit-sound-preferences` — operator notification sound prefs.
//!
//! Per `BannerSeverity` (Calm / Notice / Warn / Critical), operator
//! picks a sound (None / Soft / Standard / Sharp / Alarm) and a master
//! volume (0..=100). Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_cockpit_banner_state::BannerSeverity;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 5 sound choices.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Sound {
    /// Silent.
    None,
    /// Soft chime.
    Soft,
    /// Standard tone.
    Standard,
    /// Sharp ping.
    Sharp,
    /// Loud alarm.
    Alarm,
}

/// Per-severity entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SeveritySound {
    /// Severity.
    pub severity: BannerSeverity,
    /// Sound choice.
    pub sound: Sound,
}

/// Preferences envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SoundPreferences {
    /// Schema version.
    pub schema_version: String,
    /// Master volume 0..=100.
    pub master_volume: u8,
    /// Per-severity choices (exactly 4 entries).
    pub mappings: Vec<SeveritySound>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SoundError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Volume out of range.
    #[error("master_volume {0} > 100")]
    VolumeOutOfRange(u8),
    /// Count != 4.
    #[error("mapping count {0} != 4 canonical")]
    CountInvalid(usize),
    /// Missing severity mapping.
    #[error("missing severity: {0:?}")]
    Missing(BannerSeverity),
}

const REQUIRED: [BannerSeverity; 4] = [
    BannerSeverity::Calm,
    BannerSeverity::Notice,
    BannerSeverity::Warn,
    BannerSeverity::Critical,
];

impl SoundPreferences {
    /// Canonical defaults.
    pub fn canonical() -> Self {
        let mappings = vec![
            SeveritySound { severity: BannerSeverity::Calm,     sound: Sound::None },
            SeveritySound { severity: BannerSeverity::Notice,   sound: Sound::Soft },
            SeveritySound { severity: BannerSeverity::Warn,     sound: Sound::Standard },
            SeveritySound { severity: BannerSeverity::Critical, sound: Sound::Sharp },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            master_volume: 70,
            mappings,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SoundError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SoundError::SchemaMismatch);
        }
        if self.master_volume > 100 {
            return Err(SoundError::VolumeOutOfRange(self.master_volume));
        }
        if self.mappings.len() != 4 {
            return Err(SoundError::CountInvalid(self.mappings.len()));
        }
        for s in REQUIRED {
            if !self.mappings.iter().any(|m| m.severity == s) {
                return Err(SoundError::Missing(s));
            }
        }
        Ok(())
    }

    /// Sound for a severity.
    pub fn sound_for(&self, sev: BannerSeverity) -> Sound {
        self.mappings.iter().find(|m| m.severity == sev)
            .map(|m| m.sound)
            .unwrap_or(Sound::None)
    }

    /// Set master volume; clamps to 100.
    pub fn set_volume(&mut self, vol: u8) -> u8 {
        self.master_volume = vol.min(100);
        self.master_volume
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        SoundPreferences::canonical().validate().unwrap();
    }

    #[test]
    fn sound_for_calm_is_none() {
        let p = SoundPreferences::canonical();
        assert_eq!(p.sound_for(BannerSeverity::Calm), Sound::None);
    }

    #[test]
    fn critical_uses_sharp() {
        let p = SoundPreferences::canonical();
        assert_eq!(p.sound_for(BannerSeverity::Critical), Sound::Sharp);
    }

    #[test]
    fn set_volume_clamps_to_100() {
        let mut p = SoundPreferences::canonical();
        let new = p.set_volume(200);
        assert_eq!(new, 100);
        assert_eq!(p.master_volume, 100);
    }

    #[test]
    fn volume_out_of_range_caught_in_validate() {
        let mut p = SoundPreferences::canonical();
        p.master_volume = 200;
        assert!(matches!(p.validate().unwrap_err(), SoundError::VolumeOutOfRange(200)));
    }

    #[test]
    fn count_invalid_caught() {
        let mut p = SoundPreferences::canonical();
        p.mappings.pop();
        assert!(matches!(p.validate().unwrap_err(), SoundError::CountInvalid(3)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = SoundPreferences::canonical();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), SoundError::SchemaMismatch));
    }

    #[test]
    fn sound_serde_kebab() {
        assert_eq!(serde_json::to_string(&Sound::Soft).unwrap(), "\"soft\"");
        assert_eq!(serde_json::to_string(&Sound::Sharp).unwrap(), "\"sharp\"");
        assert_eq!(serde_json::to_string(&Sound::Alarm).unwrap(), "\"alarm\"");
    }

    #[test]
    fn preferences_serde_roundtrip() {
        let p = SoundPreferences::canonical();
        let j = serde_json::to_string(&p).unwrap();
        let back: SoundPreferences = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
