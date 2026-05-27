//! `sovereign-cockpit-pip-window` — picture-in-picture mini-window.
//!
//! PiP wraps a `content_id` (which dashboard or widget to render
//! inline-elsewhere) in a small fixed-corner frame. State tracks the
//! corner, the size (px), and whether the PiP is shown.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Corner.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Corner {
    /// Top-left.
    TopLeft,
    /// Top-right.
    TopRight,
    /// Bottom-left.
    BottomLeft,
    /// Bottom-right.
    BottomRight,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PipWindow {
    /// Schema version.
    pub schema_version: String,
    /// Visible.
    pub visible: bool,
    /// Corner.
    pub corner: Corner,
    /// Width px.
    pub w_px: u32,
    /// Height px.
    pub h_px: u32,
    /// Content id (which widget).
    pub content_id: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PipError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero dim.
    #[error("width/height must be > 0")]
    ZeroDim,
}

impl PipWindow {
    /// New (hidden).
    pub fn new(default_corner: Corner, default_w: u32, default_h: u32) -> Result<Self, PipError> {
        if default_w == 0 || default_h == 0 {
            return Err(PipError::ZeroDim);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            visible: false,
            corner: default_corner,
            w_px: default_w,
            h_px: default_h,
            content_id: None,
        })
    }

    /// Show.
    pub fn show(&mut self, content_id: &str) {
        self.content_id = Some(content_id.into());
        self.visible = true;
    }

    /// Hide.
    pub fn hide(&mut self) {
        self.visible = false;
    }

    /// Move corner.
    pub fn move_to(&mut self, corner: Corner) {
        self.corner = corner;
    }

    /// Resize.
    pub fn resize(&mut self, w_px: u32, h_px: u32) -> Result<(), PipError> {
        if w_px == 0 || h_px == 0 {
            return Err(PipError::ZeroDim);
        }
        self.w_px = w_px;
        self.h_px = h_px;
        Ok(())
    }

    /// Set content.
    pub fn set_content(&mut self, content_id: &str) {
        self.content_id = Some(content_id.into());
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PipError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PipError::SchemaMismatch);
        }
        if self.w_px == 0 || self.h_px == 0 {
            return Err(PipError::ZeroDim);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_dims_rejected() {
        assert!(matches!(
            PipWindow::new(Corner::TopRight, 0, 100).unwrap_err(),
            PipError::ZeroDim
        ));
    }

    #[test]
    fn show_sets_content() {
        let mut p = PipWindow::new(Corner::BottomRight, 320, 180).unwrap();
        p.show("dash-1");
        assert!(p.visible);
        assert_eq!(p.content_id.as_deref(), Some("dash-1"));
    }

    #[test]
    fn hide_clears_visible() {
        let mut p = PipWindow::new(Corner::BottomRight, 320, 180).unwrap();
        p.show("dash-1");
        p.hide();
        assert!(!p.visible);
        // Content id preserved.
        assert!(p.content_id.is_some());
    }

    #[test]
    fn move_corner() {
        let mut p = PipWindow::new(Corner::BottomRight, 320, 180).unwrap();
        p.move_to(Corner::TopLeft);
        assert_eq!(p.corner, Corner::TopLeft);
    }

    #[test]
    fn resize_validates() {
        let mut p = PipWindow::new(Corner::BottomRight, 320, 180).unwrap();
        p.resize(400, 200).unwrap();
        assert_eq!((p.w_px, p.h_px), (400, 200));
        assert!(matches!(p.resize(0, 100).unwrap_err(), PipError::ZeroDim));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = PipWindow::new(Corner::BottomRight, 320, 180).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PipError::SchemaMismatch
        ));
    }

    #[test]
    fn pip_serde_roundtrip() {
        let mut p = PipWindow::new(Corner::BottomRight, 320, 180).unwrap();
        p.show("dash-1");
        let j = serde_json::to_string(&p).unwrap();
        let back: PipWindow = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
