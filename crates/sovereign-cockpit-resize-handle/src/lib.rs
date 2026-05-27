//! `sovereign-cockpit-resize-handle` — pane resize handle state.
//!
//! Captures one resizable split (orientation + current px between
//! min and max). drag(delta) clamps to [min, max]; reset() returns
//! to the stored default. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Split orientation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Orientation {
    /// Horizontal divider (rows).
    Horizontal,
    /// Vertical divider (columns).
    Vertical,
}

/// Resize handle state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ResizeHandle {
    /// Schema version.
    pub schema_version: String,
    /// Orientation.
    pub orientation: Orientation,
    /// Current size of the first pane in px.
    pub current_px: u32,
    /// Min in px (≥ 1).
    pub min_px: u32,
    /// Max in px (> min_px).
    pub max_px: u32,
    /// Default to restore on reset.
    pub default_px: u32,
    /// Is a drag in progress?
    pub dragging: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ResizeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// min_px zero.
    #[error("min_px is zero")]
    MinZero,
    /// max <= min.
    #[error("max_px {0} <= min_px {1}")]
    BadBounds(u32, u32),
    /// Default out of bounds.
    #[error("default_px {0} out of [{1}, {2}]")]
    DefaultOutOfBounds(u32, u32, u32),
    /// Current out of bounds.
    #[error("current_px {0} out of [{1}, {2}]")]
    CurrentOutOfBounds(u32, u32, u32),
}

impl ResizeHandle {
    /// New handle.
    pub fn new(
        orientation: Orientation,
        min_px: u32,
        max_px: u32,
        default_px: u32,
    ) -> Result<Self, ResizeError> {
        if min_px == 0 {
            return Err(ResizeError::MinZero);
        }
        if max_px <= min_px {
            return Err(ResizeError::BadBounds(max_px, min_px));
        }
        if default_px < min_px || default_px > max_px {
            return Err(ResizeError::DefaultOutOfBounds(default_px, min_px, max_px));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            orientation,
            current_px: default_px,
            min_px,
            max_px,
            default_px,
            dragging: false,
        })
    }

    /// Start a drag.
    pub fn start_drag(&mut self) {
        self.dragging = true;
    }

    /// End a drag.
    pub fn end_drag(&mut self) {
        self.dragging = false;
    }

    /// Apply a px delta (positive = grow, negative = shrink). Clamps
    /// to [min_px, max_px]. Returns the new current_px.
    pub fn drag(&mut self, delta_px: i32) -> u32 {
        let raw = self.current_px as i64 + delta_px as i64;
        let clamped = raw.clamp(self.min_px as i64, self.max_px as i64) as u32;
        self.current_px = clamped;
        clamped
    }

    /// Snap to a specific px (clamped).
    pub fn snap_to(&mut self, px: u32) -> u32 {
        self.current_px = px.clamp(self.min_px, self.max_px);
        self.current_px
    }

    /// Restore default.
    pub fn reset(&mut self) {
        self.current_px = self.default_px;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ResizeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ResizeError::SchemaMismatch);
        }
        if self.min_px == 0 {
            return Err(ResizeError::MinZero);
        }
        if self.max_px <= self.min_px {
            return Err(ResizeError::BadBounds(self.max_px, self.min_px));
        }
        if self.default_px < self.min_px || self.default_px > self.max_px {
            return Err(ResizeError::DefaultOutOfBounds(
                self.default_px,
                self.min_px,
                self.max_px,
            ));
        }
        if self.current_px < self.min_px || self.current_px > self.max_px {
            return Err(ResizeError::CurrentOutOfBounds(
                self.current_px,
                self.min_px,
                self.max_px,
            ));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h() -> ResizeHandle {
        ResizeHandle::new(Orientation::Vertical, 100, 500, 250).unwrap()
    }

    #[test]
    fn new_min_zero_rejected() {
        assert!(matches!(
            ResizeHandle::new(Orientation::Vertical, 0, 100, 50).unwrap_err(),
            ResizeError::MinZero
        ));
    }

    #[test]
    fn new_bad_bounds_rejected() {
        assert!(matches!(
            ResizeHandle::new(Orientation::Vertical, 100, 50, 75).unwrap_err(),
            ResizeError::BadBounds(50, 100)
        ));
        assert!(matches!(
            ResizeHandle::new(Orientation::Vertical, 100, 100, 100).unwrap_err(),
            ResizeError::BadBounds(_, _)
        ));
    }

    #[test]
    fn new_bad_default_rejected() {
        assert!(matches!(
            ResizeHandle::new(Orientation::Vertical, 100, 500, 600).unwrap_err(),
            ResizeError::DefaultOutOfBounds(_, _, _)
        ));
    }

    #[test]
    fn drag_grows() {
        let mut h = h();
        let p = h.drag(50);
        assert_eq!(p, 300);
        assert_eq!(h.current_px, 300);
    }

    #[test]
    fn drag_shrinks() {
        let mut h = h();
        let p = h.drag(-50);
        assert_eq!(p, 200);
    }

    #[test]
    fn drag_clamps_to_min() {
        let mut h = h();
        let p = h.drag(-9999);
        assert_eq!(p, 100);
    }

    #[test]
    fn drag_clamps_to_max() {
        let mut h = h();
        let p = h.drag(9999);
        assert_eq!(p, 500);
    }

    #[test]
    fn snap_clamps() {
        let mut h = h();
        assert_eq!(h.snap_to(1), 100);
        assert_eq!(h.snap_to(10_000), 500);
        assert_eq!(h.snap_to(300), 300);
    }

    #[test]
    fn reset_restores_default() {
        let mut h = h();
        h.drag(100);
        assert_eq!(h.current_px, 350);
        h.reset();
        assert_eq!(h.current_px, 250);
    }

    #[test]
    fn drag_state_lifecycle() {
        let mut h = h();
        assert!(!h.dragging);
        h.start_drag();
        assert!(h.dragging);
        h.end_drag();
        assert!(!h.dragging);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = h();
        h.schema_version = "9.9.9".into();
        assert!(matches!(
            h.validate().unwrap_err(),
            ResizeError::SchemaMismatch
        ));
    }

    #[test]
    fn validate_current_out_of_range_rejected() {
        let mut h = h();
        h.current_px = 9999;
        assert!(matches!(
            h.validate().unwrap_err(),
            ResizeError::CurrentOutOfBounds(_, _, _)
        ));
    }

    #[test]
    fn orientation_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Orientation::Horizontal).unwrap(),
            "\"horizontal\""
        );
        assert_eq!(
            serde_json::to_string(&Orientation::Vertical).unwrap(),
            "\"vertical\""
        );
    }

    #[test]
    fn handle_serde_roundtrip() {
        let h = h();
        let j = serde_json::to_string(&h).unwrap();
        let back: ResizeHandle = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
