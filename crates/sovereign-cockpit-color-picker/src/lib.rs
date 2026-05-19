//! `sovereign-cockpit-color-picker` — RGBA color picker state.
//!
//! Holds current `Rgba` + a bounded `recent` MRU list + a `favorites`
//! pinned list. set_hex parses #RGB, #RRGGBB, or #RRGGBBAA.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// RGBA color (8-bit channels).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Rgba {
    /// Red.
    pub r: u8,
    /// Green.
    pub g: u8,
    /// Blue.
    pub b: u8,
    /// Alpha.
    pub a: u8,
}

impl Rgba {
    /// Opaque rgb.
    pub fn rgb(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b, a: 0xff }
    }

    /// To hex `#RRGGBBAA`.
    pub fn to_hex(self) -> String {
        format!("#{:02X}{:02X}{:02X}{:02X}", self.r, self.g, self.b, self.a)
    }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColorPicker {
    /// Schema version.
    pub schema_version: String,
    /// Current swatch.
    pub current: Rgba,
    /// Recent picks (MRU first), capped to `max_recent`.
    pub recent: Vec<Rgba>,
    /// Operator favorites (manually pinned).
    pub favorites: Vec<Rgba>,
    /// Max recent.
    pub max_recent: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ColorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad hex string.
    #[error("invalid hex {0:?}")]
    BadHex(String),
    /// max_recent zero.
    #[error("max_recent is zero")]
    MaxRecentZero,
}

impl ColorPicker {
    /// New picker.
    pub fn new(initial: Rgba, max_recent: u32) -> Result<Self, ColorError> {
        if max_recent == 0 {
            return Err(ColorError::MaxRecentZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            current: initial,
            recent: Vec::new(),
            favorites: Vec::new(),
            max_recent,
        })
    }

    /// Commit current to recent (deduplicated; moves to head if present).
    pub fn commit_recent(&mut self) {
        let cur = self.current;
        self.recent.retain(|c| *c != cur);
        self.recent.insert(0, cur);
        while self.recent.len() > self.max_recent as usize {
            self.recent.pop();
        }
    }

    /// Set current from a hex string.
    pub fn set_hex(&mut self, hex: &str) -> Result<(), ColorError> {
        let raw = hex.trim().trim_start_matches('#');
        let (r, g, b, a) = match raw.len() {
            3 => {
                let p = |i: usize| u8::from_str_radix(&raw[i..=i].repeat(2), 16);
                (p(0).map_err(|_| ColorError::BadHex(hex.into()))?,
                 p(1).map_err(|_| ColorError::BadHex(hex.into()))?,
                 p(2).map_err(|_| ColorError::BadHex(hex.into()))?,
                 0xff)
            }
            6 => {
                let p = |i: usize| u8::from_str_radix(&raw[i..i + 2], 16);
                (p(0).map_err(|_| ColorError::BadHex(hex.into()))?,
                 p(2).map_err(|_| ColorError::BadHex(hex.into()))?,
                 p(4).map_err(|_| ColorError::BadHex(hex.into()))?,
                 0xff)
            }
            8 => {
                let p = |i: usize| u8::from_str_radix(&raw[i..i + 2], 16);
                (p(0).map_err(|_| ColorError::BadHex(hex.into()))?,
                 p(2).map_err(|_| ColorError::BadHex(hex.into()))?,
                 p(4).map_err(|_| ColorError::BadHex(hex.into()))?,
                 p(6).map_err(|_| ColorError::BadHex(hex.into()))?)
            }
            _ => return Err(ColorError::BadHex(hex.into())),
        };
        self.current = Rgba { r, g, b, a };
        Ok(())
    }

    /// Pin current to favorites (dedup).
    pub fn favorite_current(&mut self) {
        let cur = self.current;
        if !self.favorites.iter().any(|c| *c == cur) {
            self.favorites.push(cur);
        }
    }

    /// Unfavorite an exact color.
    pub fn unfavorite(&mut self, c: Rgba) -> bool {
        let pre = self.favorites.len();
        self.favorites.retain(|x| *x != c);
        self.favorites.len() != pre
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ColorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ColorError::SchemaMismatch);
        }
        if self.max_recent == 0 {
            return Err(ColorError::MaxRecentZero);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn red() -> Rgba { Rgba::rgb(255, 0, 0) }
    fn green() -> Rgba { Rgba::rgb(0, 255, 0) }

    #[test]
    fn max_recent_zero_rejected() {
        assert!(matches!(ColorPicker::new(red(), 0).unwrap_err(), ColorError::MaxRecentZero));
    }

    #[test]
    fn commit_recent_dedup() {
        let mut p = ColorPicker::new(red(), 3).unwrap();
        p.commit_recent();
        p.commit_recent();
        assert_eq!(p.recent.len(), 1);
    }

    #[test]
    fn commit_recent_evicts_oldest() {
        let mut p = ColorPicker::new(Rgba::rgb(1, 1, 1), 2).unwrap();
        p.commit_recent();
        p.current = Rgba::rgb(2, 2, 2);
        p.commit_recent();
        p.current = Rgba::rgb(3, 3, 3);
        p.commit_recent();
        assert_eq!(p.recent.len(), 2);
        assert_eq!(p.recent[0], Rgba::rgb(3, 3, 3));
    }

    #[test]
    fn set_hex_short_form() {
        let mut p = ColorPicker::new(red(), 3).unwrap();
        p.set_hex("#0f0").unwrap();
        assert_eq!(p.current, Rgba { r: 0, g: 0xff, b: 0, a: 0xff });
    }

    #[test]
    fn set_hex_long_rgb() {
        let mut p = ColorPicker::new(red(), 3).unwrap();
        p.set_hex("#112233").unwrap();
        assert_eq!(p.current, Rgba { r: 0x11, g: 0x22, b: 0x33, a: 0xff });
    }

    #[test]
    fn set_hex_with_alpha() {
        let mut p = ColorPicker::new(red(), 3).unwrap();
        p.set_hex("#11223380").unwrap();
        assert_eq!(p.current, Rgba { r: 0x11, g: 0x22, b: 0x33, a: 0x80 });
    }

    #[test]
    fn bad_hex_rejected() {
        let mut p = ColorPicker::new(red(), 3).unwrap();
        assert!(matches!(p.set_hex("not-hex").unwrap_err(), ColorError::BadHex(_)));
        assert!(matches!(p.set_hex("#xyz").unwrap_err(), ColorError::BadHex(_)));
        assert!(matches!(p.set_hex("#12345").unwrap_err(), ColorError::BadHex(_)));
    }

    #[test]
    fn to_hex_roundtrip() {
        let r = Rgba { r: 0x11, g: 0x22, b: 0x33, a: 0xab };
        assert_eq!(r.to_hex(), "#112233AB");
    }

    #[test]
    fn favorite_pins_and_unpins() {
        let mut p = ColorPicker::new(red(), 3).unwrap();
        p.favorite_current();
        p.favorite_current(); // dedup
        assert_eq!(p.favorites.len(), 1);
        p.current = green();
        p.favorite_current();
        assert_eq!(p.favorites.len(), 2);
        assert!(p.unfavorite(red()));
        assert!(!p.unfavorite(red()));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ColorPicker::new(red(), 3).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), ColorError::SchemaMismatch));
    }

    #[test]
    fn picker_serde_roundtrip() {
        let mut p = ColorPicker::new(red(), 3).unwrap();
        p.favorite_current();
        p.commit_recent();
        let j = serde_json::to_string(&p).unwrap();
        let back: ColorPicker = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
