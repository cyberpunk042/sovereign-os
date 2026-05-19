//! `sovereign-replay-playback-rate` — operator replay playback speed.
//!
//! 6 discrete rates: 0.25x / 0.5x / 1x / 2x / 4x / 8x. The cockpit
//! divides wall-time intervals between turns by this factor when
//! advancing the replay cursor. Pure UX — correctness of the replay
//! itself remains IPS-side.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 6 discrete playback rates.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PlaybackRate {
    /// 0.25x.
    Quarter,
    /// 0.5x.
    Half,
    /// 1x (default).
    Normal,
    /// 2x.
    Double,
    /// 4x.
    Quadruple,
    /// 8x.
    Octuple,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PlaybackRateState {
    /// Schema version.
    pub schema_version: String,
    /// Current rate.
    pub rate: PlaybackRate,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PlaybackError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// At extremity, cannot step further.
    #[error("cannot step further at {0:?}")]
    AtBound(PlaybackRate),
}

impl PlaybackRate {
    /// All 6.
    pub const ALL: [PlaybackRate; 6] = [
        PlaybackRate::Quarter, PlaybackRate::Half, PlaybackRate::Normal,
        PlaybackRate::Double, PlaybackRate::Quadruple, PlaybackRate::Octuple,
    ];

    /// Float multiplier.
    pub fn multiplier(self) -> f32 {
        match self {
            PlaybackRate::Quarter => 0.25,
            PlaybackRate::Half => 0.5,
            PlaybackRate::Normal => 1.0,
            PlaybackRate::Double => 2.0,
            PlaybackRate::Quadruple => 4.0,
            PlaybackRate::Octuple => 8.0,
        }
    }

    /// Next faster.
    pub fn faster(self) -> Option<PlaybackRate> {
        match self {
            PlaybackRate::Quarter => Some(PlaybackRate::Half),
            PlaybackRate::Half => Some(PlaybackRate::Normal),
            PlaybackRate::Normal => Some(PlaybackRate::Double),
            PlaybackRate::Double => Some(PlaybackRate::Quadruple),
            PlaybackRate::Quadruple => Some(PlaybackRate::Octuple),
            PlaybackRate::Octuple => None,
        }
    }

    /// Next slower.
    pub fn slower(self) -> Option<PlaybackRate> {
        match self {
            PlaybackRate::Quarter => None,
            PlaybackRate::Half => Some(PlaybackRate::Quarter),
            PlaybackRate::Normal => Some(PlaybackRate::Half),
            PlaybackRate::Double => Some(PlaybackRate::Normal),
            PlaybackRate::Quadruple => Some(PlaybackRate::Double),
            PlaybackRate::Octuple => Some(PlaybackRate::Quadruple),
        }
    }
}

impl PlaybackRateState {
    /// Default 1x.
    pub fn default_state() -> Self {
        Self { schema_version: SCHEMA_VERSION.into(), rate: PlaybackRate::Normal }
    }

    /// Step faster.
    pub fn faster(&mut self) -> Result<(), PlaybackError> {
        match self.rate.faster() {
            Some(r) => { self.rate = r; Ok(()) }
            None => Err(PlaybackError::AtBound(self.rate)),
        }
    }

    /// Step slower.
    pub fn slower(&mut self) -> Result<(), PlaybackError> {
        match self.rate.slower() {
            Some(r) => { self.rate = r; Ok(()) }
            None => Err(PlaybackError::AtBound(self.rate)),
        }
    }

    /// Reset to 1x.
    pub fn reset(&mut self) { self.rate = PlaybackRate::Normal; }

    /// Validate.
    pub fn validate(&self) -> Result<(), PlaybackError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PlaybackError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_normal() {
        assert_eq!(PlaybackRateState::default_state().rate, PlaybackRate::Normal);
    }

    #[test]
    fn multipliers_correct() {
        assert!((PlaybackRate::Quarter.multiplier() - 0.25).abs() < 1e-6);
        assert!((PlaybackRate::Normal.multiplier() - 1.0).abs() < 1e-6);
        assert!((PlaybackRate::Octuple.multiplier() - 8.0).abs() < 1e-6);
    }

    #[test]
    fn faster_walks_up() {
        let mut s = PlaybackRateState::default_state();
        s.faster().unwrap();
        assert_eq!(s.rate, PlaybackRate::Double);
        s.faster().unwrap();
        s.faster().unwrap();
        assert_eq!(s.rate, PlaybackRate::Octuple);
        assert!(s.faster().is_err());
    }

    #[test]
    fn slower_walks_down() {
        let mut s = PlaybackRateState::default_state();
        s.slower().unwrap();
        s.slower().unwrap();
        assert_eq!(s.rate, PlaybackRate::Quarter);
        assert!(s.slower().is_err());
    }

    #[test]
    fn reset_returns_to_normal() {
        let mut s = PlaybackRateState::default_state();
        s.faster().unwrap();
        s.reset();
        assert_eq!(s.rate, PlaybackRate::Normal);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = PlaybackRateState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), PlaybackError::SchemaMismatch));
    }

    #[test]
    fn rate_serde_kebab() {
        assert_eq!(serde_json::to_string(&PlaybackRate::Normal).unwrap(), "\"normal\"");
        assert_eq!(serde_json::to_string(&PlaybackRate::Quadruple).unwrap(), "\"quadruple\"");
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = PlaybackRateState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: PlaybackRateState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
