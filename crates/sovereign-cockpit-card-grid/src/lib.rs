//! `sovereign-cockpit-card-grid` — responsive card-grid layout.
//!
//! Given a container width + per-card min/max width + gap, compute
//! the number of columns and actual per-card width that fits
//! without horizontal scroll.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Inputs.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct CardGridInputs {
    /// Container width.
    pub container_w: u32,
    /// Minimum card width.
    pub min_card_w: u32,
    /// Maximum card width.
    pub max_card_w: u32,
    /// Gap between cards (and between cards and edges).
    pub gap_px: u32,
}

/// Output.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct CardGridLayout {
    /// Number of columns.
    pub columns: u32,
    /// Actual per-card width (clamped to [min, max]).
    pub card_w: u32,
}

/// Envelope (for schema versioning).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CardGrid {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CardGridError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Container zero.
    #[error("container_w zero")]
    ContainerZero,
    /// Min >= Max.
    #[error("min_card_w {min} >= max_card_w {max}")]
    BadBounds {
        /// min.
        min: u32,
        /// max.
        max: u32,
    },
    /// min_card_w zero.
    #[error("min_card_w zero")]
    MinZero,
}

impl CardGrid {
    /// New.
    pub fn new() -> Self { Self { schema_version: SCHEMA_VERSION.into() } }

    /// Compute layout.
    pub fn layout(inputs: CardGridInputs) -> Result<CardGridLayout, CardGridError> {
        if inputs.container_w == 0 { return Err(CardGridError::ContainerZero); }
        if inputs.min_card_w == 0 { return Err(CardGridError::MinZero); }
        if inputs.min_card_w >= inputs.max_card_w {
            return Err(CardGridError::BadBounds { min: inputs.min_card_w, max: inputs.max_card_w });
        }
        // Find largest N where N*min + (N+1)*gap <= container_w.
        // Equivalently N <= (container - gap) / (min + gap)
        let denom = inputs.min_card_w + inputs.gap_px;
        let columns = if denom == 0 {
            1
        } else {
            ((inputs.container_w.saturating_sub(inputs.gap_px)) / denom).max(1)
        };
        // Compute actual card width: available width minus gaps divided by columns.
        let total_gap = inputs.gap_px * (columns + 1);
        let avail = inputs.container_w.saturating_sub(total_gap);
        let card_w_raw = avail / columns;
        let card_w = card_w_raw.clamp(inputs.min_card_w, inputs.max_card_w);
        Ok(CardGridLayout { columns, card_w })
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CardGridError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CardGridError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for CardGrid {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn inp(c: u32, min: u32, max: u32, gap: u32) -> CardGridInputs {
        CardGridInputs { container_w: c, min_card_w: min, max_card_w: max, gap_px: gap }
    }

    #[test]
    fn container_zero_rejected() {
        assert!(matches!(CardGrid::layout(inp(0, 100, 300, 10)).unwrap_err(), CardGridError::ContainerZero));
    }

    #[test]
    fn min_zero_rejected() {
        assert!(matches!(CardGrid::layout(inp(800, 0, 300, 10)).unwrap_err(), CardGridError::MinZero));
    }

    #[test]
    fn bad_bounds_rejected() {
        assert!(matches!(CardGrid::layout(inp(800, 300, 100, 10)).unwrap_err(), CardGridError::BadBounds { .. }));
    }

    #[test]
    fn three_columns_fit_at_min() {
        // container 800, min 200, max 300, gap 10
        // (800-10)/(200+10) = 790/210 = 3
        let l = CardGrid::layout(inp(800, 200, 300, 10)).unwrap();
        assert_eq!(l.columns, 3);
    }

    #[test]
    fn card_width_clamped_to_max() {
        // very wide container -> card_w would exceed max -> clamped
        let l = CardGrid::layout(inp(2000, 100, 200, 10)).unwrap();
        assert!(l.card_w <= 200);
    }

    #[test]
    fn card_width_clamped_to_min() {
        // small container -> at least 1 column, card_w >= min
        let l = CardGrid::layout(inp(120, 100, 300, 10)).unwrap();
        assert!(l.card_w >= 100);
    }

    #[test]
    fn single_column_when_tight() {
        let l = CardGrid::layout(inp(150, 100, 300, 10)).unwrap();
        assert_eq!(l.columns, 1);
    }

    #[test]
    fn gap_zero_works() {
        let l = CardGrid::layout(inp(800, 200, 300, 0)).unwrap();
        assert_eq!(l.columns, 4);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = CardGrid::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(g.validate().unwrap_err(), CardGridError::SchemaMismatch));
    }

    #[test]
    fn layout_serde_roundtrip() {
        let l = CardGrid::layout(inp(800, 200, 300, 10)).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: CardGridLayout = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
