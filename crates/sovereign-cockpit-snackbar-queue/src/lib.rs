//! `sovereign-cockpit-snackbar-queue` — transient notifications.
//!
//! FIFO of snackbar entries with TTL, max-visible cap, and a
//! dismissed log. tick(now) auto-dismisses entries whose TTL has
//! elapsed and surfaces the next from the queue when capacity opens.
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
    /// Warning.
    Warning,
    /// Error.
    Error,
}

/// One snackbar entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Snackbar {
    /// Stable id.
    pub id: String,
    /// Body text.
    pub message: String,
    /// Severity.
    pub severity: Severity,
    /// Wall-clock seconds when posted.
    pub posted_at: u64,
    /// Time-to-live in seconds.
    pub ttl_seconds: u32,
}

/// Queue envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SnackbarQueue {
    /// Schema version.
    pub schema_version: String,
    /// Pending (not yet visible).
    pub pending: Vec<Snackbar>,
    /// Currently visible.
    pub visible: Vec<Snackbar>,
    /// Dismissed log (MRU first).
    pub dismissed: Vec<Snackbar>,
    /// Max concurrent visible.
    pub max_visible: u32,
    /// Max dismissed log size.
    pub max_log: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SnackbarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// max_visible zero.
    #[error("max_visible is zero")]
    MaxVisibleZero,
    /// Empty id.
    #[error("snackbar id empty")]
    EmptyId,
    /// Empty message.
    #[error("snackbar {0} message empty")]
    EmptyMessage(String),
    /// Duplicate id across queue.
    #[error("duplicate snackbar id: {0}")]
    DuplicateId(String),
    /// TTL zero.
    #[error("ttl_seconds is zero")]
    TtlZero,
    /// Unknown id.
    #[error("unknown snackbar id: {0}")]
    Unknown(String),
}

impl SnackbarQueue {
    /// New.
    pub fn new(max_visible: u32, max_log: u32) -> Result<Self, SnackbarError> {
        if max_visible == 0 {
            return Err(SnackbarError::MaxVisibleZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            pending: Vec::new(),
            visible: Vec::new(),
            dismissed: Vec::new(),
            max_visible,
            max_log,
        })
    }

    /// Post a new snackbar. Visible immediately if capacity, else pending.
    pub fn post(&mut self, s: Snackbar) -> Result<(), SnackbarError> {
        check_snack(&s)?;
        if self.has_id(&s.id) {
            return Err(SnackbarError::DuplicateId(s.id));
        }
        if (self.visible.len() as u32) < self.max_visible {
            self.visible.push(s);
        } else {
            self.pending.push(s);
        }
        Ok(())
    }

    fn has_id(&self, id: &str) -> bool {
        self.visible.iter().any(|x| x.id == id)
            || self.pending.iter().any(|x| x.id == id)
    }

    /// Manually dismiss an id (from visible or pending).
    pub fn dismiss(&mut self, id: &str) -> Result<(), SnackbarError> {
        if let Some(pos) = self.visible.iter().position(|x| x.id == id) {
            let s = self.visible.remove(pos);
            self.log(s);
            self.promote_one();
            return Ok(());
        }
        if let Some(pos) = self.pending.iter().position(|x| x.id == id) {
            let s = self.pending.remove(pos);
            self.log(s);
            return Ok(());
        }
        Err(SnackbarError::Unknown(id.into()))
    }

    fn promote_one(&mut self) {
        while (self.visible.len() as u32) < self.max_visible && !self.pending.is_empty() {
            let s = self.pending.remove(0);
            self.visible.push(s);
        }
    }

    fn log(&mut self, s: Snackbar) {
        self.dismissed.insert(0, s);
        while self.dismissed.len() as u32 > self.max_log {
            self.dismissed.pop();
        }
    }

