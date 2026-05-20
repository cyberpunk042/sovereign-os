//! `sovereign-cockpit-minimap-state` — minimap geometry.
//!
//! Content rectangle (content_w, content_h) is scaled to fit the
//! minimap box (minimap_w, minimap_h) preserving aspect ratio
//! (centered). viewport_rect() returns the minimap-space
//! rectangle representing the current viewport. click_to_viewport
//! converts a minimap click into a content-space center point.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Rect in minimap space.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct MinimapRect {
    /// X.
    pub x: f64,
    /// Y.
    pub y: f64,
    /// Width.
    pub w: f64,
    /// Height.
    pub h: f64,
}

/// Content-space point.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct ContentPoint {
    /// X.
    pub x: f64,
    /// Y.
    pub y: f64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MinimapState {
    /// Schema version.
    pub schema_version: String,
    /// Content width.
    pub content_w: u32,
    /// Content height.
    pub content_h: u32,
    /// Minimap box width.
    pub minimap_w: u32,
    /// Minimap box height.
    pub minimap_h: u32,
    /// Viewport top-left x in content.
    pub viewport_x: u32,
    /// Viewport top-left y in content.
    pub viewport_y: u32,
    /// Viewport width.
    pub viewport_w: u32,
    /// Viewport height.
    pub viewport_h: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MinimapError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad dim.
    #[error("dimension must be >= 1")]
    BadDimension,
}

impl MinimapState {
    /// New.
    pub fn new(content_w: u32, content_h: u32, minimap_w: u32, minimap_h: u32) -> Result<Self, MinimapError> {
        if content_w == 0 || content_h == 0 || minimap_w == 0 || minimap_h == 0 {
            return Err(MinimapError::BadDimension);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            content_w,
            content_h,
            minimap_w,
            minimap_h,
            viewport_x: 0,
            viewport_y: 0,
            viewport_w: content_w,
            viewport_h: content_h,
        })
    }

    /// Set viewport (content-space).
    pub fn set_viewport(&mut self, x: u32, y: u32, w: u32, h: u32) {
        self.viewport_x = x;
        self.viewport_y = y;
        self.viewport_w = w;
        self.viewport_h = h;
    }

    /// Scale factor + letterbox offset to map content → minimap.
    fn fit(&self) -> (f64, f64, f64) {
        let sx = self.minimap_w as f64 / self.content_w as f64;
        let sy = self.minimap_h as f64 / self.content_h as f64;
        let s = if sx < sy { sx } else { sy };
        let used_w = s * self.content_w as f64;
        let used_h = s * self.content_h as f64;
        let off_x = (self.minimap_w as f64 - used_w) / 2.0;
        let off_y = (self.minimap_h as f64 - used_h) / 2.0;
        (s, off_x, off_y)
    }

    /// Minimap-space rect representing the current viewport.
    pub fn viewport_rect(&self) -> MinimapRect {
        let (s, off_x, off_y) = self.fit();
        MinimapRect {
            x: off_x + (self.viewport_x as f64) * s,
            y: off_y + (self.viewport_y as f64) * s,
            w: (self.viewport_w as f64) * s,
            h: (self.viewport_h as f64) * s,
        }
    }

    /// Convert a minimap click to a content-space center point
    /// (clamped so viewport stays within content).
    pub fn click_to_viewport(&self, click_x: f64, click_y: f64) -> ContentPoint {
        let (s, off_x, off_y) = self.fit();
        let cx = (click_x - off_x) / s;
        let cy = (click_y - off_y) / s;
        let half_w = self.viewport_w as f64 / 2.0;
        let half_h = self.viewport_h as f64 / 2.0;
        let max_x = (self.content_w as f64 - half_w).max(half_w);
        let max_y = (self.content_h as f64 - half_h).max(half_h);
        ContentPoint {
            x: cx.clamp(half_w, max_x),
            y: cy.clamp(half_h, max_y),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MinimapError> {
        if self.schema_version != SCHEMA_VERSION { return Err(MinimapError::SchemaMismatch); }
        if self.content_w == 0 || self.content_h == 0 || self.minimap_w == 0 || self.minimap_h == 0 {
            return Err(MinimapError::BadDimension);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn full_viewport_covers_minimap_letterbox() {
        let m = MinimapState::new(1000, 500, 100, 100).unwrap();
        let r = m.viewport_rect();
        // Aspect 2:1; scale = min(0.1, 0.2) = 0.1; minimap content = 100x50.
        assert!((r.x - 0.0).abs() < 1e-6);
        assert!((r.y - 25.0).abs() < 1e-6); // (100-50)/2
        assert!((r.w - 100.0).abs() < 1e-6);
        assert!((r.h - 50.0).abs() < 1e-6);
    }

    #[test]
    fn partial_viewport_scales() {
        let mut m = MinimapState::new(1000, 1000, 100, 100).unwrap();
        m.set_viewport(100, 200, 300, 400);
        let r = m.viewport_rect();
        // scale = 0.1.
        assert!((r.x - 10.0).abs() < 1e-6);
        assert!((r.y - 20.0).abs() < 1e-6);
        assert!((r.w - 30.0).abs() < 1e-6);
        assert!((r.h - 40.0).abs() < 1e-6);
    }

    #[test]
    fn click_centers_viewport() {
        let mut m = MinimapState::new(1000, 1000, 100, 100).unwrap();
        m.set_viewport(0, 0, 200, 200);
        let p = m.click_to_viewport(50.0, 50.0);
        // Center click → content center 500,500.
        assert!((p.x - 500.0).abs() < 1e-6);
        assert!((p.y - 500.0).abs() < 1e-6);
    }

    #[test]
    fn click_clamps_to_edges() {
        let mut m = MinimapState::new(1000, 1000, 100, 100).unwrap();
        m.set_viewport(0, 0, 200, 200);
        let p = m.click_to_viewport(0.0, 0.0);
        // Top-left click clamps to viewport-half = 100.
        assert!((p.x - 100.0).abs() < 1e-6);
        assert!((p.y - 100.0).abs() < 1e-6);
    }

    #[test]
    fn click_clamps_far_edge() {
        let mut m = MinimapState::new(1000, 1000, 100, 100).unwrap();
        m.set_viewport(0, 0, 200, 200);
        let p = m.click_to_viewport(100.0, 100.0);
        // 1000 - half(100) = 900.
        assert!((p.x - 900.0).abs() < 1e-6);
        assert!((p.y - 900.0).abs() < 1e-6);
    }

    #[test]
    fn bad_dimension_rejected() {
        assert!(matches!(MinimapState::new(0, 100, 100, 100).unwrap_err(), MinimapError::BadDimension));
        assert!(matches!(MinimapState::new(100, 100, 0, 100).unwrap_err(), MinimapError::BadDimension));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = MinimapState::new(100, 100, 50, 50).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), MinimapError::SchemaMismatch));
    }

    #[test]
    fn minimap_serde_roundtrip() {
        let mut m = MinimapState::new(100, 100, 50, 50).unwrap();
        m.set_viewport(10, 10, 20, 20);
        let j = serde_json::to_string(&m).unwrap();
        let back: MinimapState = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
