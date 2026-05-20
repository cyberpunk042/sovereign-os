//! `sovereign-cockpit-column-resize` — per-column width state.
//!
//! Each column has min/max/current width in px. set_width clamps;
//! drag_delta applies a delta to width; clamp keeps within bounds.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One column.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Column {
    /// Min width px.
    pub min_px: u32,
    /// Max width px.
    pub max_px: u32,
    /// Current width.
    pub width_px: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColumnResize {
    /// Schema version.
    pub schema_version: String,
    /// id → column.
    pub columns: BTreeMap<String, Column>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ResizeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("column id empty")]
    EmptyId,
    /// Bad bounds.
    #[error("min ({min}) > max ({max})")]
    BadBounds {
        /// min.
        min: u32,
        /// max.
        max: u32,
    },
    /// Unknown.
    #[error("unknown column: {0}")]
    UnknownColumn(String),
}

impl ColumnResize {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            columns: BTreeMap::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, id: &str, min_px: u32, max_px: u32, initial_px: u32) -> Result<(), ResizeError> {
        if id.is_empty() { return Err(ResizeError::EmptyId); }
        if min_px > max_px { return Err(ResizeError::BadBounds { min: min_px, max: max_px }); }
        let clamped = initial_px.clamp(min_px, max_px);
        self.columns.insert(id.into(), Column { min_px, max_px, width_px: clamped });
        Ok(())
    }

    /// Set width (clamped).
    pub fn set_width(&mut self, id: &str, width_px: u32) -> Result<u32, ResizeError> {
        let c = self.columns.get_mut(id).ok_or_else(|| ResizeError::UnknownColumn(id.into()))?;
        let new = width_px.clamp(c.min_px, c.max_px);
        c.width_px = new;
        Ok(new)
    }

    /// Drag delta (signed) — returns new width.
    pub fn drag_delta(&mut self, id: &str, delta_px: i32) -> Result<u32, ResizeError> {
        let c = self.columns.get_mut(id).ok_or_else(|| ResizeError::UnknownColumn(id.into()))?;
        let new = if delta_px >= 0 {
            c.width_px.saturating_add(delta_px as u32)
        } else {
            c.width_px.saturating_sub((-delta_px) as u32)
        };
        let clamped = new.clamp(c.min_px, c.max_px);
        c.width_px = clamped;
        Ok(clamped)
    }

    /// Reset to min.
    pub fn reset(&mut self, id: &str) -> Result<u32, ResizeError> {
        let c = self.columns.get_mut(id).ok_or_else(|| ResizeError::UnknownColumn(id.into()))?;
        c.width_px = c.min_px;
        Ok(c.width_px)
    }

    /// Width.
    pub fn width_of(&self, id: &str) -> Option<u32> {
        self.columns.get(id).map(|c| c.width_px)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ResizeError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ResizeError::SchemaMismatch); }
        for (id, c) in &self.columns {
            if id.is_empty() { return Err(ResizeError::EmptyId); }
            if c.min_px > c.max_px { return Err(ResizeError::BadBounds { min: c.min_px, max: c.max_px }); }
        }
        Ok(())
    }
}

impl Default for ColumnResize {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn initial_clamped() {
        let mut r = ColumnResize::new();
        r.register("c", 50, 200, 500).unwrap();
        assert_eq!(r.width_of("c"), Some(200));
    }

    #[test]
    fn set_width_clamps() {
        let mut r = ColumnResize::new();
        r.register("c", 50, 200, 100).unwrap();
        let w = r.set_width("c", 1000).unwrap();
        assert_eq!(w, 200);
        let w = r.set_width("c", 0).unwrap();
        assert_eq!(w, 50);
    }

    #[test]
    fn drag_delta_positive_negative() {
        let mut r = ColumnResize::new();
        r.register("c", 50, 200, 100).unwrap();
        let w = r.drag_delta("c", 30).unwrap();
        assert_eq!(w, 130);
        let w = r.drag_delta("c", -200).unwrap();
        assert_eq!(w, 50);
    }

    #[test]
    fn reset_to_min() {
        let mut r = ColumnResize::new();
        r.register("c", 50, 200, 150).unwrap();
        let w = r.reset("c").unwrap();
        assert_eq!(w, 50);
    }

    #[test]
    fn bad_bounds_rejected() {
        let mut r = ColumnResize::new();
        assert!(matches!(r.register("c", 200, 50, 100).unwrap_err(), ResizeError::BadBounds { .. }));
    }

    #[test]
    fn unknown_column_rejected() {
        let mut r = ColumnResize::new();
        assert!(matches!(r.set_width("nope", 100).unwrap_err(), ResizeError::UnknownColumn(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut r = ColumnResize::new();
        assert!(matches!(r.register("", 50, 200, 100).unwrap_err(), ResizeError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = ColumnResize::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), ResizeError::SchemaMismatch));
    }

    #[test]
    fn resize_serde_roundtrip() {
        let mut r = ColumnResize::new();
        r.register("c", 50, 200, 100).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: ColumnResize = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