    /// Auto-dismiss entries whose TTL has elapsed. Returns count dismissed.
    pub fn tick(&mut self, now: u64) -> u32 {
        let to_dismiss: Vec<String> = self.visible.iter()
            .filter(|s| now.saturating_sub(s.posted_at) >= s.ttl_seconds as u64)
            .map(|s| s.id.clone())
            .collect();
        let count = to_dismiss.len() as u32;
        for id in to_dismiss {
            let _ = self.dismiss(&id);
        }
        count
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SnackbarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SnackbarError::SchemaMismatch);
        }
        if self.max_visible == 0 {
            return Err(SnackbarError::MaxVisibleZero);
        }
        use std::collections::HashSet;
        let mut ids: HashSet<&str> = HashSet::new();
        for s in self.visible.iter().chain(self.pending.iter()) {
            check_snack(s)?;
            if !ids.insert(s.id.as_str()) {
                return Err(SnackbarError::DuplicateId(s.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_snack(s: &Snackbar) -> Result<(), SnackbarError> {
    if s.id.is_empty() { return Err(SnackbarError::EmptyId); }
    if s.message.is_empty() { return Err(SnackbarError::EmptyMessage(s.id.clone())); }
    if s.ttl_seconds == 0 { return Err(SnackbarError::TtlZero); }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snack(id: &str, posted: u64, ttl: u32, sev: Severity) -> Snackbar {
        Snackbar {
            id: id.into(),
            message: format!("msg-{id}"),
            severity: sev,
            posted_at: posted,
            ttl_seconds: ttl,
        }
    }

    #[test]
    fn max_visible_zero_rejected() {
        assert!(matches!(SnackbarQueue::new(0, 10).unwrap_err(), SnackbarError::MaxVisibleZero));
    }

    #[test]
    fn post_visible_under_capacity() {
        let mut q = SnackbarQueue::new(3, 10).unwrap();
        q.post(snack("a", 0, 5, Severity::Info)).unwrap();
        assert_eq!(q.visible.len(), 1);
        assert!(q.pending.is_empty());
    }

    #[test]
    fn post_pending_over_capacity() {
        let mut q = SnackbarQueue::new(1, 10).unwrap();
        q.post(snack("a", 0, 5, Severity::Info)).unwrap();
        q.post(snack("b", 0, 5, Severity::Info)).unwrap();
        assert_eq!(q.visible.len(), 1);
        assert_eq!(q.pending.len(), 1);
    }

    #[test]
    fn dismiss_promotes_pending() {
        let mut q = SnackbarQueue::new(1, 10).unwrap();
        q.post(snack("a", 0, 5, Severity::Info)).unwrap();
        q.post(snack("b", 0, 5, Severity::Info)).unwrap();
        q.dismiss("a").unwrap();
        assert_eq!(q.visible.len(), 1);
        assert_eq!(q.visible[0].id, "b");
        assert!(q.pending.is_empty());
        assert_eq!(q.dismissed[0].id, "a");
    }

    #[test]
    fn dismiss_pending_works() {
        let mut q = SnackbarQueue::new(1, 10).unwrap();
        q.post(snack("a", 0, 5, Severity::Info)).unwrap();
        q.post(snack("b", 0, 5, Severity::Info)).unwrap();
        q.dismiss("b").unwrap();
        assert!(q.pending.is_empty());
        // 'a' still visible.
        assert_eq!(q.visible[0].id, "a");
    }

    #[test]
    fn dismiss_unknown_rejected() {
        let mut q = SnackbarQueue::new(1, 10).unwrap();
        assert!(matches!(q.dismiss("z").unwrap_err(), SnackbarError::Unknown(_)));
    }

    #[test]
    fn tick_auto_dismisses() {
        let mut q = SnackbarQueue::new(2, 10).unwrap();
        q.post(snack("a", 0, 5, Severity::Info)).unwrap();
        q.post(snack("b", 0, 10, Severity::Info)).unwrap();
        let n = q.tick(6);
        assert_eq!(n, 1);
        assert_eq!(q.visible.len(), 1);
        assert_eq!(q.visible[0].id, "b");
    }

    #[test]
    fn dismissed_log_capped() {
        let mut q = SnackbarQueue::new(1, 2).unwrap();
        for i in 0..5 {
            let s = snack(&format!("x{i}"), 0, 1, Severity::Info);
            q.post(s).unwrap();
            q.dismiss(&format!("x{i}")).unwrap();
        }
        assert_eq!(q.dismissed.len(), 2);
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut q = SnackbarQueue::new(2, 10).unwrap();
        q.post(snack("a", 0, 5, Severity::Info)).unwrap();
        assert!(matches!(
            q.post(snack("a", 0, 5, Severity::Info)).unwrap_err(),
            SnackbarError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_message_rejected() {
        let mut q = SnackbarQueue::new(2, 10).unwrap();
        let mut s = snack("a", 0, 5, Severity::Info);
        s.message = String::new();
        assert!(matches!(q.post(s).unwrap_err(), SnackbarError::EmptyMessage(_)));
    }

    #[test]
    fn ttl_zero_rejected() {
        let mut q = SnackbarQueue::new(2, 10).unwrap();
        let s = snack("a", 0, 0, Severity::Info);
        assert!(matches!(q.post(s).unwrap_err(), SnackbarError::TtlZero));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut q = SnackbarQueue::new(2, 10).unwrap();
        q.schema_version = "9.9.9".into();
        assert!(matches!(q.validate().unwrap_err(), SnackbarError::SchemaMismatch));
    }

    #[test]
    fn severity_serde_kebab() {
        assert_eq!(serde_json::to_string(&Severity::Error).unwrap(), "\"error\"");
    }

    #[test]
    fn queue_serde_roundtrip() {
        let mut q = SnackbarQueue::new(2, 10).unwrap();
        q.post(snack("a", 0, 5, Severity::Info)).unwrap();
        let j = serde_json::to_string(&q).unwrap();
        let back: SnackbarQueue = serde_json::from_str(&j).unwrap();
        assert_eq!(q, back);
    }
}
