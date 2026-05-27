//! `sovereign-cockpit-kpi-tile-grid` — KPI dashboard tiles.
//!
//! Each tile has a label, an optional unit, a value (as integer
//! count or float-encoded-via-millis-of-precision, kept simple here
//! with `f64`), an optional `goal_value`, and tri-thresholds:
//! `warn_at` and `crit_at` (each with a `direction`: HigherIsWorse
//! or LowerIsWorse). `status_for(tile_id)` returns Ok/Warn/Crit/
//! Unknown. `format_value(tile_id)` returns the human string.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Threshold direction.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Direction {
    /// Higher is worse (e.g. error rate, latency).
    HigherIsWorse,
    /// Lower is worse (e.g. throughput).
    LowerIsWorse,
}

/// Status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// OK.
    Ok,
    /// Warning.
    Warn,
    /// Critical.
    Crit,
    /// No value yet.
    Unknown,
}

/// One tile.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Tile {
    /// Stable id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Unit (e.g. "ms", "req/s", "%"); empty = no unit.
    pub unit: String,
    /// Decimal places to render.
    pub decimals: u8,
    /// Current value.
    pub value: Option<f64>,
    /// Goal (rendered as hint; optional).
    pub goal: Option<f64>,
    /// Warn threshold.
    pub warn_at: Option<f64>,
    /// Crit threshold.
    pub crit_at: Option<f64>,
    /// Direction.
    pub direction: Direction,
    /// Display order.
    pub order: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct KpiTileGrid {
    /// Schema version.
    pub schema_version: String,
    /// id → tile.
    pub tiles: BTreeMap<String, Tile>,
    /// Next order to assign.
    pub next_order: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum KpiError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("tile id empty")]
    EmptyId,
    /// Empty label.
    #[error("tile label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate tile id: {0}")]
    DuplicateId(String),
    /// Unknown tile.
    #[error("unknown tile: {0}")]
    UnknownTile(String),
    /// Threshold direction mismatch.
    #[error("warn/crit ordering violates direction: warn={warn:?} crit={crit:?} {direction:?}")]
    BadThresholds {
        /// warn.
        warn: Option<f64>,
        /// crit.
        crit: Option<f64>,
        /// direction.
        direction: Direction,
    },
}

impl KpiTileGrid {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tiles: BTreeMap::new(),
            next_order: 0,
        }
    }

    /// Add a tile.
    pub fn add(&mut self, mut tile: Tile) -> Result<(), KpiError> {
        if tile.id.is_empty() {
            return Err(KpiError::EmptyId);
        }
        if tile.label.is_empty() {
            return Err(KpiError::EmptyLabel);
        }
        if self.tiles.contains_key(&tile.id) {
            return Err(KpiError::DuplicateId(tile.id));
        }
        check_thresholds(&tile)?;
        tile.order = self.next_order;
        self.next_order = self.next_order.wrapping_add(1);
        self.tiles.insert(tile.id.clone(), tile);
        Ok(())
    }

    /// Update value.
    pub fn set_value(&mut self, id: &str, value: Option<f64>) -> Result<(), KpiError> {
        let t = self
            .tiles
            .get_mut(id)
            .ok_or_else(|| KpiError::UnknownTile(id.into()))?;
        t.value = value;
        Ok(())
    }

    /// Status for a tile.
    pub fn status_for(&self, id: &str) -> Status {
        let Some(t) = self.tiles.get(id) else {
            return Status::Unknown;
        };
        let Some(v) = t.value else {
            return Status::Unknown;
        };
        match t.direction {
            Direction::HigherIsWorse => {
                if let Some(c) = t.crit_at
                    && v >= c
                {
                    return Status::Crit;
                }
                if let Some(w) = t.warn_at
                    && v >= w
                {
                    return Status::Warn;
                }
                Status::Ok
            }
            Direction::LowerIsWorse => {
                if let Some(c) = t.crit_at
                    && v <= c
                {
                    return Status::Crit;
                }
                if let Some(w) = t.warn_at
                    && v <= w
                {
                    return Status::Warn;
                }
                Status::Ok
            }
        }
    }

    /// Format the tile's value as a human string.
    pub fn format_value(&self, id: &str) -> Option<String> {
        let t = self.tiles.get(id)?;
        let v = t.value?;
        let decimals = t.decimals as usize;
        let formatted = format!("{:.*}", decimals, v);
        if t.unit.is_empty() {
            Some(formatted)
        } else {
            Some(format!("{formatted}{unit}", unit = t.unit))
        }
    }

    /// Tiles in declared order.
    pub fn ordered(&self) -> Vec<Tile> {
        let mut v: Vec<Tile> = self.tiles.values().cloned().collect();
        v.sort_by_key(|t| t.order);
        v
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.tiles.remove(id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), KpiError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(KpiError::SchemaMismatch);
        }
        for (id, t) in &self.tiles {
            if id.is_empty() {
                return Err(KpiError::EmptyId);
            }
            if t.label.is_empty() {
                return Err(KpiError::EmptyLabel);
            }
            check_thresholds(t)?;
        }
        Ok(())
    }
}

