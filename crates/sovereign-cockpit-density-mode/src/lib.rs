//! `sovereign-cockpit-density-mode` — operator-selectable UI density.
//!
//! 4 density modes:
//! - Compact     — tight rows, small typography (default for power users)
//! - Comfortable — default
//! - Spacious    — wide rows, generous padding
//! - Touch       — touch-optimized large hit targets
//!
//! Each mode declares (row_height_px, padding_px, font_pt). Pure visual.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 4 density modes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DensityMode {
    /// Compact.
    Compact,
    /// Comfortable (default).
    Comfortable,
    /// Spacious.
    Spacious,
    /// Touch.
    Touch,
}

/// Resolved spacing tuple.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Spacing {
    /// Row height (px).
    pub row_height_px: u16,
    /// Padding (px).
    pub padding_px: u16,
    /// Font size (pt).
    pub font_pt: u16,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DensityState {
    /// Schema version.
    pub schema_version: String,
    /// Current mode.
    pub mode: DensityMode,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DensityError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl DensityMode {
    /// All 4 modes.
    pub const ALL: [DensityMode; 4] = [
        DensityMode::Compact,
        DensityMode::Comfortable,
        DensityMode::Spacious,
        DensityMode::Touch,
    ];

    /// Canonical spacing for this mode.
    pub fn spacing(self) -> Spacing {
        match self {
            DensityMode::Compact => Spacing {
                row_height_px: 28,
                padding_px: 4,
                font_pt: 11,
            },
            DensityMode::Comfortable => Spacing {
                row_height_px: 36,
                padding_px: 8,
                font_pt: 13,
            },
            DensityMode::Spacious => Spacing {
                row_height_px: 48,
                padding_px: 12,
                font_pt: 14,
            },
            DensityMode::Touch => Spacing {
                row_height_px: 56,
                padding_px: 16,
                font_pt: 16,
            },
        }
    }
}

impl DensityState {
    /// Default state — Comfortable.
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: DensityMode::Comfortable,
        }
    }

    /// Switch mode.
    pub fn switch(&mut self, mode: DensityMode) {
        self.mode = mode;
    }

    /// Resolved spacing.
    pub fn spacing(&self) -> Spacing {
        self.mode.spacing()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DensityError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DensityError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_comfortable() {
        assert_eq!(DensityState::default_state().mode, DensityMode::Comfortable);
    }

    #[test]
    fn spacing_progression_monotonic_row_height() {
        let order = [
            DensityMode::Compact,
            DensityMode::Comfortable,
            DensityMode::Spacious,
            DensityMode::Touch,
        ];
        for w in order.windows(2) {
            assert!(w[0].spacing().row_height_px < w[1].spacing().row_height_px);
        }
    }

    #[test]
    fn spacing_progression_monotonic_padding() {
        let order = [
            DensityMode::Compact,
            DensityMode::Comfortable,
            DensityMode::Spacious,
            DensityMode::Touch,
        ];
        for w in order.windows(2) {
            assert!(w[0].spacing().padding_px < w[1].spacing().padding_px);
        }
    }

    #[test]
    fn switch_updates_mode() {
        let mut s = DensityState::default_state();
        s.switch(DensityMode::Touch);
        assert_eq!(s.mode, DensityMode::Touch);
        assert_eq!(s.spacing().row_height_px, 56);
    }

    #[test]
    fn touch_has_largest_font() {
        assert_eq!(DensityMode::Touch.spacing().font_pt, 16);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = DensityState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            DensityError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&DensityMode::Compact).unwrap(),
            "\"compact\""
        );
        assert_eq!(
            serde_json::to_string(&DensityMode::Comfortable).unwrap(),
            "\"comfortable\""
        );
        assert_eq!(
            serde_json::to_string(&DensityMode::Spacious).unwrap(),
            "\"spacious\""
        );
        assert_eq!(
            serde_json::to_string(&DensityMode::Touch).unwrap(),
            "\"touch\""
        );
    }

    #[test]
    fn state_serde_roundtrip() {
        let mut s = DensityState::default_state();
        s.switch(DensityMode::Spacious);
        let j = serde_json::to_string(&s).unwrap();
        let back: DensityState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
