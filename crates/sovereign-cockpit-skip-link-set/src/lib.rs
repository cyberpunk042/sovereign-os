//! `sovereign-cockpit-skip-link-set` — keyboard skip-links.
//!
//! A skip-link is a focusable shortcut (rendered visually only when
//! tabbed-to) that jumps keyboard focus to a named landmark
//! (e.g. main content, nav, search). Operators register landmarks
//! in declared order; the link set is exposed in that order.
//!
//! `register(landmark_id, label, target)`. `set_enabled(id, bool)`
//! to hide one without losing position. `links_in_order()` returns
//! only currently-enabled, ordered. `activate(id, ts_ms)` records
//! that the link was used (focuses target). `usage(id)` reports
//! how many times a link has been activated.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One skip-link.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkipLink {
    /// Landmark id.
    pub id: String,
    /// Visible label.
    pub label: String,
    /// Target element id / route.
    pub target: String,
    /// Declared order (lower = earlier in tab cycle).
    pub order: u32,
    /// Enabled?
    pub enabled: bool,
    /// Times activated.
    pub activations: u64,
    /// Last activated ts (0 if never).
    pub last_activated_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkipLinkSet {
    /// Schema version.
    pub schema_version: String,
    /// id → link.
    pub links: BTreeMap<String, SkipLink>,
    /// Next order to assign.
    pub next_order: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SkipLinkError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("link id empty")]
    EmptyId,
    /// Empty label.
    #[error("link label empty")]
    EmptyLabel,
    /// Empty target.
    #[error("link target empty")]
    EmptyTarget,
    /// Duplicate.
    #[error("duplicate link id: {0}")]
    DuplicateId(String),
    /// Unknown link.
    #[error("unknown link: {0}")]
    UnknownLink(String),
}

impl SkipLinkSet {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            links: BTreeMap::new(),
            next_order: 0,
        }
    }

    /// Register a skip-link.
    pub fn register(&mut self, id: &str, label: &str, target: &str) -> Result<(), SkipLinkError> {
        if id.is_empty() { return Err(SkipLinkError::EmptyId); }
        if label.is_empty() { return Err(SkipLinkError::EmptyLabel); }
        if target.is_empty() { return Err(SkipLinkError::EmptyTarget); }
        if self.links.contains_key(id) {
            return Err(SkipLinkError::DuplicateId(id.into()));
        }
        let order = self.next_order;
        self.next_order = self.next_order.wrapping_add(1);
        self.links.insert(id.into(), SkipLink {
            id: id.into(),
            label: label.into(),
            target: target.into(),
            order,
            enabled: true,
            activations: 0,
            last_activated_ms: 0,
        });
        Ok(())
    }

    /// Enable / disable a link without losing its position.
    pub fn set_enabled(&mut self, id: &str, enabled: bool) -> Result<(), SkipLinkError> {
        let l = self.links.get_mut(id).ok_or_else(|| SkipLinkError::UnknownLink(id.into()))?;
        l.enabled = enabled;
        Ok(())
    }

    /// Activate (focus the target).
    pub fn activate(&mut self, id: &str, ts_ms: u64) -> Result<(), SkipLinkError> {
        let l = self.links.get_mut(id).ok_or_else(|| SkipLinkError::UnknownLink(id.into()))?;
        if !l.enabled {
            // Activating a disabled link is a no-op rather than error
            // (UI shouldn't be able to surface it, but be defensive).
            return Ok(());
        }
        l.activations = l.activations.saturating_add(1);
        l.last_activated_ms = ts_ms;
        Ok(())
    }

    /// Links in declared order, enabled only.
    pub fn links_in_order(&self) -> Vec<SkipLink> {
        let mut v: Vec<SkipLink> = self.links.values().filter(|l| l.enabled).cloned().collect();
        v.sort_by_key(|l| l.order);
        v
    }

    /// All links (including disabled) in order.
    pub fn all_in_order(&self) -> Vec<SkipLink> {
        let mut v: Vec<SkipLink> = self.links.values().cloned().collect();
        v.sort_by_key(|l| l.order);
        v
    }

    /// Activation count.
    pub fn usage(&self, id: &str) -> u64 {
        self.links.get(id).map(|l| l.activations).unwrap_or(0)
    }

    /// Remove a link.
    pub fn remove(&mut self, id: &str) -> bool {
        self.links.remove(id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SkipLinkError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SkipLinkError::SchemaMismatch); }
        for (id, l) in &self.links {
            if id.is_empty() { return Err(SkipLinkError::EmptyId); }
            if l.label.is_empty() { return Err(SkipLinkError::EmptyLabel); }
            if l.target.is_empty() { return Err(SkipLinkError::EmptyTarget); }
        }
        Ok(())
    }
}

impl Default for SkipLinkSet {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_preserves_order() {
        let mut s = SkipLinkSet::new();
        s.register("main", "Skip to main", "#main").unwrap();
        s.register("nav", "Skip to nav", "#nav").unwrap();
        let v = s.links_in_order();
        assert_eq!(v[0].id, "main");
        assert_eq!(v[1].id, "nav");
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = SkipLinkSet::new();
        s.register("main", "x", "y").unwrap();
        assert!(matches!(s.register("main", "x", "y").unwrap_err(), SkipLinkError::DuplicateId(_)));
    }

    #[test]
    fn disabled_hidden_from_in_order_but_not_all() {
        let mut s = SkipLinkSet::new();
        s.register("main", "Skip to main", "#main").unwrap();
        s.register("nav", "Skip to nav", "#nav").unwrap();
        s.set_enabled("nav", false).unwrap();
        assert_eq!(s.links_in_order().len(), 1);
        assert_eq!(s.all_in_order().len(), 2);
    }

    #[test]
    fn activate_increments_usage() {
        let mut s = SkipLinkSet::new();
        s.register("main", "x", "#m").unwrap();
        s.activate("main", 100).unwrap();
        s.activate("main", 200).unwrap();
        assert_eq!(s.usage("main"), 2);
    }

    #[test]
    fn activate_disabled_noop() {
        let mut s = SkipLinkSet::new();
        s.register("main", "x", "#m").unwrap();
        s.set_enabled("main", false).unwrap();
        s.activate("main", 100).unwrap();
        assert_eq!(s.usage("main"), 0);
    }

    #[test]
    fn unknown_activate_rejected() {
        let mut s = SkipLinkSet::new();
        assert!(matches!(s.activate("nope", 0).unwrap_err(), SkipLinkError::UnknownLink(_)));
    }

    #[test]
    fn remove_works() {
        let mut s = SkipLinkSet::new();
        s.register("main", "x", "#m").unwrap();
        assert!(s.remove("main"));
        assert!(s.links_in_order().is_empty());
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = SkipLinkSet::new();
        assert!(matches!(s.register("", "x", "#m").unwrap_err(), SkipLinkError::EmptyId));
        assert!(matches!(s.register("a", "", "#m").unwrap_err(), SkipLinkError::EmptyLabel));
        assert!(matches!(s.register("a", "x", "").unwrap_err(), SkipLinkError::EmptyTarget));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SkipLinkSet::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SkipLinkError::SchemaMismatch));
    }

    #[test]
    fn skiplink_serde_roundtrip() {
        let mut s = SkipLinkSet::new();
        s.register("main", "x", "#m").unwrap();
        s.activate("main", 100).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SkipLinkSet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
