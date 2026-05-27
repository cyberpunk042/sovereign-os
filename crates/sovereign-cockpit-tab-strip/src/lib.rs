//! `sovereign-cockpit-tab-strip` — operator-managed window tabs.
//!
//! Each `Tab` declares (id, kind, label, payload_id, pinned). Max 20
//! tabs. Pinned tabs cannot be closed.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max tabs.
pub const MAX_TABS: usize = 20;

/// Tab kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TabKind {
    /// Conversation thread.
    Conversation,
    /// Dashboard view.
    Dashboard,
    /// Replay session.
    Replay,
    /// Search results.
    Search,
    /// Settings page.
    Settings,
}

/// One tab.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tab {
    /// Stable id.
    pub id: String,
    /// Kind.
    pub kind: TabKind,
    /// Display label.
    pub label: String,
    /// Payload id (thread_id / dashboard_slot / replay_id / search_query).
    pub payload_id: String,
    /// Pinned.
    pub pinned: bool,
}

/// Strip envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TabStrip {
    /// Schema version.
    pub schema_version: String,
    /// Tabs in display order.
    pub tabs: Vec<Tab>,
    /// Index of currently-active tab (None if no tabs).
    pub active: Option<usize>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TabError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("tab id empty")]
    EmptyId,
    /// Empty label.
    #[error("tab {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate tab id: {0}")]
    DuplicateId(String),
    /// Strip full.
    #[error("tab strip full ({MAX_TABS} max)")]
    Full,
    /// Tab not found.
    #[error("unknown tab id: {0}")]
    Unknown(String),
    /// Pinned tab cannot be closed.
    #[error("tab {0} is pinned")]
    Pinned(String),
}

impl TabStrip {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tabs: Vec::new(),
            active: None,
        }
    }

    /// Open a new tab and activate it.
    pub fn open(&mut self, tab: Tab) -> Result<(), TabError> {
        if tab.id.is_empty() {
            return Err(TabError::EmptyId);
        }
        if tab.label.is_empty() {
            return Err(TabError::EmptyLabel(tab.id));
        }
        if self.tabs.iter().any(|t| t.id == tab.id) {
            return Err(TabError::DuplicateId(tab.id));
        }
        if self.tabs.len() >= MAX_TABS {
            return Err(TabError::Full);
        }
        self.tabs.push(tab);
        self.active = Some(self.tabs.len() - 1);
        Ok(())
    }

    /// Close a tab by id. Refuses if pinned.
    pub fn close(&mut self, id: &str) -> Result<(), TabError> {
        let pos = self
            .tabs
            .iter()
            .position(|t| t.id == id)
            .ok_or_else(|| TabError::Unknown(id.into()))?;
        if self.tabs[pos].pinned {
            return Err(TabError::Pinned(id.into()));
        }
        self.tabs.remove(pos);
        // Adjust active.
        self.active = match self.active {
            Some(a) if a == pos => {
                if self.tabs.is_empty() {
                    None
                } else {
                    Some(a.min(self.tabs.len() - 1))
                }
            }
            Some(a) if a > pos => Some(a - 1),
            other => other,
        };
        Ok(())
    }

    /// Activate a tab by id.
    pub fn activate(&mut self, id: &str) -> Result<(), TabError> {
        let pos = self
            .tabs
            .iter()
            .position(|t| t.id == id)
            .ok_or_else(|| TabError::Unknown(id.into()))?;
        self.active = Some(pos);
        Ok(())
    }

    /// Currently active tab.
    pub fn active_tab(&self) -> Option<&Tab> {
        self.active.and_then(|i| self.tabs.get(i))
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TabError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TabError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.tabs {
            if t.id.is_empty() {
                return Err(TabError::EmptyId);
            }
            if t.label.is_empty() {
                return Err(TabError::EmptyLabel(t.id.clone()));
            }
            if !seen.insert(t.id.as_str()) {
                return Err(TabError::DuplicateId(t.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for TabStrip {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tab(id: &str, kind: TabKind, pinned: bool) -> Tab {
        Tab {
            id: id.into(),
            kind,
            label: id.into(),
            payload_id: id.into(),
            pinned,
        }
    }

    #[test]
    fn empty_strip_validates() {
        TabStrip::new().validate().unwrap();
    }

    #[test]
    fn open_activates_new_tab() {
        let mut s = TabStrip::new();
        s.open(tab("a", TabKind::Conversation, false)).unwrap();
        s.open(tab("b", TabKind::Dashboard, false)).unwrap();
        assert_eq!(s.active_tab().unwrap().id, "b");
    }

    #[test]
    fn close_unknown_rejected() {
        let mut s = TabStrip::new();
        assert!(matches!(s.close("none").unwrap_err(), TabError::Unknown(_)));
    }

    #[test]
    fn close_pinned_rejected() {
        let mut s = TabStrip::new();
        s.open(tab("a", TabKind::Conversation, true)).unwrap();
        assert!(matches!(s.close("a").unwrap_err(), TabError::Pinned(_)));
    }

    #[test]
    fn close_unpinned_ok() {
        let mut s = TabStrip::new();
        s.open(tab("a", TabKind::Conversation, false)).unwrap();
        s.close("a").unwrap();
        assert!(s.tabs.is_empty());
        assert!(s.active.is_none());
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut s = TabStrip::new();
        s.open(tab("a", TabKind::Conversation, false)).unwrap();
        assert!(matches!(
            s.open(tab("a", TabKind::Dashboard, false)).unwrap_err(),
            TabError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = TabStrip::new();
        assert!(matches!(
            s.open(tab("", TabKind::Conversation, false)).unwrap_err(),
            TabError::EmptyId
        ));
    }

    #[test]
    fn max_tabs_enforced() {
        let mut s = TabStrip::new();
        for i in 0..MAX_TABS {
            s.open(tab(&format!("t{i}"), TabKind::Conversation, false))
                .unwrap();
        }
        assert!(matches!(
            s.open(tab("overflow", TabKind::Conversation, false))
                .unwrap_err(),
            TabError::Full
        ));
    }

    #[test]
    fn activate_switches() {
        let mut s = TabStrip::new();
        s.open(tab("a", TabKind::Conversation, false)).unwrap();
        s.open(tab("b", TabKind::Dashboard, false)).unwrap();
        s.activate("a").unwrap();
        assert_eq!(s.active_tab().unwrap().id, "a");
    }

    #[test]
    fn close_adjusts_active_index_when_after() {
        let mut s = TabStrip::new();
        s.open(tab("a", TabKind::Conversation, false)).unwrap();
        s.open(tab("b", TabKind::Dashboard, false)).unwrap();
        s.open(tab("c", TabKind::Replay, false)).unwrap();
        // active = c (idx 2). Close idx 0 ("a") → active shifts to idx 1.
        s.close("a").unwrap();
        assert_eq!(s.active_tab().unwrap().id, "c");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = TabStrip::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            TabError::SchemaMismatch
        ));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&TabKind::Conversation).unwrap(),
            "\"conversation\""
        );
        assert_eq!(
            serde_json::to_string(&TabKind::Replay).unwrap(),
            "\"replay\""
        );
        assert_eq!(
            serde_json::to_string(&TabKind::Settings).unwrap(),
            "\"settings\""
        );
    }

    #[test]
    fn strip_serde_roundtrip() {
        let mut s = TabStrip::new();
        s.open(tab("a", TabKind::Conversation, true)).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: TabStrip = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
