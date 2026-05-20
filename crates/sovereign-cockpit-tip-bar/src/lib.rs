//! `sovereign-cockpit-tip-bar` — bottom contextual-tip strip.
//!
//! Each Tip is `(scope_id, message, optional chord)`. `tips_for
//! (scope_id)` returns the in-scope tips that haven't been dismissed.
//! `dismiss(message)` permanently hides a specific tip;
//! `restore_all()` brings them back.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One tip.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tip {
    /// Scope this tip applies to.
    pub scope_id: String,
    /// Message text.
    pub message: String,
    /// Optional chord to display (e.g. "⌘K").
    pub chord: Option<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TipBar {
    /// Schema version.
    pub schema_version: String,
    /// Registered tips.
    pub tips: Vec<Tip>,
    /// Dismissed message strings.
    pub dismissed: BTreeSet<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TipError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty scope.
    #[error("scope empty")]
    EmptyScope,
    /// Empty message.
    #[error("message empty")]
    EmptyMessage,
}

impl TipBar {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tips: Vec::new(),
            dismissed: BTreeSet::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, tip: Tip) -> Result<(), TipError> {
        if tip.scope_id.is_empty() { return Err(TipError::EmptyScope); }
        if tip.message.is_empty() { return Err(TipError::EmptyMessage); }
        self.tips.push(tip);
        Ok(())
    }

    /// Tips for a scope (excludes dismissed).
    pub fn tips_for(&self, scope_id: &str) -> Vec<Tip> {
        self.tips.iter()
            .filter(|t| t.scope_id == scope_id && !self.dismissed.contains(&t.message))
            .cloned()
            .collect()
    }

    /// Dismiss one tip.
    pub fn dismiss(&mut self, message: &str) {
        self.dismissed.insert(message.into());
    }

    /// Restore all.
    pub fn restore_all(&mut self) {
        self.dismissed.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TipError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TipError::SchemaMismatch); }
        for t in &self.tips {
            if t.scope_id.is_empty() { return Err(TipError::EmptyScope); }
            if t.message.is_empty() { return Err(TipError::EmptyMessage); }
        }
        Ok(())
    }
}

impl Default for TipBar {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tip(scope: &str, msg: &str, chord: Option<&str>) -> Tip {
        Tip { scope_id: scope.into(), message: msg.into(), chord: chord.map(|s| s.into()) }
    }

    #[test]
    fn register_and_query() {
        let mut t = TipBar::new();
        t.register(tip("logs", "Press F to filter", Some("F"))).unwrap();
        assert_eq!(t.tips_for("logs").len(), 1);
        assert!(t.tips_for("other").is_empty());
    }

    #[test]
    fn dismiss_hides() {
        let mut t = TipBar::new();
        t.register(tip("logs", "Press F to filter", Some("F"))).unwrap();
        t.dismiss("Press F to filter");
        assert!(t.tips_for("logs").is_empty());
    }

    #[test]
    fn restore_all_brings_back() {
        let mut t = TipBar::new();
        t.register(tip("logs", "Press F", None)).unwrap();
        t.dismiss("Press F");
        t.restore_all();
        assert_eq!(t.tips_for("logs").len(), 1);
    }

    #[test]
    fn empty_fields_rejected() {
        let mut t = TipBar::new();
        assert!(matches!(t.register(tip("", "x", None)).unwrap_err(), TipError::EmptyScope));
        assert!(matches!(t.register(tip("s", "", None)).unwrap_err(), TipError::EmptyMessage));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TipBar::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TipError::SchemaMismatch));
    }

    #[test]
    fn tip_serde_roundtrip() {
        let mut t = TipBar::new();
        t.register(tip("logs", "Press F", Some("F"))).unwrap();
        t.dismiss("Press F");
        let j = serde_json::to_string(&t).unwrap();
        let back: TipBar = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
