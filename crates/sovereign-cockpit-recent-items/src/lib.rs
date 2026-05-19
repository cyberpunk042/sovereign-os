//! `sovereign-cockpit-recent-items` — recently-viewed items LRU.
//!
//! Visit pushes (or refreshes) an entry to the top. Capacity 30; oldest
//! drops on overflow.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max recent items.
pub const MAX_ITEMS: usize = 30;

/// Item kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ItemKind {
    /// Conversation.
    Conversation,
    /// Dashboard.
    Dashboard,
    /// Replay session.
    Replay,
    /// Pin board.
    PinBoard,
    /// Settings page.
    Settings,
}

/// One recent item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RecentItem {
    /// Kind.
    pub kind: ItemKind,
    /// Subject id.
    pub subject_id: String,
    /// Display label.
    pub label: String,
    /// ISO-8601 UTC visited_at.
    pub visited_at: String,
}

/// Recent items list.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RecentItemsList {
    /// Schema version.
    pub schema_version: String,
    /// Items (most-recent first).
    pub items: Vec<RecentItem>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RecentItemError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty subject_id.
    #[error("subject_id empty")]
    EmptySubjectId,
    /// Empty label.
    #[error("label empty for {0}")]
    EmptyLabel(String),
    /// Empty visited_at.
    #[error("visited_at empty for {0}")]
    EmptyVisitedAt(String),
}

impl RecentItemsList {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            items: Vec::new(),
        }
    }

    /// Visit an item. If same (kind, subject_id) exists, move to top + refresh visited_at.
    pub fn visit(&mut self, item: RecentItem) -> Result<(), RecentItemError> {
        if item.subject_id.is_empty() { return Err(RecentItemError::EmptySubjectId); }
        if item.label.is_empty() { return Err(RecentItemError::EmptyLabel(item.subject_id)); }
        if item.visited_at.is_empty() { return Err(RecentItemError::EmptyVisitedAt(item.subject_id)); }
        // Remove existing same (kind, subject_id).
        self.items.retain(|x| !(x.kind == item.kind && x.subject_id == item.subject_id));
        // Push to top.
        self.items.insert(0, item);
        // Cap.
        while self.items.len() > MAX_ITEMS {
            self.items.pop();
        }
        Ok(())
    }

    /// Items filtered by kind (most-recent first).
    pub fn by_kind(&self, kind: ItemKind) -> Vec<&RecentItem> {
        self.items.iter().filter(|x| x.kind == kind).collect()
    }

    /// Clear all items.
    pub fn clear(&mut self) { self.items.clear(); }

    /// Validate.
    pub fn validate(&self) -> Result<(), RecentItemError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RecentItemError::SchemaMismatch);
        }
        for it in &self.items {
            if it.subject_id.is_empty() { return Err(RecentItemError::EmptySubjectId); }
            if it.label.is_empty() { return Err(RecentItemError::EmptyLabel(it.subject_id.clone())); }
            if it.visited_at.is_empty() { return Err(RecentItemError::EmptyVisitedAt(it.subject_id.clone())); }
        }
        Ok(())
    }
}

impl Default for RecentItemsList {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(kind: ItemKind, id: &str) -> RecentItem {
        RecentItem {
            kind, subject_id: id.into(),
            label: format!("Label {id}"),
            visited_at: "2026-05-19T03:00:00Z".into(),
        }
    }

    #[test]
    fn empty_validates() {
        RecentItemsList::new().validate().unwrap();
    }

    #[test]
    fn visit_pushes_to_top() {
        let mut l = RecentItemsList::new();
        l.visit(item(ItemKind::Conversation, "a")).unwrap();
        l.visit(item(ItemKind::Conversation, "b")).unwrap();
        assert_eq!(l.items[0].subject_id, "b");
        assert_eq!(l.items[1].subject_id, "a");
    }

    #[test]
    fn visit_existing_moves_to_top() {
        let mut l = RecentItemsList::new();
        l.visit(item(ItemKind::Conversation, "a")).unwrap();
        l.visit(item(ItemKind::Conversation, "b")).unwrap();
        l.visit(item(ItemKind::Conversation, "a")).unwrap();
        assert_eq!(l.items.len(), 2);
        assert_eq!(l.items[0].subject_id, "a");
    }

    #[test]
    fn overflow_drops_oldest() {
        let mut l = RecentItemsList::new();
        for i in 0..(MAX_ITEMS + 5) {
            l.visit(item(ItemKind::Conversation, &format!("c{i}"))).unwrap();
        }
        assert_eq!(l.items.len(), MAX_ITEMS);
        // Newest is c34, oldest retained is c5.
        assert_eq!(l.items[0].subject_id, format!("c{}", MAX_ITEMS + 4));
    }

    #[test]
    fn by_kind_filters() {
        let mut l = RecentItemsList::new();
        l.visit(item(ItemKind::Conversation, "c1")).unwrap();
        l.visit(item(ItemKind::Dashboard, "d1")).unwrap();
        l.visit(item(ItemKind::Conversation, "c2")).unwrap();
        assert_eq!(l.by_kind(ItemKind::Conversation).len(), 2);
        assert_eq!(l.by_kind(ItemKind::Dashboard).len(), 1);
        assert_eq!(l.by_kind(ItemKind::PinBoard).len(), 0);
    }

    #[test]
    fn empty_subject_id_rejected() {
        let mut l = RecentItemsList::new();
        let mut bad = item(ItemKind::Conversation, "a");
        bad.subject_id = String::new();
        assert!(matches!(l.visit(bad).unwrap_err(), RecentItemError::EmptySubjectId));
    }

    #[test]
    fn clear_empties() {
        let mut l = RecentItemsList::new();
        l.visit(item(ItemKind::Conversation, "a")).unwrap();
        l.clear();
        assert!(l.items.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = RecentItemsList::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), RecentItemError::SchemaMismatch));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(serde_json::to_string(&ItemKind::PinBoard).unwrap(), "\"pin-board\"");
        assert_eq!(serde_json::to_string(&ItemKind::Settings).unwrap(), "\"settings\"");
    }

    #[test]
    fn list_serde_roundtrip() {
        let mut l = RecentItemsList::new();
        l.visit(item(ItemKind::Conversation, "a")).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: RecentItemsList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
