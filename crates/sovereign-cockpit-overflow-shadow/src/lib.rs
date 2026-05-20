//! `sovereign-cockpit-overflow-shadow` — top/bottom shadow when content overflows.
//!
//! Given `(scroll_top, viewport_h, content_h)`, compute:
//!   * top shadow intensity 0..=255: ramps over `fade_px` as scroll_top
//!     increases from 0 to fade_px.
//!   * bottom shadow intensity 0..=255: ramps over `fade_px` as
//!     `bottom_distance = content_h - viewport_h - scroll_top`
//!     decreases from fade_px to 0.
//!
//! Returns a `ShadowState` with both intensities + a coarse `Edge` enum
//! for renderers that only want a discrete signal.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Coarse edge classification.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Edge {
    /// No shadow.
    None,
    /// Top only.
    Top,
    /// Bottom only.
    Bottom,
    /// Both.
    Both,
}

/// Computed state.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct ShadowState {
    /// Edge classification.
    pub edge: Edge,
    /// Top shadow intensity 0..=255.
    pub top_intensity: u8,
    /// Bottom shadow intensity 0..=255.
    pub bottom_intensity: u8,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct OverflowShadow {
    /// Schema version.
    pub schema_version: String,
    /// Pixels over which the shadow ramps from 0 to full.
    pub fade_px: u32,
    /// Last computed state.
    pub last: Option<ShadowState>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ShadowError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// fade_px zero.
    #[error("fade_px must be > 0")]
    FadeZero,
}

impl OverflowShadow {
    /// New.
    pub fn new(fade_px: u32) -> Result<Self, ShadowError> {
        if fade_px == 0 { return Err(ShadowError::FadeZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            fade_px,
            last: None,
        })
    }

    /// Compute shadow state for a region.
    pub fn compute(&mut self, scroll_top: u32, viewport_h: u32, content_h: u32) -> ShadowState {
        let top_distance = scroll_top;
        let bottom_distance = content_h.saturating_sub(viewport_h).saturating_sub(scroll_top);

        let top_intensity = ramp(top_distance, self.fade_px);
        let bottom_intensity = ramp(bottom_distance, self.fade_px);

        let edge = match (top_intensity > 0, bottom_intensity > 0) {
            (true, true) => Edge::Both,
            (true, false) => Edge::Top,
            (false, true) => Edge::Bottom,
            (false, false) => Edge::None,
        };
        let s = ShadowState { edge, top_intensity, bottom_intensity };
        self.last = Some(s);
        s
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ShadowError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ShadowError::SchemaMismatch); }
        if self.fade_px == 0 { return Err(ShadowError::FadeZero); }
        Ok(())
    }
}

fn ramp(distance: u32, fade_px: u32) -> u8 {
    if distance == 0 { return 0; }
    if distance >= fade_px { return 255; }
    ((distance as u64) * 255 / (fade_px as u64)) as u8
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fade_zero_rejected() {
        assert!(matches!(OverflowShadow::new(0).unwrap_err(), ShadowError::FadeZero));
    }

    #[test]
    fn content_fits_no_shadow() {
        let mut s = OverflowShadow::new(16).unwrap();
        let st = s.compute(0, 500, 400);
        assert_eq!(st.edge, Edge::None);
        assert_eq!(st.top_intensity, 0);
        assert_eq!(st.bottom_intensity, 0);
    }

    #[test]
    fn scrolled_to_top_only_bottom() {
        let mut s = OverflowShadow::new(16).unwrap();
        let st = s.compute(0, 500, 2000);
        assert_eq!(st.edge, Edge::Bottom);
        assert_eq!(st.top_intensity, 0);
        assert_eq!(st.bottom_intensity, 255);
    }

    #[test]
    fn scrolled_to_bottom_only_top() {
        let mut s = OverflowShadow::new(16).unwrap();
        let st = s.compute(1500, 500, 2000);
        assert_eq!(st.edge, Edge::Top);
        assert_eq!(st.top_intensity, 255);
        assert_eq!(st.bottom_intensity, 0);
    }

    #[test]
    fn scrolled_middle_both() {
        let mut s = OverflowShadow::new(16).unwrap();
        let st = s.compute(500, 500, 2000);
        assert_eq!(st.edge, Edge::Both);
        assert_eq!(st.top_intensity, 255);
        assert_eq!(st.bottom_intensity, 255);
    }

    #[test]
    fn ramp_partial() {
        let mut s = OverflowShadow::new(100).unwrap();
        let st = s.compute(50, 500, 2000);
        // Top distance 50 → 50*255/100 = 127.
        assert_eq!(st.top_intensity, 127);
    }

    #[test]
    fn last_persists() {
        let mut s = OverflowShadow::new(16).unwrap();
        s.compute(100, 500, 2000);
        assert!(s.last.is_some());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = OverflowShadow::new(16).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), ShadowError::SchemaMismatch));
    }

    #[test]
    fn shadow_serde_roundtrip() {
        let mut s = OverflowShadow::new(16).unwrap();
        s.compute(100, 500, 2000);
        let j = serde_json::to_string(&s).unwrap();
        let back: OverflowShadow = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
