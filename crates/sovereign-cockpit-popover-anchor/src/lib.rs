//! `sovereign-cockpit-popover-anchor` — viewport-clamped popover positioning.
//!
//! Given:
//!   * anchor rect `(ax, ay, aw, ah)`
//!   * popover size `(pw, ph)`
//!   * viewport size `(vw, vh)`
//!   * preferred `Placement`
//!
//! Returns the resolved `(x, y)` of the popover's top-left corner plus
//! the effective placement. Flips to the opposite side when the
//! preferred side overflows the viewport. After placement is chosen,
//! the cross-axis coordinate is clamped to keep the popover inside the
//! viewport.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Side preference.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Placement {
    /// Top.
    Top,
    /// Bottom.
    Bottom,
    /// Left.
    Left,
    /// Right.
    Right,
}

/// Resolved placement result.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct AnchorResult {
    /// resolved x.
    pub x: i32,
    /// resolved y.
    pub y: i32,
    /// effective placement after flips.
    pub placement: Placement,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AnchorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// State (versioned, no per-call state).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PopoverAnchor {
    /// Schema version.
    pub schema_version: String,
    /// Gap (px) between anchor and popover.
    pub gap_px: u32,
}

impl PopoverAnchor {
    /// New.
    pub fn new(gap_px: u32) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            gap_px,
        }
    }

    /// Resolve placement.
    pub fn resolve(
        &self,
        ax: i32,
        ay: i32,
        aw: u32,
        ah: u32,
        pw: u32,
        ph: u32,
        vw: u32,
        vh: u32,
        preferred: Placement,
    ) -> AnchorResult {
        let gap = self.gap_px as i32;
        let pw_i = pw as i32;
        let ph_i = ph as i32;
        let vw_i = vw as i32;
        let vh_i = vh as i32;

        // Decide whether the preferred side fits; if not, flip.
        let placement = match preferred {
            Placement::Top => {
                if ay - gap - ph_i >= 0 {
                    Placement::Top
                } else {
                    Placement::Bottom
                }
            }
            Placement::Bottom => {
                if ay + ah as i32 + gap + ph_i <= vh_i {
                    Placement::Bottom
                } else {
                    Placement::Top
                }
            }
            Placement::Left => {
                if ax - gap - pw_i >= 0 {
                    Placement::Left
                } else {
                    Placement::Right
                }
            }
            Placement::Right => {
                if ax + aw as i32 + gap + pw_i <= vw_i {
                    Placement::Right
                } else {
                    Placement::Left
                }
            }
        };

        // Compute initial (x, y) per chosen side, centering on the cross axis.
        let (mut x, mut y) = match placement {
            Placement::Top => (ax + (aw as i32 - pw_i) / 2, ay - gap - ph_i),
            Placement::Bottom => (ax + (aw as i32 - pw_i) / 2, ay + ah as i32 + gap),
            Placement::Left => (ax - gap - pw_i, ay + (ah as i32 - ph_i) / 2),
            Placement::Right => (ax + aw as i32 + gap, ay + (ah as i32 - ph_i) / 2),
        };

        // Clamp inside viewport.
        if x < 0 {
            x = 0;
        }
        if x + pw_i > vw_i {
            x = vw_i - pw_i;
        }
        if x < 0 {
            x = 0;
        }
        if y < 0 {
            y = 0;
        }
        if y + ph_i > vh_i {
            y = vh_i - ph_i;
        }
        if y < 0 {
            y = 0;
        }

        AnchorResult { x, y, placement }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AnchorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(AnchorError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bottom_when_room_below() {
        let a = PopoverAnchor::new(4);
        let r = a.resolve(100, 100, 50, 30, 80, 40, 800, 600, Placement::Bottom);
        assert_eq!(r.placement, Placement::Bottom);
        // x centered: 100 + (50-80)/2 = 85
        assert_eq!(r.x, 85);
        // y = 100 + 30 + 4 = 134
        assert_eq!(r.y, 134);
    }

    #[test]
    fn flips_to_top_when_no_room_below() {
        let a = PopoverAnchor::new(4);
        // viewport 600; anchor at y=580 with height 10 → bottom+gap+ph = 580+10+4+40=634 > 600.
        let r = a.resolve(100, 580, 50, 10, 80, 40, 800, 600, Placement::Bottom);
        assert_eq!(r.placement, Placement::Top);
    }

    #[test]
    fn flips_to_left_when_no_room_right() {
        let a = PopoverAnchor::new(4);
        let r = a.resolve(750, 100, 30, 30, 80, 40, 800, 600, Placement::Right);
        assert_eq!(r.placement, Placement::Left);
    }

    #[test]
    fn flips_to_right_when_no_room_left() {
        let a = PopoverAnchor::new(4);
        let r = a.resolve(10, 100, 30, 30, 80, 40, 800, 600, Placement::Left);
        assert_eq!(r.placement, Placement::Right);
    }

    #[test]
    fn clamps_x_to_viewport_right() {
        let a = PopoverAnchor::new(4);
        // Anchor near right edge, bottom placement, popover wide enough to overflow.
        let r = a.resolve(780, 100, 10, 10, 80, 40, 800, 600, Placement::Bottom);
        assert_eq!(r.x, 800 - 80);
    }

    #[test]
    fn clamps_x_to_viewport_left() {
        let a = PopoverAnchor::new(4);
        let r = a.resolve(5, 100, 10, 10, 80, 40, 800, 600, Placement::Bottom);
        assert_eq!(r.x, 0);
    }

    #[test]
    fn top_when_room_above() {
        let a = PopoverAnchor::new(4);
        let r = a.resolve(100, 200, 50, 30, 80, 40, 800, 600, Placement::Top);
        assert_eq!(r.placement, Placement::Top);
        assert_eq!(r.y, 200 - 4 - 40);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut a = PopoverAnchor::new(4);
        a.schema_version = "9.9.9".into();
        assert!(matches!(
            a.validate().unwrap_err(),
            AnchorError::SchemaMismatch
        ));
    }

    #[test]
    fn anchor_serde_roundtrip() {
        let a = PopoverAnchor::new(4);
        let j = serde_json::to_string(&a).unwrap();
        let back: PopoverAnchor = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
