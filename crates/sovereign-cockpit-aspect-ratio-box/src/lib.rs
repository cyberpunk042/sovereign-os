//! `sovereign-cockpit-aspect-ratio-box` — aspect-ratio sized box.
//!
//! Given a target ratio (w_num : w_den) and an outer container
//! (w, h), compute the inner box dimensions that preserve the
//! ratio AND fit inside, centered along the dominant axis.
//!
//! Distinct from object-fit: this sizes the BOX itself; object-fit
//! sizes content within a fixed box.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Inner box geometry.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Box2D {
    /// x offset within outer.
    pub x: u32,
    /// y offset within outer.
    pub y: u32,
    /// Width.
    pub w: u32,
    /// Height.
    pub h: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AspectError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero ratio.
    #[error("ratio numerator/denominator must be >= 1")]
    ZeroRatio,
    /// Zero outer.
    #[error("outer w/h must be >= 1")]
    ZeroOuter,
}

/// Compute inner box with target ratio (w_num/w_den), centered.
pub fn fit(outer_w: u32, outer_h: u32, w_num: u32, w_den: u32) -> Result<Box2D, AspectError> {
    if outer_w == 0 || outer_h == 0 {
        return Err(AspectError::ZeroOuter);
    }
    if w_num == 0 || w_den == 0 {
        return Err(AspectError::ZeroRatio);
    }
    // Target is w/h = w_num/w_den.
    // Width-limited: w' = outer_w, h' = outer_w * w_den / w_num.
    // Height-limited: h' = outer_h, w' = outer_h * w_num / w_den.
    let by_w_h = (outer_w as u64) * (w_den as u64) / (w_num as u64);
    let by_h_w = (outer_h as u64) * (w_num as u64) / (w_den as u64);

    let (iw, ih) = if by_w_h <= outer_h as u64 {
        (outer_w as u64, by_w_h)
    } else {
        (by_h_w, outer_h as u64)
    };
    let iw = iw.min(outer_w as u64) as u32;
    let ih = ih.min(outer_h as u64) as u32;
    let x = (outer_w - iw) / 2;
    let y = (outer_h - ih) / 2;
    Ok(Box2D { x, y, w: iw, h: ih })
}

/// Validate schema version.
pub fn validate_schema_version(s: &str) -> Result<(), AspectError> {
    if s != SCHEMA_VERSION {
        return Err(AspectError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_outer_when_ratio_equal() {
        let b = fit(200, 100, 2, 1).unwrap();
        assert_eq!(
            b,
            Box2D {
                x: 0,
                y: 0,
                w: 200,
                h: 100
            }
        );
    }

    #[test]
    fn pillarbox_when_outer_wider() {
        // Outer 400x100, target 1:1 → inner 100x100 centered horizontally.
        let b = fit(400, 100, 1, 1).unwrap();
        assert_eq!(
            b,
            Box2D {
                x: 150,
                y: 0,
                w: 100,
                h: 100
            }
        );
    }

    #[test]
    fn letterbox_when_outer_taller() {
        // Outer 100x400, target 1:1 → inner 100x100 centered vertically.
        let b = fit(100, 400, 1, 1).unwrap();
        assert_eq!(
            b,
            Box2D {
                x: 0,
                y: 150,
                w: 100,
                h: 100
            }
        );
    }

    #[test]
    fn sixteen_by_nine_in_square() {
        // Outer 1000x1000, ratio 16:9 → w_limited = 1000, h = 1000*9/16=562.
        let b = fit(1000, 1000, 16, 9).unwrap();
        assert_eq!(b.w, 1000);
        assert_eq!(b.h, 562);
        assert_eq!(b.x, 0);
        assert_eq!(b.y, (1000 - 562) / 2);
    }

    #[test]
    fn zero_outer_rejected() {
        assert!(matches!(
            fit(0, 10, 1, 1).unwrap_err(),
            AspectError::ZeroOuter
        ));
        assert!(matches!(
            fit(10, 0, 1, 1).unwrap_err(),
            AspectError::ZeroOuter
        ));
    }

    #[test]
    fn zero_ratio_rejected() {
        assert!(matches!(
            fit(10, 10, 0, 1).unwrap_err(),
            AspectError::ZeroRatio
        ));
        assert!(matches!(
            fit(10, 10, 1, 0).unwrap_err(),
            AspectError::ZeroRatio
        ));
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            AspectError::SchemaMismatch
        ));
    }

    #[test]
    fn box2d_serde_roundtrip() {
        let b = Box2D {
            x: 1,
            y: 2,
            w: 3,
            h: 4,
        };
        let j = serde_json::to_string(&b).unwrap();
        let back: Box2D = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
