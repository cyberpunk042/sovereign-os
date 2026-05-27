//! `sovereign-cockpit-text-size-policy` — text size accessibility.
//!
//! Global `scale_bp` (basis points, 10000 = 100%). Per-element
//! override allowed via `set_element_override(id, scale_bp)`.
//! `effective_scale_bp(element_id)` returns override × global / 10000.
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
pub struct TextSizePolicy {
    /// Schema version.
    pub schema_version: String,
    /// Global scale (10000 = 100%).
    pub scale_bp: u32,
    /// element id → override scale_bp.
    pub overrides: BTreeMap<String, u32>,
    /// Allowed presets.
    pub presets: BTreeMap<String, u32>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TextSizeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("element id empty")]
    EmptyElement,
    /// Empty.
    #[error("preset name empty")]
    EmptyPreset,
    /// Out of range.
    #[error("scale_bp must be in 1000..=40000 (10% to 400%), got {0}")]
    OutOfRange(u32),
}

const MIN_BP: u32 = 1000;
const MAX_BP: u32 = 40000;

impl TextSizePolicy {
    /// New with default presets.
    pub fn new() -> Self {
        let mut presets = BTreeMap::new();
        presets.insert("small".into(), 8500);
        presets.insert("normal".into(), 10000);
        presets.insert("large".into(), 11500);
        presets.insert("x-large".into(), 13000);
        presets.insert("xx-large".into(), 15000);
        Self {
            schema_version: SCHEMA_VERSION.into(),
            scale_bp: 10000,
            overrides: BTreeMap::new(),
            presets,
        }
    }

    /// Set global scale.
    pub fn set_scale(&mut self, scale_bp: u32) -> Result<(), TextSizeError> {
        if !(MIN_BP..=MAX_BP).contains(&scale_bp) {
            return Err(TextSizeError::OutOfRange(scale_bp));
        }
        self.scale_bp = scale_bp;
        Ok(())
    }

    /// Apply preset by name.
    pub fn apply_preset(&mut self, name: &str) -> Result<(), TextSizeError> {
        if name.is_empty() {
            return Err(TextSizeError::EmptyPreset);
        }
        let scale = self
            .presets
            .get(name)
            .copied()
            .ok_or(TextSizeError::EmptyPreset)?;
        self.scale_bp = scale;
        Ok(())
    }

    /// Per-element override.
    pub fn set_element_override(&mut self, id: &str, scale_bp: u32) -> Result<(), TextSizeError> {
        if id.is_empty() {
            return Err(TextSizeError::EmptyElement);
        }
        if !(MIN_BP..=MAX_BP).contains(&scale_bp) {
            return Err(TextSizeError::OutOfRange(scale_bp));
        }
        self.overrides.insert(id.into(), scale_bp);
        Ok(())
    }

    /// Clear override.
    pub fn clear_override(&mut self, id: &str) -> bool {
        self.overrides.remove(id).is_some()
    }

    /// Effective scale_bp for an element id (multiplicative composition).
    pub fn effective_scale_bp(&self, id: &str) -> u32 {
        match self.overrides.get(id) {
            None => self.scale_bp,
            Some(o) => {
                // Composed: o × global / 10000. Saturating.
                let composed = (*o as u64).saturating_mul(self.scale_bp as u64) / 10000;
                composed.min(u32::MAX as u64) as u32
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TextSizeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TextSizeError::SchemaMismatch);
        }
        if !(MIN_BP..=MAX_BP).contains(&self.scale_bp) {
            return Err(TextSizeError::OutOfRange(self.scale_bp));
        }
        for (id, sc) in &self.overrides {
            if id.is_empty() {
                return Err(TextSizeError::EmptyElement);
            }
            if !(MIN_BP..=MAX_BP).contains(sc) {
                return Err(TextSizeError::OutOfRange(*sc));
            }
        }
        Ok(())
    }
}

impl Default for TextSizePolicy {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_normal() {
        let p = TextSizePolicy::new();
        assert_eq!(p.scale_bp, 10000);
    }

    #[test]
    fn preset_changes_scale() {
        let mut p = TextSizePolicy::new();
        p.apply_preset("large").unwrap();
        assert_eq!(p.scale_bp, 11500);
    }

    #[test]
    fn effective_no_override() {
        let p = TextSizePolicy::new();
        assert_eq!(p.effective_scale_bp("body"), 10000);
    }

    #[test]
    fn override_composes() {
        let mut p = TextSizePolicy::new();
        p.set_scale(12000).unwrap(); // global 120%
        p.set_element_override("title", 15000).unwrap(); // 150%
        // Effective: 15000 × 12000 / 10000 = 18000.
        assert_eq!(p.effective_scale_bp("title"), 18000);
    }

    #[test]
    fn out_of_range_rejected() {
        let mut p = TextSizePolicy::new();
        assert!(matches!(
            p.set_scale(500).unwrap_err(),
            TextSizeError::OutOfRange(_)
        ));
        assert!(matches!(
            p.set_scale(50000).unwrap_err(),
            TextSizeError::OutOfRange(_)
        ));
    }

    #[test]
    fn clear_override_reverts() {
        let mut p = TextSizePolicy::new();
        p.set_element_override("body", 15000).unwrap();
        p.clear_override("body");
        assert_eq!(p.effective_scale_bp("body"), 10000);
    }

    #[test]
    fn unknown_preset_rejected() {
        let mut p = TextSizePolicy::new();
        assert!(matches!(
            p.apply_preset("nope").unwrap_err(),
            TextSizeError::EmptyPreset
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut p = TextSizePolicy::new();
        assert!(matches!(
            p.set_element_override("", 10000).unwrap_err(),
            TextSizeError::EmptyElement
        ));
        assert!(matches!(
            p.apply_preset("").unwrap_err(),
            TextSizeError::EmptyPreset
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = TextSizePolicy::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            TextSizeError::SchemaMismatch
        ));
    }

    #[test]
    fn text_serde_roundtrip() {
        let mut p = TextSizePolicy::new();
        p.set_scale(12000).unwrap();
        p.set_element_override("title", 15000).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: TextSizePolicy = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
