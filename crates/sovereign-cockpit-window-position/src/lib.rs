//! `sovereign-cockpit-window-position` — operator window placement.
//!
//! Persisted on close, restored on launch. Tracks (x, y, w, h,
//! monitor_id, maximized, fullscreen). Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Minimum window dimensions.
pub const MIN_W: u32 = 640;
/// Minimum height.
pub const MIN_H: u32 = 400;

/// Window position.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WindowPosition {
    /// Schema version.
    pub schema_version: String,
    /// X coordinate.
    pub x: i32,
    /// Y coordinate.
    pub y: i32,
    /// Width.
    pub width: u32,
    /// Height.
    pub height: u32,
    /// Monitor id (operator label).
    pub monitor_id: String,
    /// Maximized.
    pub maximized: bool,
    /// Fullscreen.
    pub fullscreen: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum WindowPositionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Width too small.
    #[error("width {0} < {MIN_W}")]
    WidthTooSmall(u32),
    /// Height too small.
    #[error("height {0} < {MIN_H}")]
    HeightTooSmall(u32),
    /// Empty monitor_id.
    #[error("monitor_id empty")]
    EmptyMonitor,
    /// Both maximized AND fullscreen set.
    #[error("maximized and fullscreen both true")]
    ConflictingFlags,
}

impl WindowPosition {
    /// Default state — 1280x800 on "primary".
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            x: 100,
            y: 100,
            width: 1280,
            height: 800,
            monitor_id: "primary".into(),
            maximized: false,
            fullscreen: false,
        }
    }

    /// Maximize.
    pub fn maximize(&mut self) {
        self.maximized = true;
        self.fullscreen = false;
    }

    /// Fullscreen.
    pub fn fullscreen(&mut self) {
        self.fullscreen = true;
        self.maximized = false;
    }

    /// Restore (clear maximized + fullscreen).
    pub fn restore(&mut self) {
        self.maximized = false;
        self.fullscreen = false;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), WindowPositionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(WindowPositionError::SchemaMismatch);
        }
        if self.width < MIN_W {
            return Err(WindowPositionError::WidthTooSmall(self.width));
        }
        if self.height < MIN_H {
            return Err(WindowPositionError::HeightTooSmall(self.height));
        }
        if self.monitor_id.is_empty() {
            return Err(WindowPositionError::EmptyMonitor);
        }
        if self.maximized && self.fullscreen {
            return Err(WindowPositionError::ConflictingFlags);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        WindowPosition::default_state().validate().unwrap();
    }

    #[test]
    fn width_too_small_rejected() {
        let mut p = WindowPosition::default_state();
        p.width = 100;
        assert!(matches!(
            p.validate().unwrap_err(),
            WindowPositionError::WidthTooSmall(100)
        ));
    }

    #[test]
    fn height_too_small_rejected() {
        let mut p = WindowPosition::default_state();
        p.height = 100;
        assert!(matches!(
            p.validate().unwrap_err(),
            WindowPositionError::HeightTooSmall(100)
        ));
    }

    #[test]
    fn empty_monitor_rejected() {
        let mut p = WindowPosition::default_state();
        p.monitor_id = String::new();
        assert!(matches!(
            p.validate().unwrap_err(),
            WindowPositionError::EmptyMonitor
        ));
    }

    #[test]
    fn maximize_sets_correctly() {
        let mut p = WindowPosition::default_state();
        p.maximize();
        assert!(p.maximized);
        assert!(!p.fullscreen);
    }

    #[test]
    fn fullscreen_clears_maximized() {
        let mut p = WindowPosition::default_state();
        p.maximize();
        p.fullscreen();
        assert!(p.fullscreen);
        assert!(!p.maximized);
    }

    #[test]
    fn restore_clears_both() {
        let mut p = WindowPosition::default_state();
        p.maximize();
        p.restore();
        assert!(!p.maximized);
        assert!(!p.fullscreen);
    }

    #[test]
    fn conflicting_flags_caught_in_validate() {
        let mut p = WindowPosition::default_state();
        p.maximized = true;
        p.fullscreen = true;
        assert!(matches!(
            p.validate().unwrap_err(),
            WindowPositionError::ConflictingFlags
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = WindowPosition::default_state();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            WindowPositionError::SchemaMismatch
        ));
    }

    #[test]
    fn position_serde_roundtrip() {
        let p = WindowPosition::default_state();
        let j = serde_json::to_string(&p).unwrap();
        let back: WindowPosition = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
