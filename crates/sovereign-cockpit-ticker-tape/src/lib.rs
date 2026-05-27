//! `sovereign-cockpit-ticker-tape` — horizontal scrolling status tape.
//!
//! Item{id, text, priority, expires_at_ms}. push adds; tick(now_ms)
//! drops expired; render(now) yields items in priority-desc then
//! insertion-order. Surface scrolls a concatenation; consumer code
//! does the visual scroll, this owns the state.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Ticker item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Item {
    /// Stable id.
    pub id: String,
    /// Text body.
    pub text: String,
    /// Priority (higher = surfaced first).
    pub priority: u32,
    /// Insertion ts ms (for tie-break).
    pub inserted_at_ms: u64,
    /// Expiration; 0 = never.
    pub expires_at_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TickerTape {
    /// Schema version.
    pub schema_version: String,
    /// Items.
    pub items: Vec<Item>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TickerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty text.
    #[error("text empty")]
    EmptyText,
    /// Duplicate id.
    #[error("duplicate item id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown item id: {0}")]
    UnknownId(String),
}

impl TickerTape {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            items: Vec::new(),
        }
    }

    /// Push an item.
    pub fn push(
        &mut self,
        id: &str,
        text: &str,
        priority: u32,
        now_ms: u64,
        ttl_ms: u64,
    ) -> Result<(), TickerError> {
        if id.is_empty() {
            return Err(TickerError::EmptyId);
        }
        if text.is_empty() {
            return Err(TickerError::EmptyText);
        }
        if self.items.iter().any(|x| x.id == id) {
            return Err(TickerError::DuplicateId(id.into()));
        }
        let expires_at_ms = if ttl_ms == 0 {
            0
        } else {
            now_ms.saturating_add(ttl_ms)
        };
        self.items.push(Item {
            id: id.into(),
            text: text.into(),
            priority,
            inserted_at_ms: now_ms,
            expires_at_ms,
        });
        Ok(())
    }

    /// Remove an item.
    pub fn remove(&mut self, id: &str) -> Result<(), TickerError> {
        let n = self.items.len();
        self.items.retain(|x| x.id != id);
        if self.items.len() == n {
            return Err(TickerError::UnknownId(id.into()));
        }
        Ok(())
    }

    /// Drop expired items.
    pub fn tick(&mut self, now_ms: u64) {
        self.items
            .retain(|x| x.expires_at_ms == 0 || x.expires_at_ms > now_ms);
    }

    /// Render order: priority desc, then insertion asc.
    pub fn render(&self, now_ms: u64) -> Vec<&Item> {
        let mut live: Vec<&Item> = self
            .items
            .iter()
            .filter(|x| x.expires_at_ms == 0 || x.expires_at_ms > now_ms)
            .collect();
        live.sort_by(|a, b| {
            b.priority
                .cmp(&a.priority)
                .then(a.inserted_at_ms.cmp(&b.inserted_at_ms))
        });
        live
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TickerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TickerError::SchemaMismatch);
        }
        for x in &self.items {
            if x.id.is_empty() {
                return Err(TickerError::EmptyId);
            }
            if x.text.is_empty() {
                return Err(TickerError::EmptyText);
            }
        }
        Ok(())
    }
}

impl Default for TickerTape {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn render_priority_desc_then_insertion_asc() {
        let mut t = TickerTape::new();
        t.push("a", "low", 1, 100, 0).unwrap();
        t.push("b", "high1", 5, 200, 0).unwrap();
        t.push("c", "high2", 5, 300, 0).unwrap();
        let order: Vec<_> = t.render(1_000).iter().map(|i| i.id.clone()).collect();
        assert_eq!(order, vec!["b", "c", "a"]);
    }

    #[test]
    fn tick_drops_expired() {
        let mut t = TickerTape::new();
        t.push("a", "x", 1, 0, 1000).unwrap();
        t.push("b", "y", 1, 0, 5000).unwrap();
        t.tick(2000);
        assert_eq!(t.items.len(), 1);
        assert_eq!(t.items[0].id, "b");
    }

    #[test]
    fn ttl_zero_is_never_expires() {
        let mut t = TickerTape::new();
        t.push("a", "permanent", 1, 0, 0).unwrap();
        t.tick(u64::MAX);
        assert_eq!(t.items.len(), 1);
    }

    #[test]
    fn remove_takes_item_out() {
        let mut t = TickerTape::new();
        t.push("a", "x", 1, 0, 0).unwrap();
        t.remove("a").unwrap();
        assert!(t.items.is_empty());
        assert!(matches!(
            t.remove("a").unwrap_err(),
            TickerError::UnknownId(_)
        ));
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut t = TickerTape::new();
        t.push("a", "x", 1, 0, 0).unwrap();
        assert!(matches!(
            t.push("a", "y", 1, 0, 0).unwrap_err(),
            TickerError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut t = TickerTape::new();
        assert!(matches!(
            t.push("", "x", 1, 0, 0).unwrap_err(),
            TickerError::EmptyId
        ));
        assert!(matches!(
            t.push("a", "", 1, 0, 0).unwrap_err(),
            TickerError::EmptyText
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TickerTape::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            TickerError::SchemaMismatch
        ));
    }

    #[test]
    fn ticker_serde_roundtrip() {
        let mut t = TickerTape::new();
        t.push("a", "x", 3, 100, 1000).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: TickerTape = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
