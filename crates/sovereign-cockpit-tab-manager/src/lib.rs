//! `sovereign-cockpit-tab-manager` — tab manager.
//!
//! Each Tab{id, title, pinned, order}. Tabs render in pinned-first
//! order, then by `order` ascending. open/close/switch/pin/move_to.
//! Active tab tracked; close auto-switches to a neighbor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One tab.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tab {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Pinned (sorted first).
    pub pinned: bool,
    /// Display order.
    pub order: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TabManager {
    /// Schema version.
    pub schema_version: String,
    /// id → tab.
    pub tabs: BTreeMap<String, Tab>,
    /// Active tab.
    pub active: Option<String>,
    /// Next order to assign.
    pub next_order: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TabError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Duplicate.
    #[error("duplicate tab id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown tab: {0}")]
    UnknownTab(String),
}

impl TabManager {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tabs: BTreeMap::new(),
            active: None,
            next_order: 0,
        }
    }

    /// Open tab.
    pub fn open(&mut self, id: &str, title: &str) -> Result<(), TabError> {
        if id.is_empty() {
            return Err(TabError::EmptyId);
        }
        if title.is_empty() {
            return Err(TabError::EmptyTitle);
        }
        if self.tabs.contains_key(id) {
            return Err(TabError::DuplicateId(id.into()));
        }
        let order = self.next_order;
        self.next_order = self.next_order.saturating_add(1);
        self.tabs.insert(
            id.into(),
            Tab {
                id: id.into(),
                title: title.into(),
                pinned: false,
                order,
            },
        );
        if self.active.is_none() {
            self.active = Some(id.into());
        }
        Ok(())
    }

    /// Close.
    pub fn close(&mut self, id: &str) -> bool {
        let removed = self.tabs.remove(id).is_some();
        if removed && self.active.as_deref() == Some(id) {
            // Switch to first remaining tab.
            self.active = self.ordered().first().map(|t| t.id.clone());
        }
        removed
    }

    /// Switch.
    pub fn switch(&mut self, id: &str) -> Result<(), TabError> {
        if !self.tabs.contains_key(id) {
            return Err(TabError::UnknownTab(id.into()));
        }
        self.active = Some(id.into());
        Ok(())
    }

    /// Pin / unpin.
    pub fn set_pinned(&mut self, id: &str, pinned: bool) -> Result<(), TabError> {
        let t = self
            .tabs
            .get_mut(id)
            .ok_or_else(|| TabError::UnknownTab(id.into()))?;
        t.pinned = pinned;
        Ok(())
    }

    /// Reorder: assign new `order` to a tab.
    pub fn move_to(&mut self, id: &str, new_order: u32) -> Result<(), TabError> {
        let t = self
            .tabs
            .get_mut(id)
            .ok_or_else(|| TabError::UnknownTab(id.into()))?;
        t.order = new_order;
        if new_order >= self.next_order {
            self.next_order = new_order.saturating_add(1);
        }
        Ok(())
    }

    /// Ordered list: pinned-first then by order then alpha.
    pub fn ordered(&self) -> Vec<Tab> {
        let mut v: Vec<Tab> = self.tabs.values().cloned().collect();
        v.sort_by(|a, b| {
            b.pinned
                .cmp(&a.pinned)
                .then(a.order.cmp(&b.order))
                .then(a.title.cmp(&b.title))
        });
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TabError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TabError::SchemaMismatch);
        }
        for (id, t) in &self.tabs {
            if id.is_empty() {
                return Err(TabError::EmptyId);
            }
            if t.title.is_empty() {
                return Err(TabError::EmptyTitle);
            }
        }
        Ok(())
    }
}

impl Default for TabManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn open_sets_active_first() {
        let mut m = TabManager::new();
        m.open("a", "A").unwrap();
        m.open("b", "B").unwrap();
        assert_eq!(m.active.as_deref(), Some("a"));
    }

    #[test]
    fn close_active_switches() {
        let mut m = TabManager::new();
        m.open("a", "A").unwrap();
        m.open("b", "B").unwrap();
        m.close("a");
        assert_eq!(m.active.as_deref(), Some("b"));
    }

    #[test]
    fn pin_floats_to_front() {
        let mut m = TabManager::new();
        m.open("a", "A").unwrap();
        m.open("b", "B").unwrap();
        m.set_pinned("b", true).unwrap();
        let o = m.ordered();
        assert_eq!(o[0].id, "b");
    }

    #[test]
    fn switch_updates_active() {
        let mut m = TabManager::new();
        m.open("a", "A").unwrap();
        m.open("b", "B").unwrap();
        m.switch("b").unwrap();
        assert_eq!(m.active.as_deref(), Some("b"));
    }

    #[test]
    fn move_to_reorders() {
        let mut m = TabManager::new();
        m.open("a", "A").unwrap();
        m.open("b", "B").unwrap();
        m.move_to("b", 0).unwrap();
        let o = m.ordered();
        // b now first (order 0, a still at 0 — tie broken by title).
        // a.order=0, b.order=0; titles "A" < "B" so a still first.
        assert_eq!(o[0].id, "a");
        m.move_to("b", 100).unwrap();
        let o = m.ordered();
        assert_eq!(o[0].id, "a");
        assert_eq!(o[1].id, "b");
    }

    #[test]
    fn duplicate_rejected() {
        let mut m = TabManager::new();
        m.open("a", "A").unwrap();
        assert!(matches!(
            m.open("a", "A").unwrap_err(),
            TabError::DuplicateId(_)
        ));
    }

    #[test]
    fn switch_unknown_rejected() {
        let mut m = TabManager::new();
        assert!(matches!(
            m.switch("nope").unwrap_err(),
            TabError::UnknownTab(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut m = TabManager::new();
        assert!(matches!(m.open("", "A").unwrap_err(), TabError::EmptyId));
        assert!(matches!(m.open("a", "").unwrap_err(), TabError::EmptyTitle));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = TabManager::new();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            TabError::SchemaMismatch
        ));
    }

    #[test]
    fn tab_serde_roundtrip() {
        let mut m = TabManager::new();
        m.open("a", "A").unwrap();
        m.set_pinned("a", true).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: TabManager = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
