//! `sovereign-cockpit-side-nav-state` — collapsible side-nav state.
//!
//! Operator-managed (anchor, state, width). 3 states: Collapsed (icon
//! rail only), Expanded (full nav), Pinned (always-shown, no auto-hide).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Anchor side.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Anchor {
    /// Left side.
    Left,
    /// Right side.
    Right,
}

/// Nav state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum NavState {
    /// Collapsed (icon rail only).
    Collapsed,
    /// Expanded (full nav, auto-hides on mouse out).
    Expanded,
    /// Pinned (always shown).
    Pinned,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SideNavState {
    /// Schema version.
    pub schema_version: String,
    /// Anchor.
    pub anchor: Anchor,
    /// State.
    pub state: NavState,
    /// Expanded / pinned width in px (60..400 valid range).
    pub width_px: u16,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SideNavError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Width out of range.
    #[error("width_px {0} outside 60..=400")]
    WidthOutOfRange(u16),
}

impl SideNavState {
    /// Default state — left-anchored expanded at 240px.
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            anchor: Anchor::Left,
            state: NavState::Expanded,
            width_px: 240,
        }
    }

    /// Toggle Collapsed ↔ Expanded (no-op when Pinned).
    pub fn toggle(&mut self) {
        self.state = match self.state {
            NavState::Collapsed => NavState::Expanded,
            NavState::Expanded => NavState::Collapsed,
            NavState::Pinned => NavState::Pinned,
        };
    }

    /// Pin (always-shown).
    pub fn pin(&mut self) {
        self.state = NavState::Pinned;
    }

    /// Unpin (drop back to Expanded).
    pub fn unpin(&mut self) {
        if self.state == NavState::Pinned {
            self.state = NavState::Expanded;
        }
    }

    /// Flip anchor.
    pub fn flip_anchor(&mut self) {
        self.anchor = match self.anchor {
            Anchor::Left => Anchor::Right,
            Anchor::Right => Anchor::Left,
        };
    }

    /// Set width; returns clamped value.
    pub fn set_width(&mut self, w: u16) -> u16 {
        let clamped = w.clamp(60, 400);
        self.width_px = clamped;
        clamped
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SideNavError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SideNavError::SchemaMismatch);
        }
        if self.width_px < 60 || self.width_px > 400 {
            return Err(SideNavError::WidthOutOfRange(self.width_px));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        SideNavState::default_state().validate().unwrap();
    }

    #[test]
    fn toggle_walks() {
        let mut s = SideNavState::default_state();
        assert_eq!(s.state, NavState::Expanded);
        s.toggle();
        assert_eq!(s.state, NavState::Collapsed);
        s.toggle();
        assert_eq!(s.state, NavState::Expanded);
    }

    #[test]
    fn pinned_toggle_no_op() {
        let mut s = SideNavState::default_state();
        s.pin();
        s.toggle();
        assert_eq!(s.state, NavState::Pinned);
    }

    #[test]
    fn unpin_drops_to_expanded() {
        let mut s = SideNavState::default_state();
        s.pin();
        s.unpin();
        assert_eq!(s.state, NavState::Expanded);
    }

    #[test]
    fn flip_anchor_switches() {
        let mut s = SideNavState::default_state();
        s.flip_anchor();
        assert_eq!(s.anchor, Anchor::Right);
        s.flip_anchor();
        assert_eq!(s.anchor, Anchor::Left);
    }

    #[test]
    fn set_width_clamps() {
        let mut s = SideNavState::default_state();
        let v = s.set_width(10);
        assert_eq!(v, 60);
        let v = s.set_width(9999);
        assert_eq!(v, 400);
        let v = s.set_width(300);
        assert_eq!(v, 300);
    }

    #[test]
    fn width_out_of_range_caught_in_validate() {
        let mut s = SideNavState::default_state();
        s.width_px = 10;
        assert!(matches!(
            s.validate().unwrap_err(),
            SideNavError::WidthOutOfRange(10)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SideNavState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SideNavError::SchemaMismatch
        ));
    }

    #[test]
    fn anchor_serde_kebab() {
        assert_eq!(serde_json::to_string(&Anchor::Left).unwrap(), "\"left\"");
        assert_eq!(serde_json::to_string(&Anchor::Right).unwrap(), "\"right\"");
    }

    #[test]
    fn state_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&NavState::Collapsed).unwrap(),
            "\"collapsed\""
        );
        assert_eq!(
            serde_json::to_string(&NavState::Pinned).unwrap(),
            "\"pinned\""
        );
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = SideNavState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: SideNavState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
