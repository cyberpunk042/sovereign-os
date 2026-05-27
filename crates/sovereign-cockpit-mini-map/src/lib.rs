//! `sovereign-cockpit-mini-map` — minimap viewport-rect.
//!
//! Given content dims and viewport (x,y,w,h), compute the scaled
//! minimap dimensions and the viewport rectangle inside the minimap.
//! Aspect ratio is preserved by picking the smaller of the per-axis
//! fits.
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
pub struct MiniMap {
    /// Schema version.
    pub schema_version: String,
    /// Content width.
    pub content_w: u32,
    /// Content height.
    pub content_h: u32,
    /// Viewport x in content space.
    pub viewport_x: u32,
    /// Viewport y in content space.
    pub viewport_y: u32,
    /// Viewport width.
    pub viewport_w: u32,
    /// Viewport height.
    pub viewport_h: u32,
    /// Max minimap width (renders fit within this).
    pub minimap_max_w: u32,
    /// Max minimap height.
    pub minimap_max_h: u32,
}

/// Rendered rectangle (px in minimap space).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Rect {
    /// x.
    pub x: u32,
    /// y.
    pub y: u32,
    /// w.
    pub w: u32,
    /// h.
    pub h: u32,
}

/// Projected layout.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Layout {
    /// Minimap width (px).
    pub minimap_w: u32,
    /// Minimap height (px).
    pub minimap_h: u32,
    /// Viewport rect within minimap.
    pub viewport_rect: Rect,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MiniMapError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Content dims zero.
    #[error("content dims zero")]
    ContentZero,
    /// Minimap max dims zero.
    #[error("minimap_max dims zero")]
    MinimapZero,
}

impl MiniMap {
    /// New.
    pub fn new(
        content_w: u32,
        content_h: u32,
        viewport: (u32, u32, u32, u32),
        minimap_max_w: u32,
        minimap_max_h: u32,
    ) -> Result<Self, MiniMapError> {
        if content_w == 0 || content_h == 0 {
            return Err(MiniMapError::ContentZero);
        }
        if minimap_max_w == 0 || minimap_max_h == 0 {
            return Err(MiniMapError::MinimapZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            content_w,
            content_h,
            viewport_x: viewport.0,
            viewport_y: viewport.1,
            viewport_w: viewport.2,
            viewport_h: viewport.3,
            minimap_max_w,
            minimap_max_h,
        })
    }

    /// Compute scaled layout.
    pub fn layout(&self) -> Layout {
        // Scale = min(max_w/content_w, max_h/content_h) preserving aspect.
        let sx = self.minimap_max_w as f64 / self.content_w as f64;
        let sy = self.minimap_max_h as f64 / self.content_h as f64;
        let s = sx.min(sy);
        let mw = (self.content_w as f64 * s) as u32;
        let mh = (self.content_h as f64 * s) as u32;
        let vx = (self.viewport_x as f64 * s) as u32;
        let vy = (self.viewport_y as f64 * s) as u32;
        let vw = (self.viewport_w as f64 * s).max(1.0) as u32;
        let vh = (self.viewport_h as f64 * s).max(1.0) as u32;
        // Clamp viewport to minimap bounds.
        let vw_c = vw.min(mw);
        let vh_c = vh.min(mh);
        let vx_c = vx.min(mw.saturating_sub(vw_c));
        let vy_c = vy.min(mh.saturating_sub(vh_c));
        Layout {
            minimap_w: mw,
            minimap_h: mh,
            viewport_rect: Rect {
                x: vx_c,
                y: vy_c,
                w: vw_c,
                h: vh_c,
            },
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MiniMapError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MiniMapError::SchemaMismatch);
        }
        if self.content_w == 0 || self.content_h == 0 {
            return Err(MiniMapError::ContentZero);
        }
        if self.minimap_max_w == 0 || self.minimap_max_h == 0 {
            return Err(MiniMapError::MinimapZero);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn content_zero_rejected() {
        assert!(matches!(
            MiniMap::new(0, 100, (0, 0, 10, 10), 100, 100).unwrap_err(),
            MiniMapError::ContentZero
        ));
    }

    #[test]
    fn minimap_zero_rejected() {
        assert!(matches!(
            MiniMap::new(100, 100, (0, 0, 10, 10), 0, 100).unwrap_err(),
            MiniMapError::MinimapZero
        ));
    }

    #[test]
    fn square_aspect_fit() {
        let m = MiniMap::new(1000, 1000, (100, 100, 200, 200), 100, 100).unwrap();
        let l = m.layout();
        assert_eq!(l.minimap_w, 100);
        assert_eq!(l.minimap_h, 100);
        assert_eq!(l.viewport_rect.w, 20);
        assert_eq!(l.viewport_rect.h, 20);
    }

    #[test]
    fn wider_content_constrained_by_width() {
        let m = MiniMap::new(2000, 1000, (0, 0, 100, 100), 100, 100).unwrap();
        let l = m.layout();
        // sx = 100/2000 = 0.05, sy = 100/1000 = 0.1. min = 0.05.
        assert_eq!(l.minimap_w, 100);
        assert_eq!(l.minimap_h, 50);
    }

    #[test]
    fn tall_content_constrained_by_height() {
        let m = MiniMap::new(1000, 2000, (0, 0, 100, 100), 100, 100).unwrap();
        let l = m.layout();
        assert_eq!(l.minimap_w, 50);
        assert_eq!(l.minimap_h, 100);
    }

    #[test]
    fn viewport_rect_clamped_to_bounds() {
        let m = MiniMap::new(100, 100, (90, 90, 200, 200), 100, 100).unwrap();
        let l = m.layout();
        // viewport huge, clamped to minimap.
        assert!(l.viewport_rect.x + l.viewport_rect.w <= l.minimap_w);
        assert!(l.viewport_rect.y + l.viewport_rect.h <= l.minimap_h);
    }

    #[test]
    fn tiny_viewport_minimum_1px() {
        let m = MiniMap::new(10000, 10000, (0, 0, 5, 5), 100, 100).unwrap();
        let l = m.layout();
        assert!(l.viewport_rect.w >= 1);
        assert!(l.viewport_rect.h >= 1);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = MiniMap::new(100, 100, (0, 0, 10, 10), 100, 100).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            MiniMapError::SchemaMismatch
        ));
    }

    #[test]
    fn map_serde_roundtrip() {
        let m = MiniMap::new(100, 100, (0, 0, 10, 10), 100, 100).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: MiniMap = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
