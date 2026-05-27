//! `sovereign-cockpit-color-contrast` — WCAG-2.1 §1.4.3
//! relative-luminance + contrast-ratio computation.
//!
//! The cockpit needs a hardware-free way to validate
//! foreground/background color pairs against WCAG-2.1 AA + AAA
//! contrast thresholds BEFORE rendering, so accent-color policy
//! decisions + dynamic theming surfaces can reject low-contrast
//! combinations at the type layer.
//!
//! - `relative_luminance(rgb)` per WCAG-2.1 §1.4.3 (linearised
//!   sRGB → Y' coefficient: 0.2126 R + 0.7152 G + 0.0722 B).
//! - `contrast_ratio(fg, bg)` = (Llight + 0.05) / (Ldark + 0.05);
//!   the ordering of fg/bg does NOT matter — the formula picks the
//!   lighter of the two automatically.
//! - `WcagLevel::passes` checks AA (4.5:1 normal, 3:1 large) and
//!   AAA (7:1 normal, 4.5:1 large) per WCAG-2.1.
//!
//! Standing rule: we do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// An sRGB color in the standard 0..=255 range per channel.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Rgb {
    /// Red 0..=255.
    pub r: u8,
    /// Green 0..=255.
    pub g: u8,
    /// Blue 0..=255.
    pub b: u8,
}

impl Rgb {
    /// Construct from 0..=255 channels.
    pub const fn new(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b }
    }
    /// Construct from a 24-bit packed integer `0xRRGGBB`.
    pub const fn from_hex(rgb: u32) -> Self {
        Self {
            r: ((rgb >> 16) & 0xFF) as u8,
            g: ((rgb >> 8) & 0xFF) as u8,
            b: (rgb & 0xFF) as u8,
        }
    }
}

/// WCAG conformance level + text-size category for the threshold
/// lookup. Per WCAG-2.1 §1.4.3 + §1.4.6:
/// - AA  large-text:  3.0:1
/// - AA  normal-text: 4.5:1
/// - AAA large-text:  4.5:1
/// - AAA normal-text: 7.0:1
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum WcagLevel {
    /// AA (Level A + AA — minimum-required for accessibility claims).
    AA,
    /// AAA (enhanced).
    AAA,
}

impl WcagLevel {
    /// Required contrast ratio threshold for this level + text size.
    pub const fn threshold(self, large_text: bool) -> f64 {
        match (self, large_text) {
            (WcagLevel::AA, true) => 3.0,
            (WcagLevel::AA, false) => 4.5,
            (WcagLevel::AAA, true) => 4.5,
            (WcagLevel::AAA, false) => 7.0,
        }
    }
    /// True iff `ratio` is at-or-above the threshold for the given
    /// level + text size.
    pub fn passes(self, ratio: f64, large_text: bool) -> bool {
        ratio + 1e-9 >= self.threshold(large_text)
    }
}

/// Errors.
#[derive(Debug, Error)]
pub enum ContrastError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// Linearise a single sRGB channel per WCAG-2.1 §1.4.3.
fn linearise_channel(c: u8) -> f64 {
    let v = (c as f64) / 255.0;
    if v <= 0.040_45 {
        v / 12.92
    } else {
        ((v + 0.055) / 1.055).powf(2.4)
    }
}

/// Relative luminance of an sRGB color per WCAG-2.1 §1.4.3.
/// Returns a value in [0.0, 1.0].
pub fn relative_luminance(c: Rgb) -> f64 {
    let r = linearise_channel(c.r);
    let g = linearise_channel(c.g);
    let b = linearise_channel(c.b);
    0.2126 * r + 0.7152 * g + 0.0722 * b
}

/// Contrast ratio of two colors per WCAG-2.1 §1.4.3. The ordering
/// of `fg` and `bg` does NOT matter — the formula picks the lighter
/// of the two automatically. Returns a value in [1.0, 21.0].
pub fn contrast_ratio(fg: Rgb, bg: Rgb) -> f64 {
    let l1 = relative_luminance(fg);
    let l2 = relative_luminance(bg);
    let (light, dark) = if l1 >= l2 { (l1, l2) } else { (l2, l1) };
    (light + 0.05) / (dark + 0.05)
}

/// Convenience: bundle the ratio + AA/AAA verdicts for one color
/// pair + text size.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct Verdict {
    /// Computed contrast ratio.
    pub ratio: f64,
    /// True if the ratio passes AA at the given text size.
    pub passes_aa: bool,
    /// True if the ratio passes AAA at the given text size.
    pub passes_aaa: bool,
}

