//! `sovereign-cockpit-theme-palette` — operator color theme.
//!
//! 5 canonical themes, each a fixed 4-color palette
//! (background / surface / foreground / accent). Pure visual.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 5 themes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Theme {
    /// Light (high-contrast on white).
    Light,
    /// Dark.
    Dark,
    /// High contrast (accessibility).
    HighContrast,
    /// Solarized.
    Solarized,
    /// Sepia.
    Sepia,
}

/// 4-color palette tuple (hex RGB without `#`).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Palette {
    /// Background.
    pub background: String,
    /// Surface (panel/card).
    pub surface: String,
    /// Foreground (text).
    pub foreground: String,
    /// Accent (highlights/cta).
    pub accent: String,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ThemeState {
    /// Schema version.
    pub schema_version: String,
    /// Current theme.
    pub theme: Theme,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ThemeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Hex string malformed.
    #[error("hex {0} invalid (expect 6 ascii-hex chars)")]
    BadHex(String),
}

impl Theme {
    /// All 5.
    pub const ALL: [Theme; 5] = [
        Theme::Light,
        Theme::Dark,
        Theme::HighContrast,
        Theme::Solarized,
        Theme::Sepia,
    ];

    /// Resolved palette for this theme.
    pub fn palette(self) -> Palette {
        match self {
            Theme::Light => Palette {
                background: "ffffff".into(),
                surface: "f7f7f7".into(),
                foreground: "1a1a1a".into(),
                accent: "0066cc".into(),
            },
            Theme::Dark => Palette {
                background: "0e0e10".into(),
                surface: "1a1a1d".into(),
                foreground: "e0e0e0".into(),
                accent: "5aa9ff".into(),
            },
            Theme::HighContrast => Palette {
                background: "000000".into(),
                surface: "0a0a0a".into(),
                foreground: "ffffff".into(),
                accent: "ffff00".into(),
            },
            Theme::Solarized => Palette {
                background: "002b36".into(),
                surface: "073642".into(),
                foreground: "839496".into(),
                accent: "b58900".into(),
            },
            Theme::Sepia => Palette {
                background: "f4ecd8".into(),
                surface: "ebe2c5".into(),
                foreground: "5b4636".into(),
                accent: "8b5e3c".into(),
            },
        }
    }
}

fn hex_ok(s: &str) -> bool {
    s.len() == 6 && s.bytes().all(|b| b.is_ascii_hexdigit())
}

impl Palette {
    /// Validate hex strings.
    pub fn validate(&self) -> Result<(), ThemeError> {
        for (label, h) in [
            ("background", &self.background),
            ("surface", &self.surface),
            ("foreground", &self.foreground),
            ("accent", &self.accent),
        ] {
            let _ = label;
            if !hex_ok(h) {
                return Err(ThemeError::BadHex(h.clone()));
            }
        }
        Ok(())
    }
}

impl ThemeState {
    /// Default — Dark.
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            theme: Theme::Dark,
        }
    }

    /// Switch theme.
    pub fn switch(&mut self, theme: Theme) {
        self.theme = theme;
    }

    /// Resolved palette.
    pub fn palette(&self) -> Palette {
        self.theme.palette()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ThemeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ThemeError::SchemaMismatch);
        }
        self.theme.palette().validate()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_dark() {
        assert_eq!(ThemeState::default_state().theme, Theme::Dark);
    }

    #[test]
    fn each_theme_palette_validates() {
        for t in Theme::ALL {
            t.palette().validate().unwrap();
        }
    }

    #[test]
    fn switch_updates_palette() {
        let mut s = ThemeState::default_state();
        s.switch(Theme::HighContrast);
        assert_eq!(s.palette().accent, "ffff00");
    }

    #[test]
    fn high_contrast_uses_black_and_white() {
        let p = Theme::HighContrast.palette();
        assert_eq!(p.background, "000000");
        assert_eq!(p.foreground, "ffffff");
    }

    #[test]
    fn solarized_uses_dark_blue_background() {
        assert_eq!(Theme::Solarized.palette().background, "002b36");
    }

    #[test]
    fn bad_hex_caught() {
        let p = Palette {
            background: "xxx".into(),
            surface: "ffffff".into(),
            foreground: "000000".into(),
            accent: "ff0000".into(),
        };
        assert!(matches!(p.validate().unwrap_err(), ThemeError::BadHex(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ThemeState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            ThemeError::SchemaMismatch
        ));
    }

    #[test]
    fn theme_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Theme::HighContrast).unwrap(),
            "\"high-contrast\""
        );
        assert_eq!(
            serde_json::to_string(&Theme::Solarized).unwrap(),
            "\"solarized\""
        );
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = ThemeState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: ThemeState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
