//! `sovereign-cockpit-cascading-select` — parent → child select.
//!
//! Registers (parent_value, child_values) pairs. select_parent
//! sets parent and clears child if it's no longer valid.
//! select_child only succeeds if child is among options for the
//! current parent. options_for_child() returns valid children.
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
pub struct CascadingSelect {
    /// Schema version.
    pub schema_version: String,
    /// parent value → list of child values.
    pub children: BTreeMap<String, Vec<String>>,
    /// Current parent (None = unset).
    pub parent: Option<String>,
    /// Current child (None = unset).
    pub child: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SelectError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("value empty")]
    EmptyValue,
    /// Unknown parent.
    #[error("unknown parent: {0}")]
    UnknownParent(String),
    /// Unknown child.
    #[error("unknown child for parent: {0}")]
    UnknownChild(String),
    /// Parent not set.
    #[error("parent not set")]
    NoParent,
}

impl CascadingSelect {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            children: BTreeMap::new(),
            parent: None,
            child: None,
        }
    }

    /// Register children for a parent (replaces existing).
    pub fn set_children(&mut self, parent: &str, children: Vec<String>) -> Result<(), SelectError> {
        if parent.is_empty() { return Err(SelectError::EmptyValue); }
        for c in &children {
            if c.is_empty() { return Err(SelectError::EmptyValue); }
        }
        self.children.insert(parent.into(), children);
        Ok(())
    }

    /// Select parent; clears child if no longer valid.
    pub fn select_parent(&mut self, parent: &str) -> Result<(), SelectError> {
        if !self.children.contains_key(parent) {
            return Err(SelectError::UnknownParent(parent.into()));
        }
        let prev_child = self.child.clone();
        self.parent = Some(parent.into());
        if let Some(c) = prev_child {
            let still_valid = self.children.get(parent).unwrap().contains(&c);
            if !still_valid { self.child = None; }
        }
        Ok(())
    }

    /// Select child (requires parent set + child in options).
    pub fn select_child(&mut self, child: &str) -> Result<(), SelectError> {
        let p = self.parent.as_deref().ok_or(SelectError::NoParent)?;
        let opts = self.children.get(p).ok_or_else(|| SelectError::UnknownParent(p.into()))?;
        if !opts.iter().any(|s| s == child) {
            return Err(SelectError::UnknownChild(child.into()));
        }
        self.child = Some(child.into());
        Ok(())
    }

    /// Options for the currently-selected parent.
    pub fn options_for_child(&self) -> Vec<&str> {
        let Some(p) = self.parent.as_deref() else { return Vec::new(); };
        self.children.get(p).map(|v| v.iter().map(|s| s.as_str()).collect()).unwrap_or_default()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SelectError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SelectError::SchemaMismatch); }
        for (k, vs) in &self.children {
            if k.is_empty() { return Err(SelectError::EmptyValue); }
            for v in vs { if v.is_empty() { return Err(SelectError::EmptyValue); } }
        }
        Ok(())
    }
}

impl Default for CascadingSelect {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn setup() -> CascadingSelect {
        let mut s = CascadingSelect::new();
        s.set_children("US", vec!["NY".into(), "CA".into()]).unwrap();
        s.set_children("UK", vec!["London".into(), "Manchester".into()]).unwrap();
        s
    }

    #[test]
    fn select_parent_then_child() {
        let mut s = setup();
        s.select_parent("US").unwrap();
        s.select_child("CA").unwrap();
        assert_eq!(s.parent.as_deref(), Some("US"));
        assert_eq!(s.child.as_deref(), Some("CA"));
    }

    #[test]
    fn switching_parent_clears_invalid_child() {
        let mut s = setup();
        s.select_parent("US").unwrap();
        s.select_child("NY").unwrap();
        s.select_parent("UK").unwrap();
        assert!(s.child.is_none());
    }

    #[test]
    fn switching_parent_keeps_valid_child() {
        let mut s = CascadingSelect::new();
        s.set_children("a", vec!["common".into(), "x".into()]).unwrap();
        s.set_children("b", vec!["common".into(), "y".into()]).unwrap();
        s.select_parent("a").unwrap();
        s.select_child("common").unwrap();
        s.select_parent("b").unwrap();
        assert_eq!(s.child.as_deref(), Some("common"));
    }

    #[test]
    fn invalid_child_rejected() {
        let mut s = setup();
        s.select_parent("US").unwrap();
        assert!(matches!(s.select_child("London").unwrap_err(), SelectError::UnknownChild(_)));
    }

    #[test]
    fn child_without_parent_rejected() {
        let mut s = setup();
        assert!(matches!(s.select_child("NY").unwrap_err(), SelectError::NoParent));
    }

    #[test]
    fn options_listed() {
        let mut s = setup();
        s.select_parent("US").unwrap();
        let opts = s.options_for_child();
        assert_eq!(opts, vec!["NY", "CA"]);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = setup();
        assert!(matches!(s.set_children("", vec!["x".into()]).unwrap_err(), SelectError::EmptyValue));
        assert!(matches!(s.set_children("p", vec!["".into()]).unwrap_err(), SelectError::EmptyValue));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = setup();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SelectError::SchemaMismatch));
    }

    #[test]
    fn select_serde_roundtrip() {
        let mut s = setup();
        s.select_parent("US").unwrap();
        s.select_child("CA").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: CascadingSelect = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
