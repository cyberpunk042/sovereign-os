//! `sovereign-cockpit-rubber-band` — drag-selection rect.
//!
//! State{Idle/Dragging}. start(x, y) → Dragging at anchor.
//! update(x, y) sets current. finish() returns the normalized
//! Rect (None if no drag). cancel returns to Idle without
//! emitting a rect.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum DragState {
    /// Idle.
    Idle,
    /// Dragging.
    Dragging,
}

/// Selection rect (normalized — lo_x<=hi_x, lo_y<=hi_y).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct SelRect {
    /// Lo x.
    pub lo_x: i32,
    /// Lo y.
    pub lo_y: i32,
    /// Hi x.
    pub hi_x: i32,
    /// Hi y.
    pub hi_y: i32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RubberBand {
    /// Schema version.
    pub schema_version: String,
    /// State.
    pub state: DragState,
    /// Anchor (where the drag started).
    pub anchor: (i32, i32),
    /// Current (latest update).
    pub current: (i32, i32),
}

/// Errors.
#[derive(Debug, Error)]
pub enum DragError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Not dragging.
    #[error("not dragging")]
    NotDragging,
}

impl RubberBand {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            state: DragState::Idle,
            anchor: (0, 0),
            current: (0, 0),
        }
    }

    /// Start drag at (x, y).
    pub fn start(&mut self, x: i32, y: i32) {
        self.state = DragState::Dragging;
        self.anchor = (x, y);
        self.current = (x, y);
    }

    /// Update current point during drag.
    pub fn update(&mut self, x: i32, y: i32) -> Result<(), DragError> {
        if self.state != DragState::Dragging {
            return Err(DragError::NotDragging);
        }
        self.current = (x, y);
        Ok(())
    }

    /// Finish drag; returns normalized rect (None if not dragging).
    pub fn finish(&mut self) -> Option<SelRect> {
        if self.state != DragState::Dragging {
            return None;
        }
        self.state = DragState::Idle;
        Some(self.rect())
    }

    /// Cancel drag (no rect emitted).
    pub fn cancel(&mut self) {
        self.state = DragState::Idle;
    }

    /// Current normalized rect (valid only when Dragging).
    pub fn rect(&self) -> SelRect {
        let (ax, ay) = self.anchor;
        let (cx, cy) = self.current;
        SelRect {
            lo_x: ax.min(cx),
            lo_y: ay.min(cy),
            hi_x: ax.max(cx),
            hi_y: ay.max(cy),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DragError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DragError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for RubberBand {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_update_finish() {
        let mut r = RubberBand::new();
        r.start(5, 10);
        r.update(20, 30).unwrap();
        let rect = r.finish().unwrap();
        assert_eq!(
            rect,
            SelRect {
                lo_x: 5,
                lo_y: 10,
                hi_x: 20,
                hi_y: 30
            }
        );
        assert_eq!(r.state, DragState::Idle);
    }

    #[test]
    fn reverse_direction_normalizes() {
        let mut r = RubberBand::new();
        r.start(20, 30);
        r.update(5, 10).unwrap();
        let rect = r.finish().unwrap();
        assert_eq!(
            rect,
            SelRect {
                lo_x: 5,
                lo_y: 10,
                hi_x: 20,
                hi_y: 30
            }
        );
    }

    #[test]
    fn update_without_start_rejected() {
        let mut r = RubberBand::new();
        assert!(matches!(
            r.update(5, 5).unwrap_err(),
            DragError::NotDragging
        ));
    }

    #[test]
    fn finish_without_start_returns_none() {
        let mut r = RubberBand::new();
        assert!(r.finish().is_none());
    }

    #[test]
    fn cancel_resets() {
        let mut r = RubberBand::new();
        r.start(0, 0);
        r.cancel();
        assert_eq!(r.state, DragState::Idle);
        assert!(r.finish().is_none());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = RubberBand::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            DragError::SchemaMismatch
        ));
    }

    #[test]
    fn band_serde_roundtrip() {
        let mut r = RubberBand::new();
        r.start(1, 2);
        let j = serde_json::to_string(&r).unwrap();
        let back: RubberBand = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
