//! `sovereign-cockpit-empty-state` — empty-state catalog.
//!
//! 8 canonical empty-state slots. Each carries (illustration_id,
//! headline, body, primary_cta_id). Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 8 empty-state slots.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EmptyStateSlot {
    /// No conversations.
    NoConversations,
    /// No dashboards.
    NoDashboards,
    /// No replay sessions.
    NoReplay,
    /// No bookmarks.
    NoBookmarks,
    /// No pin board cards.
    NoPins,
    /// No search results.
    NoSearchResults,
    /// No tasks running.
    NoTasks,
    /// No toasts.
    NoToasts,
}

/// One empty-state entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EmptyStateEntry {
    /// Slot.
    pub slot: EmptyStateSlot,
    /// Illustration id (glyph or vector name).
    pub illustration: String,
    /// Headline.
    pub headline: String,
    /// Body explanation.
    pub body: String,
    /// Primary CTA command id (may be empty).
    pub primary_cta_id: String,
}

/// Catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EmptyStateCatalog {
    /// Schema version.
    pub schema_version: String,
    /// 8 entries.
    pub entries: Vec<EmptyStateEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum EmptyStateError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 8.
    #[error("entry count {0} != 8 canonical")]
    CountInvalid(usize),
    /// Missing.
    #[error("missing slot: {0:?}")]
    Missing(EmptyStateSlot),
    /// Empty headline.
    #[error("slot {0:?} headline empty")]
    EmptyHeadline(EmptyStateSlot),
}

const REQUIRED: [EmptyStateSlot; 8] = [
    EmptyStateSlot::NoConversations,
    EmptyStateSlot::NoDashboards,
    EmptyStateSlot::NoReplay,
    EmptyStateSlot::NoBookmarks,
    EmptyStateSlot::NoPins,
    EmptyStateSlot::NoSearchResults,
    EmptyStateSlot::NoTasks,
    EmptyStateSlot::NoToasts,
];

impl EmptyStateCatalog {
    /// Canonical defaults.
    pub fn canonical() -> Self {
        let entries = vec![
            EmptyStateEntry {
                slot: EmptyStateSlot::NoConversations,
                illustration: "chat-bubble".into(),
                headline: "No conversations yet".into(),
                body: "Open the palette and start a new thread.".into(),
                primary_cta_id: "conv.new".into(),
            },
            EmptyStateEntry {
                slot: EmptyStateSlot::NoDashboards,
                illustration: "dashboard".into(),
                headline: "No dashboards visible".into(),
                body: "Enable a dashboard from the toggle panel.".into(),
                primary_cta_id: "settings.toggles".into(),
            },
            EmptyStateEntry {
                slot: EmptyStateSlot::NoReplay,
                illustration: "rewind".into(),
                headline: "No replay session".into(),
                body: "Open a captured trace to replay.".into(),
                primary_cta_id: "mode.replay".into(),
            },
            EmptyStateEntry {
                slot: EmptyStateSlot::NoBookmarks,
                illustration: "bookmark".into(),
                headline: "No bookmarks yet".into(),
                body: "Bookmark a turn in your replay session.".into(),
                primary_cta_id: String::new(),
            },
            EmptyStateEntry {
                slot: EmptyStateSlot::NoPins,
                illustration: "pin".into(),
                headline: "Pin board is empty".into(),
                body: "Drop a card from the right rail.".into(),
                primary_cta_id: String::new(),
            },
            EmptyStateEntry {
                slot: EmptyStateSlot::NoSearchResults,
                illustration: "search".into(),
                headline: "No matches".into(),
                body: "Try a different query.".into(),
                primary_cta_id: String::new(),
            },
            EmptyStateEntry {
                slot: EmptyStateSlot::NoTasks,
                illustration: "task".into(),
                headline: "Nothing running".into(),
                body: "Background tasks will appear here.".into(),
                primary_cta_id: String::new(),
            },
            EmptyStateEntry {
                slot: EmptyStateSlot::NoToasts,
                illustration: "bell".into(),
                headline: "All clear".into(),
                body: "No notifications waiting.".into(),
                primary_cta_id: String::new(),
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), EmptyStateError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(EmptyStateError::SchemaMismatch);
        }
        if self.entries.len() != 8 {
            return Err(EmptyStateError::CountInvalid(self.entries.len()));
        }
        for s in REQUIRED {
            if !self.entries.iter().any(|e| e.slot == s) {
                return Err(EmptyStateError::Missing(s));
            }
        }
        for e in &self.entries {
            if e.headline.is_empty() {
                return Err(EmptyStateError::EmptyHeadline(e.slot));
            }
        }
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, slot: EmptyStateSlot) -> Option<&EmptyStateEntry> {
        self.entries.iter().find(|e| e.slot == slot)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        EmptyStateCatalog::canonical().validate().unwrap();
    }

    #[test]
    fn eight_slots_present() {
        let c = EmptyStateCatalog::canonical();
        for s in REQUIRED {
            assert!(c.get(s).is_some(), "missing {s:?}");
        }
    }

    #[test]
    fn no_conversations_has_cta() {
        let c = EmptyStateCatalog::canonical();
        assert!(
            !c.get(EmptyStateSlot::NoConversations)
                .unwrap()
                .primary_cta_id
                .is_empty()
        );
    }

    #[test]
    fn count_invalid_caught() {
        let mut c = EmptyStateCatalog::canonical();
        c.entries.pop();
        assert!(matches!(
            c.validate().unwrap_err(),
            EmptyStateError::CountInvalid(7)
        ));
    }

    #[test]
    fn empty_headline_rejected() {
        let mut c = EmptyStateCatalog::canonical();
        c.entries[0].headline = String::new();
        assert!(matches!(
            c.validate().unwrap_err(),
            EmptyStateError::EmptyHeadline(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = EmptyStateCatalog::canonical();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            EmptyStateError::SchemaMismatch
        ));
    }

    #[test]
    fn slot_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&EmptyStateSlot::NoConversations).unwrap(),
            "\"no-conversations\""
        );
        assert_eq!(
            serde_json::to_string(&EmptyStateSlot::NoSearchResults).unwrap(),
            "\"no-search-results\""
        );
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let c = EmptyStateCatalog::canonical();
        let j = serde_json::to_string(&c).unwrap();
        let back: EmptyStateCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
