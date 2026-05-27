//! `sovereign-cockpit-watchlist` — operator-watched items + notify mode.
//!
//! Items are keyed by `(kind, item_id)` so the same id can be tracked
//! in different watch-domains. Each item carries a `notify_mode`
//! (Off / InApp / InAppAndPush / All).
//!
//! `items_for_notify(min_mode)` returns the subset of items whose
//! mode is at-or-above the threshold for delivery routing.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Notification mode (ordered low → high).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Ord, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum NotifyMode {
    /// Off (watched but silent).
    Off,
    /// In-app only.
    InApp,
    /// In-app + push.
    InAppAndPush,
    /// All channels (email + push + in-app).
    All,
}

/// One watch entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WatchEntry {
    /// kind label.
    pub kind: String,
    /// item id within the kind.
    pub item_id: String,
    /// notify mode.
    pub notify_mode: NotifyMode,
    /// when added.
    pub added_ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Watchlist {
    /// Schema version.
    pub schema_version: String,
    /// kind → item_id → WatchEntry.
    pub by_kind: BTreeMap<String, BTreeMap<String, WatchEntry>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum WatchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty kind.
    #[error("kind empty")]
    EmptyKind,
    /// Empty item id.
    #[error("item id empty")]
    EmptyItem,
}

impl Watchlist {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            by_kind: BTreeMap::new(),
        }
    }

    /// Add or update.
    pub fn add(
        &mut self,
        kind: &str,
        item_id: &str,
        notify_mode: NotifyMode,
        ts_ms: u64,
    ) -> Result<(), WatchError> {
        if kind.is_empty() {
            return Err(WatchError::EmptyKind);
        }
        if item_id.is_empty() {
            return Err(WatchError::EmptyItem);
        }
        self.by_kind.entry(kind.into()).or_default().insert(
            item_id.into(),
            WatchEntry {
                kind: kind.into(),
                item_id: item_id.into(),
                notify_mode,
                added_ts_ms: ts_ms,
            },
        );
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, kind: &str, item_id: &str) -> bool {
        if let Some(m) = self.by_kind.get_mut(kind) {
            if m.remove(item_id).is_some() {
                if m.is_empty() {
                    self.by_kind.remove(kind);
                }
                return true;
            }
        }
        false
    }

    /// Get notify mode.
    pub fn mode_of(&self, kind: &str, item_id: &str) -> Option<NotifyMode> {
        self.by_kind.get(kind)?.get(item_id).map(|e| e.notify_mode)
    }

    /// All items at-or-above a threshold.
    pub fn items_for_notify(&self, min_mode: NotifyMode) -> Vec<WatchEntry> {
        self.by_kind
            .values()
            .flat_map(|m| m.values().cloned())
            .filter(|e| e.notify_mode >= min_mode)
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), WatchError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(WatchError::SchemaMismatch);
        }
        for (k, m) in &self.by_kind {
            if k.is_empty() {
                return Err(WatchError::EmptyKind);
            }
            for id in m.keys() {
                if id.is_empty() {
                    return Err(WatchError::EmptyItem);
                }
            }
        }
        Ok(())
    }
}

impl Default for Watchlist {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_query() {
        let mut w = Watchlist::new();
        w.add("alert", "alert-1", NotifyMode::All, 100).unwrap();
        assert_eq!(w.mode_of("alert", "alert-1"), Some(NotifyMode::All));
    }

    #[test]
    fn remove_returns_true() {
        let mut w = Watchlist::new();
        w.add("alert", "alert-1", NotifyMode::Off, 100).unwrap();
        assert!(w.remove("alert", "alert-1"));
        assert!(!w.remove("alert", "alert-1"));
    }

    #[test]
    fn items_for_notify_filters() {
        let mut w = Watchlist::new();
        w.add("alert", "a", NotifyMode::Off, 0).unwrap();
        w.add("alert", "b", NotifyMode::InApp, 0).unwrap();
        w.add("alert", "c", NotifyMode::All, 0).unwrap();
        let push = w.items_for_notify(NotifyMode::InAppAndPush);
        assert_eq!(push.len(), 1);
        assert_eq!(push[0].item_id, "c");
    }

    #[test]
    fn distinct_kinds_independent() {
        let mut w = Watchlist::new();
        w.add("alert", "a", NotifyMode::All, 0).unwrap();
        w.add("task", "a", NotifyMode::Off, 0).unwrap();
        assert_eq!(w.mode_of("alert", "a"), Some(NotifyMode::All));
        assert_eq!(w.mode_of("task", "a"), Some(NotifyMode::Off));
    }

    #[test]
    fn add_overwrites() {
        let mut w = Watchlist::new();
        w.add("alert", "a", NotifyMode::Off, 0).unwrap();
        w.add("alert", "a", NotifyMode::All, 100).unwrap();
        assert_eq!(w.mode_of("alert", "a"), Some(NotifyMode::All));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut w = Watchlist::new();
        assert!(matches!(
            w.add("", "a", NotifyMode::Off, 0).unwrap_err(),
            WatchError::EmptyKind
        ));
        assert!(matches!(
            w.add("k", "", NotifyMode::Off, 0).unwrap_err(),
            WatchError::EmptyItem
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut w = Watchlist::new();
        w.schema_version = "9.9.9".into();
        assert!(matches!(
            w.validate().unwrap_err(),
            WatchError::SchemaMismatch
        ));
    }

    #[test]
    fn watchlist_serde_roundtrip() {
        let mut w = Watchlist::new();
        w.add("alert", "a", NotifyMode::All, 100).unwrap();
        let j = serde_json::to_string(&w).unwrap();
        let back: Watchlist = serde_json::from_str(&j).unwrap();
        assert_eq!(w, back);
    }
}
