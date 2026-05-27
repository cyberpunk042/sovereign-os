//! `sovereign-cockpit-dock-position` — dock placement state.
//!
//! Holds a `Placement` enum:
//!
//!   * `Left` / `Right` / `Top` / `Bottom` — edge-snapped.
//!   * `Floating { x, y }` — anchor pos inside the viewport.
//!
//! `dock_to(edge)` snaps to an edge. `float_to(x, y)` clamps to the
//! viewport rect (must `set_viewport(w, h)` first). `is_floating()`
//! convenience.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Edge.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
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

/// Placement.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Placement {
    /// Docked to an edge.
    Edge {
        /// edge.
        edge: Edge,
    },
    /// Floating.
    Floating {
        /// x.
        x: u32,
        /// y.
        y: u32,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DockPosition {
    /// Schema version.
    pub schema_version: String,
    /// Placement.
    pub placement: Placement,
    /// Viewport width.
    pub viewport_w: u32,
    /// Viewport height.
    pub viewport_h: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DockError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// viewport zero.
    #[error("viewport must be > 0")]
    ViewportZero,
}

impl DockPosition {
    /// New, docked to Left.
    pub fn new(viewport_w: u32, viewport_h: u32) -> Result<Self, DockError> {
        if viewport_w == 0 || viewport_h == 0 {
            return Err(DockError::ViewportZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            placement: Placement::Edge { edge: Edge::Left },
            viewport_w,
            viewport_h,
        })
    }

    /// Set viewport (e.g. window resize).
    pub fn set_viewport(&mut self, w: u32, h: u32) -> Result<(), DockError> {
        if w == 0 || h == 0 {
            return Err(DockError::ViewportZero);
        }
        self.viewport_w = w;
        self.viewport_h = h;
        // Reclamp floating position.
        if let Placement::Floating { x, y } = self.placement {
            let cx = x.min(w.saturating_sub(1));
            let cy = y.min(h.saturating_sub(1));
            self.placement = Placement::Floating { x: cx, y: cy };
        }
        Ok(())
    }

    /// Snap to edge.
    pub fn dock_to(&mut self, edge: Edge) {
        self.placement = Placement::Edge { edge };
    }

    /// Float to position.
    pub fn float_to(&mut self, x: u32, y: u32) {
        let cx = x.min(self.viewport_w.saturating_sub(1));
        let cy = y.min(self.viewport_h.saturating_sub(1));
        self.placement = Placement::Floating { x: cx, y: cy };
    }

    /// Is floating?
    pub fn is_floating(&self) -> bool {
        matches!(self.placement, Placement::Floating { .. })
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DockError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DockError::SchemaMismatch);
        }
        if self.viewport_w == 0 || self.viewport_h == 0 {
            return Err(DockError::ViewportZero);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn viewport_zero_rejected() {
        assert!(matches!(
            DockPosition::new(0, 100).unwrap_err(),
            DockError::ViewportZero
        ));
    }

    #[test]
    fn defaults_to_left() {
        let d = DockPosition::new(800, 600).unwrap();
        assert_eq!(d.placement, Placement::Edge { edge: Edge::Left });
        assert!(!d.is_floating());
    }

    #[test]
    fn dock_to_right() {
        let mut d = DockPosition::new(800, 600).unwrap();
        d.dock_to(Edge::Right);
        assert_eq!(d.placement, Placement::Edge { edge: Edge::Right });
    }

    #[test]
    fn float_clamps_to_viewport() {
        let mut d = DockPosition::new(800, 600).unwrap();
        d.float_to(2000, 3000);
        assert_eq!(d.placement, Placement::Floating { x: 799, y: 599 });
        assert!(d.is_floating());
    }

    #[test]
    fn resize_reclamps_floating() {
        let mut d = DockPosition::new(800, 600).unwrap();
        d.float_to(700, 500);
        d.set_viewport(400, 300).unwrap();
        assert_eq!(d.placement, Placement::Floating { x: 399, y: 299 });
    }

    #[test]
    fn resize_keeps_edge() {
        let mut d = DockPosition::new(800, 600).unwrap();
        d.dock_to(Edge::Top);
        d.set_viewport(400, 300).unwrap();
        assert_eq!(d.placement, Placement::Edge { edge: Edge::Top });
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DockPosition::new(800, 600).unwrap();
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DockError::SchemaMismatch
        ));
    }

    #[test]
    fn dock_serde_roundtrip() {
        let mut d = DockPosition::new(800, 600).unwrap();
        d.float_to(100, 200);
        let j = serde_json::to_string(&d).unwrap();
        let back: DockPosition = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