/// Compute the full verdict for a color pair + text size.
pub fn verdict(fg: Rgb, bg: Rgb, large_text: bool) -> Verdict {
    let r = contrast_ratio(fg, bg);
    Verdict {
        ratio: r,
        passes_aa: WcagLevel::AA.passes(r, large_text),
        passes_aaa: WcagLevel::AAA.passes(r, large_text),
    }
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), ContrastError> {
    if s != SCHEMA_VERSION {
        return Err(ContrastError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64, eps: f64) -> bool {
        (a - b).abs() < eps
    }

    #[test]
    fn black_on_white_is_21_to_1() {
        let white = Rgb::new(255, 255, 255);
        let black = Rgb::new(0, 0, 0);
        let r = contrast_ratio(black, white);
        assert!(approx(r, 21.0, 0.001), "expected 21.0, got {r}");
        // Ordering does not matter.
        assert!(approx(contrast_ratio(white, black), r, 1e-9));
    }

    #[test]
    fn identical_colors_are_1_to_1() {
        let c = Rgb::new(123, 45, 200);
        let r = contrast_ratio(c, c);
        assert!(approx(r, 1.0, 1e-9), "expected 1.0, got {r}");
    }

    #[test]
    fn white_relative_luminance_is_1() {
        let l = relative_luminance(Rgb::new(255, 255, 255));
        assert!(approx(l, 1.0, 1e-6));
    }

    #[test]
    fn black_relative_luminance_is_0() {
        let l = relative_luminance(Rgb::new(0, 0, 0));
        assert!(approx(l, 0.0, 1e-9));
    }

    #[test]
    fn wcag_aa_normal_text_threshold_is_4_5() {
        assert!(approx(WcagLevel::AA.threshold(false), 4.5, 1e-9));
    }

    #[test]
    fn wcag_aa_large_text_threshold_is_3_0() {
        assert!(approx(WcagLevel::AA.threshold(true), 3.0, 1e-9));
    }

    #[test]
    fn wcag_aaa_normal_text_threshold_is_7_0() {
        assert!(approx(WcagLevel::AAA.threshold(false), 7.0, 1e-9));
    }

    #[test]
    fn wcag_aaa_large_text_threshold_is_4_5() {
        assert!(approx(WcagLevel::AAA.threshold(true), 4.5, 1e-9));
    }

    #[test]
    fn from_hex_round_trips() {
        let c = Rgb::from_hex(0x4A_C8_F0);
        assert_eq!(c, Rgb::new(0x4A, 0xC8, 0xF0));
    }

    #[test]
    fn verdict_for_black_on_white_passes_everything() {
        let v = verdict(Rgb::new(0, 0, 0), Rgb::new(255, 255, 255), false);
        assert!(approx(v.ratio, 21.0, 0.001));
        assert!(v.passes_aa);
        assert!(v.passes_aaa);
    }

    #[test]
    fn verdict_for_mid_gray_on_white_fails_aaa_normal() {
        // Mid-gray (128) on white has ratio ~3.95 — fails AA normal
        // (4.5), fails AAA normal (7.0), passes AA large (3.0).
        let v = verdict(Rgb::new(128, 128, 128), Rgb::new(255, 255, 255), false);
        assert!(v.ratio > 3.0 && v.ratio < 5.0, "ratio={}", v.ratio);
        assert!(!v.passes_aa, "must fail AA normal at this ratio");
        assert!(!v.passes_aaa);
        let large = verdict(Rgb::new(128, 128, 128), Rgb::new(255, 255, 255), true);
        assert!(large.passes_aa, "must pass AA large at this ratio");
    }

    #[test]
    fn verdict_ordering_invariant() {
        // Swapping fg + bg must yield identical verdict.
        let fg = Rgb::new(20, 80, 200);
        let bg = Rgb::new(240, 240, 230);
        let a = verdict(fg, bg, false);
        let b = verdict(bg, fg, false);
        assert!(approx(a.ratio, b.ratio, 1e-12));
        assert_eq!(a.passes_aa, b.passes_aa);
        assert_eq!(a.passes_aaa, b.passes_aaa);
    }

    #[test]
    fn boundary_ratio_at_threshold_passes() {
        // Synthetic case where the ratio is exactly the threshold:
        // the `passes` predicate uses a 1e-9 tolerance to handle
        // f64 rounding so a "just at threshold" pair counts.
        assert!(WcagLevel::AA.passes(4.5, false));
        assert!(WcagLevel::AA.passes(3.0, true));
        assert!(WcagLevel::AAA.passes(7.0, false));
        assert!(WcagLevel::AAA.passes(4.5, true));
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            ContrastError::SchemaMismatch
        ));
    }

    #[test]
    fn rgb_serde_roundtrip() {
        let c = Rgb::new(10, 20, 30);
        let j = serde_json::to_string(&c).unwrap();
        let back: Rgb = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }

    #[test]
    fn verdict_serde_roundtrip() {
        let v = Verdict {
            ratio: 4.5,
            passes_aa: true,
            passes_aaa: false,
        };
        let j = serde_json::to_string(&v).unwrap();
        let back: Verdict = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }

    #[test]
    fn level_serde_kebab() {
        let s = serde_json::to_string(&WcagLevel::AA).unwrap();
        assert_eq!(s, "\"aa\"");
        let s2 = serde_json::to_string(&WcagLevel::AAA).unwrap();
        assert_eq!(s2, "\"aaa\"");
    }
}
