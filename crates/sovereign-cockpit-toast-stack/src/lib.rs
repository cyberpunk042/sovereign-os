//! `sovereign-cockpit-toast-stack` — stacked-toast queue.
//!
//! `post(toast)` appends; if the stack exceeds `max_visible`, the
//! oldest (lowest `posted_at_ms`) is dropped. `dismiss(id)` removes
//! the named entry. `visible(now)` returns the live entries after
//! filtering out those past their TTL.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Info.
    Info,
    /// Success.
    Success,
    /// Warn.
    Warn,
    /// Error.
    Error,
}

/// One toast.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Toast {
    /// Stable id.
    pub id: String,
    /// Body text.
    pub body: String,
    /// Severity.
    pub severity: Severity,
    /// Posted-at ts.
    pub posted_at_ms: u64,
    /// TTL ms.
    pub ttl_ms: u64,
    /// Can the operator dismiss?
    pub dismissable: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToastStack {
    /// Schema version.
    pub schema_version: String,
    /// Max-visible.
    pub max_visible: usize,
    /// Stack (newest last).
    pub toasts: Vec<Toast>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToastError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("toast id empty")]
    EmptyId,
    /// Empty body.
    #[error("body empty")]
    EmptyBody,
    /// Duplicate id.
    #[error("duplicate toast id: {0}")]
    DuplicateId(String),
    /// max_visible zero.
    #[error("max_visible must be > 0")]
    MaxVisibleZero,
}

impl ToastStack {
    /// New.
    pub fn new(max_visible: usize) -> Result<Self, ToastError> {
        if max_visible == 0 { return Err(ToastError::MaxVisibleZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            max_visible,
            toasts: Vec::new(),
        })
    }

    /// Post.
    pub fn post(&mut self, toast: Toast) -> Result<(), ToastError> {
        if toast.id.is_empty() { return Err(ToastError::EmptyId); }
        if toast.body.is_empty() { return Err(ToastError::EmptyBody); }
        if self.toasts.iter().any(|t| t.id == toast.id) {
            return Err(ToastError::DuplicateId(toast.id));
        }
        self.toasts.push(toast);
        while self.toasts.len() > self.max_visible {
            self.toasts.remove(0);
        }
        Ok(())
    }

    /// Dismiss by id.
    pub fn dismiss(&mut self, id: &str) -> bool {
        if let Some(pos) = self.toasts.iter().position(|t| t.id == id) {
            self.toasts.remove(pos);
            return true;
        }
        false
    }

    /// Visible at now (filters out past-TTL).
    pub fn visible(&mut self, now_ms: u64) -> Vec<Toast> {
        self.toasts.retain(|t| now_ms.saturating_sub(t.posted_at_ms) < t.ttl_ms);
        self.toasts.clone()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToastError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ToastError::SchemaMismatch); }
        if self.max_visible == 0 { return Err(ToastError::MaxVisibleZero); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.toasts {
            if t.id.is_empty() { return Err(ToastError::EmptyId); }
            if t.body.is_empty() { return Err(ToastError::EmptyBody); }
            if !seen.insert(t.id.as_str()) {
                return Err(ToastError::DuplicateId(t.id.clone()));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn toast(id: &str, ts: u64, ttl: u64) -> Toast {
        Toast {
            id: id.into(),
            body: format!("Body {id}"),
            severity: Severity::Info,
            posted_at_ms: ts,
            ttl_ms: ttl,
            dismissable: true,
        }
    }

    #[test]
    fn post_and_visible() {
        let mut s = ToastStack::new(4).unwrap();
        s.post(toast("a", 0, 5000)).unwrap();
        assert_eq!(s.visible(1000).len(), 1);
    }

    #[test]
    fn ttl_drops_after_window() {
        let mut s = ToastStack::new(4).unwrap();
        s.post(toast("a", 0, 1000)).unwrap();
        assert!(s.visible(5000).is_empty());
    }

    #[test]
    fn overflow_drops_oldest() {
        let mut s = ToastStack::new(2).unwrap();
        s.post(toast("a", 0, 10_000)).unwrap();
        s.post(toast("b", 1, 10_000)).unwrap();
        s.post(toast("c", 2, 10_000)).unwrap();
        let v = s.visible(0);
        let ids: Vec<_> = v.iter().map(|t| t.id.clone()).collect();
        assert_eq!(ids, vec!["b", "c"]);
    }

    #[test]
    fn dismiss_returns_true() {
        let mut s = ToastStack::new(4).unwrap();
        s.post(toast("a", 0, 10_000)).unwrap();
        assert!(s.dismiss("a"));
        assert!(!s.dismiss("a"));
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = ToastStack::new(4).unwrap();
        s.post(toast("a", 0, 10_000)).unwrap();
        assert!(matches!(s.post(toast("a", 1, 10_000)).unwrap_err(), ToastError::DuplicateId(_)));
    }

    #[test]
    fn max_visible_zero_rejected() {
        assert!(matches!(ToastStack::new(0).unwrap_err(), ToastError::MaxVisibleZero));
    }

    #[test]
    fn empty_fields_rejected() {
        let mut s = ToastStack::new(4).unwrap();
        let mut bad = toast("a", 0, 10_000);
        bad.id = "".into();
        assert!(matches!(s.post(bad).unwrap_err(), ToastError::EmptyId));
        let mut bad2 = toast("a", 0, 10_000);
        bad2.body = "".into();
        assert!(matches!(s.post(bad2).unwrap_err(), ToastError::EmptyBody));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ToastStack::new(4).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), ToastError::SchemaMismatch));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = ToastStack::new(4).unwrap();
        s.post(toast("a", 0, 10_000)).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ToastStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
