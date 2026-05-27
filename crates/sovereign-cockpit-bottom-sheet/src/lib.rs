//! `sovereign-cockpit-bottom-sheet` — three-snap bottom-sheet state.
//!
//! Three named snap heights: `Collapsed`, `Half`, `Full`. `set_snap`
//! teleports to one. `drag_to(px)` clamps to `[collapsed_px, full_px]`
//! and snaps to the nearest snap if within `snap_threshold_px`,
//! otherwise reports the drag height as `Custom`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Snap.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Snap {
    /// Collapsed.
    Collapsed,
    /// Half.
    Half,
    /// Full.
    Full,
    /// Custom (during drag).
    Custom,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BottomSheet {
    /// Schema version.
    pub schema_version: String,
    /// Snap heights (px).
    pub collapsed_px: u32,
    /// Snap heights (px).
    pub half_px: u32,
    /// Snap heights (px).
    pub full_px: u32,
    /// Threshold to snap on drag-release.
    pub snap_threshold_px: u32,
    /// Current snap.
    pub snap: Snap,
    /// Current height during a drag.
    pub current_px: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SheetError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Snap order violated.
    #[error("snap order: collapsed_px {0} < half_px {1} < full_px {2} required")]
    BadOrder(u32, u32, u32),
}

impl BottomSheet {
    /// New.
    pub fn new(
        collapsed_px: u32,
        half_px: u32,
        full_px: u32,
        snap_threshold_px: u32,
    ) -> Result<Self, SheetError> {
        if !(collapsed_px < half_px && half_px < full_px) {
            return Err(SheetError::BadOrder(collapsed_px, half_px, full_px));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            collapsed_px,
            half_px,
            full_px,
            snap_threshold_px,
            snap: Snap::Collapsed,
            current_px: collapsed_px,
        })
    }

    /// Snap to a named position.
    pub fn set_snap(&mut self, snap: Snap) {
        match snap {
            Snap::Collapsed => {
                self.snap = Snap::Collapsed;
                self.current_px = self.collapsed_px;
            }
            Snap::Half => {
                self.snap = Snap::Half;
                self.current_px = self.half_px;
            }
            Snap::Full => {
                self.snap = Snap::Full;
                self.current_px = self.full_px;
            }
            Snap::Custom => { /* ignore explicit Custom */ }
        }
    }

    /// Drag to px.
    pub fn drag_to(&mut self, px: u32) {
        let clamped = px.max(self.collapsed_px).min(self.full_px);
        self.current_px = clamped;
        let closest = [
            (Snap::Collapsed, self.collapsed_px),
            (Snap::Half, self.half_px),
            (Snap::Full, self.full_px),
        ]
        .into_iter()
        .min_by_key(|(_, p)| p.abs_diff(clamped))
        .unwrap();
        if closest.1.abs_diff(clamped) <= self.snap_threshold_px {
            self.snap = closest.0;
            self.current_px = closest.1;
        } else {
            self.snap = Snap::Custom;
        }
    }

    /// Current resolved height.
    pub fn current_height(&self) -> u32 {
        self.current_px
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SheetError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SheetError::SchemaMismatch);
        }
        if !(self.collapsed_px < self.half_px && self.half_px < self.full_px) {
            return Err(SheetError::BadOrder(
                self.collapsed_px,
                self.half_px,
                self.full_px,
            ));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bad_order_rejected() {
        assert!(matches!(
            BottomSheet::new(100, 50, 200, 10).unwrap_err(),
            SheetError::BadOrder(_, _, _)
        ));
    }

    #[test]
    fn set_snap_teleports() {
        let mut s = BottomSheet::new(80, 400, 800, 20).unwrap();
        s.set_snap(Snap::Half);
        assert_eq!(s.current_height(), 400);
    }

    #[test]
    fn drag_snaps_to_nearest_within_threshold() {
        let mut s = BottomSheet::new(80, 400, 800, 30).unwrap();
        s.drag_to(420);
        assert_eq!(s.snap, Snap::Half);
        assert_eq!(s.current_height(), 400);
    }

    #[test]
    fn drag_falls_to_custom_when_far() {
        let mut s = BottomSheet::new(80, 400, 800, 10).unwrap();
        s.drag_to(600);
        assert_eq!(s.snap, Snap::Custom);
        assert_eq!(s.current_height(), 600);
    }

    #[test]
    fn drag_clamps_below_collapsed() {
        let mut s = BottomSheet::new(80, 400, 800, 10).unwrap();
        s.drag_to(0);
        assert_eq!(s.snap, Snap::Collapsed);
        assert_eq!(s.current_height(), 80);
    }

    #[test]
    fn drag_clamps_above_full() {
        let mut s = BottomSheet::new(80, 400, 800, 10).unwrap();
        s.drag_to(9999);
        assert_eq!(s.snap, Snap::Full);
        assert_eq!(s.current_height(), 800);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = BottomSheet::new(80, 400, 800, 10).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SheetError::SchemaMismatch
        ));
    }

    #[test]
    fn sheet_serde_roundtrip() {
        let mut s = BottomSheet::new(80, 400, 800, 10).unwrap();
        s.drag_to(420);
        let j = serde_json::to_string(&s).unwrap();
        let back: BottomSheet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
