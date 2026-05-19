//! `sovereign-cockpit-screen-reader-hints` — ARIA-style hints.
//!
//! Per element_id, declares (role, label, live_region) so the cockpit
//! emits the right attributes for assistive tech.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 8 ARIA roles.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Role {
    /// button.
    Button,
    /// link.
    Link,
    /// dialog.
    Dialog,
    /// alert.
    Alert,
    /// region.
    Region,
    /// list.
    List,
    /// listitem.
    Listitem,
    /// status.
    Status,
}

/// 4 live-region politeness levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Politeness {
    /// Off (not a live region).
    Off,
    /// Polite (announce when idle).
    Polite,
    /// Assertive (interrupt).
    Assertive,
    /// Status (atomic = true, polite).
    Status,
}

/// One hint entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Hint {
    /// Element id.
    pub element_id: String,
    /// Role.
    pub role: Role,
    /// Operator-visible label.
    pub label: String,
    /// Live region politeness.
    pub politeness: Politeness,
}

/// Catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HintCatalog {
    /// Schema version.
    pub schema_version: String,
    /// Hints.
    pub hints: Vec<Hint>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HintError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty element_id.
    #[error("element_id empty")]
    EmptyElementId,
    /// Empty label.
    #[error("hint {0} label empty")]
    EmptyLabel(String),
    /// Duplicate.
    #[error("duplicate element_id: {0}")]
    DuplicateId(String),
}

impl HintCatalog {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            hints: Vec::new(),
        }
    }

    /// Register a hint.
    pub fn register(&mut self, h: Hint) -> Result<(), HintError> {
        check_shape(&h)?;
        if self.hints.iter().any(|x| x.element_id == h.element_id) {
            return Err(HintError::DuplicateId(h.element_id));
        }
        self.hints.push(h);
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, id: &str) -> Option<&Hint> {
        self.hints.iter().find(|h| h.element_id == id)
    }

    /// Filter by politeness.
    pub fn by_politeness(&self, p: Politeness) -> Vec<&Hint> {
        self.hints.iter().filter(|h| h.politeness == p).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HintError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HintError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for h in &self.hints {
            check_shape(h)?;
            if !seen.insert(h.element_id.as_str()) {
                return Err(HintError::DuplicateId(h.element_id.clone()));
            }
        }
        Ok(())
    }
}

fn check_shape(h: &Hint) -> Result<(), HintError> {
    if h.element_id.is_empty() { return Err(HintError::EmptyElementId); }
    if h.label.is_empty() { return Err(HintError::EmptyLabel(h.element_id.clone())); }
    Ok(())
}

impl Default for HintCatalog {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(id: &str, role: Role, politeness: Politeness) -> Hint {
        Hint {
            element_id: id.into(),
            role,
            label: format!("Label {id}"),
            politeness,
        }
    }

    #[test]
    fn empty_catalog_validates() {
        HintCatalog::new().validate().unwrap();
    }

    #[test]
    fn register_and_lookup() {
        let mut c = HintCatalog::new();
        c.register(h("btn-save", Role::Button, Politeness::Off)).unwrap();
        assert!(c.get("btn-save").is_some());
    }

    #[test]
    fn duplicate_rejected() {
        let mut c = HintCatalog::new();
        c.register(h("a", Role::Button, Politeness::Off)).unwrap();
        assert!(matches!(c.register(h("a", Role::Link, Politeness::Off)).unwrap_err(),
            HintError::DuplicateId(_)));
    }

    #[test]
    fn by_politeness_filters() {
        let mut c = HintCatalog::new();
        c.register(h("a", Role::Status, Politeness::Status)).unwrap();
        c.register(h("b", Role::Alert, Politeness::Assertive)).unwrap();
        c.register(h("c", Role::Status, Politeness::Status)).unwrap();
        assert_eq!(c.by_politeness(Politeness::Status).len(), 2);
        assert_eq!(c.by_politeness(Politeness::Assertive).len(), 1);
    }

    #[test]
    fn empty_id_rejected() {
        let mut c = HintCatalog::new();
        assert!(matches!(c.register(h("", Role::Button, Politeness::Off)).unwrap_err(),
            HintError::EmptyElementId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut c = HintCatalog::new();
        let mut bad = h("a", Role::Button, Politeness::Off);
        bad.label = String::new();
        assert!(matches!(c.register(bad).unwrap_err(), HintError::EmptyLabel(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = HintCatalog::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), HintError::SchemaMismatch));
    }

    #[test]
    fn role_serde_kebab() {
        assert_eq!(serde_json::to_string(&Role::Listitem).unwrap(), "\"listitem\"");
        assert_eq!(serde_json::to_string(&Role::Status).unwrap(), "\"status\"");
    }

    #[test]
    fn politeness_serde_kebab() {
        assert_eq!(serde_json::to_string(&Politeness::Polite).unwrap(), "\"polite\"");
        assert_eq!(serde_json::to_string(&Politeness::Assertive).unwrap(), "\"assertive\"");
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let mut c = HintCatalog::new();
        c.register(h("a", Role::Button, Politeness::Off)).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: HintCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
