//! `sovereign-cockpit-live-collab-cursors` — collaborator cursors.
//!
//! Each peer reports a cursor as `(line, col)` offsets (or byte
//! offsets — caller's choice) plus a colour token and label.
//! `update(peer, x, y, ts)` records; `prune(now, max_age_ms)` drops
//! peers idle past max_age. `active(now, max_age_ms)` returns live
//! cursors sorted by label.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One peer cursor.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PeerCursor {
    /// Peer id.
    pub peer_id: String,
    /// Visible label (e.g. user name).
    pub label: String,
    /// Colour token.
    pub color_token: String,
    /// X / line.
    pub x: u64,
    /// Y / column or byte offset.
    pub y: u64,
    /// Last update.
    pub last_seen_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveCollabCursors {
    /// Schema version.
    pub schema_version: String,
    /// peer_id → cursor.
    pub cursors: BTreeMap<String, PeerCursor>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CursorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("peer id empty")]
    EmptyPeer,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Empty.
    #[error("color token empty")]
    EmptyColor,
}

impl LiveCollabCursors {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            cursors: BTreeMap::new(),
        }
    }

    /// Register or update.
    pub fn update(
        &mut self,
        peer_id: &str,
        label: &str,
        color_token: &str,
        x: u64,
        y: u64,
        ts_ms: u64,
    ) -> Result<(), CursorError> {
        if peer_id.is_empty() {
            return Err(CursorError::EmptyPeer);
        }
        if label.is_empty() {
            return Err(CursorError::EmptyLabel);
        }
        if color_token.is_empty() {
            return Err(CursorError::EmptyColor);
        }
        self.cursors.insert(
            peer_id.into(),
            PeerCursor {
                peer_id: peer_id.into(),
                label: label.into(),
                color_token: color_token.into(),
                x,
                y,
                last_seen_ms: ts_ms,
            },
        );
        Ok(())
    }

    /// Remove a peer.
    pub fn remove(&mut self, peer_id: &str) -> bool {
        self.cursors.remove(peer_id).is_some()
    }

    /// Drop cursors older than max_age.
    pub fn prune(&mut self, now_ms: u64, max_age_ms: u64) -> usize {
        let to_drop: Vec<String> = self
            .cursors
            .iter()
            .filter(|(_, c)| now_ms.saturating_sub(c.last_seen_ms) > max_age_ms)
            .map(|(k, _)| k.clone())
            .collect();
        let n = to_drop.len();
        for k in to_drop {
            self.cursors.remove(&k);
        }
        n
    }

    /// Active cursors at now (sorted by label).
    pub fn active(&self, now_ms: u64, max_age_ms: u64) -> Vec<PeerCursor> {
        let mut v: Vec<PeerCursor> = self
            .cursors
            .values()
            .filter(|c| now_ms.saturating_sub(c.last_seen_ms) <= max_age_ms)
            .cloned()
            .collect();
        v.sort_by(|a, b| a.label.cmp(&b.label).then(a.peer_id.cmp(&b.peer_id)));
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CursorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CursorError::SchemaMismatch);
        }
        for c in self.cursors.values() {
            if c.peer_id.is_empty() {
                return Err(CursorError::EmptyPeer);
            }
            if c.label.is_empty() {
                return Err(CursorError::EmptyLabel);
            }
            if c.color_token.is_empty() {
                return Err(CursorError::EmptyColor);
            }
        }
        Ok(())
    }
}

impl Default for LiveCollabCursors {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn update_and_active() {
        let mut c = LiveCollabCursors::new();
        c.update("p1", "Alice", "blue", 10, 5, 100).unwrap();
        let a = c.active(150, 1000);
        assert_eq!(a.len(), 1);
        assert_eq!(a[0].label, "Alice");
    }

    #[test]
    fn update_overwrites_position() {
        let mut c = LiveCollabCursors::new();
        c.update("p1", "Alice", "blue", 10, 5, 100).unwrap();
        c.update("p1", "Alice", "blue", 20, 10, 200).unwrap();
        let a = c.active(300, 1000);
        assert_eq!(a[0].x, 20);
    }

    #[test]
    fn active_sorted_by_label() {
        let mut c = LiveCollabCursors::new();
        c.update("p1", "Zelda", "red", 0, 0, 100).unwrap();
        c.update("p2", "Alice", "blue", 0, 0, 100).unwrap();
        let a = c.active(150, 1000);
        assert_eq!(a[0].label, "Alice");
        assert_eq!(a[1].label, "Zelda");
    }

    #[test]
    fn prune_drops_stale() {
        let mut c = LiveCollabCursors::new();
        c.update("p1", "Alice", "blue", 0, 0, 0).unwrap();
        c.update("p2", "Bob", "red", 0, 0, 9500).unwrap();
        // now 10_000, max_age 1000 → p1 elapsed 10_000 > 1000 (drop), p2 elapsed 500 (keep).
        let n = c.prune(10_000, 1000);
        assert_eq!(n, 1);
        assert!(!c.cursors.contains_key("p1"));
        assert!(c.cursors.contains_key("p2"));
    }

    #[test]
    fn active_filters_stale_without_pruning() {
        let mut c = LiveCollabCursors::new();
        c.update("p1", "Alice", "blue", 0, 0, 0).unwrap();
        // 10s elapsed, max 1s — filtered out of active() but state still present.
        let a = c.active(10_000, 1000);
        assert!(a.is_empty());
        assert_eq!(c.cursors.len(), 1);
    }

    #[test]
    fn remove() {
        let mut c = LiveCollabCursors::new();
        c.update("p1", "A", "x", 0, 0, 0).unwrap();
        assert!(c.remove("p1"));
        assert!(!c.remove("p1"));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut c = LiveCollabCursors::new();
        assert!(matches!(
            c.update("", "A", "x", 0, 0, 0).unwrap_err(),
            CursorError::EmptyPeer
        ));
        assert!(matches!(
            c.update("p", "", "x", 0, 0, 0).unwrap_err(),
            CursorError::EmptyLabel
        ));
        assert!(matches!(
            c.update("p", "A", "", 0, 0, 0).unwrap_err(),
            CursorError::EmptyColor
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = LiveCollabCursors::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            CursorError::SchemaMismatch
        ));
    }

    #[test]
    fn cursor_serde_roundtrip() {
        let mut c = LiveCollabCursors::new();
        c.update("p1", "Alice", "blue", 10, 5, 100).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: LiveCollabCursors = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
