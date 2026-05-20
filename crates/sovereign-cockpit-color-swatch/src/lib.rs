//! `sovereign-cockpit-color-swatch` — ordered named-color grid.
//!
//! Maintains `Vec<Swatch>` and a `selected_index: Option<usize>`.
//! `add(swatch)` appends; `insert_at(idx, swatch)` inserts and adjusts
//! selection if needed; `remove(idx)` clears selection if it pointed
//! to the removed slot.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One swatch.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Swatch {
    /// Stable name.
    pub name: String,
    /// Hex (#RRGGBB or #RRGGBBAA, case-insensitive).
    pub hex: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColorSwatch {
    /// Schema version.
    pub schema_version: String,
    /// Swatches in render order.
    pub swatches: Vec<Swatch>,
    /// Selected index.
    pub selected_index: Option<usize>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SwatchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty name.
    #[error("name empty")]
    EmptyName,
    /// Bad hex.
    #[error("bad hex: {0}")]
    BadHex(String),
    /// Duplicate.
    #[error("duplicate swatch name: {0}")]
    DuplicateName(String),
    /// Out of bounds.
    #[error("index {0} out of bounds (len {1})")]
    OutOfBounds(usize, usize),
}

impl ColorSwatch {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            swatches: Vec::new(),
            selected_index: None,
        }
    }

    /// Append.
    pub fn add(&mut self, s: Swatch) -> Result<(), SwatchError> {
        Self::validate_swatch(&s)?;
        if self.swatches.iter().any(|x| x.name == s.name) {
            return Err(SwatchError::DuplicateName(s.name));
        }
        self.swatches.push(s);
        Ok(())
    }

    /// Insert at index.
    pub fn insert_at(&mut self, idx: usize, s: Swatch) -> Result<(), SwatchError> {
        if idx > self.swatches.len() {
            return Err(SwatchError::OutOfBounds(idx, self.swatches.len()));
        }
        Self::validate_swatch(&s)?;
        if self.swatches.iter().any(|x| x.name == s.name) {
            return Err(SwatchError::DuplicateName(s.name));
        }
        self.swatches.insert(idx, s);
        if let Some(sel) = self.selected_index {
            if sel >= idx { self.selected_index = Some(sel + 1); }
        }
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, idx: usize) -> Result<Swatch, SwatchError> {
        if idx >= self.swatches.len() {
            return Err(SwatchError::OutOfBounds(idx, self.swatches.len()));
        }
        let s = self.swatches.remove(idx);
        match self.selected_index {
            Some(sel) if sel == idx => self.selected_index = None,
            Some(sel) if sel > idx => self.selected_index = Some(sel - 1),
            _ => {}
        }
        Ok(s)
    }

    /// Select.
    pub fn select(&mut self, idx: usize) -> Result<(), SwatchError> {
        if idx >= self.swatches.len() {
            return Err(SwatchError::OutOfBounds(idx, self.swatches.len()));
        }
        self.selected_index = Some(idx);
        Ok(())
    }

    /// Clear selection.
    pub fn clear_selection(&mut self) { self.selected_index = None; }

    /// Currently selected swatch.
    pub fn selected(&self) -> Option<&Swatch> {
        self.selected_index.and_then(|i| self.swatches.get(i))
    }

    fn validate_swatch(s: &Swatch) -> Result<(), SwatchError> {
        if s.name.is_empty() { return Err(SwatchError::EmptyName); }
        let h = s.hex.strip_prefix('#').ok_or_else(|| SwatchError::BadHex(s.hex.clone()))?;
        if !(h.len() == 6 || h.len() == 8) {
            return Err(SwatchError::BadHex(s.hex.clone()));
        }
        if !h.chars().all(|c| c.is_ascii_hexdigit()) {
            return Err(SwatchError::BadHex(s.hex.clone()));
        }
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SwatchError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SwatchError::SchemaMismatch); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in &self.swatches {
            Self::validate_swatch(s)?;
            if !seen.insert(s.name.as_str()) {
                return Err(SwatchError::DuplicateName(s.name.clone()));
            }
        }
        if let Some(i) = self.selected_index {
            if i >= self.swatches.len() {
                return Err(SwatchError::OutOfBounds(i, self.swatches.len()));
            }
        }
        Ok(())
    }
}

impl Default for ColorSwatch {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sw(n: &str, h: &str) -> Swatch { Swatch { name: n.into(), hex: h.into() } }

    #[test]
    fn add_and_select() {
        let mut g = ColorSwatch::new();
        g.add(sw("primary", "#ff0000")).unwrap();
        g.select(0).unwrap();
        assert_eq!(g.selected().unwrap().name, "primary");
    }

    #[test]
    fn add_short_hex_rejected() {
        let mut g = ColorSwatch::new();
        assert!(matches!(g.add(sw("p", "#fff")).unwrap_err(), SwatchError::BadHex(_)));
    }

    #[test]
    fn missing_hash_rejected() {
        let mut g = ColorSwatch::new();
        assert!(matches!(g.add(sw("p", "ff0000")).unwrap_err(), SwatchError::BadHex(_)));
    }

    #[test]
    fn duplicate_rejected() {
        let mut g = ColorSwatch::new();
        g.add(sw("p", "#ff0000")).unwrap();
        assert!(matches!(g.add(sw("p", "#00ff00")).unwrap_err(), SwatchError::DuplicateName(_)));
    }

    #[test]
    fn insert_before_selected_shifts() {
        let mut g = ColorSwatch::new();
        g.add(sw("a", "#000000")).unwrap();
        g.add(sw("b", "#ffffff")).unwrap();
        g.select(1).unwrap();
        g.insert_at(0, sw("z", "#888888")).unwrap();
        assert_eq!(g.selected_index, Some(2));
    }

    #[test]
    fn remove_selected_clears() {
        let mut g = ColorSwatch::new();
        g.add(sw("a", "#000000")).unwrap();
        g.select(0).unwrap();
        g.remove(0).unwrap();
        assert!(g.selected_index.is_none());
    }

    #[test]
    fn remove_before_selected_shifts_down() {
        let mut g = ColorSwatch::new();
        g.add(sw("a", "#000000")).unwrap();
        g.add(sw("b", "#ffffff")).unwrap();
        g.select(1).unwrap();
        g.remove(0).unwrap();
        assert_eq!(g.selected_index, Some(0));
    }

    #[test]
    fn alpha_hex_accepted() {
        let mut g = ColorSwatch::new();
        g.add(sw("a", "#ff000080")).unwrap();
        g.validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = ColorSwatch::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(g.validate().unwrap_err(), SwatchError::SchemaMismatch));
    }

    #[test]
    fn swatch_serde_roundtrip() {
        let mut g = ColorSwatch::new();
        g.add(sw("a", "#ff0000")).unwrap();
        g.select(0).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: ColorSwatch = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
