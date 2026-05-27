//! `sovereign-cockpit-tag-color-palette` — tag colour mapping.
//!
//! A palette holds an ordered list of color tokens. Each tag may
//! be explicitly assigned a color; otherwise a deterministic fallback
//! is computed from `FNV-1a-64(tag) % palette.len()`. This keeps tag
//! colours stable across sessions without explicit assignment.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TagColorPalette {
    /// Schema version.
    pub schema_version: String,
    /// Color tokens in order.
    pub palette: Vec<String>,
    /// tag → explicit color token.
    pub assignments: BTreeMap<String, String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PaletteError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty palette.
    #[error("palette must have ≥1 color")]
    EmptyPalette,
    /// Empty.
    #[error("color token empty")]
    EmptyColor,
    /// Empty.
    #[error("tag empty")]
    EmptyTag,
    /// Unknown color.
    #[error("color not in palette: {0}")]
    UnknownColor(String),
}

fn fnv1a_64(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in bytes {
        h ^= u64::from(*b);
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

impl TagColorPalette {
    /// New.
    pub fn new(palette: &[&str]) -> Result<Self, PaletteError> {
        if palette.is_empty() {
            return Err(PaletteError::EmptyPalette);
        }
        for c in palette {
            if c.is_empty() {
                return Err(PaletteError::EmptyColor);
            }
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            palette: palette.iter().map(|c| (*c).into()).collect(),
            assignments: BTreeMap::new(),
        })
    }

    /// Assign explicit color.
    pub fn assign(&mut self, tag: &str, color: &str) -> Result<(), PaletteError> {
        if tag.is_empty() {
            return Err(PaletteError::EmptyTag);
        }
        if !self.palette.iter().any(|c| c == color) {
            return Err(PaletteError::UnknownColor(color.into()));
        }
        self.assignments.insert(tag.into(), color.into());
        Ok(())
    }

    /// Clear explicit assignment (falls back to deterministic).
    pub fn unassign(&mut self, tag: &str) -> bool {
        self.assignments.remove(tag).is_some()
    }

    /// Color for a tag.
    pub fn color_for(&self, tag: &str) -> Result<String, PaletteError> {
        if tag.is_empty() {
            return Err(PaletteError::EmptyTag);
        }
        if let Some(c) = self.assignments.get(tag) {
            return Ok(c.clone());
        }
        let idx = (fnv1a_64(tag.as_bytes()) % self.palette.len() as u64) as usize;
        Ok(self.palette[idx].clone())
    }

    /// Replace palette (drops assignments referring to removed colors).
    pub fn set_palette(&mut self, palette: &[&str]) -> Result<usize, PaletteError> {
        if palette.is_empty() {
            return Err(PaletteError::EmptyPalette);
        }
        for c in palette {
            if c.is_empty() {
                return Err(PaletteError::EmptyColor);
            }
        }
        let new_set: std::collections::BTreeSet<String> =
            palette.iter().map(|c| (*c).into()).collect();
        let to_drop: Vec<String> = self
            .assignments
            .iter()
            .filter(|(_, c)| !new_set.contains(c.as_str()))
            .map(|(k, _)| k.clone())
            .collect();
        let n = to_drop.len();
        for k in to_drop {
            self.assignments.remove(&k);
        }
        self.palette = palette.iter().map(|c| (*c).into()).collect();
        Ok(n)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PaletteError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PaletteError::SchemaMismatch);
        }
        if self.palette.is_empty() {
            return Err(PaletteError::EmptyPalette);
        }
        for c in &self.palette {
            if c.is_empty() {
                return Err(PaletteError::EmptyColor);
            }
        }
        let set: std::collections::BTreeSet<&String> = self.palette.iter().collect();
        for (t, c) in &self.assignments {
            if t.is_empty() {
                return Err(PaletteError::EmptyTag);
            }
            if !set.contains(c) {
                return Err(PaletteError::UnknownColor(c.clone()));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deterministic_fallback() {
        let p = TagColorPalette::new(&["red", "green", "blue"]).unwrap();
        let a = p.color_for("urgent").unwrap();
        let b = p.color_for("urgent").unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn explicit_assignment_wins() {
        let mut p = TagColorPalette::new(&["red", "green", "blue"]).unwrap();
        p.assign("urgent", "red").unwrap();
        assert_eq!(p.color_for("urgent").unwrap(), "red");
    }

    #[test]
    fn unassign_falls_back() {
        let mut p = TagColorPalette::new(&["red", "green", "blue"]).unwrap();
        let fallback = p.color_for("urgent").unwrap();
        p.assign("urgent", "red").unwrap();
        p.unassign("urgent");
        assert_eq!(p.color_for("urgent").unwrap(), fallback);
    }

    #[test]
    fn assign_unknown_color_rejected() {
        let mut p = TagColorPalette::new(&["red"]).unwrap();
        assert!(matches!(
            p.assign("x", "purple").unwrap_err(),
            PaletteError::UnknownColor(_)
        ));
    }

    #[test]
    fn set_palette_drops_invalid_assignments() {
        let mut p = TagColorPalette::new(&["red", "green", "blue"]).unwrap();
        p.assign("a", "red").unwrap();
        p.assign("b", "blue").unwrap();
        // Drop blue.
        let n = p.set_palette(&["red", "green", "yellow"]).unwrap();
        assert_eq!(n, 1);
        assert!(p.assignments.contains_key("a"));
        assert!(!p.assignments.contains_key("b"));
    }

    #[test]
    fn empty_palette_rejected() {
        assert!(matches!(
            TagColorPalette::new(&[]).unwrap_err(),
            PaletteError::EmptyPalette
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        assert!(matches!(
            TagColorPalette::new(&[""]).unwrap_err(),
            PaletteError::EmptyColor
        ));
        let mut p = TagColorPalette::new(&["red"]).unwrap();
        assert!(matches!(
            p.assign("", "red").unwrap_err(),
            PaletteError::EmptyTag
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = TagColorPalette::new(&["red"]).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PaletteError::SchemaMismatch
        ));
    }

    #[test]
    fn palette_distributes() {
        let p = TagColorPalette::new(&["a", "b", "c", "d"]).unwrap();
        let mut counts = std::collections::BTreeMap::<String, u32>::new();
        for i in 0..400 {
            let c = p.color_for(&format!("tag-{i}")).unwrap();
            *counts.entry(c).or_default() += 1;
        }
        // All 4 colors used.
        assert_eq!(counts.len(), 4);
    }

    #[test]
    fn palette_serde_roundtrip() {
        let mut p = TagColorPalette::new(&["red", "green"]).unwrap();
        p.assign("urgent", "red").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: TagColorPalette = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
