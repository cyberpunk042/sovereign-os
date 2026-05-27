//! `sovereign-cockpit-marquee-loop` — horizontal-loop offset for overflowing labels.
//!
//! If `text_px <= container_px`, the label is static at offset 0
//! (`State::Static`). Otherwise it scrolls left at `speed_px_per_s`,
//! looping over `cycle_px = text_px + gap_px`. Returned offset is the
//! current `x_offset` in [0, cycle_px). `reduced_motion = true` forces
//! `State::Static` regardless of overflow.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Marquee state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// No animation; offset 0.
    Static,
    /// Looping; offset varies.
    Looping,
}

/// Frame result.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Frame {
    /// state.
    pub state: State,
    /// x_offset px (always 0 if Static).
    pub x_offset_px: u32,
    /// cycle width px (0 if Static).
    pub cycle_px: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MarqueeLoop {
    /// Schema version.
    pub schema_version: String,
    /// Speed (px/s).
    pub speed_px_per_s: u32,
    /// Gap between repetitions (px).
    pub gap_px: u32,
    /// Reduced motion override.
    pub reduced_motion: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MarqueeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Speed zero in looping mode is allowed (Static), but if reduced-motion is off and we are looping speed must be > 0.
    #[error("speed_px_per_s must be > 0")]
    SpeedZero,
}

impl MarqueeLoop {
    /// New.
    pub fn new(
        speed_px_per_s: u32,
        gap_px: u32,
        reduced_motion: bool,
    ) -> Result<Self, MarqueeError> {
        if speed_px_per_s == 0 && !reduced_motion {
            return Err(MarqueeError::SpeedZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            speed_px_per_s,
            gap_px,
            reduced_motion,
        })
    }

    /// Compute frame at time `t_ms`.
    pub fn frame(&self, text_px: u32, container_px: u32, t_ms: u64) -> Frame {
        if self.reduced_motion || text_px <= container_px {
            return Frame {
                state: State::Static,
                x_offset_px: 0,
                cycle_px: 0,
            };
        }
        let cycle_px = text_px.saturating_add(self.gap_px);
        // offset = (speed * t_ms / 1000) mod cycle_px
        let micro_px = (self.speed_px_per_s as u128) * (t_ms as u128);
        let px = (micro_px / 1000u128) as u128;
        let x_offset_px = (px % (cycle_px as u128)) as u32;
        Frame {
            state: State::Looping,
            x_offset_px,
            cycle_px,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MarqueeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MarqueeError::SchemaMismatch);
        }
        if self.speed_px_per_s == 0 && !self.reduced_motion {
            return Err(MarqueeError::SpeedZero);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn speed_zero_rejected_unless_reduced() {
        assert!(matches!(
            MarqueeLoop::new(0, 20, false).unwrap_err(),
            MarqueeError::SpeedZero
        ));
        MarqueeLoop::new(0, 20, true).unwrap();
    }

    #[test]
    fn static_when_text_fits() {
        let m = MarqueeLoop::new(40, 16, false).unwrap();
        let f = m.frame(100, 200, 1000);
        assert_eq!(f.state, State::Static);
        assert_eq!(f.x_offset_px, 0);
    }

    #[test]
    fn looping_when_overflow() {
        let m = MarqueeLoop::new(50, 10, false).unwrap();
        let f = m.frame(400, 200, 0);
        assert_eq!(f.state, State::Looping);
        assert_eq!(f.cycle_px, 410);
        assert_eq!(f.x_offset_px, 0);
    }

    #[test]
    fn offset_advances_with_time() {
        let m = MarqueeLoop::new(50, 10, false).unwrap();
        // 1 second @ 50 px/s = 50 px.
        let f = m.frame(400, 200, 1000);
        assert_eq!(f.x_offset_px, 50);
    }

    #[test]
    fn offset_wraps() {
        let m = MarqueeLoop::new(50, 10, false).unwrap();
        // cycle 410, 10 seconds @ 50 = 500 px, 500 mod 410 = 90.
        let f = m.frame(400, 200, 10_000);
        assert_eq!(f.x_offset_px, 90);
    }

    #[test]
    fn reduced_motion_static() {
        let m = MarqueeLoop::new(50, 10, true).unwrap();
        let f = m.frame(1000, 100, 5000);
        assert_eq!(f.state, State::Static);
        assert_eq!(f.x_offset_px, 0);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = MarqueeLoop::new(50, 10, false).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            MarqueeError::SchemaMismatch
        ));
    }

    #[test]
    fn marquee_serde_roundtrip() {
        let m = MarqueeLoop::new(50, 10, false).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: MarqueeLoop = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
