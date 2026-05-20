//! `sovereign-cockpit-side-drawer` — slide-in drawer state.
//!
//! Edge{Left/Right/Top/Bottom}; Mode{Push/Overlay}. open/close
//! toggles; set_width clamps to min/max.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Edge.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Edge {
    /// Left.
    Left,
    /// Right.
    Right,
    /// Top.
    Top,
    /// Bottom.
    Bottom,
}

/// Mode.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Push (shifts main content).
    Push,
    /// Overlay (floats over content).
    Overlay,
}

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct SideDrawer {
    /// Schema version.
    pub schema_version_marker: u32,
    /// Edge.
    pub edge: Edge,
    /// Mode.
    pub mode: Mode,
    /// Open?
    pub open: bool,
    /// Min width px.
    pub min_px: u32,
    /// Max width px.
    pub max_px: u32,
    /// Current width.
    pub width_px: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DrawerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad bounds.
    #[error("min ({min}) > max ({max})")]
    BadBounds {
        /// min.
        min: u32,
        /// max.
        max: u32,
    },
}

impl SideDrawer {
    /// New.
    pub fn new(edge: Edge, mode: Mode, min_px: u32, max_px: u32, initial_px: u32) -> Result<Self, DrawerError> {
        if min_px > max_px { return Err(DrawerError::BadBounds { min: min_px, max: max_px }); }
        Ok(Self {
            schema_version_marker: 1,
            edge,
            mode,
            open: false,
            min_px,
            max_px,
            width_px: initial_px.clamp(min_px, max_px),
        })
    }

    /// Open.
    pub fn open(&mut self) {
        self.open = true;
    }

    /// Close.
    pub fn close(&mut self) {
        self.open = false;
    }

    /// Toggle.
    pub fn toggle(&mut self) -> bool {
        self.open = !self.open;
        self.open
    }

    /// Set width (clamped).
    pub fn set_width(&mut self, width_px: u32) {
        self.width_px = width_px.clamp(self.min_px, self.max_px);
    }

    /// Set mode.
    pub fn set_mode(&mut self, mode: Mode) {
        self.mode = mode;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DrawerError> {
        if self.schema_version_marker != 1 { return Err(DrawerError::SchemaMismatch); }
        if self.min_px > self.max_px { return Err(DrawerError::BadBounds { min: self.min_px, max: self.max_px }); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn initial_closed() {
        let d = SideDrawer::new(Edge::Left, Mode::Overlay, 200, 400, 300).unwrap();
        assert!(!d.open);
        assert_eq!(d.width_px, 300);
    }

    #[test]
    fn open_close_toggle() {
        let mut d = SideDrawer::new(Edge::Left, Mode::Overlay, 100, 500, 200).unwrap();
        d.open();
        assert!(d.open);
        d.close();
        assert!(!d.open);
        assert!(d.toggle());
        assert!(!d.toggle());
    }

    #[test]
    fn set_width_clamps() {
        let mut d = SideDrawer::new(Edge::Left, Mode::Push, 100, 300, 200).unwrap();
        d.set_width(1000);
        assert_eq!(d.width_px, 300);
        d.set_width(0);
        assert_eq!(d.width_px, 100);
    }

    #[test]
    fn switch_mode() {
        let mut d = SideDrawer::new(Edge::Left, Mode::Overlay, 100, 300, 200).unwrap();
        d.set_mode(Mode::Push);
        assert_eq!(d.mode, Mode::Push);
    }

    #[test]
    fn bad_bounds_rejected() {
        assert!(matches!(SideDrawer::new(Edge::Left, Mode::Push, 500, 100, 200).unwrap_err(), DrawerError::BadBounds { .. }));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = SideDrawer::new(Edge::Left, Mode::Push, 100, 300, 200).unwrap();
        d.schema_version_marker = 99;
        assert!(matches!(d.validate().unwrap_err(), DrawerError::SchemaMismatch));
    }

    #[test]
    fn drawer_serde_roundtrip() {
        let mut d = SideDrawer::new(Edge::Right, Mode::Push, 100, 500, 200).unwrap();
        d.open();
        let j = serde_json::to_string(&d).unwrap();
        let back: SideDrawer = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
