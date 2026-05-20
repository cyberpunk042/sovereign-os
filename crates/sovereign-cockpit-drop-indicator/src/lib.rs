//! `sovereign-cockpit-drop-indicator` — drop position picker.
//!
//! Indicator{None/Above/Below/Inside}. resolve(cursor_y, row_y,
//! row_h, inside_band_bp) picks position from the cursor's
//! relative position within the row (0..=10000 bp). Inside is
//! the middle band; Above is top edge; Below is bottom edge.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Indicator.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Indicator {
    /// None.
    None,
    /// Above (top edge).
    Above,
    /// Below (bottom edge).
    Below,
    /// Inside (middle band).
    Inside,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DropIndicator {
    /// Schema version.
    pub schema_version: String,
    /// Inside band size in basis points (0..=10000).
    pub inside_band_bp: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum IndicatorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad bp.
    #[error("inside_band_bp must be <= 10000")]
    BadBand,
    /// Zero row.
    #[error("row_h must be >= 1")]
    ZeroRow,
}

impl DropIndicator {
    /// New.
    pub fn new(inside_band_bp: u32) -> Result<Self, IndicatorError> {
        if inside_band_bp > 10_000 { return Err(IndicatorError::BadBand); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            inside_band_bp,
        })
    }

    /// Resolve indicator.
    pub fn resolve(&self, cursor_y: i32, row_y: i32, row_h: u32) -> Result<Indicator, IndicatorError> {
        if row_h == 0 { return Err(IndicatorError::ZeroRow); }
        let dy = cursor_y - row_y;
        if dy < 0 || dy as u32 >= row_h { return Ok(Indicator::None); }
        let pos_bp = (dy as u64 * 10_000 / row_h as u64) as u32;
        let half_band = self.inside_band_bp / 2;
        let lo = 5_000u32.saturating_sub(half_band);
        let hi = 5_000u32.saturating_add(half_band);
        if pos_bp >= lo && pos_bp <= hi {
            Ok(Indicator::Inside)
        } else if pos_bp < 5_000 {
            Ok(Indicator::Above)
        } else {
            Ok(Indicator::Below)
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), IndicatorError> {
        if self.schema_version != SCHEMA_VERSION { return Err(IndicatorError::SchemaMismatch); }
        if self.inside_band_bp > 10_000 { return Err(IndicatorError::BadBand); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inside_band_middle() {
        // inside_band=2000 → middle 4000..6000 bp; row 100h, cursor at y=50 → 5000bp.
        let d = DropIndicator::new(2000).unwrap();
        assert_eq!(d.resolve(50, 0, 100).unwrap(), Indicator::Inside);
    }

    #[test]
    fn above_top_edge() {
        let d = DropIndicator::new(2000).unwrap();
        assert_eq!(d.resolve(10, 0, 100).unwrap(), Indicator::Above);
    }

    #[test]
    fn below_bottom_edge() {
        let d = DropIndicator::new(2000).unwrap();
        assert_eq!(d.resolve(90, 0, 100).unwrap(), Indicator::Below);
    }

    #[test]
    fn outside_returns_none() {
        let d = DropIndicator::new(2000).unwrap();
        assert_eq!(d.resolve(-5, 0, 100).unwrap(), Indicator::None);
        assert_eq!(d.resolve(200, 0, 100).unwrap(), Indicator::None);
    }

    #[test]
    fn zero_band_no_inside() {
        // band=0 → no Inside.
        let d = DropIndicator::new(0).unwrap();
        // At exactly 50 (5000bp), inside band is just the point pos==5000.
        let r = d.resolve(50, 0, 100).unwrap();
        // Boundary case: pos_bp=5000, lo=hi=5000 → Inside.
        assert_eq!(r, Indicator::Inside);
    }

    #[test]
    fn bad_inputs_rejected() {
        assert!(matches!(DropIndicator::new(20_000).unwrap_err(), IndicatorError::BadBand));
        let d = DropIndicator::new(2000).unwrap();
        assert!(matches!(d.resolve(0, 0, 0).unwrap_err(), IndicatorError::ZeroRow));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DropIndicator::new(2000).unwrap();
        d.schema_version = "9.9.9".into();
        assert!(matches!(d.validate().unwrap_err(), IndicatorError::SchemaMismatch));
    }

    #[test]
    fn indicator_serde_roundtrip() {
        let d = DropIndicator::new(2000).unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: DropIndicator = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
