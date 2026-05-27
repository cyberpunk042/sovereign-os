//! `sovereign-cockpit-tooltip-catalog` — operator-controllable tooltips.
//!
//! Registry keyed by element_id → (text, placement, delay_ms, enabled).
//! Operator can override default text + disable noisy tooltips.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Placement.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Placement {
    /// Above element.
    Top,
    /// Right of element.
    Right,
    /// Below element.
    Bottom,
    /// Left of element.
    Left,
}

/// One tooltip entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tooltip {
    /// Element id.
    pub element_id: String,
    /// Tooltip text (≤ 200 chars).
    pub text: String,
    /// Placement.
    pub placement: Placement,
    /// Delay before showing (ms).
    pub delay_ms: u16,
    /// Operator enabled this tooltip.
    pub enabled: bool,
}

/// Catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TooltipCatalog {
    /// Schema version.
    pub schema_version: String,
    /// Tooltips.
    pub tooltips: Vec<Tooltip>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TooltipError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty element_id.
    #[error("element_id empty")]
    EmptyElementId,
    /// Duplicate.
    #[error("duplicate element_id: {0}")]
    DuplicateId(String),
    /// Text too long.
    #[error("tooltip {id} text length {len} > 200")]
    TextTooLong {
        /// id.
        id: String,
        /// len.
        len: usize,
    },
    /// Unknown.
    #[error("unknown element_id: {0}")]
    Unknown(String),
}

impl TooltipCatalog {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tooltips: Vec::new(),
        }
    }

    /// Register a tooltip.
    pub fn register(&mut self, t: Tooltip) -> Result<(), TooltipError> {
        check_shape(&t)?;
        if self.tooltips.iter().any(|x| x.element_id == t.element_id) {
            return Err(TooltipError::DuplicateId(t.element_id));
        }
        self.tooltips.push(t);
        Ok(())
    }

    /// Override text for an existing tooltip.
    pub fn set_text(&mut self, id: &str, text: &str) -> Result<(), TooltipError> {
        let n = text.chars().count();
        if n > 200 {
            return Err(TooltipError::TextTooLong {
                id: id.into(),
                len: n,
            });
        }
        let t = self
            .tooltips
            .iter_mut()
            .find(|t| t.element_id == id)
            .ok_or_else(|| TooltipError::Unknown(id.into()))?;
        t.text = text.into();
        Ok(())
    }

    /// Set enabled flag.
    pub fn set_enabled(&mut self, id: &str, enabled: bool) -> Result<(), TooltipError> {
        let t = self
            .tooltips
            .iter_mut()
            .find(|t| t.element_id == id)
            .ok_or_else(|| TooltipError::Unknown(id.into()))?;
        t.enabled = enabled;
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, id: &str) -> Option<&Tooltip> {
        self.tooltips.iter().find(|t| t.element_id == id)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TooltipError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TooltipError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.tooltips {
            check_shape(t)?;
            if !seen.insert(t.element_id.as_str()) {
                return Err(TooltipError::DuplicateId(t.element_id.clone()));
            }
        }
        Ok(())
    }
}

fn check_shape(t: &Tooltip) -> Result<(), TooltipError> {
    if t.element_id.is_empty() {
        return Err(TooltipError::EmptyElementId);
    }
    let n = t.text.chars().count();
    if n > 200 {
        return Err(TooltipError::TextTooLong {
            id: t.element_id.clone(),
            len: n,
        });
    }
    Ok(())
}

impl Default for TooltipCatalog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(id: &str, text: &str, placement: Placement) -> Tooltip {
        Tooltip {
            element_id: id.into(),
            text: text.into(),
            placement,
            delay_ms: 500,
            enabled: true,
        }
    }

    #[test]
    fn empty_catalog_validates() {
        TooltipCatalog::new().validate().unwrap();
    }

    #[test]
    fn register_and_lookup() {
        let mut c = TooltipCatalog::new();
        c.register(t("btn-save", "Save (Ctrl+S)", Placement::Top))
            .unwrap();
        assert_eq!(c.get("btn-save").unwrap().text, "Save (Ctrl+S)");
    }

    #[test]
    fn duplicate_rejected() {
        let mut c = TooltipCatalog::new();
        c.register(t("a", "x", Placement::Top)).unwrap();
        assert!(matches!(
            c.register(t("a", "y", Placement::Bottom)).unwrap_err(),
            TooltipError::DuplicateId(_)
        ));
    }

    #[test]
    fn override_text() {
        let mut c = TooltipCatalog::new();
        c.register(t("a", "old", Placement::Top)).unwrap();
        c.set_text("a", "new").unwrap();
        assert_eq!(c.get("a").unwrap().text, "new");
    }

    #[test]
    fn disable_tooltip() {
        let mut c = TooltipCatalog::new();
        c.register(t("a", "x", Placement::Top)).unwrap();
        c.set_enabled("a", false).unwrap();
        assert!(!c.get("a").unwrap().enabled);
    }

    #[test]
    fn unknown_set_rejected() {
        let mut c = TooltipCatalog::new();
        assert!(matches!(
            c.set_text("none", "x").unwrap_err(),
            TooltipError::Unknown(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut c = TooltipCatalog::new();
        assert!(matches!(
            c.register(t("", "x", Placement::Top)).unwrap_err(),
            TooltipError::EmptyElementId
        ));
    }

    #[test]
    fn text_too_long_rejected() {
        let mut c = TooltipCatalog::new();
        let long = "x".repeat(201);
        assert!(matches!(
            c.register(t("a", &long, Placement::Top)).unwrap_err(),
            TooltipError::TextTooLong { .. }
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = TooltipCatalog::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            TooltipError::SchemaMismatch
        ));
    }

    #[test]
    fn placement_serde_kebab() {
        assert_eq!(serde_json::to_string(&Placement::Top).unwrap(), "\"top\"");
        assert_eq!(
            serde_json::to_string(&Placement::Bottom).unwrap(),
            "\"bottom\""
        );
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let mut c = TooltipCatalog::new();
        c.register(t("a", "x", Placement::Top)).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: TooltipCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
