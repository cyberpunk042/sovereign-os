//! `sovereign-cockpit-trash-buffer` — soft-delete with undo.
//!
//! TrashItem{payload, deleted_at_ms}. soft_delete(id, payload,
//! now) inserts; undo(id) removes and returns payload; purge
//! (now) deletes items past TTL.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TrashItem {
    /// Payload.
    pub payload: String,
    /// Soft-deleted ts ms.
    pub deleted_at_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TrashBuffer {
    /// Schema version.
    pub schema_version: String,
    /// Items.
    pub items: BTreeMap<String, TrashItem>,
    /// TTL ms before purge.
    pub ttl_ms: u64,
    /// Lifetime undos.
    pub undos: u64,
    /// Lifetime purges.
    pub purges: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TrashError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("payload empty")]
    EmptyPayload,
    /// Zero ttl.
    #[error("ttl_ms must be >= 1")]
    ZeroTtl,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl TrashBuffer {
    /// New.
    pub fn new(ttl_ms: u64) -> Result<Self, TrashError> {
        if ttl_ms == 0 { return Err(TrashError::ZeroTtl); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            items: BTreeMap::new(),
            ttl_ms,
            undos: 0,
            purges: 0,
        })
    }

    /// Soft-delete.
    pub fn soft_delete(&mut self, id: &str, payload: &str, now_ms: u64) -> Result<(), TrashError> {
        if id.is_empty() { return Err(TrashError::EmptyId); }
        if payload.is_empty() { return Err(TrashError::EmptyPayload); }
        if self.items.contains_key(id) {
            return Err(TrashError::DuplicateId(id.into()));
        }
        self.items.insert(id.into(), TrashItem {
            payload: payload.into(),
            deleted_at_ms: now_ms,
        });
        Ok(())
    }

    /// Undo (returns the payload if found).
    pub fn undo(&mut self, id: &str) -> Option<String> {
        let item = self.items.remove(id)?;
        self.undos = self.undos.saturating_add(1);
        Some(item.payload)
    }

    /// Purge expired (deleted_at + ttl <= now); returns count.
    pub fn purge(&mut self, now_ms: u64) -> u32 {
        let stale: Vec<String> = self.items.iter()
            .filter(|(_, i)| now_ms.saturating_sub(i.deleted_at_ms) >= self.ttl_ms)
            .map(|(k, _)| k.clone())
            .collect();
        let n = stale.len() as u32;
        for k in stale { self.items.remove(&k); }
        self.purges = self.purges.saturating_add(n as u64);
        n
    }

    /// In-trash count.
    pub fn len(&self) -> usize { self.items.len() }

    /// Empty?
    pub fn is_empty(&self) -> bool { self.items.is_empty() }

    /// Validate.
    pub fn validate(&self) -> Result<(), TrashError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TrashError::SchemaMismatch); }
        if self.ttl_ms == 0 { return Err(TrashError::ZeroTtl); }
        for (k, v) in &self.items {
            if k.is_empty() { return Err(TrashError::EmptyId); }
            if v.payload.is_empty() { return Err(TrashError::EmptyPayload); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn soft_delete_and_undo() {
        let mut t = TrashBuffer::new(1000).unwrap();
        t.soft_delete("a", "payload", 0).unwrap();
        assert_eq!(t.len(), 1);
        let p = t.undo("a").unwrap();
        assert_eq!(p, "payload");
        assert!(t.is_empty());
    }

    #[test]
    fn undo_unknown_returns_none() {
        let mut t = TrashBuffer::new(1000).unwrap();
        assert!(t.undo("nope").is_none());
    }

    #[test]
    fn purge_expired() {
        let mut t = TrashBuffer::new(1000).unwrap();
        t.soft_delete("a", "x", 0).unwrap();
        t.soft_delete("b", "x", 500).unwrap();
        let n = t.purge(1200);
        assert_eq!(n, 1); // "a" expired at 1000; "b" at 1500
        assert!(t.items.contains_key("b"));
    }

    #[test]
    fn duplicate_rejected() {
        let mut t = TrashBuffer::new(1000).unwrap();
        t.soft_delete("a", "x", 0).unwrap();
        assert!(matches!(t.soft_delete("a", "y", 100).unwrap_err(), TrashError::DuplicateId(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut t = TrashBuffer::new(1000).unwrap();
        assert!(matches!(t.soft_delete("", "x", 0).unwrap_err(), TrashError::EmptyId));
        assert!(matches!(t.soft_delete("i", "", 0).unwrap_err(), TrashError::EmptyPayload));
        assert!(matches!(TrashBuffer::new(0).unwrap_err(), TrashError::ZeroTtl));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TrashBuffer::new(1000).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TrashError::SchemaMismatch));
    }

    #[test]
    fn trash_serde_roundtrip() {
        let mut t = TrashBuffer::new(1000).unwrap();
        t.soft_delete("a", "x", 0).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: TrashBuffer = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
