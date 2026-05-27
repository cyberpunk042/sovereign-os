//! `sovereign-cockpit-context-help` — anchor-keyed help tooltips.
//!
//! Tooltip{body, a11y_label}. register(anchor_id, body, label).
//! resolve(anchor_id) returns the tooltip or None. update
//! replaces body+label; remove drops.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Tooltip.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tooltip {
    /// Body text.
    pub body: String,
    /// ARIA label.
    pub a11y_label: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContextHelp {
    /// Schema version.
    pub schema_version: String,
    /// anchor → tooltip.
    pub tooltips: BTreeMap<String, Tooltip>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HelpError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("anchor empty")]
    EmptyAnchor,
    /// Empty.
    #[error("body empty")]
    EmptyBody,
    /// Empty.
    #[error("a11y_label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate anchor: {0}")]
    DuplicateAnchor(String),
    /// Unknown.
    #[error("unknown anchor: {0}")]
    UnknownAnchor(String),
}

impl ContextHelp {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tooltips: BTreeMap::new(),
        }
    }

    /// Register (rejects duplicate).
    pub fn register(
        &mut self,
        anchor: &str,
        body: &str,
        a11y_label: &str,
    ) -> Result<(), HelpError> {
        if anchor.is_empty() {
            return Err(HelpError::EmptyAnchor);
        }
        if body.is_empty() {
            return Err(HelpError::EmptyBody);
        }
        if a11y_label.is_empty() {
            return Err(HelpError::EmptyLabel);
        }
        if self.tooltips.contains_key(anchor) {
            return Err(HelpError::DuplicateAnchor(anchor.into()));
        }
        self.tooltips.insert(
            anchor.into(),
            Tooltip {
                body: body.into(),
                a11y_label: a11y_label.into(),
            },
        );
        Ok(())
    }

    /// Update existing.
    pub fn update(&mut self, anchor: &str, body: &str, a11y_label: &str) -> Result<(), HelpError> {
        if body.is_empty() {
            return Err(HelpError::EmptyBody);
        }
        if a11y_label.is_empty() {
            return Err(HelpError::EmptyLabel);
        }
        let t = self
            .tooltips
            .get_mut(anchor)
            .ok_or_else(|| HelpError::UnknownAnchor(anchor.into()))?;
        t.body = body.into();
        t.a11y_label = a11y_label.into();
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, anchor: &str) -> bool {
        self.tooltips.remove(anchor).is_some()
    }

    /// Resolve.
    pub fn resolve(&self, anchor: &str) -> Option<&Tooltip> {
        self.tooltips.get(anchor)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HelpError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HelpError::SchemaMismatch);
        }
        for (k, t) in &self.tooltips {
            if k.is_empty() {
                return Err(HelpError::EmptyAnchor);
            }
            if t.body.is_empty() {
                return Err(HelpError::EmptyBody);
            }
            if t.a11y_label.is_empty() {
                return Err(HelpError::EmptyLabel);
            }
        }
        Ok(())
    }
}

impl Default for ContextHelp {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_and_resolve() {
        let mut h = ContextHelp::new();
        h.register("save-btn", "Save changes.", "Save button")
            .unwrap();
        let t = h.resolve("save-btn").unwrap();
        assert_eq!(t.body, "Save changes.");
        assert_eq!(t.a11y_label, "Save button");
    }

    #[test]
    fn unknown_returns_none() {
        let h = ContextHelp::new();
        assert!(h.resolve("nope").is_none());
    }

    #[test]
    fn update_works() {
        let mut h = ContextHelp::new();
        h.register("a", "old", "L").unwrap();
        h.update("a", "new", "L2").unwrap();
        let t = h.resolve("a").unwrap();
        assert_eq!(t.body, "new");
    }

    #[test]
    fn remove_works() {
        let mut h = ContextHelp::new();
        h.register("a", "x", "L").unwrap();
        assert!(h.remove("a"));
        assert!(!h.remove("a"));
    }

    #[test]
    fn duplicate_rejected() {
        let mut h = ContextHelp::new();
        h.register("a", "x", "L").unwrap();
        assert!(matches!(
            h.register("a", "y", "L").unwrap_err(),
            HelpError::DuplicateAnchor(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut h = ContextHelp::new();
        assert!(matches!(
            h.register("", "x", "L").unwrap_err(),
            HelpError::EmptyAnchor
        ));
        assert!(matches!(
            h.register("a", "", "L").unwrap_err(),
            HelpError::EmptyBody
        ));
        assert!(matches!(
            h.register("a", "x", "").unwrap_err(),
            HelpError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = ContextHelp::new();
        h.schema_version = "9.9.9".into();
        assert!(matches!(
            h.validate().unwrap_err(),
            HelpError::SchemaMismatch
        ));
    }

    #[test]
    fn help_serde_roundtrip() {
        let mut h = ContextHelp::new();
        h.register("a", "x", "L").unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: ContextHelp = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
