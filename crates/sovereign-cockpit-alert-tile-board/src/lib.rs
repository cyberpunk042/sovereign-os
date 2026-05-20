//! `sovereign-cockpit-alert-tile-board` — alert tile board.
//!
//! Each `AlertTile { id, title, severity, summary, pinned,
//! acknowledged, ts_ms }`. Order:
//!   1. Pinned tiles first (alpha by title).
//!   2. Unacknowledged before acknowledged.
//!   3. Higher severity first.
//!   4. Newer ts first.
//!   5. Title alpha.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Info.
    Info,
    /// Notice.
    Notice,
    /// Warn.
    Warn,
    /// Error.
    Error,
    /// Critical.
    Critical,
}

/// One tile.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AlertTile {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Severity.
    pub severity: Severity,
    /// Summary.
    pub summary: String,
    /// Pinned.
    pub pinned: bool,
    /// Acked.
    pub acknowledged: bool,
    /// Ts.
    pub ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AlertTileBoard {
    /// Schema version.
    pub schema_version: String,
    /// id → tile.
    pub tiles: BTreeMap<String, AlertTile>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TileError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Empty.
    #[error("summary empty")]
    EmptySummary,
    /// Duplicate.
    #[error("duplicate tile id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown tile: {0}")]
    UnknownTile(String),
}

impl AlertTileBoard {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tiles: BTreeMap::new(),
        }
    }

    /// Add a tile.
    pub fn add(&mut self, tile: AlertTile) -> Result<(), TileError> {
        if tile.id.is_empty() { return Err(TileError::EmptyId); }
        if tile.title.is_empty() { return Err(TileError::EmptyTitle); }
        if tile.summary.is_empty() { return Err(TileError::EmptySummary); }
        if self.tiles.contains_key(&tile.id) {
            return Err(TileError::DuplicateId(tile.id));
        }
        self.tiles.insert(tile.id.clone(), tile);
        Ok(())
    }

    /// Ack.
    pub fn ack(&mut self, id: &str) -> Result<bool, TileError> {
        let t = self.tiles.get_mut(id).ok_or_else(|| TileError::UnknownTile(id.into()))?;
        let was = t.acknowledged;
        t.acknowledged = true;
        Ok(!was)
    }

    /// Pin.
    pub fn pin(&mut self, id: &str, pinned: bool) -> Result<(), TileError> {
        let t = self.tiles.get_mut(id).ok_or_else(|| TileError::UnknownTile(id.into()))?;
        t.pinned = pinned;
        Ok(())
    }

    /// Ordered for display.
    pub fn ordered(&self) -> Vec<AlertTile> {
        let mut v: Vec<AlertTile> = self.tiles.values().cloned().collect();
        v.sort_by(|a, b| {
            b.pinned.cmp(&a.pinned)
                .then(a.acknowledged.cmp(&b.acknowledged))
                .then(b.severity.cmp(&a.severity))
                .then(b.ts_ms.cmp(&a.ts_ms))
                .then(a.title.cmp(&b.title))
        });
        v
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.tiles.remove(id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TileError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TileError::SchemaMismatch); }
        for (id, t) in &self.tiles {
            if id.is_empty() { return Err(TileError::EmptyId); }
            if t.title.is_empty() { return Err(TileError::EmptyTitle); }
            if t.summary.is_empty() { return Err(TileError::EmptySummary); }
        }
        Ok(())
    }
}

impl Default for AlertTileBoard {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(id: &str, sev: Severity, ts: u64) -> AlertTile {
        AlertTile {
            id: id.into(),
            title: id.into(),
            severity: sev,
            summary: format!("{id} summary"),
            pinned: false,
            acknowledged: false,
            ts_ms: ts,
        }
    }

    #[test]
    fn pinned_first() {
        let mut b = AlertTileBoard::new();
        b.add(t("a", Severity::Info, 0)).unwrap();
        b.add(t("b", Severity::Critical, 0)).unwrap();
        b.pin("a", true).unwrap();
        let o = b.ordered();
        assert_eq!(o[0].id, "a"); // pinned beats critical
    }

    #[test]
    fn unacked_before_acked() {
        let mut b = AlertTileBoard::new();
        b.add(t("a", Severity::Info, 0)).unwrap();
        b.add(t("b", Severity::Info, 0)).unwrap();
        b.ack("a").unwrap();
        let o = b.ordered();
        assert_eq!(o[0].id, "b"); // unacked b first
    }

    #[test]
    fn higher_severity_first() {
        let mut b = AlertTileBoard::new();
        b.add(t("low", Severity::Info, 0)).unwrap();
        b.add(t("high", Severity::Critical, 0)).unwrap();
        let o = b.ordered();
        assert_eq!(o[0].id, "high");
    }

    #[test]
    fn newer_first_among_same_severity() {
        let mut b = AlertTileBoard::new();
        b.add(t("old", Severity::Warn, 100)).unwrap();
        b.add(t("new", Severity::Warn, 200)).unwrap();
        let o = b.ordered();
        assert_eq!(o[0].id, "new");
    }

    #[test]
    fn ack_idempotent() {
        let mut b = AlertTileBoard::new();
        b.add(t("a", Severity::Info, 0)).unwrap();
        assert!(b.ack("a").unwrap());
        assert!(!b.ack("a").unwrap()); // second ack returns false
    }

    #[test]
    fn duplicate_rejected() {
        let mut b = AlertTileBoard::new();
        b.add(t("a", Severity::Info, 0)).unwrap();
        assert!(matches!(b.add(t("a", Severity::Info, 0)).unwrap_err(), TileError::DuplicateId(_)));
    }

    #[test]
    fn ack_unknown_rejected() {
        let mut b = AlertTileBoard::new();
        assert!(matches!(b.ack("nope").unwrap_err(), TileError::UnknownTile(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut b = AlertTileBoard::new();
        let mut tile = t("a", Severity::Info, 0);
        tile.id = "".into();
        assert!(matches!(b.add(tile).unwrap_err(), TileError::EmptyId));
        let mut tile = t("a", Severity::Info, 0);
        tile.title = "".into();
        assert!(matches!(b.add(tile).unwrap_err(), TileError::EmptyTitle));
        let mut tile = t("a", Severity::Info, 0);
        tile.summary = "".into();
        assert!(matches!(b.add(tile).unwrap_err(), TileError::EmptySummary));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = AlertTileBoard::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), TileError::SchemaMismatch));
    }

    #[test]
    fn tile_serde_roundtrip() {
        let mut b = AlertTileBoard::new();
        b.add(t("a", Severity::Critical, 100)).unwrap();
        b.pin("a", true).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: AlertTileBoard = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
