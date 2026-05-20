//! `sovereign-cockpit-external-link-policy` — link gating.
//!
//! Per-policy: internal_host (exact) + trusted_hosts set (exact).
//! classify(url_host): Internal iff == internal_host;
//! Trusted iff in trusted_hosts; UnknownExternal otherwise.
//! action(class): Open/OpenNewTab/Warn/Block by config.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Class.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Class {
    /// Same as our internal_host.
    Internal,
    /// In trusted_hosts.
    Trusted,
    /// Anything else.
    UnknownExternal,
}

/// Action.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Action {
    /// Open in same tab.
    Open,
    /// Open in new tab.
    OpenNewTab,
    /// Warn before opening.
    Warn,
    /// Block (do nothing).
    Block,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExternalLinkPolicy {
    /// Schema version.
    pub schema_version: String,
    /// Internal host (e.g., "app.example.com").
    pub internal_host: String,
    /// Trusted external hosts (exact match).
    pub trusted_hosts: BTreeSet<String>,
    /// Action per class.
    pub action_internal: Action,
    /// Action.
    pub action_trusted: Action,
    /// Action.
    pub action_unknown: Action,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PolicyError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("host empty")]
    EmptyHost,
}

impl ExternalLinkPolicy {
    /// New with default actions: Internal=Open, Trusted=OpenNewTab,
    /// Unknown=Warn.
    pub fn new(internal_host: &str) -> Result<Self, PolicyError> {
        if internal_host.is_empty() { return Err(PolicyError::EmptyHost); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            internal_host: internal_host.into(),
            trusted_hosts: BTreeSet::new(),
            action_internal: Action::Open,
            action_trusted: Action::OpenNewTab,
            action_unknown: Action::Warn,
        })
    }

    /// Add trusted host.
    pub fn trust(&mut self, host: &str) -> Result<(), PolicyError> {
        if host.is_empty() { return Err(PolicyError::EmptyHost); }
        self.trusted_hosts.insert(host.into());
        Ok(())
    }

    /// Remove trusted host.
    pub fn untrust(&mut self, host: &str) -> bool {
        self.trusted_hosts.remove(host)
    }

    /// Classify host.
    pub fn classify(&self, host: &str) -> Class {
        if host == self.internal_host { Class::Internal }
        else if self.trusted_hosts.contains(host) { Class::Trusted }
        else { Class::UnknownExternal }
    }

    /// Action for class.
    pub fn action_for_class(&self, class: Class) -> Action {
        match class {
            Class::Internal => self.action_internal,
            Class::Trusted => self.action_trusted,
            Class::UnknownExternal => self.action_unknown,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PolicyError> {
        if self.schema_version != SCHEMA_VERSION { return Err(PolicyError::SchemaMismatch); }
        if self.internal_host.is_empty() { return Err(PolicyError::EmptyHost); }
        for h in &self.trusted_hosts {
            if h.is_empty() { return Err(PolicyError::EmptyHost); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn internal_classifies() {
        let p = ExternalLinkPolicy::new("app.example.com").unwrap();
        assert_eq!(p.classify("app.example.com"), Class::Internal);
        assert_eq!(p.action_for_class(Class::Internal), Action::Open);
    }

    #[test]
    fn trusted_classifies() {
        let mut p = ExternalLinkPolicy::new("app.example.com").unwrap();
        p.trust("docs.example.com").unwrap();
        assert_eq!(p.classify("docs.example.com"), Class::Trusted);
        assert_eq!(p.action_for_class(Class::Trusted), Action::OpenNewTab);
    }

    #[test]
    fn unknown_classifies() {
        let p = ExternalLinkPolicy::new("app.example.com").unwrap();
        assert_eq!(p.classify("evil.test"), Class::UnknownExternal);
        assert_eq!(p.action_for_class(Class::UnknownExternal), Action::Warn);
    }

    #[test]
    fn untrust_works() {
        let mut p = ExternalLinkPolicy::new("app.example.com").unwrap();
        p.trust("docs.example.com").unwrap();
        assert!(p.untrust("docs.example.com"));
        assert_eq!(p.classify("docs.example.com"), Class::UnknownExternal);
    }

    #[test]
    fn empty_inputs_rejected() {
        assert!(matches!(ExternalLinkPolicy::new("").unwrap_err(), PolicyError::EmptyHost));
        let mut p = ExternalLinkPolicy::new("h").unwrap();
        assert!(matches!(p.trust("").unwrap_err(), PolicyError::EmptyHost));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ExternalLinkPolicy::new("h").unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), PolicyError::SchemaMismatch));
    }

    #[test]
    fn policy_serde_roundtrip() {
        let mut p = ExternalLinkPolicy::new("app.example.com").unwrap();
        p.trust("docs.example.com").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: ExternalLinkPolicy = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
