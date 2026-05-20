//! `sovereign-cockpit-scroll-lock` — refcounted body-scroll lock.
//!
//! Multiple stacked overlays (modal + popover + nested dialog) each
//! `acquire(reason)` a lock; the body is scroll-locked while ≥ 1 holder
//! exists. Each acquire returns an opaque `LockId` to pass back into
//! `release(id)`. Releases for unknown ids are an error.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One outstanding lock holder.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Holder {
    /// Opaque id.
    pub id: u64,
    /// Short reason / source label.
    pub reason: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ScrollLock {
    /// Schema version.
    pub schema_version: String,
    /// Current holders.
    pub holders: Vec<Holder>,
    /// Next id.
    pub next_id: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LockError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty reason.
    #[error("empty reason")]
    EmptyReason,
    /// Unknown holder id.
    #[error("unknown holder id: {0}")]
    UnknownId(u64),
}

impl ScrollLock {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            holders: Vec::new(),
            next_id: 1,
        }
    }

    /// Locked?
    pub fn locked(&self) -> bool {
        !self.holders.is_empty()
    }

    /// Holder count.
    pub fn depth(&self) -> usize {
        self.holders.len()
    }

    /// Acquire a lock. Returns the id to pass into release().
    pub fn acquire(&mut self, reason: &str) -> Result<u64, LockError> {
        if reason.is_empty() { return Err(LockError::EmptyReason); }
        let id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1);
        self.holders.push(Holder { id, reason: reason.into() });
        Ok(id)
    }

    /// Release.
    pub fn release(&mut self, id: u64) -> Result<(), LockError> {
        let pos = self.holders.iter().position(|h| h.id == id)
            .ok_or(LockError::UnknownId(id))?;
        self.holders.remove(pos);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LockError> {
        if self.schema_version != SCHEMA_VERSION { return Err(LockError::SchemaMismatch); }
        for h in &self.holders {
            if h.reason.is_empty() { return Err(LockError::EmptyReason); }
        }
        Ok(())
    }
}

impl Default for ScrollLock {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_unlocked() {
        let l = ScrollLock::new();
        assert!(!l.locked());
        assert_eq!(l.depth(), 0);
    }

    #[test]
    fn acquire_locks() {
        let mut l = ScrollLock::new();
        l.acquire("modal").unwrap();
        assert!(l.locked());
        assert_eq!(l.depth(), 1);
    }

    #[test]
    fn nested_locks_refcount() {
        let mut l = ScrollLock::new();
        let a = l.acquire("modal").unwrap();
        let _b = l.acquire("popover").unwrap();
        l.release(a).unwrap();
        assert!(l.locked());
        assert_eq!(l.depth(), 1);
    }

    #[test]
    fn release_last_unlocks() {
        let mut l = ScrollLock::new();
        let a = l.acquire("modal").unwrap();
        l.release(a).unwrap();
        assert!(!l.locked());
    }

    #[test]
    fn empty_reason_rejected() {
        let mut l = ScrollLock::new();
        assert!(matches!(l.acquire("").unwrap_err(), LockError::EmptyReason));
    }

    #[test]
    fn unknown_id_rejected() {
        let mut l = ScrollLock::new();
        assert!(matches!(l.release(999).unwrap_err(), LockError::UnknownId(_)));
    }

    #[test]
    fn ids_unique() {
        let mut l = ScrollLock::new();
        let a = l.acquire("a").unwrap();
        let b = l.acquire("b").unwrap();
        assert_ne!(a, b);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = ScrollLock::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), LockError::SchemaMismatch));
    }

    #[test]
    fn lock_serde_roundtrip() {
        let mut l = ScrollLock::new();
        l.acquire("modal").unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: ScrollLock = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
