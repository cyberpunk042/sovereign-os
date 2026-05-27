//! `sovereign-cockpit-scroll-shadow-state` — scroll shadow toggles.
//!
//! Given scroll position + viewport_h + content_h, derive whether
//! to show top/bottom shadow.
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
pub struct ScrollShadowState {
    /// Schema version marker.
    pub schema_version_marker: u32,
    /// Current scroll top (px).
    pub scroll_top: u64,
    /// Viewport height.
    pub viewport_h: u64,
    /// Content height.
    pub content_h: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ShadowError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero viewport.
    #[error("viewport must be > 0")]
    ZeroViewport,
}

impl ScrollShadowState {
    /// New.
    pub fn new(viewport_h: u64, content_h: u64) -> Result<Self, ShadowError> {
        if viewport_h == 0 {
            return Err(ShadowError::ZeroViewport);
        }
        Ok(Self {
            schema_version_marker: 1,
            scroll_top: 0,
            viewport_h,
            content_h,
        })
    }

    /// Update scroll position.
    pub fn set_scroll(&mut self, scroll_top: u64) {
        let max = self.content_h.saturating_sub(self.viewport_h);
        self.scroll_top = scroll_top.min(max);
    }

    /// Set heights (clamps scroll).
    pub fn set_heights(&mut self, viewport_h: u64, content_h: u64) -> Result<(), ShadowError> {
        if viewport_h == 0 {
            return Err(ShadowError::ZeroViewport);
        }
        self.viewport_h = viewport_h;
        self.content_h = content_h;
        let max = self.content_h.saturating_sub(self.viewport_h);
        if self.scroll_top > max {
            self.scroll_top = max;
        }
        Ok(())
    }

    /// Show top shadow (content above the viewport)?
    pub fn show_top(&self) -> bool {
        self.scroll_top > 0
    }

    /// Show bottom shadow (content below the viewport)?
    pub fn show_bottom(&self) -> bool {
        self.scroll_top + self.viewport_h < self.content_h
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ShadowError> {
        if self.schema_version_marker != 1 {
            return Err(ShadowError::SchemaMismatch);
        }
        if self.viewport_h == 0 {
            return Err(ShadowError::ZeroViewport);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_shadows_when_content_fits() {
        let s = ScrollShadowState::new(500, 400).unwrap();
        assert!(!s.show_top());
        assert!(!s.show_bottom());
    }

    #[test]
    fn bottom_shadow_when_more_below() {
        let s = ScrollShadowState::new(500, 2000).unwrap();
        assert!(!s.show_top());
        assert!(s.show_bottom());
    }

    #[test]
    fn top_shadow_when_scrolled() {
        let mut s = ScrollShadowState::new(500, 2000).unwrap();
        s.set_scroll(100);
        assert!(s.show_top());
        assert!(s.show_bottom());
    }

    #[test]
    fn no_bottom_at_end() {
        let mut s = ScrollShadowState::new(500, 2000).unwrap();
        s.set_scroll(1500);
        assert!(s.show_top());
        assert!(!s.show_bottom());
    }

    #[test]
    fn set_scroll_clamps() {
        let mut s = ScrollShadowState::new(500, 2000).unwrap();
        s.set_scroll(10_000);
        assert_eq!(s.scroll_top, 1500);
    }

    #[test]
    fn set_heights_clamps_scroll() {
        let mut s = ScrollShadowState::new(500, 2000).unwrap();
        s.set_scroll(1500);
        s.set_heights(500, 800).unwrap();
        assert_eq!(s.scroll_top, 300);
    }

    #[test]
    fn zero_viewport_rejected() {
        assert!(matches!(
            ScrollShadowState::new(0, 100).unwrap_err(),
            ShadowError::ZeroViewport
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ScrollShadowState::new(500, 2000).unwrap();
        s.schema_version_marker = 99;
        assert!(matches!(
            s.validate().unwrap_err(),
            ShadowError::SchemaMismatch
        ));
    }

    #[test]
    fn shadow_serde_roundtrip() {
        let mut s = ScrollShadowState::new(500, 2000).unwrap();
        s.set_scroll(500);
        let j = serde_json::to_string(&s).unwrap();
        let back: ScrollShadowState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
