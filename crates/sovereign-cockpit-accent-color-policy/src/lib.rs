//! `sovereign-cockpit-accent-color-policy` — accent color.
//!
//! Hex "#rrggbb" parsed to (r,g,b). luminance returns 0..255
//! perceived brightness (rough). prefer_white_text returns true
//! when text-on-accent should be white (low luminance).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AccentColorPolicy {
    /// Schema version.
    pub schema_version: String,
    /// Hex like "#3366ff".
    pub hex: String,
    /// Parsed r,g,b.
    pub r: u8,
    /// g.
    pub g: u8,
    /// b.
    pub b: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ColorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad hex.
    #[error("invalid hex color: {0}")]
    BadHex(String),
}

fn parse_hex(hex: &str) -> Result<(u8, u8, u8), ColorError> {
    let s = hex.trim();
    let s = s.strip_prefix('#').unwrap_or(s);
    if s.len() != 6 {
        return Err(ColorError::BadHex(hex.into()));
    }
    let r = u8::from_str_radix(&s[0..2], 16).map_err(|_| ColorError::BadHex(hex.into()))?;
    let g = u8::from_str_radix(&s[2..4], 16).map_err(|_| ColorError::BadHex(hex.into()))?;
    let b = u8::from_str_radix(&s[4..6], 16).map_err(|_| ColorError::BadHex(hex.into()))?;
    Ok((r, g, b))
}

impl AccentColorPolicy {
    /// New from hex.
    pub fn new(hex: &str) -> Result<Self, ColorError> {
        let (r, g, b) = parse_hex(hex)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            hex: format!("#{r:02x}{g:02x}{b:02x}"),
            r,
            g,
            b,
        })
    }

    /// Set color.
    pub fn set(&mut self, hex: &str) -> Result<(), ColorError> {
        let (r, g, b) = parse_hex(hex)?;
        self.r = r;
        self.g = g;
        self.b = b;
        self.hex = format!("#{r:02x}{g:02x}{b:02x}");
        Ok(())
    }

    /// Perceived luminance (0..255, rough).
    pub fn luminance(&self) -> u8 {
        // 0.299r + 0.587g + 0.114b (rounded).
        let l = (299u32 * self.r as u32 + 587u32 * self.g as u32 + 114u32 * self.b as u32) / 1000;
        l.min(255) as u8
    }

    /// Prefer white text? Yes when accent is dark (luminance < 128).
    pub fn prefer_white_text(&self) -> bool {
        self.luminance() < 128
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ColorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ColorError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_with_hash() {
        let c = AccentColorPolicy::new("#3366ff").unwrap();
        assert_eq!(c.r, 0x33);
        assert_eq!(c.g, 0x66);
        assert_eq!(c.b, 0xff);
    }

    #[test]
    fn parse_without_hash() {
        let c = AccentColorPolicy::new("3366ff").unwrap();
        assert_eq!(c.r, 0x33);
    }

    #[test]
    fn bad_hex_rejected() {
        assert!(matches!(
            AccentColorPolicy::new("not-a-color").unwrap_err(),
            ColorError::BadHex(_)
        ));
        assert!(matches!(
            AccentColorPolicy::new("#gghhii").unwrap_err(),
            ColorError::BadHex(_)
        ));
        assert!(matches!(
            AccentColorPolicy::new("#333").unwrap_err(),
            ColorError::BadHex(_)
        ));
    }

    #[test]
    fn set_replaces() {
        let mut c = AccentColorPolicy::new("#000000").unwrap();
        c.set("#ffffff").unwrap();
        assert_eq!(c.luminance(), 255);
    }

    #[test]
    fn luminance_black_white() {
        let black = AccentColorPolicy::new("#000000").unwrap();
        let white = AccentColorPolicy::new("#ffffff").unwrap();
        assert_eq!(black.luminance(), 0);
        assert_eq!(white.luminance(), 255);
    }

    #[test]
    fn prefer_white_on_dark() {
        let dark = AccentColorPolicy::new("#000000").unwrap();
        let light = AccentColorPolicy::new("#ffffff").unwrap();
        assert!(dark.prefer_white_text());
        assert!(!light.prefer_white_text());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = AccentColorPolicy::new("#000000").unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            ColorError::SchemaMismatch
        ));
    }

    #[test]
    fn accent_serde_roundtrip() {
        let c = AccentColorPolicy::new("#3366ff").unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: AccentColorPolicy = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
