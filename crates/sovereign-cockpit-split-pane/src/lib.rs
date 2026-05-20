//! `sovereign-cockpit-split-pane` — two-pane split with draggable gutter.
//!
//! Tracks `split_px` (the gutter offset from one edge) inside a
//! `container_size`. `set_split(value)` clamps the value to
//! `(min_a_px, container_size - min_b_px)`. `drag_to(value)` does
//! the same clamping and optionally snaps to `min_a_px` or
//! `container_size - min_b_px` when within `snap_threshold_px`.
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
pub struct SplitPane {
    /// Schema version.
    pub schema_version: String,
    /// Container size in the split axis (px).
    pub container_size: u32,
    /// Current gutter offset from the leading edge.
    pub split_px: u32,
    /// Minimum size for pane A (leading).
    pub min_a_px: u32,
    /// Minimum size for pane B (trailing).
    pub min_b_px: u32,
    /// Snap threshold (px) for collapsing to min on either side.
    pub snap_threshold_px: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SplitError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Container too small for the configured minima.
    #[error("container_size {0} < min_a + min_b ({1})")]
    ContainerTooSmall(u32, u32),
}

impl SplitPane {
    /// New.
    pub fn new(container_size: u32, split_px: u32, min_a_px: u32, min_b_px: u32, snap_threshold_px: u32) -> Result<Self, SplitError> {
        let minima = min_a_px.saturating_add(min_b_px);
        if container_size < minima {
            return Err(SplitError::ContainerTooSmall(container_size, minima));
        }
        let mut s = Self {
            schema_version: SCHEMA_VERSION.into(),
            container_size,
            split_px: 0,
            min_a_px,
            min_b_px,
            snap_threshold_px,
        };
        s.split_px = s.clamp(split_px);
        Ok(s)
    }

    fn clamp(&self, v: u32) -> u32 {
        let max = self.container_size.saturating_sub(self.min_b_px);
        v.max(self.min_a_px).min(max)
    }

    /// Set the split (clamped, no snap).
    pub fn set_split(&mut self, v: u32) {
        self.split_px = self.clamp(v);
    }

    /// Drag-to with snap.
    pub fn drag_to(&mut self, v: u32) {
        let max = self.container_size.saturating_sub(self.min_b_px);
        let clamped = v.max(self.min_a_px).min(max);
        let near_min = clamped.saturating_sub(self.min_a_px) <= self.snap_threshold_px;
        let near_max = max.saturating_sub(clamped) <= self.snap_threshold_px;
        self.split_px = if near_min {
            self.min_a_px
        } else if near_max {
            max
        } else {
            clamped
        };
    }

    /// Width of pane A.
    pub fn a_size(&self) -> u32 { self.split_px }

    /// Width of pane B.
    pub fn b_size(&self) -> u32 { self.container_size.saturating_sub(self.split_px) }

    /// Resize the container; reclamp the split.
    pub fn resize_container(&mut self, new_size: u32) -> Result<(), SplitError> {
        let minima = self.min_a_px.saturating_add(self.min_b_px);
        if new_size < minima {
            return Err(SplitError::ContainerTooSmall(new_size, minima));
        }
        self.container_size = new_size;
        self.split_px = self.clamp(self.split_px);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SplitError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SplitError::SchemaMismatch); }
        let minima = self.min_a_px.saturating_add(self.min_b_px);
        if self.container_size < minima {
            return Err(SplitError::ContainerTooSmall(self.container_size, minima));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn container_too_small_rejected() {
        assert!(matches!(SplitPane::new(50, 25, 40, 40, 4).unwrap_err(), SplitError::ContainerTooSmall(_, _)));
    }

    #[test]
    fn clamps_below_min_a() {
        let mut s = SplitPane::new(500, 50, 100, 100, 4).unwrap();
        s.set_split(20);
        assert_eq!(s.split_px, 100);
    }

    #[test]
    fn clamps_above_max() {
        let mut s = SplitPane::new(500, 100, 100, 100, 4).unwrap();
        s.set_split(490);
        assert_eq!(s.split_px, 400);
    }

    #[test]
    fn drag_to_snaps_to_min() {
        let mut s = SplitPane::new(500, 200, 100, 100, 10).unwrap();
        s.drag_to(105);
        assert_eq!(s.split_px, 100);
    }

    #[test]
    fn drag_to_snaps_to_max() {
        let mut s = SplitPane::new(500, 200, 100, 100, 10).unwrap();
        s.drag_to(395);
        assert_eq!(s.split_px, 400);
    }

    #[test]
    fn drag_to_no_snap_in_middle() {
        let mut s = SplitPane::new(500, 200, 100, 100, 10).unwrap();
        s.drag_to(250);
        assert_eq!(s.split_px, 250);
    }

    #[test]
    fn a_b_sizes() {
        let s = SplitPane::new(500, 200, 50, 50, 4).unwrap();
        assert_eq!(s.a_size(), 200);
        assert_eq!(s.b_size(), 300);
    }

    #[test]
    fn resize_container_reclamps() {
        let mut s = SplitPane::new(500, 400, 100, 100, 4).unwrap();
        // Shrink container so the existing split is past max.
        s.resize_container(300).unwrap();
        // max = 300 - 100 = 200
        assert_eq!(s.split_px, 200);
    }

    #[test]
    fn resize_too_small_rejected() {
        let mut s = SplitPane::new(500, 200, 100, 100, 4).unwrap();
        assert!(matches!(s.resize_container(50).unwrap_err(), SplitError::ContainerTooSmall(_, _)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SplitPane::new(500, 200, 100, 100, 4).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SplitError::SchemaMismatch));
    }

    #[test]
    fn split_serde_roundtrip() {
        let s = SplitPane::new(500, 200, 100, 100, 4).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SplitPane = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
