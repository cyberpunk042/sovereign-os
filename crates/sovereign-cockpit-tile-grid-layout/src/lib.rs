//! `sovereign-cockpit-tile-grid-layout` — bounded W×H tile grid.
//!
//! Each tile claims a rectangle (x, y, w, h). place/move_to refuse
//! overlap with other tiles or out-of-bounds.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One tile rectangle.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Rect {
    /// x.
    pub x: u32,
    /// y.
    pub y: u32,
    /// w.
    pub w: u32,
    /// h.
    pub h: u32,
}

impl Rect {
    fn overlaps(&self, other: &Rect) -> bool {
        self.x < other.x + other.w
            && other.x < self.x + self.w
            && self.y < other.y + other.h
            && other.y < self.y + self.h
    }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TileGridLayout {
    /// Schema version.
    pub schema_version: String,
    /// Grid width.
    pub grid_w: u32,
    /// Grid height.
    pub grid_h: u32,
    /// id → tile rect.
    pub tiles: BTreeMap<String, Rect>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LayoutError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Zero size.
    #[error("zero-area tile")]
    ZeroArea,
    /// Out of bounds.
    #[error("rect ({x},{y},{w},{h}) extends past grid ({gw}×{gh})")]
    OutOfBounds {
        /// x.
        x: u32,
        /// y.
        y: u32,
        /// w.
        w: u32,
        /// h.
        h: u32,
        /// gw.
        gw: u32,
        /// gh.
        gh: u32,
    },
    /// Overlap.
    #[error("rect overlaps tile: {0}")]
    Overlap(String),
    /// Duplicate.
    #[error("duplicate tile id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown tile: {0}")]
    UnknownTile(String),
    /// Zero grid.
    #[error("grid_w and grid_h must be > 0")]
    ZeroGrid,
}

impl TileGridLayout {
    /// New.
    pub fn new(grid_w: u32, grid_h: u32) -> Result<Self, LayoutError> {
        if grid_w == 0 || grid_h == 0 { return Err(LayoutError::ZeroGrid); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            grid_w,
            grid_h,
            tiles: BTreeMap::new(),
        })
    }

    fn check_placement(&self, id: &str, rect: &Rect) -> Result<(), LayoutError> {
        if rect.w == 0 || rect.h == 0 { return Err(LayoutError::ZeroArea); }
        if rect.x.saturating_add(rect.w) > self.grid_w || rect.y.saturating_add(rect.h) > self.grid_h {
            return Err(LayoutError::OutOfBounds {
                x: rect.x, y: rect.y, w: rect.w, h: rect.h,
                gw: self.grid_w, gh: self.grid_h,
            });
        }
        for (other_id, other) in &self.tiles {
            if other_id == id { continue; }
            if rect.overlaps(other) {
                return Err(LayoutError::Overlap(other_id.clone()));
            }
        }
        Ok(())
    }

    /// Place new tile.
    pub fn place(&mut self, id: &str, rect: Rect) -> Result<(), LayoutError> {
        if id.is_empty() { return Err(LayoutError::EmptyId); }
        if self.tiles.contains_key(id) { return Err(LayoutError::DuplicateId(id.into())); }
        self.check_placement(id, &rect)?;
        self.tiles.insert(id.into(), rect);
        Ok(())
    }

    /// Move existing tile.
    pub fn move_to(&mut self, id: &str, rect: Rect) -> Result<(), LayoutError> {
        if !self.tiles.contains_key(id) {
            return Err(LayoutError::UnknownTile(id.into()));
        }
        self.check_placement(id, &rect)?;
        self.tiles.insert(id.into(), rect);
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.tiles.remove(id).is_some()
    }

    /// Tile at coords (returns id if any).
    pub fn tile_at(&self, x: u32, y: u32) -> Option<String> {
        for (id, r) in &self.tiles {
            if x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h {
                return Some(id.clone());
            }
        }
        None
    }

    /// Cells occupied.
    pub fn occupied_cells(&self) -> u64 {
        self.tiles.values().map(|r| (r.w as u64) * (r.h as u64)).sum()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LayoutError> {
        if self.schema_version != SCHEMA_VERSION { return Err(LayoutError::SchemaMismatch); }
        if self.grid_w == 0 || self.grid_h == 0 { return Err(LayoutError::ZeroGrid); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rect(x: u32, y: u32, w: u32, h: u32) -> Rect {
        Rect { x, y, w, h }
    }

    #[test]
    fn place_single() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        l.place("a", rect(0, 0, 3, 3)).unwrap();
        assert_eq!(l.tile_at(1, 1).as_deref(), Some("a"));
    }

    #[test]
    fn out_of_bounds_rejected() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        assert!(matches!(l.place("a", rect(8, 0, 5, 3)).unwrap_err(), LayoutError::OutOfBounds { .. }));
    }

    #[test]
    fn overlap_rejected() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        l.place("a", rect(0, 0, 3, 3)).unwrap();
        assert!(matches!(l.place("b", rect(2, 2, 3, 3)).unwrap_err(), LayoutError::Overlap(_)));
    }

    #[test]
    fn duplicate_rejected() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        l.place("a", rect(0, 0, 1, 1)).unwrap();
        assert!(matches!(l.place("a", rect(2, 2, 1, 1)).unwrap_err(), LayoutError::DuplicateId(_)));
    }

    #[test]
    fn move_to_clear_space() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        l.place("a", rect(0, 0, 3, 3)).unwrap();
        l.move_to("a", rect(5, 5, 3, 3)).unwrap();
        assert!(l.tile_at(1, 1).is_none());
        assert_eq!(l.tile_at(6, 6).as_deref(), Some("a"));
    }

    #[test]
    fn occupied_cells() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        l.place("a", rect(0, 0, 3, 2)).unwrap();
        l.place("b", rect(5, 0, 2, 2)).unwrap();
        assert_eq!(l.occupied_cells(), 10);
    }

    #[test]
    fn zero_area_rejected() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        assert!(matches!(l.place("a", rect(0, 0, 0, 3)).unwrap_err(), LayoutError::ZeroArea));
    }

    #[test]
    fn zero_grid_rejected() {
        assert!(matches!(TileGridLayout::new(0, 10).unwrap_err(), LayoutError::ZeroGrid));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), LayoutError::SchemaMismatch));
    }

    #[test]
    fn layout_serde_roundtrip() {
        let mut l = TileGridLayout::new(10, 10).unwrap();
        l.place("a", rect(0, 0, 2, 2)).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: TileGridLayout = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
