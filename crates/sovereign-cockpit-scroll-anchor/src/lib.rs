//! `sovereign-cockpit-scroll-anchor` — stable-position scroll.
//!
//! Tracks content_height + scroll_offset. When content_height
//! grows by N (prepended), apply_insert(n) shifts scroll_offset
//! by +n to keep the visible portion fixed. mode{Top/Bottom/
//! Anchored}: Top keeps offset 0; Bottom snaps to (content -
//! viewport); Anchored maintains relative.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Anchor mode.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Stay at top (offset 0).
    Top,
    /// Stick to bottom.
    Bottom,
    /// Maintain visible window.
    Anchored,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ScrollAnchor {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: Mode,
    /// Viewport height.
    pub viewport_h: u32,
    /// Content height.
    pub content_h: u32,
    /// Current scroll offset.
    pub scroll_offset: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AnchorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero viewport.
    #[error("viewport_h must be >= 1")]
    ZeroViewport,
}

impl ScrollAnchor {
    /// New.
    pub fn new(viewport_h: u32, content_h: u32, mode: Mode) -> Result<Self, AnchorError> {
        if viewport_h == 0 { return Err(AnchorError::ZeroViewport); }
        let mut s = Self {
            schema_version: SCHEMA_VERSION.into(),
            mode,
            viewport_h,
            content_h,
            scroll_offset: 0,
        };
        s.snap();
        Ok(s)
    }

    /// Set scroll offset (clamped).
    pub fn set_offset(&mut self, offset: u32) {
        let max = self.content_h.saturating_sub(self.viewport_h);
        self.scroll_offset = offset.min(max);
    }

    /// Snap by mode (Top→0, Bottom→max, Anchored leaves unchanged but clamps).
    fn snap(&mut self) {
        let max = self.content_h.saturating_sub(self.viewport_h);
        match self.mode {
            Mode::Top => self.scroll_offset = 0,
            Mode::Bottom => self.scroll_offset = max,
            Mode::Anchored => self.scroll_offset = self.scroll_offset.min(max),
        }
    }

    /// Apply prepend of `n` px (content grows from top).
    pub fn apply_prepend(&mut self, n: u32) {
        self.content_h = self.content_h.saturating_add(n);
        match self.mode {
            Mode::Anchored => {
                // Shift offset by +n to keep visible content stable.
                let max = self.content_h.saturating_sub(self.viewport_h);
                self.scroll_offset = self.scroll_offset.saturating_add(n).min(max);
            }
            Mode::Top => self.scroll_offset = 0,
            Mode::Bottom => {
                self.scroll_offset = self.content_h.saturating_sub(self.viewport_h);
            }
        }
    }

    /// Apply append of `n` px (content grows from bottom).
    pub fn apply_append(&mut self, n: u32) {
        self.content_h = self.content_h.saturating_add(n);
        self.snap();
    }

    /// True iff at bottom.
    pub fn at_bottom(&self) -> bool {
        let max = self.content_h.saturating_sub(self.viewport_h);
        self.scroll_offset >= max
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AnchorError> {
        if self.schema_version != SCHEMA_VERSION { return Err(AnchorError::SchemaMismatch); }
        if self.viewport_h == 0 { return Err(AnchorError::ZeroViewport); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn top_mode_keeps_zero() {
        let mut a = ScrollAnchor::new(100, 500, Mode::Top).unwrap();
        a.apply_prepend(50);
        assert_eq!(a.scroll_offset, 0);
    }

    #[test]
    fn bottom_mode_sticks_to_bottom() {
        let mut a = ScrollAnchor::new(100, 500, Mode::Bottom).unwrap();
        assert_eq!(a.scroll_offset, 400);
        a.apply_append(100);
        assert_eq!(a.scroll_offset, 500); // content 600 - viewport 100
        assert!(a.at_bottom());
    }

    #[test]
    fn anchored_prepend_shifts_offset() {
        let mut a = ScrollAnchor::new(100, 500, Mode::Anchored).unwrap();
        a.set_offset(200);
        a.apply_prepend(50);
        // Visible content stays fixed → offset += 50.
        assert_eq!(a.scroll_offset, 250);
        assert_eq!(a.content_h, 550);
    }

    #[test]
    fn anchored_append_keeps_offset() {
        let mut a = ScrollAnchor::new(100, 500, Mode::Anchored).unwrap();
        a.set_offset(200);
        a.apply_append(100);
        assert_eq!(a.scroll_offset, 200);
    }

    #[test]
    fn offset_clamps_to_max() {
        let mut a = ScrollAnchor::new(100, 500, Mode::Anchored).unwrap();
        a.set_offset(9999);
        assert_eq!(a.scroll_offset, 400);
    }

    #[test]
    fn zero_viewport_rejected() {
        assert!(matches!(ScrollAnchor::new(0, 100, Mode::Top).unwrap_err(), AnchorError::ZeroViewport));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut a = ScrollAnchor::new(100, 500, Mode::Top).unwrap();
        a.schema_version = "9.9.9".into();
        assert!(matches!(a.validate().unwrap_err(), AnchorError::SchemaMismatch));
    }

    #[test]
    fn anchor_serde_roundtrip() {
        let mut a = ScrollAnchor::new(100, 500, Mode::Anchored).unwrap();
        a.set_offset(200);
        let j = serde_json::to_string(&a).unwrap();
        let back: ScrollAnchor = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
