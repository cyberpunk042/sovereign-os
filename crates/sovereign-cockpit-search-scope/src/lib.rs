//! `sovereign-cockpit-search-scope` — search-scope chip selector.
//!
//! Maintains ordered `Scope { id, label, enabled }`. The chrome
//! renders a chip per enabled scope; `activate(id)` selects one;
//! `available()` returns the enabled set in declaration order;
//! `effective_active()` returns the active scope when it's enabled
//! or falls back to `default_id` otherwise.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One scope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Scope {
    /// Stable id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Enabled?
    pub enabled: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SearchScope {
    /// Schema version.
    pub schema_version: String,
    /// Ordered scopes.
    pub scopes: Vec<Scope>,
    /// Canonical fallback when active is missing/disabled.
    pub default_id: String,
    /// Operator-selected active.
    pub active_id: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ScopeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("scope id empty")]
    EmptyId,
    /// Duplicate.
    #[error("duplicate scope id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown scope id: {0}")]
    UnknownId(String),
    /// Default missing from scopes.
    #[error("default {0} not in scopes")]
    DefaultMissing(String),
}

impl SearchScope {
    /// New.
    pub fn new(default_id: &str) -> Result<Self, ScopeError> {
        if default_id.is_empty() {
            return Err(ScopeError::EmptyId);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            scopes: Vec::new(),
            default_id: default_id.into(),
            active_id: None,
        })
    }

    /// Register.
    pub fn register(&mut self, scope: Scope) -> Result<(), ScopeError> {
        if scope.id.is_empty() {
            return Err(ScopeError::EmptyId);
        }
        if self.scopes.iter().any(|s| s.id == scope.id) {
            return Err(ScopeError::DuplicateId(scope.id));
        }
        self.scopes.push(scope);
        Ok(())
    }

    /// Activate.
    pub fn activate(&mut self, id: &str) -> Result<(), ScopeError> {
        if !self.scopes.iter().any(|s| s.id == id) {
            return Err(ScopeError::UnknownId(id.into()));
        }
        self.active_id = Some(id.into());
        Ok(())
    }

    /// Enable / disable.
    pub fn set_enabled(&mut self, id: &str, enabled: bool) -> Result<(), ScopeError> {
        let s = self
            .scopes
            .iter_mut()
            .find(|s| s.id == id)
            .ok_or_else(|| ScopeError::UnknownId(id.into()))?;
        s.enabled = enabled;
        Ok(())
    }

    /// Enabled scopes in declaration order.
    pub fn available(&self) -> Vec<Scope> {
        self.scopes.iter().filter(|s| s.enabled).cloned().collect()
    }

    /// Effective active = active if enabled, else default if enabled, else None.
    pub fn effective_active(&self) -> Option<&Scope> {
        let try_id = self
            .active_id
            .as_deref()
            .unwrap_or(self.default_id.as_str());
        let s = self.scopes.iter().find(|s| s.id == try_id && s.enabled);
        if s.is_some() {
            return s;
        }
        // Active disabled — fall back to default if enabled.
        if try_id != self.default_id.as_str() {
            self.scopes
                .iter()
                .find(|s| s.id == self.default_id && s.enabled)
        } else {
            None
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ScopeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ScopeError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in &self.scopes {
            if s.id.is_empty() {
                return Err(ScopeError::EmptyId);
            }
            if !seen.insert(s.id.as_str()) {
                return Err(ScopeError::DuplicateId(s.id.clone()));
            }
        }
        if !self.scopes.iter().any(|s| s.id == self.default_id) {
            return Err(ScopeError::DefaultMissing(self.default_id.clone()));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(id: &str, en: bool) -> Scope {
        Scope {
            id: id.into(),
            label: id.into(),
            enabled: en,
        }
    }

    #[test]
    fn register_and_activate() {
        let mut sc = SearchScope::new("all").unwrap();
        sc.register(s("all", true)).unwrap();
        sc.register(s("logs", true)).unwrap();
        sc.activate("logs").unwrap();
        assert_eq!(sc.effective_active().unwrap().id, "logs");
    }

    #[test]
    fn unknown_activate_rejected() {
        let mut sc = SearchScope::new("all").unwrap();
        sc.register(s("all", true)).unwrap();
        assert!(matches!(
            sc.activate("nope").unwrap_err(),
            ScopeError::UnknownId(_)
        ));
    }

    #[test]
    fn available_filters_disabled() {
        let mut sc = SearchScope::new("all").unwrap();
        sc.register(s("all", true)).unwrap();
        sc.register(s("logs", false)).unwrap();
        assert_eq!(sc.available().len(), 1);
    }

    #[test]
    fn effective_falls_back_to_default() {
        let mut sc = SearchScope::new("all").unwrap();
        sc.register(s("all", true)).unwrap();
        sc.register(s("logs", true)).unwrap();
        sc.activate("logs").unwrap();
        sc.set_enabled("logs", false).unwrap();
        // Active disabled → default.
        assert_eq!(sc.effective_active().unwrap().id, "all");
    }

    #[test]
    fn effective_none_when_default_disabled() {
        let mut sc = SearchScope::new("all").unwrap();
        sc.register(s("all", false)).unwrap();
        assert!(sc.effective_active().is_none());
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut sc = SearchScope::new("all").unwrap();
        sc.register(s("all", true)).unwrap();
        assert!(matches!(
            sc.register(s("all", true)).unwrap_err(),
            ScopeError::DuplicateId(_)
        ));
    }

    #[test]
    fn validate_requires_default_in_set() {
        let sc = SearchScope::new("all").unwrap();
        assert!(matches!(
            sc.validate().unwrap_err(),
            ScopeError::DefaultMissing(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut sc = SearchScope::new("all").unwrap();
        assert!(matches!(
            sc.register(s("", true)).unwrap_err(),
            ScopeError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut sc = SearchScope::new("all").unwrap();
        sc.register(s("all", true)).unwrap();
        sc.schema_version = "9.9.9".into();
        assert!(matches!(
            sc.validate().unwrap_err(),
            ScopeError::SchemaMismatch
        ));
    }

    #[test]
    fn scope_serde_roundtrip() {
        let mut sc = SearchScope::new("all").unwrap();
        sc.register(s("all", true)).unwrap();
        sc.register(s("logs", true)).unwrap();
        sc.activate("logs").unwrap();
        let j = serde_json::to_string(&sc).unwrap();
        let back: SearchScope = serde_json::from_str(&j).unwrap();
        assert_eq!(sc, back);
    }
}
