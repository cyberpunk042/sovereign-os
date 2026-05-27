//! `sovereign-cockpit-image-viewer-zoom` — discrete-zoom + pan state.
//!
//! Image dims + viewport dims + zoom level (% in
//! [25, 50, 75, 100, 125, 150, 200, 300, 400]) + (pan_x_px, pan_y_px)
//! clamped so the image stays at least partially on-screen.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Allowed zoom levels (in percent).
pub const ZOOM_LEVELS: [u16; 9] = [25, 50, 75, 100, 125, 150, 200, 300, 400];

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImageViewerZoom {
    /// Schema version.
    pub schema_version: String,
    /// Image width in native px.
    pub image_w: u32,
    /// Image height in native px.
    pub image_h: u32,
    /// Viewport width in px.
    pub viewport_w: u32,
    /// Viewport height in px.
    pub viewport_h: u32,
    /// Current zoom percent.
    pub zoom_pct: u16,
    /// Pan offset x (px in image-space relative to viewport center).
    pub pan_x_px: i32,
    /// Pan offset y.
    pub pan_y_px: i32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ZoomError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Image dims zero.
    #[error("image dims zero")]
    ImageZero,
    /// Viewport dims zero.
    #[error("viewport dims zero")]
    ViewportZero,
    /// Zoom not in allowed levels.
    #[error("zoom_pct {0} not in ZOOM_LEVELS")]
    BadZoom(u16),
}

impl ImageViewerZoom {
    /// New (pan zero, fit-to-viewport zoom by default).
    pub fn new(
        image_w: u32,
        image_h: u32,
        viewport_w: u32,
        viewport_h: u32,
    ) -> Result<Self, ZoomError> {
        if image_w == 0 || image_h == 0 {
            return Err(ZoomError::ImageZero);
        }
        if viewport_w == 0 || viewport_h == 0 {
            return Err(ZoomError::ViewportZero);
        }
        let mut v = Self {
            schema_version: SCHEMA_VERSION.into(),
            image_w,
            image_h,
            viewport_w,
            viewport_h,
            zoom_pct: 100,
            pan_x_px: 0,
            pan_y_px: 0,
        };
        v.zoom_pct = v.fit_to_viewport_zoom();
        Ok(v)
    }

    /// Largest zoom level that still fits the image entirely in the viewport.
    pub fn fit_to_viewport_zoom(&self) -> u16 {
        let max_x = ((self.viewport_w as u64) * 100) / self.image_w as u64;
        let max_y = ((self.viewport_h as u64) * 100) / self.image_h as u64;
        let max = max_x.min(max_y) as u16;
        let mut best = ZOOM_LEVELS[0];
        for &z in &ZOOM_LEVELS {
            if z <= max {
                best = z;
            }
        }
        best
    }

    /// Set zoom to a specific allowed level. Re-clamps pan.
    pub fn set_zoom(&mut self, zoom_pct: u16) -> Result<(), ZoomError> {
        if !ZOOM_LEVELS.contains(&zoom_pct) {
            return Err(ZoomError::BadZoom(zoom_pct));
        }
        self.zoom_pct = zoom_pct;
        let (x, y) = (self.pan_x_px, self.pan_y_px);
        self.set_pan(x, y);
        Ok(())
    }

    /// Step zoom up one level (saturating at max).
    pub fn zoom_in(&mut self) {
        let cur = self.zoom_pct;
        if let Some(pos) = ZOOM_LEVELS.iter().position(|&z| z == cur)
            && pos + 1 < ZOOM_LEVELS.len()
        {
            self.zoom_pct = ZOOM_LEVELS[pos + 1];
            let (x, y) = (self.pan_x_px, self.pan_y_px);
            self.set_pan(x, y);
        }
    }

    /// Step zoom down one level (saturating at min).
    pub fn zoom_out(&mut self) {
        let cur = self.zoom_pct;
        if let Some(pos) = ZOOM_LEVELS.iter().position(|&z| z == cur)
            && pos > 0
        {
            self.zoom_pct = ZOOM_LEVELS[pos - 1];
            let (x, y) = (self.pan_x_px, self.pan_y_px);
            self.set_pan(x, y);
        }
    }

    /// Effective rendered image size in viewport px.
    pub fn rendered_w(&self) -> u32 {
        (self.image_w as u64 * self.zoom_pct as u64 / 100) as u32
    }

    /// Effective rendered image height.
    pub fn rendered_h(&self) -> u32 {
        (self.image_h as u64 * self.zoom_pct as u64 / 100) as u32
    }

