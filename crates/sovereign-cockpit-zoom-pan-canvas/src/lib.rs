//! `sovereign-cockpit-zoom-pan-canvas` — free zoom + pan camera.
//!
//! Continuous scale (clamped to [min_scale, max_scale]) + camera
//! center (cx, cy) in world coords. Helpers convert
//! world↔screen coordinates given the viewport size. Pure UX
//! descriptor (no IPS authority).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ZoomPanCanvas {
    /// Schema version.
    pub schema_version: String,
    /// Camera center x (world).
    pub cx: f32,
    /// Camera center y (world).
    pub cy: f32,
    /// Scale factor (world unit → screen px).
    pub scale: f32,
    /// Min allowed scale.
    pub min_scale: f32,
    /// Max allowed scale.
    pub max_scale: f32,
    /// Viewport width in px.
    pub viewport_w: u32,
    /// Viewport height in px.
    pub viewport_h: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ZoomPanError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad scale bounds.
    #[error("bad scale bounds min {min} max {max}")]
    BadScaleBounds {
        /// min.
        min: f32,
        /// max.
        max: f32,
    },
    /// NaN.
    #[error("value is NaN")]
    NanValue,
    /// Viewport zero.
    #[error("viewport dims zero")]
    ViewportZero,
}

impl ZoomPanCanvas {
    /// New.
    pub fn new(
        min_scale: f32,
        max_scale: f32,
        viewport_w: u32,
        viewport_h: u32,
    ) -> Result<Self, ZoomPanError> {
        if min_scale.is_nan() || max_scale.is_nan() {
            return Err(ZoomPanError::NanValue);
        }
        if min_scale <= 0.0 || max_scale < min_scale {
            return Err(ZoomPanError::BadScaleBounds {
                min: min_scale,
                max: max_scale,
            });
        }
        if viewport_w == 0 || viewport_h == 0 {
            return Err(ZoomPanError::ViewportZero);
        }
        // Initial scale = midpoint geometric mean clamped.
        let init = (min_scale * max_scale).sqrt().clamp(min_scale, max_scale);
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            cx: 0.0,
            cy: 0.0,
            scale: init,
            min_scale,
            max_scale,
            viewport_w,
            viewport_h,
        })
    }

    /// Set scale clamped.
    pub fn set_scale(&mut self, scale: f32) -> Result<(), ZoomPanError> {
        if scale.is_nan() {
            return Err(ZoomPanError::NanValue);
        }
        self.scale = scale.clamp(self.min_scale, self.max_scale);
        Ok(())
    }

    /// Pan in screen-space px delta.
    pub fn pan_screen(&mut self, dx_px: f32, dy_px: f32) -> Result<(), ZoomPanError> {
        if dx_px.is_nan() || dy_px.is_nan() {
            return Err(ZoomPanError::NanValue);
        }
        // Move camera in world coords opposite to pixel pan to give
        // operator the impression of dragging the canvas.
        self.cx -= dx_px / self.scale;
        self.cy -= dy_px / self.scale;
        Ok(())
    }

    /// World → screen.
    pub fn world_to_screen(&self, wx: f32, wy: f32) -> (f32, f32) {
        let sx = (wx - self.cx) * self.scale + self.viewport_w as f32 * 0.5;
        let sy = (wy - self.cy) * self.scale + self.viewport_h as f32 * 0.5;
        (sx, sy)
    }

    /// Screen → world.
    pub fn screen_to_world(&self, sx: f32, sy: f32) -> (f32, f32) {
        let wx = (sx - self.viewport_w as f32 * 0.5) / self.scale + self.cx;
        let wy = (sy - self.viewport_h as f32 * 0.5) / self.scale + self.cy;
        (wx, wy)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ZoomPanError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ZoomPanError::SchemaMismatch);
        }
        if self.scale.is_nan() || self.cx.is_nan() || self.cy.is_nan() {
            return Err(ZoomPanError::NanValue);
        }
        if self.min_scale <= 0.0 || self.max_scale < self.min_scale {
            return Err(ZoomPanError::BadScaleBounds {
                min: self.min_scale,
                max: self.max_scale,
            });
        }
        if self.viewport_w == 0 || self.viewport_h == 0 {
            return Err(ZoomPanError::ViewportZero);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn c() -> ZoomPanCanvas {
        ZoomPanCanvas::new(0.1, 10.0, 800, 600).unwrap()
    }

    #[test]
    fn bad_bounds_rejected() {
        assert!(matches!(
            ZoomPanCanvas::new(2.0, 1.0, 800, 600).unwrap_err(),
            ZoomPanError::BadScaleBounds { .. }
        ));
    }

    #[test]
    fn viewport_zero_rejected() {
        assert!(matches!(
            ZoomPanCanvas::new(0.1, 10.0, 0, 600).unwrap_err(),
            ZoomPanError::ViewportZero
        ));
    }

    #[test]
    fn nan_scale_rejected_on_construction() {
        assert!(matches!(
            ZoomPanCanvas::new(f32::NAN, 10.0, 800, 600).unwrap_err(),
            ZoomPanError::NanValue
        ));
    }

    #[test]
    fn set_scale_clamps() {
        let mut c = c();
        c.set_scale(1000.0).unwrap();
        assert_eq!(c.scale, 10.0);
        c.set_scale(0.0).unwrap();
        assert_eq!(c.scale, 0.1);
    }

    #[test]
    fn pan_moves_camera_opposite_direction() {
        let mut c = c();
        c.scale = 1.0;
        let before = c.cx;
        c.pan_screen(100.0, 0.0).unwrap();
        assert!(c.cx < before);
    }

    #[test]
    fn world_to_screen_roundtrip() {
        let c = c();
        let (sx, sy) = c.world_to_screen(50.0, 30.0);
        let (wx, wy) = c.screen_to_world(sx, sy);
        assert!((wx - 50.0).abs() < 0.01);
        assert!((wy - 30.0).abs() < 0.01);
    }

    #[test]
    fn nan_pan_rejected() {
        let mut c = c();
        assert!(matches!(
            c.pan_screen(f32::NAN, 0.0).unwrap_err(),
            ZoomPanError::NanValue
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = c();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            ZoomPanError::SchemaMismatch
        ));
    }

    #[test]
    fn canvas_serde_roundtrip() {
        let c = c();
        let j = serde_json::to_string(&c).unwrap();
        let back: ZoomPanCanvas = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
