//! `sovereign-cockpit-drag-snap-grid` — grid snap for drag/resize.
//!
//! `Grid { step_x, step_y, threshold_px }`. `snap_point(x, y)`
//! returns the nearest grid intersection — but only snaps when the
//! drag is within `threshold_px` of the grid line. Below threshold
//! the raw (x, y) is returned unchanged, allowing free placement
//! between snap zones.
//!
//! `snap_size(w, h)` snaps dimensions to multiples of step_x/step_y
//! with the same threshold rule. `enabled = false` disables all
//! snapping.
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
pub struct DragSnapGrid {
    /// Schema version is held as a static const in this crate.
    /// X step.
    pub step_x: u32,
    /// Y step.
    pub step_y: u32,
    /// Snap threshold (px from nearest grid line).
    pub threshold_px: u32,
    /// Enabled.
    pub enabled: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SnapError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero step.
    #[error("step must be > 0")]
    ZeroStep,
}

fn nearest(v: u32, step: u32) -> u32 {
    let q = v / step;
    let lower = q * step;
    let upper = lower.saturating_add(step);
    if v - lower <= upper - v { lower } else { upper }
}

impl DragSnapGrid {
    /// New.
    pub fn new(step_x: u32, step_y: u32, threshold_px: u32) -> Result<Self, SnapError> {
        if step_x == 0 || step_y == 0 { return Err(SnapError::ZeroStep); }
        Ok(Self { step_x, step_y, threshold_px, enabled: true })
    }

    /// Enable / disable.
    pub fn set_enabled(&mut self, b: bool) { self.enabled = b; }

    /// Snap a point.
    pub fn snap_point(&self, x: u32, y: u32) -> (u32, u32) {
        if !self.enabled { return (x, y); }
        (self.snap_axis(x, self.step_x), self.snap_axis(y, self.step_y))
    }

    /// Snap a size.
    pub fn snap_size(&self, w: u32, h: u32) -> (u32, u32) {
        if !self.enabled { return (w, h); }
        (self.snap_axis(w, self.step_x), self.snap_axis(h, self.step_y))
    }

    fn snap_axis(&self, v: u32, step: u32) -> u32 {
        let snapped = nearest(v, step);
        let delta = v.abs_diff(snapped);
        if delta <= self.threshold_px { snapped } else { v }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SnapError> {
        if self.step_x == 0 || self.step_y == 0 { return Err(SnapError::ZeroStep); }
        Ok(())
    }
}

/// Wrapper carrying schema version for serde compat with the rest of the workspace.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct DragSnapGridConfig {
    /// Schema version.
    pub schema_version_marker: u32,
    /// Inner grid.
    pub grid: DragSnapGrid,
}

impl DragSnapGridConfig {
    /// New.
    pub fn new(grid: DragSnapGrid) -> Self {
        Self {
            schema_version_marker: 1,
            grid,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SnapError> {
        if self.schema_version_marker != 1 { return Err(SnapError::SchemaMismatch); }
        self.grid.validate()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snaps_within_threshold() {
        let g = DragSnapGrid::new(10, 10, 3).unwrap();
        // 12 is closer to 10 (delta 2 ≤ 3) → snap.
        assert_eq!(g.snap_point(12, 12), (10, 10));
    }

    #[test]
    fn no_snap_beyond_threshold() {
        let g = DragSnapGrid::new(10, 10, 2).unwrap();
        // 14 is closer to 10 (delta 4 > 2) → no snap.
        assert_eq!(g.snap_point(14, 14), (14, 14));
    }

    #[test]
    fn nearest_upward() {
        let g = DragSnapGrid::new(10, 10, 5).unwrap();
        // 17 → between 10 (delta 7) and 20 (delta 3); nearest is 20.
        assert_eq!(g.snap_point(17, 17), (20, 20));
    }

    #[test]
    fn equidistant_picks_lower() {
        let g = DragSnapGrid::new(10, 10, 5).unwrap();
        // 5 is equidistant 0 and 10; nearest helper picks lower.
        assert_eq!(g.snap_point(5, 5), (0, 0));
    }

    #[test]
    fn disabled_no_snap() {
        let mut g = DragSnapGrid::new(10, 10, 5).unwrap();
        g.set_enabled(false);
        assert_eq!(g.snap_point(12, 12), (12, 12));
        assert_eq!(g.snap_size(12, 12), (12, 12));
    }

    #[test]
    fn snap_size_works() {
        let g = DragSnapGrid::new(20, 20, 5).unwrap();
        assert_eq!(g.snap_size(18, 22), (20, 20));
    }

    #[test]
    fn zero_step_rejected() {
        assert!(matches!(DragSnapGrid::new(0, 10, 1).unwrap_err(), SnapError::ZeroStep));
        assert!(matches!(DragSnapGrid::new(10, 0, 1).unwrap_err(), SnapError::ZeroStep));
    }

    #[test]
    fn nearest_boundary() {
        let g = DragSnapGrid::new(10, 10, 100).unwrap();
        // huge threshold — always snaps.
        assert_eq!(g.snap_point(0, 0), (0, 0));
        // 35 equidistant 30/40 → lower (30); 99 closer to 100.
        assert_eq!(g.snap_point(35, 99), (30, 100));
    }

    #[test]
    fn config_schema_drift_rejected() {
        let mut c = DragSnapGridConfig::new(DragSnapGrid::new(10, 10, 3).unwrap());
        c.schema_version_marker = 99;
        assert!(matches!(c.validate().unwrap_err(), SnapError::SchemaMismatch));
    }

    #[test]
    fn snap_serde_roundtrip() {
        let g = DragSnapGrid::new(10, 10, 3).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: DragSnapGrid = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
