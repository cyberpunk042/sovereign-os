//! `sovereign-cockpit-hero-stat-tile` — big-number stat tile.
//!
//! Stat{label, value, unit, prev}. set(value, prev) populates;
//! delta_bp returns (value - prev) * 10000 / prev (zero prev →
//! 0 unless value > 0 → 10000 i32). Trend{Up/Flat/Down} derived
//! from delta sign with epsilon tolerance.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Trend.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Trend {
    /// Up.
    Up,
    /// Flat.
    Flat,
    /// Down.
    Down,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HeroStatTile {
    /// Schema version.
    pub schema_version: String,
    /// Label (e.g. "Active Sessions").
    pub label: String,
    /// Current value × 100 (centi-units to keep fractions precise).
    pub value_x100: i64,
    /// Previous value × 100.
    pub prev_x100: i64,
    /// Unit suffix (e.g. "ms", "%", "").
    pub unit: String,
    /// Delta threshold (bp) below which Trend is Flat.
    pub flat_epsilon_bp: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TileError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
}

impl HeroStatTile {
    /// New.
    pub fn new(label: &str, unit: &str, flat_epsilon_bp: u32) -> Result<Self, TileError> {
        if label.is_empty() { return Err(TileError::EmptyLabel); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            label: label.into(),
            value_x100: 0,
            prev_x100: 0,
            unit: unit.into(),
            flat_epsilon_bp,
        })
    }

    /// Set value + prev (centi-units, so 12.50 = 1250).
    pub fn set(&mut self, value_x100: i64, prev_x100: i64) {
        self.value_x100 = value_x100;
        self.prev_x100 = prev_x100;
    }

    /// Delta in basis points (relative to prev).
    pub fn delta_bp(&self) -> i64 {
        let prev = self.prev_x100;
        let diff = self.value_x100 - prev;
        if prev == 0 {
            if diff == 0 { 0 } else if diff > 0 { 10_000 } else { -10_000 }
        } else {
            (diff * 10_000) / prev.abs()
        }
    }

    /// Trend with epsilon.
    pub fn trend(&self) -> Trend {
        let d = self.delta_bp();
        let eps = self.flat_epsilon_bp as i64;
        if d.abs() <= eps { Trend::Flat }
        else if d > 0 { Trend::Up }
        else { Trend::Down }
    }

    /// Display value (integer-format value_x100 to "N" or "N.NN").
    pub fn display(&self) -> String {
        let whole = self.value_x100 / 100;
        let frac = (self.value_x100 % 100).abs();
        if frac == 0 {
            format!("{}{}", whole, self.unit)
        } else {
            format!("{}.{:02}{}", whole, frac, self.unit)
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TileError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TileError::SchemaMismatch); }
        if self.label.is_empty() { return Err(TileError::EmptyLabel); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn up_trend_detected() {
        let mut t = HeroStatTile::new("X", "", 50).unwrap();
        t.set(11000, 10000);
        // delta = 1000 / 10000 * 10000 = 1000 bp.
        assert_eq!(t.delta_bp(), 1000);
        assert_eq!(t.trend(), Trend::Up);
    }

    #[test]
    fn down_trend_detected() {
        let mut t = HeroStatTile::new("X", "", 50).unwrap();
        t.set(9000, 10000);
        assert_eq!(t.delta_bp(), -1000);
        assert_eq!(t.trend(), Trend::Down);
    }

    #[test]
    fn flat_within_epsilon() {
        let mut t = HeroStatTile::new("X", "", 100).unwrap();
        // 1% delta = 100 bp; eps = 100 → Flat (|<=eps).
        t.set(10100, 10000);
        assert_eq!(t.trend(), Trend::Flat);
    }

    #[test]
    fn zero_prev_with_positive_now() {
        let mut t = HeroStatTile::new("X", "", 0).unwrap();
        t.set(500, 0);
        assert_eq!(t.delta_bp(), 10000);
        assert_eq!(t.trend(), Trend::Up);
    }

    #[test]
    fn zero_prev_zero_now() {
        let mut t = HeroStatTile::new("X", "", 0).unwrap();
        t.set(0, 0);
        assert_eq!(t.delta_bp(), 0);
        assert_eq!(t.trend(), Trend::Flat);
    }

    #[test]
    fn display_integer_and_fraction() {
        let mut t = HeroStatTile::new("X", "ms", 0).unwrap();
        t.set(1234, 0);
        assert_eq!(t.display(), "12.34ms");
        t.set(1200, 0);
        assert_eq!(t.display(), "12ms");
    }

    #[test]
    fn empty_label_rejected() {
        assert!(matches!(HeroStatTile::new("", "", 0).unwrap_err(), TileError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = HeroStatTile::new("X", "", 0).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TileError::SchemaMismatch));
    }

    #[test]
    fn tile_serde_roundtrip() {
        let mut t = HeroStatTile::new("X", "", 0).unwrap();
        t.set(500, 400);
        let j = serde_json::to_string(&t).unwrap();
        let back: HeroStatTile = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