    /// Set pan clamped so at least 1 px of the image is on-screen
    /// (technically: image's bbox center stays within viewport).
    pub fn set_pan(&mut self, x: i32, y: i32) {
        let rw = self.rendered_w() as i32;
        let rh = self.rendered_h() as i32;
        let vw = self.viewport_w as i32;
        let vh = self.viewport_h as i32;
        // Allow pan up to ±(rendered/2) so center stays in viewport.
        let max_x = (rw / 2).max(0);
        let max_y = (rh / 2).max(0);
        // Tighter constraint when image larger than viewport: cap so edge meets viewport edge.
        let edge_x = (rw - vw).max(0) / 2;
        let edge_y = (rh - vh).max(0) / 2;
        let cap_x = max_x.max(edge_x);
        let cap_y = max_y.max(edge_y);
        self.pan_x_px = x.clamp(-cap_x, cap_x);
        self.pan_y_px = y.clamp(-cap_y, cap_y);
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ZoomError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ZoomError::SchemaMismatch);
        }
        if self.image_w == 0 || self.image_h == 0 {
            return Err(ZoomError::ImageZero);
        }
        if self.viewport_w == 0 || self.viewport_h == 0 {
            return Err(ZoomError::ViewportZero);
        }
        if !ZOOM_LEVELS.contains(&self.zoom_pct) {
            return Err(ZoomError::BadZoom(self.zoom_pct));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn image_zero_rejected() {
        assert!(matches!(
            ImageViewerZoom::new(0, 100, 100, 100).unwrap_err(),
            ZoomError::ImageZero
        ));
    }

    #[test]
    fn viewport_zero_rejected() {
        assert!(matches!(
            ImageViewerZoom::new(100, 100, 0, 100).unwrap_err(),
            ZoomError::ViewportZero
        ));
    }

    #[test]
    fn fit_to_viewport_default() {
        let v = ImageViewerZoom::new(200, 200, 200, 200).unwrap();
        assert_eq!(v.zoom_pct, 100);
    }

    #[test]
    fn fit_shrinks_to_largest_step() {
        let v = ImageViewerZoom::new(400, 400, 200, 200).unwrap();
        // 200/400 = 50%, largest step <= 50 = 50.
        assert_eq!(v.zoom_pct, 50);
    }

    #[test]
    fn zoom_in_steps() {
        let mut v = ImageViewerZoom::new(100, 100, 200, 200).unwrap();
        v.set_zoom(100).unwrap();
        v.zoom_in();
        assert_eq!(v.zoom_pct, 125);
    }

    #[test]
    fn zoom_in_caps_at_max() {
        let mut v = ImageViewerZoom::new(100, 100, 200, 200).unwrap();
        v.set_zoom(400).unwrap();
        v.zoom_in();
        assert_eq!(v.zoom_pct, 400);
    }

    #[test]
    fn zoom_out_caps_at_min() {
        let mut v = ImageViewerZoom::new(100, 100, 200, 200).unwrap();
        v.set_zoom(25).unwrap();
        v.zoom_out();
        assert_eq!(v.zoom_pct, 25);
    }

    #[test]
    fn bad_zoom_rejected() {
        let mut v = ImageViewerZoom::new(100, 100, 200, 200).unwrap();
        assert!(matches!(
            v.set_zoom(33).unwrap_err(),
            ZoomError::BadZoom(33)
        ));
    }

    #[test]
    fn set_pan_clamped() {
        let mut v = ImageViewerZoom::new(100, 100, 200, 200).unwrap();
        v.set_zoom(200).unwrap();
        v.set_pan(99999, -99999);
        // Image rendered = 200x200 at zoom 200% = 400x400, but new() called fit -> 100% rendered=200.
        // After set_zoom(200), rendered = 200; clamp magnitude.
        assert!(v.pan_x_px.abs() <= 200);
        assert!(v.pan_y_px.abs() <= 200);
    }

    #[test]
    fn rendered_dims_scale_with_zoom() {
        let mut v = ImageViewerZoom::new(100, 200, 500, 500).unwrap();
        v.set_zoom(200).unwrap();
        assert_eq!(v.rendered_w(), 200);
        assert_eq!(v.rendered_h(), 400);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut v = ImageViewerZoom::new(100, 100, 200, 200).unwrap();
        v.schema_version = "9.9.9".into();
        assert!(matches!(
            v.validate().unwrap_err(),
            ZoomError::SchemaMismatch
        ));
    }

    #[test]
    fn viewer_serde_roundtrip() {
        let v = ImageViewerZoom::new(100, 100, 200, 200).unwrap();
        let j = serde_json::to_string(&v).unwrap();
        let back: ImageViewerZoom = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }
}
