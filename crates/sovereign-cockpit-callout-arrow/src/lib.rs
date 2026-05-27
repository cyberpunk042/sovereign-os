//! `sovereign-cockpit-callout-arrow` — callout-arrow placement.
//!
//! Given a callout balloon rect and a target point in the viewport,
//! decide the Side (Top/Right/Bottom/Left) the arrow points OUT of
//! the balloon AND its offset along that edge (clamped). Purely
//! geometric — no DOM, no event wiring.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Side of the balloon the arrow protrudes from.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Side {
    /// Arrow points up; balloon is below target.
    Top,
    /// Arrow points right; balloon is to the left.
    Right,
    /// Arrow points down; balloon is above target.
    Bottom,
    /// Arrow points left; balloon is to the right.
    Left,
}

/// Rect.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Rect {
    /// x.
    pub x: i32,
    /// y.
    pub y: i32,
    /// width (>=1).
    pub w: i32,
    /// height (>=1).
    pub h: i32,
}

/// Placement decision.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Placement {
    /// Side the arrow points OUT of.
    pub side: Side,
    /// Offset along the edge in px, clamped within [arrow_margin,
    /// edge_len - arrow_margin].
    pub offset: i32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CalloutError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad rect.
    #[error("rect w/h must be >= 1")]
    BadRect,
}

/// Compute placement.
///
/// `arrow_margin` is the minimum distance the arrow stays from each
/// corner (e.g. arrow width). Target may be outside the balloon —
/// the side closest to the target is chosen.
pub fn place(
    balloon: Rect,
    target_x: i32,
    target_y: i32,
    arrow_margin: i32,
) -> Result<Placement, CalloutError> {
    if balloon.w < 1 || balloon.h < 1 {
        return Err(CalloutError::BadRect);
    }

    // Signed distances target→balloon edges (positive = target is
    // outside that side).
    let dx_left = balloon.x - target_x;
    let dx_right = target_x - (balloon.x + balloon.w);
    let dy_top = balloon.y - target_y;
    let dy_bottom = target_y - (balloon.y + balloon.h);

    // The side facing the target is the one with the largest
    // positive distance. If target is inside the balloon, all four
    // are non-positive; in that case pick the side with the
    // smallest gap to outside.
    let candidates = [
        (Side::Left, dx_left),
        (Side::Right, dx_right),
        (Side::Top, dy_top),
        (Side::Bottom, dy_bottom),
    ];
    let side = candidates.iter().max_by_key(|(_, d)| *d).unwrap().0;

    let offset = match side {
        Side::Top | Side::Bottom => {
            let edge = balloon.w;
            let raw = target_x - balloon.x;
            clamp(raw, arrow_margin, edge - arrow_margin)
        }
        Side::Left | Side::Right => {
            let edge = balloon.h;
            let raw = target_y - balloon.y;
            clamp(raw, arrow_margin, edge - arrow_margin)
        }
    };

    Ok(Placement { side, offset })
}

fn clamp(v: i32, lo: i32, hi: i32) -> i32 {
    let (lo, hi) = if lo <= hi { (lo, hi) } else { (hi, lo) };
    v.max(lo).min(hi)
}

/// Validate constants.
pub fn validate_schema_version(s: &str) -> Result<(), CalloutError> {
    if s != SCHEMA_VERSION {
        return Err(CalloutError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b() -> Rect {
        Rect {
            x: 100,
            y: 100,
            w: 200,
            h: 80,
        }
    }

    #[test]
    fn target_above_picks_top() {
        let p = place(b(), 200, 30, 10).unwrap();
        assert_eq!(p.side, Side::Top);
        // raw = 200 - 100 = 100, clamped to [10, 190] → 100.
        assert_eq!(p.offset, 100);
    }

    #[test]
    fn target_below_picks_bottom() {
        let p = place(b(), 200, 300, 10).unwrap();
        assert_eq!(p.side, Side::Bottom);
    }

    #[test]
    fn target_left_picks_left() {
        let p = place(b(), 10, 140, 10).unwrap();
        assert_eq!(p.side, Side::Left);
    }

    #[test]
    fn target_right_picks_right() {
        let p = place(b(), 500, 140, 10).unwrap();
        assert_eq!(p.side, Side::Right);
    }

    #[test]
    fn offset_clamps_to_margin() {
        // Target near top-left corner.
        let p = place(b(), 105, 30, 20).unwrap();
        assert_eq!(p.side, Side::Top);
        // raw = 5, clamp to [20, 180] → 20.
        assert_eq!(p.offset, 20);
    }

    #[test]
    fn offset_clamps_to_high_end() {
        // Target far right of balloon, vertically aligned to top of balloon.
        let p = place(b(), 1000, 100, 20).unwrap();
        assert_eq!(p.side, Side::Right);
        // y raw = 100 - 100 = 0, clamp to [20, 60] → 20.
        assert_eq!(p.offset, 20);
        // Same x, far below: now bottom wins (vertical distance dominates).
        let p2 = place(b(), 1000, 5000, 20).unwrap();
        assert_eq!(p2.side, Side::Bottom);
        // raw x = 1000 - 100 = 900, clamp to [20, 180] → 180.
        assert_eq!(p2.offset, 180);
    }

    #[test]
    fn bad_rect_rejected() {
        let r = Rect {
            x: 0,
            y: 0,
            w: 0,
            h: 10,
        };
        assert!(matches!(
            place(r, 0, 0, 1).unwrap_err(),
            CalloutError::BadRect
        ));
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            CalloutError::SchemaMismatch
        ));
    }

    #[test]
    fn placement_serde_roundtrip() {
        let p = Placement {
            side: Side::Left,
            offset: 42,
        };
        let j = serde_json::to_string(&p).unwrap();
        let back: Placement = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
