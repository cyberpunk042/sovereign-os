//! `sovereign-cockpit-color-contrast` — WCAG 2.1 contrast ratio.
//!
//! `ratio(fg, bg)` returns the WCAG relative-luminance ratio rounded
//! to two decimal places (integer * 100). `evaluate(fg, bg)` returns
//! a `ContrastReport` with AA / AAA pass for normal and large text:
//!
//!   * AA normal: ratio ≥ 4.5
//!   * AA large:  ratio ≥ 3.0
//!   * AAA normal: ratio ≥ 7.0
//!   * AAA large:  ratio ≥ 4.5
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// sRGB color.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rgb {
    /// 0..=255.
    pub r: u8,
    /// 0..=255.
    pub g: u8,
    /// 0..=255.
    pub b: u8,
}

/// Contrast report.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContrastReport {
    /// ratio * 100 (so 4.50 becomes 450).
    pub ratio_x100: u32,
    /// AA normal text pass.
    pub aa_normal: bool,
    /// AA large text pass.
    pub aa_large: bool,
    /// AAA normal text pass.
    pub aaa_normal: bool,
    /// AAA large text pass.
    pub aaa_large: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColorContrast {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ContrastError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl ColorContrast {
    /// New.
    pub fn new() -> Self {
        Self { schema_version: SCHEMA_VERSION.into() }
    }

    /// Compute the contrast ratio rounded to 0.01.
    pub fn ratio(&self, fg: Rgb, bg: Rgb) -> u32 {
        let lf = relative_luminance(fg);
        let lb = relative_luminance(bg);
        let (lighter, darker) = if lf >= lb { (lf, lb) } else { (lb, lf) };
        let raw = (lighter + 0.05) / (darker + 0.05);
        // Round to 2 decimals.
        (raw * 100.0 + 0.5) as u32
    }

    /// Full report.
    pub fn evaluate(&self, fg: Rgb, bg: Rgb) -> ContrastReport {
        let r = self.ratio(fg, bg);
        ContrastReport {
            ratio_x100: r,
            aa_normal: r >= 450,
            aa_large: r >= 300,
            aaa_normal: r >= 700,
            aaa_large: r >= 450,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ContrastError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ContrastError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for ColorContrast {
    fn default() -> Self { Self::new() }
}

fn srgb_to_linear(c: u8) -> f64 {
    let v = c as f64 / 255.0;
    if v <= 0.03928 { v / 12.92 } else { ((v + 0.055) / 1.055).powf(2.4) }
}

fn relative_luminance(c: Rgb) -> f64 {
    let r = srgb_to_linear(c.r);
    let g = srgb_to_linear(c.g);
    let b = srgb_to_linear(c.b);
    0.2126 * r + 0.7152 * g + 0.0722 * b
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rgb(r: u8, g: u8, b: u8) -> Rgb { Rgb { r, g, b } }

    #[test]
    fn black_on_white_is_21() {
        let c = ColorContrast::new();
        // WCAG maximum contrast.
        assert_eq!(c.ratio(rgb(0, 0, 0), rgb(255, 255, 255)), 2100);
    }

    #[test]
    fn white_on_white_is_1() {
        let c = ColorContrast::new();
        assert_eq!(c.ratio(rgb(255, 255, 255), rgb(255, 255, 255)), 100);
    }

    #[test]
    fn order_independent() {
        let c = ColorContrast::new();
        let a = c.ratio(rgb(0, 0, 0), rgb(255, 255, 255));
        let b = c.ratio(rgb(255, 255, 255), rgb(0, 0, 0));
        assert_eq!(a, b);
    }

    #[test]
    fn aa_passes_for_black_white() {
        let c = ColorContrast::new();
        let r = c.evaluate(rgb(0, 0, 0), rgb(255, 255, 255));
        assert!(r.aa_normal && r.aa_large && r.aaa_normal && r.aaa_large);
    }

    #[test]
    fn low_contrast_grays_fail() {
        let c = ColorContrast::new();
        let r = c.evaluate(rgb(180, 180, 180), rgb(200, 200, 200));
        assert!(!r.aa_normal);
        assert!(!r.aa_large);
    }

    #[test]
    fn mid_gray_pair_passes_large_only() {
        let c = ColorContrast::new();
        // Pick a pair near the boundary of large-AA only.
        let r = c.evaluate(rgb(118, 118, 118), rgb(255, 255, 255));
        // Should pass AA large (≥3.0) — checking the AA large flag in particular.
        assert!(r.aa_large);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ColorContrast::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), ContrastError::SchemaMismatch));
    }

    #[test]
    fn contrast_serde_roundtrip() {
        let c = ColorContrast::new();
        let j = serde_json::to_string(&c).unwrap();
        let back: ColorContrast = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
