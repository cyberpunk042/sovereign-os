//! `sovereign-cockpit-row-density` — per-density row dimensions.
//!
//! 4 Density levels map to (row_height_px, line_count, show_secondary)
//! triples. Density choice drives compactness/readability tradeoff.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Density.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Density {
    /// Compact — most rows visible, minimal padding.
    Compact,
    /// Cozy — readable but tight.
    Cozy,
    /// Comfortable — default.
    Comfortable,
    /// Spacious — biggest, fewest rows.
    Spacious,
}

/// Per-density layout output.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct RowLayout {
    /// Row height in px.
    pub row_height_px: u32,
    /// Visible line count.
    pub line_count: u8,
    /// Show secondary metadata row?
    pub show_secondary: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RowDensity {
    /// Schema version.
    pub schema_version: String,
    /// Active density.
    pub density: Density,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DensityError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl RowDensity {
    /// New with given density.
    pub fn new(density: Density) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            density,
        }
    }

    /// Resolve layout for current density.
    pub fn layout(&self) -> RowLayout {
        Self::layout_of(self.density)
    }

    /// Stateless layout lookup.
    pub fn layout_of(d: Density) -> RowLayout {
        match d {
            Density::Compact => RowLayout {
                row_height_px: 24,
                line_count: 1,
                show_secondary: false,
            },
            Density::Cozy => RowLayout {
                row_height_px: 32,
                line_count: 1,
                show_secondary: false,
            },
            Density::Comfortable => RowLayout {
                row_height_px: 44,
                line_count: 2,
                show_secondary: true,
            },
            Density::Spacious => RowLayout {
                row_height_px: 64,
                line_count: 3,
                show_secondary: true,
            },
        }
    }

    /// Set density.
    pub fn set_density(&mut self, d: Density) {
        self.density = d;
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
    fn compact_minimal() {
        let r = RowDensity::layout_of(Density::Compact);
        assert_eq!(r.row_height_px, 24);
        assert!(!r.show_secondary);
        assert_eq!(r.line_count, 1);
    }

    #[test]
    fn spacious_maximal() {
        let r = RowDensity::layout_of(Density::Spacious);
        assert_eq!(r.row_height_px, 64);
        assert!(r.show_secondary);
        assert_eq!(r.line_count, 3);
    }

    #[test]
    fn density_monotonic_height() {
        let h_compact = RowDensity::layout_of(Density::Compact).row_height_px;
        let h_cozy = RowDensity::layout_of(Density::Cozy).row_height_px;
        let h_comf = RowDensity::layout_of(Density::Comfortable).row_height_px;
        let h_spa = RowDensity::layout_of(Density::Spacious).row_height_px;
        assert!(h_compact < h_cozy);
        assert!(h_cozy < h_comf);
        assert!(h_comf < h_spa);
    }

    #[test]
    fn instance_layout_matches_static() {
        let d = RowDensity::new(Density::Cozy);
        assert_eq!(d.layout(), RowDensity::layout_of(Density::Cozy));
    }

    #[test]
    fn set_density_changes() {
        let mut d = RowDensity::new(Density::Compact);
        d.set_density(Density::Spacious);
        assert_eq!(d.density, Density::Spacious);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = RowDensity::new(Density::Cozy);
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DensityError::SchemaMismatch
        ));
    }

    #[test]
    fn density_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Density::Comfortable).unwrap(),
            "\"comfortable\""
        );
    }

    #[test]
    fn density_serde_roundtrip() {
        let d = RowDensity::new(Density::Spacious);
        let j = serde_json::to_string(&d).unwrap();
        let back: RowDensity = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