impl Default for KpiTileGrid {
    fn default() -> Self {
        Self::new()
    }
}

fn check_thresholds(t: &Tile) -> Result<(), KpiError> {
    if let (Some(w), Some(c)) = (t.warn_at, t.crit_at) {
        let ok = match t.direction {
            Direction::HigherIsWorse => c >= w,
            Direction::LowerIsWorse => c <= w,
        };
        if !ok {
            return Err(KpiError::BadThresholds {
                warn: Some(w),
                crit: Some(c),
                direction: t.direction,
            });
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tile(id: &str, dir: Direction, warn: Option<f64>, crit: Option<f64>) -> Tile {
        Tile {
            id: id.into(),
            label: id.into(),
            unit: "ms".into(),
            decimals: 1,
            value: None,
            goal: None,
            warn_at: warn,
            crit_at: crit,
            direction: dir,
            order: 0,
        }
    }

    #[test]
    fn higher_is_worse_thresholds() {
        let mut g = KpiTileGrid::new();
        g.add(tile(
            "lat",
            Direction::HigherIsWorse,
            Some(100.0),
            Some(500.0),
        ))
        .unwrap();
        g.set_value("lat", Some(50.0)).unwrap();
        assert_eq!(g.status_for("lat"), Status::Ok);
        g.set_value("lat", Some(200.0)).unwrap();
        assert_eq!(g.status_for("lat"), Status::Warn);
        g.set_value("lat", Some(600.0)).unwrap();
        assert_eq!(g.status_for("lat"), Status::Crit);
    }

    #[test]
    fn lower_is_worse_thresholds() {
        let mut g = KpiTileGrid::new();
        g.add(tile(
            "rps",
            Direction::LowerIsWorse,
            Some(100.0),
            Some(10.0),
        ))
        .unwrap();
        g.set_value("rps", Some(200.0)).unwrap();
        assert_eq!(g.status_for("rps"), Status::Ok);
        g.set_value("rps", Some(50.0)).unwrap();
        assert_eq!(g.status_for("rps"), Status::Warn);
        g.set_value("rps", Some(5.0)).unwrap();
        assert_eq!(g.status_for("rps"), Status::Crit);
    }

    #[test]
    fn unknown_when_no_value() {
        let mut g = KpiTileGrid::new();
        g.add(tile("lat", Direction::HigherIsWorse, None, None))
            .unwrap();
        assert_eq!(g.status_for("lat"), Status::Unknown);
    }

    #[test]
    fn format_with_unit_and_decimals() {
        let mut g = KpiTileGrid::new();
        g.add(tile("lat", Direction::HigherIsWorse, None, None))
            .unwrap();
        g.set_value("lat", Some(12.345)).unwrap();
        assert_eq!(g.format_value("lat"), Some("12.3ms".to_string()));
    }

    #[test]
    fn duplicate_rejected() {
        let mut g = KpiTileGrid::new();
        g.add(tile("a", Direction::HigherIsWorse, None, None))
            .unwrap();
        assert!(matches!(
            g.add(tile("a", Direction::HigherIsWorse, None, None))
                .unwrap_err(),
            KpiError::DuplicateId(_)
        ));
    }

    #[test]
    fn bad_thresholds_rejected() {
        let mut g = KpiTileGrid::new();
        // Higher-is-worse but crit < warn — invalid.
        assert!(matches!(
            g.add(tile(
                "a",
                Direction::HigherIsWorse,
                Some(500.0),
                Some(100.0)
            ))
            .unwrap_err(),
            KpiError::BadThresholds { .. }
        ));
    }

    #[test]
    fn ordered_preserves_insertion() {
        let mut g = KpiTileGrid::new();
        g.add(tile("a", Direction::HigherIsWorse, None, None))
            .unwrap();
        g.add(tile("b", Direction::HigherIsWorse, None, None))
            .unwrap();
        let v = g.ordered();
        assert_eq!(v[0].id, "a");
        assert_eq!(v[1].id, "b");
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut g = KpiTileGrid::new();
        assert!(matches!(
            g.add(Tile {
                id: "".into(),
                ..tile("x", Direction::HigherIsWorse, None, None)
            })
            .unwrap_err(),
            KpiError::EmptyId
        ));
        assert!(matches!(
            g.add(Tile {
                label: "".into(),
                ..tile("y", Direction::HigherIsWorse, None, None)
            })
            .unwrap_err(),
            KpiError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = KpiTileGrid::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            KpiError::SchemaMismatch
        ));
    }

    #[test]
    fn kpi_serde_roundtrip() {
        let mut g = KpiTileGrid::new();
        g.add(tile(
            "lat",
            Direction::HigherIsWorse,
            Some(100.0),
            Some(500.0),
        ))
        .unwrap();
        g.set_value("lat", Some(42.5)).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: KpiTileGrid = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
