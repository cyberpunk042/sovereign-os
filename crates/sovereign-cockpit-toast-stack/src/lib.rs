//! `sovereign-cockpit-toast-stack` — toast notification stack with
//! auto-dismiss timers + severity-ordered eviction + bounded capacity.
//!
//! Toasts are ephemeral operator-facing notifications (operation
//! succeeded, network became available, error occurred). The
//! cockpit needs the same state machine across every renderer:
//!   1. `push(toast)` adds a toast at TIME t0 with a TTL.
//!   2. `expire(now_ms)` returns the IDs of toasts whose TTL elapsed.
//!   3. When `len() == capacity`, the lowest-severity OLDEST toast
//!      is evicted to make room. Higher-severity toasts win.
//!   4. Operator-dismiss removes a specific ID immediately.
//!
//! Standing rule: we do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity tier — drives eviction order when the stack is full.
/// Higher-numbered variants win.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    /// Informational ("Saved.", "Connected.").
    Info,
    /// Success ("Module applied: 0 changes.").
    Success,
    /// Warning ("Approaching disk threshold.").
    Warning,
    /// Error ("Failed to apply: …").
    Error,
}

/// One toast.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Toast {
    /// Stable identifier (assigned by the operator or the renderer).
    pub id: String,
    /// Severity tier.
    pub severity: Severity,
    /// Operator-readable message body.
    pub message: String,
    /// Epoch ms when the toast was pushed.
    pub created_at_ms: u64,
    /// TTL in ms; auto-dismissed at `created_at_ms + ttl_ms`.
    pub ttl_ms: u64,
}

/// Errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum ToastStackError {
    /// `capacity` was 0.
    #[error("capacity must be ≥ 1")]
    InvalidCapacity,
    /// Duplicate ID push attempt.
    #[error("toast id already present in stack")]
    DuplicateId,
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// Bounded toast stack.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToastStack {
    capacity: usize,
    /// Most-recently-pushed first.
    toasts: Vec<Toast>,
}

impl ToastStack {
    /// Construct an empty stack.
    pub fn new(capacity: usize) -> Result<Self, ToastStackError> {
        if capacity == 0 {
            return Err(ToastStackError::InvalidCapacity);
        }
        Ok(Self {
            capacity,
            toasts: Vec::new(),
        })
    }

    /// Capacity ceiling.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Number of stored toasts.
    pub fn len(&self) -> usize {
        self.toasts.len()
    }

    /// True iff `len() == 0`.
    pub fn is_empty(&self) -> bool {
        self.toasts.is_empty()
    }

    /// Snapshot the toasts — newest first.
    pub fn toasts(&self) -> &[Toast] {
        &self.toasts
    }

    /// Push a toast onto the stack. If capacity is reached, evict
    /// the lowest-severity OLDEST toast. Returns `DuplicateId`
    /// if a toast with that id is already present (use `dismiss`
    /// first or pick a fresh id).
    pub fn push(&mut self, toast: Toast) -> Result<(), ToastStackError> {
        if self.toasts.iter().any(|t| t.id == toast.id) {
            return Err(ToastStackError::DuplicateId);
        }
        if self.toasts.len() == self.capacity {
            // Eviction: find the lowest-severity, oldest toast.
            let evict_idx = self
                .toasts
                .iter()
                .enumerate()
                .min_by(|(ai, a), (bi, b)| {
                    a.severity.cmp(&b.severity).then_with(|| {
                        // Older = larger index (we insert at 0).
                        bi.cmp(ai)
                    })
                })
                .map(|(i, _)| i)
                .expect("non-empty");
            self.toasts.remove(evict_idx);
        }
        self.toasts.insert(0, toast);
        Ok(())
    }

    /// Remove a specific toast by id. Returns true if found.
    pub fn dismiss(&mut self, id: &str) -> bool {
        if let Some(pos) = self.toasts.iter().position(|t| t.id == id) {
            self.toasts.remove(pos);
            true
        } else {
            false
        }
    }

    /// Remove every toast whose `created_at_ms + ttl_ms <= now_ms`.
    /// Returns the IDs of removed toasts (the caller may want to
    /// fire animation hooks per dismissal).
    pub fn expire(&mut self, now_ms: u64) -> Vec<String> {
        let mut removed: Vec<String> = Vec::new();
        self.toasts.retain(|t| {
            let expires = t.created_at_ms.saturating_add(t.ttl_ms);
            if expires <= now_ms {
                removed.push(t.id.clone());
                false
            } else {
                true
            }
        });
        removed
    }

