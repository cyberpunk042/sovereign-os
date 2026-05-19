//! `sovereign-cockpit-zoom-level` — operator-selectable zoom factor.
//!
//! 5 discrete levels: 75 / 100 / 125 / 150 / 200 (percent). The cockpit
//! multiplies typography + widget pixel dimensions by the level's
//! factor (1.0 = 100%, etc.). Pure visual.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 5 discrete zoom levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ZoomLevel {
    /// 75%.
    Pct75,
    /// 100% (default).
    Pct100,
    /// 125%.
    Pct125,
    /// 150%.
    Pct150,
    /// 200%.
    Pct200,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ZoomState {
    /// Schema version.
    pub schema_version: String,
    /// Current level.
    pub level: ZoomLevel,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ZoomError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Out of range.
    #[error("cannot zoom further: at {0:?}")]
    AtBound(ZoomLevel),
}

impl ZoomLevel {
    /// All 5.
    pub const ALL: [ZoomLevel; 5] = [
        ZoomLevel::Pct75, ZoomLevel::Pct100, ZoomLevel::Pct125,
        ZoomLevel::Pct150, ZoomLevel::Pct200,
    ];

    /// Percent integer.
    pub fn percent(self) -> u16 {
        match self {
            ZoomLevel::Pct75 => 75,
            ZoomLevel::Pct100 => 100,
            ZoomLevel::Pct125 => 125,
            ZoomLevel::Pct150 => 150,
            ZoomLevel::Pct200 => 200,
        }
    }

    /// Float factor (1.0 = 100%).
    pub fn factor(self) -> f32 {
        self.percent() as f32 / 100.0
    }

    /// Next level up. `None` if at the top.
    pub fn next_up(self) -> Option<ZoomLevel> {
        match self {
            ZoomLevel::Pct75 => Some(ZoomLevel::Pct100),
            ZoomLevel::Pct100 => Some(ZoomLevel::Pct125),
            ZoomLevel::Pct125 => Some(ZoomLevel::Pct150),
            ZoomLevel::Pct150 => Some(ZoomLevel::Pct200),
            ZoomLevel::Pct200 => None,
        }
    }

    /// Next level down. `None` if at the bottom.
    pub fn next_down(self) -> Option<ZoomLevel> {
        match self {
            ZoomLevel::Pct75 => None,
            ZoomLevel::Pct100 => Some(ZoomLevel::Pct75),
            ZoomLevel::Pct125 => Some(ZoomLevel::Pct100),
            ZoomLevel::Pct150 => Some(ZoomLevel::Pct125),
            ZoomLevel::Pct200 => Some(ZoomLevel::Pct150),
        }
    }
}

impl ZoomState {
    /// Default 100%.
    pub fn default_state() -> Self {
        Self { schema_version: SCHEMA_VERSION.into(), level: ZoomLevel::Pct100 }
    }

    /// Zoom in one step.
    pub fn zoom_in(&mut self) -> Result<(), ZoomError> {
        match self.level.next_up() {
            Some(l) => { self.level = l; Ok(()) }
            None => Err(ZoomError::AtBound(self.level)),
        }
    }

    /// Zoom out one step.
    pub fn zoom_out(&mut self) -> Result<(), ZoomError> {
        match self.level.next_down() {
            Some(l) => { self.level = l; Ok(()) }
            None => Err(ZoomError::AtBound(self.level)),
        }
    }

    /// Reset to 100%.
    pub fn reset(&mut self) { self.level = ZoomLevel::Pct100; }

    /// Validate.
    pub fn validate(&self) -> Result<(), ZoomError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ZoomError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_100() {
        assert_eq!(ZoomState::default_state().level, ZoomLevel::Pct100);
    }

    #[test]
    fn percent_progression() {
        assert_eq!(ZoomLevel::Pct75.percent(), 75);
        assert_eq!(ZoomLevel::Pct100.percent(), 100);
        assert_eq!(ZoomLevel::Pct200.percent(), 200);
    }

    #[test]
    fn factor_progression() {
        assert!((ZoomLevel::Pct100.factor() - 1.0).abs() < 0.001);
        assert!((ZoomLevel::Pct200.factor() - 2.0).abs() < 0.001);
    }

    #[test]
    fn zoom_in_walks_up() {
        let mut s = ZoomState::default_state();
        s.zoom_in().unwrap();
        assert_eq!(s.level, ZoomLevel::Pct125);
        s.zoom_in().unwrap();
        s.zoom_in().unwrap();
        // At 200% now
        assert_eq!(s.level, ZoomLevel::Pct200);
        assert!(s.zoom_in().is_err());
    }

    #[test]
    fn zoom_out_walks_down() {
        let mut s = ZoomState::default_state();
        s.zoom_out().unwrap();
        assert_eq!(s.level, ZoomLevel::Pct75);
        assert!(s.zoom_out().is_err());
    }

    #[test]
    fn reset_returns_to_100() {
        let mut s = ZoomState::default_state();
        s.zoom_in().unwrap();
        s.zoom_in().unwrap();
        s.reset();
        assert_eq!(s.level, ZoomLevel::Pct100);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ZoomState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), ZoomError::SchemaMismatch));
    }

    #[test]
    fn level_serde_kebab() {
        assert_eq!(serde_json::to_string(&ZoomLevel::Pct75).unwrap(), "\"pct75\"");
        assert_eq!(serde_json::to_string(&ZoomLevel::Pct200).unwrap(), "\"pct200\"");
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = ZoomState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: ZoomState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
