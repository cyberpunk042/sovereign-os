//! `sovereign-cockpit-hover-card` — dwell-gated hover preview.
//!
//! State machine: Idle → Pending (after hover_enter) → Visible (when
//! dwell elapsed) → FadingOut (after hover_leave, fade_out_ms) → Idle.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Phase {
    /// No hover.
    Idle,
    /// Hover started; waiting for dwell.
    Pending,
    /// Visible.
    Visible,
    /// Fading out.
    FadingOut,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HoverCard {
    /// Schema version.
    pub schema_version: String,
    /// Dwell time before Visible.
    pub dwell_ms: u32,
    /// Fade-out duration after leave.
    pub fade_out_ms: u32,
    /// Phase.
    pub phase: Phase,
    /// Target id under cursor (or empty).
    pub target_id: String,
    /// Time hover_enter was last observed.
    pub entered_at_ms: u64,
    /// Time hover_leave was last observed.
    pub left_at_ms: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HoverError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Dwell zero.
    #[error("dwell_ms is zero")]
    DwellZero,
    /// Fade zero.
    #[error("fade_out_ms is zero")]
    FadeZero,
}

impl HoverCard {
    /// New idle.
    pub fn new(dwell_ms: u32, fade_out_ms: u32) -> Result<Self, HoverError> {
        if dwell_ms == 0 { return Err(HoverError::DwellZero); }
        if fade_out_ms == 0 { return Err(HoverError::FadeZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            dwell_ms, fade_out_ms,
            phase: Phase::Idle,
            target_id: String::new(),
            entered_at_ms: 0,
            left_at_ms: 0,
        })
    }

    /// Cursor entered a target.
    pub fn hover_enter(&mut self, id: &str, now_ms: u64) {
        if self.target_id != id {
            self.target_id = id.into();
            self.phase = Phase::Pending;
            self.entered_at_ms = now_ms;
        }
    }

    /// Cursor left.
    pub fn hover_leave(&mut self, now_ms: u64) {
        match self.phase {
            Phase::Pending => {
                self.phase = Phase::Idle;
                self.target_id.clear();
            }
            Phase::Visible => {
                self.phase = Phase::FadingOut;
                self.left_at_ms = now_ms;
            }
            _ => {}
        }
    }

    /// Tick.
    pub fn tick(&mut self, now_ms: u64) {
        match self.phase {
            Phase::Pending => {
                if now_ms.saturating_sub(self.entered_at_ms) >= self.dwell_ms as u64 {
                    self.phase = Phase::Visible;
                }
            }
            Phase::FadingOut => {
                if now_ms.saturating_sub(self.left_at_ms) >= self.fade_out_ms as u64 {
                    self.phase = Phase::Idle;
                    self.target_id.clear();
                }
            }
            _ => {}
        }
    }

    /// Is card visible-renderable?
    pub fn is_renderable(&self) -> bool {
        matches!(self.phase, Phase::Visible | Phase::FadingOut)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HoverError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HoverError::SchemaMismatch);
        }
        if self.dwell_ms == 0 { return Err(HoverError::DwellZero); }
        if self.fade_out_ms == 0 { return Err(HoverError::FadeZero); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h() -> HoverCard {
        HoverCard::new(500, 200).unwrap()
    }

    #[test]
    fn dwell_zero_rejected() {
        assert!(matches!(HoverCard::new(0, 100).unwrap_err(), HoverError::DwellZero));
    }

    #[test]
    fn fade_zero_rejected() {
        assert!(matches!(HoverCard::new(100, 0).unwrap_err(), HoverError::FadeZero));
    }

    #[test]
    fn idle_initially() {
        let h = h();
        assert_eq!(h.phase, Phase::Idle);
        assert!(!h.is_renderable());
    }

    #[test]
    fn enter_goes_pending() {
        let mut h = h();
        h.hover_enter("x", 100);
        assert_eq!(h.phase, Phase::Pending);
        assert!(!h.is_renderable());
    }

    #[test]
    fn dwell_promotes_to_visible() {
        let mut h = h();
        h.hover_enter("x", 100);
        h.tick(700); // 600 elapsed > 500 dwell
        assert_eq!(h.phase, Phase::Visible);
        assert!(h.is_renderable());
    }

    #[test]
    fn leave_pending_resets_idle() {
        let mut h = h();
        h.hover_enter("x", 100);
        h.hover_leave(200);
        assert_eq!(h.phase, Phase::Idle);
    }

    #[test]
    fn leave_visible_goes_fading() {
        let mut h = h();
        h.hover_enter("x", 100);
        h.tick(700);
        h.hover_leave(800);
        assert_eq!(h.phase, Phase::FadingOut);
        assert!(h.is_renderable());
    }

    #[test]
    fn fade_completes_to_idle() {
        let mut h = h();
        h.hover_enter("x", 100);
        h.tick(700);
        h.hover_leave(800);
        h.tick(1100); // 300ms after leave > 200 fade
        assert_eq!(h.phase, Phase::Idle);
        assert!(h.target_id.is_empty());
    }

    #[test]
    fn switch_target_resets_pending() {
        let mut h = h();
        h.hover_enter("a", 100);
        h.hover_enter("b", 200);
        assert_eq!(h.target_id, "b");
        assert_eq!(h.entered_at_ms, 200);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = h();
        h.schema_version = "9.9.9".into();
        assert!(matches!(h.validate().unwrap_err(), HoverError::SchemaMismatch));
    }

    #[test]
    fn phase_serde_kebab() {
        assert_eq!(serde_json::to_string(&Phase::FadingOut).unwrap(), "\"fading-out\"");
    }

    #[test]
    fn card_serde_roundtrip() {
        let mut h = h();
        h.hover_enter("x", 100);
        let j = serde_json::to_string(&h).unwrap();
        let back: HoverCard = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