    /// Remove all toasts.
    pub fn clear(&mut self) {
        self.toasts.clear();
    }
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), ToastStackError> {
    if s != SCHEMA_VERSION {
        return Err(ToastStackError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(id: &str, severity: Severity, created_at_ms: u64, ttl_ms: u64) -> Toast {
        Toast {
            id: id.to_string(),
            severity,
            message: format!("test {id}"),
            created_at_ms,
            ttl_ms,
        }
    }

    #[test]
    fn zero_capacity_rejected() {
        assert_eq!(
            ToastStack::new(0).unwrap_err(),
            ToastStackError::InvalidCapacity
        );
    }

    #[test]
    fn push_orders_newest_first() {
        let mut s = ToastStack::new(5).unwrap();
        s.push(t("a", Severity::Info, 0, 1000)).unwrap();
        s.push(t("b", Severity::Info, 100, 1000)).unwrap();
        let ids: Vec<&str> = s.toasts().iter().map(|t| t.id.as_str()).collect();
        assert_eq!(ids, vec!["b", "a"]);
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut s = ToastStack::new(5).unwrap();
        s.push(t("a", Severity::Info, 0, 1000)).unwrap();
        assert_eq!(
            s.push(t("a", Severity::Error, 100, 1000)).unwrap_err(),
            ToastStackError::DuplicateId
        );
    }

    #[test]
    fn capacity_eviction_picks_lowest_severity() {
        let mut s = ToastStack::new(3).unwrap();
        // Stack: Info, Info, Info → all three same severity. Push
        // an Error — evicts the OLDEST Info (the one inserted first).
        s.push(t("a", Severity::Info, 0, 1000)).unwrap();
        s.push(t("b", Severity::Info, 100, 1000)).unwrap();
        s.push(t("c", Severity::Info, 200, 1000)).unwrap();
        s.push(t("d", Severity::Error, 300, 1000)).unwrap();
        let ids: Vec<&str> = s.toasts().iter().map(|t| t.id.as_str()).collect();
        assert_eq!(ids, vec!["d", "c", "b"], "evicted 'a' (oldest Info)");
    }

    #[test]
    fn higher_severity_wins_over_lower() {
        let mut s = ToastStack::new(2).unwrap();
        s.push(t("err", Severity::Error, 0, 1000)).unwrap();
        s.push(t("info", Severity::Info, 100, 1000)).unwrap();
        // Push another Info — should evict the existing Info, NOT
        // the Error, because Info < Error.
        s.push(t("info2", Severity::Info, 200, 1000)).unwrap();
        let ids: Vec<&str> = s.toasts().iter().map(|t| t.id.as_str()).collect();
        assert_eq!(ids, vec!["info2", "err"]);
    }

    #[test]
    fn dismiss_removes_specific_id() {
        let mut s = ToastStack::new(5).unwrap();
        s.push(t("a", Severity::Info, 0, 1000)).unwrap();
        s.push(t("b", Severity::Info, 0, 1000)).unwrap();
        assert!(s.dismiss("a"));
        let ids: Vec<&str> = s.toasts().iter().map(|t| t.id.as_str()).collect();
        assert_eq!(ids, vec!["b"]);
    }

    #[test]
    fn dismiss_unknown_id_returns_false() {
        let mut s = ToastStack::new(5).unwrap();
        s.push(t("a", Severity::Info, 0, 1000)).unwrap();
        assert!(!s.dismiss("nope"));
        assert_eq!(s.len(), 1);
    }

    #[test]
    fn expire_removes_due_toasts_and_returns_ids() {
        let mut s = ToastStack::new(5).unwrap();
        s.push(t("a", Severity::Info, 0, 1000)).unwrap(); // expires at 1000
        s.push(t("b", Severity::Info, 500, 1000)).unwrap(); // expires at 1500
        s.push(t("c", Severity::Info, 1000, 1000)).unwrap(); // expires at 2000

        // At t=1200, "a" is expired (1000 <= 1200); "b" + "c" survive.
        let removed = s.expire(1200);
        assert_eq!(removed, vec!["a"]);
        let ids: Vec<&str> = s.toasts().iter().map(|t| t.id.as_str()).collect();
        assert_eq!(ids, vec!["c", "b"]);
    }

    #[test]
    fn expire_at_exact_ttl_dismisses() {
        // A toast with created_at=0, ttl=1000 expires AT t=1000
        // (boundary is inclusive: created_at + ttl <= now).
        let mut s = ToastStack::new(5).unwrap();
        s.push(t("a", Severity::Info, 0, 1000)).unwrap();
        let removed = s.expire(1000);
        assert_eq!(removed, vec!["a"]);
        assert!(s.is_empty());
    }

    #[test]
    fn expire_with_no_due_toasts_returns_empty() {
        let mut s = ToastStack::new(5).unwrap();
        s.push(t("a", Severity::Info, 0, 10_000)).unwrap();
        let removed = s.expire(100);
        assert!(removed.is_empty());
        assert_eq!(s.len(), 1);
    }

    #[test]
    fn clear_empties_the_stack() {
        let mut s = ToastStack::new(5).unwrap();
        s.push(t("a", Severity::Info, 0, 1000)).unwrap();
        s.push(t("b", Severity::Info, 0, 1000)).unwrap();
        s.clear();
        assert!(s.is_empty());
    }

    #[test]
    fn severity_ord_info_lt_success_lt_warning_lt_error() {
        assert!(Severity::Info < Severity::Success);
        assert!(Severity::Success < Severity::Warning);
        assert!(Severity::Warning < Severity::Error);
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            ToastStackError::SchemaMismatch
        ));
    }

    #[test]
    fn full_serde_round_trip() {
        let mut s = ToastStack::new(3).unwrap();
        s.push(t("a", Severity::Warning, 100, 5000)).unwrap();
        s.push(t("b", Severity::Error, 200, 5000)).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ToastStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }

    #[test]
    fn severity_serde_lowercase() {
        assert_eq!(serde_json::to_string(&Severity::Info).unwrap(), "\"info\"");
        assert_eq!(
            serde_json::to_string(&Severity::Success).unwrap(),
            "\"success\""
        );
        assert_eq!(
            serde_json::to_string(&Severity::Warning).unwrap(),
            "\"warning\""
        );
        assert_eq!(
            serde_json::to_string(&Severity::Error).unwrap(),
            "\"error\""
        );
    }
}
