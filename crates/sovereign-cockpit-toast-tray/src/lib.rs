//! `sovereign-cockpit-toast-tray` — ephemeral notification queue.
//!
//! Toasts are short-lived operator-visible notifications that:
//! - carry a `BannerSeverity` for visual styling
//! - auto-dismiss after a TTL (seconds)
//! - can be dismissed manually
//! - are capped at 20 in-tray (FIFO drop on overflow)
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_cockpit_banner_state::BannerSeverity;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Maximum toasts retained in-tray at once.
pub const MAX_TOASTS: usize = 20;

/// One toast.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Toast {
    /// Stable id (operator-readable).
    pub id: String,
    /// Severity.
    pub severity: BannerSeverity,
    /// Title (≤ 60 chars).
    pub title: String,
    /// Body (≤ 240 chars).
    pub body: String,
    /// TTL in seconds; 0 means sticky (never auto-dismiss).
    pub ttl_seconds: u32,
    /// ISO-8601 UTC when toast was posted.
    pub posted_at: String,
    /// ISO-8601 UTC when toast was dismissed; empty while live.
    pub dismissed_at: String,
}

/// Tray envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToastTray {
    /// Schema version.
    pub schema_version: String,
    /// FIFO toast queue.
    pub toasts: Vec<Toast>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToastError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Duplicate id in tray.
    #[error("duplicate toast id: {0}")]
    DuplicateId(String),
    /// Empty id.
    #[error("toast id empty")]
    EmptyId,
    /// Empty posted_at.
    #[error("toast {0} missing posted_at")]
    MissingPostedAt(String),
    /// Title > 60 chars.
    #[error("toast {0} title length {1} exceeds 60")]
    TitleTooLong(String, usize),
    /// Body > 240 chars.
    #[error("toast {0} body length {1} exceeds 240")]
    BodyTooLong(String, usize),
}

impl ToastTray {
    /// New empty tray.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            toasts: Vec::new(),
        }
    }

    /// Post a toast. Drops oldest if MAX_TOASTS exceeded.
    pub fn post(&mut self, t: Toast) -> Result<(), ToastError> {
        if t.id.is_empty() {
            return Err(ToastError::EmptyId);
        }
        if self.toasts.iter().any(|x| x.id == t.id) {
            return Err(ToastError::DuplicateId(t.id));
        }
        if t.title.chars().count() > 60 {
            return Err(ToastError::TitleTooLong(t.id, t.title.chars().count()));
        }
        if t.body.chars().count() > 240 {
            return Err(ToastError::BodyTooLong(t.id, t.body.chars().count()));
        }
        if t.posted_at.is_empty() {
            return Err(ToastError::MissingPostedAt(t.id));
        }
        self.toasts.push(t);
        while self.toasts.len() > MAX_TOASTS {
            self.toasts.remove(0);
        }
        Ok(())
    }

    /// Dismiss a toast by id. Returns true if dismissed.
    pub fn dismiss(&mut self, id: &str, at: &str) -> bool {
        for t in self.toasts.iter_mut() {
            if t.id == id && t.dismissed_at.is_empty() {
                t.dismissed_at = at.into();
                return true;
            }
        }
        false
    }

    /// Count live (not-yet-dismissed) toasts.
    pub fn live_count(&self) -> usize {
        self.toasts
            .iter()
            .filter(|t| t.dismissed_at.is_empty())
            .count()
    }

    /// Count toasts by severity (live only).
    pub fn live_count_by_severity(&self, sev: BannerSeverity) -> usize {
        self.toasts
            .iter()
            .filter(|t| t.dismissed_at.is_empty() && t.severity == sev)
            .count()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToastError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToastError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.toasts {
            if t.id.is_empty() {
                return Err(ToastError::EmptyId);
            }
            if t.posted_at.is_empty() {
                return Err(ToastError::MissingPostedAt(t.id.clone()));
            }
            if t.title.chars().count() > 60 {
                return Err(ToastError::TitleTooLong(
                    t.id.clone(),
                    t.title.chars().count(),
                ));
            }
            if t.body.chars().count() > 240 {
                return Err(ToastError::BodyTooLong(
                    t.id.clone(),
                    t.body.chars().count(),
                ));
            }
            if !seen.insert(t.id.as_str()) {
                return Err(ToastError::DuplicateId(t.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for ToastTray {
    fn default() -> Self {
        Self::new()
    }
}

fn mk(id: &str, sev: BannerSeverity, title: &str, body: &str, ttl: u32, at: &str) -> Toast {
    Toast {
        id: id.into(),
        severity: sev,
        title: title.into(),
        body: body.into(),
        ttl_seconds: ttl,
        posted_at: at.into(),
        dismissed_at: String::new(),
    }
}

/// Convenience builder for use in tests + composing crates.
pub fn build(id: &str, sev: BannerSeverity, title: &str, body: &str, ttl: u32, at: &str) -> Toast {
    mk(id, sev, title, body, ttl, at)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_tray_validates() {
        ToastTray::new().validate().unwrap();
    }

    #[test]
    fn post_then_dismiss() {
        let mut tr = ToastTray::new();
        tr.post(mk(
            "t1",
            BannerSeverity::Notice,
            "Build done",
            "lib finished",
            5,
            "t",
        ))
        .unwrap();
        assert_eq!(tr.live_count(), 1);
        assert!(tr.dismiss("t1", "t2"));
        assert_eq!(tr.live_count(), 0);
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut tr = ToastTray::new();
        tr.post(mk("t1", BannerSeverity::Notice, "a", "b", 5, "t"))
            .unwrap();
        let err = tr
            .post(mk("t1", BannerSeverity::Warn, "x", "y", 5, "t"))
            .unwrap_err();
        assert!(matches!(err, ToastError::DuplicateId(ref id) if id == "t1"));
    }

    #[test]
    fn empty_id_rejected() {
        let mut tr = ToastTray::new();
        let err = tr
            .post(mk("", BannerSeverity::Notice, "a", "b", 5, "t"))
            .unwrap_err();
        assert!(matches!(err, ToastError::EmptyId));
    }

    #[test]
    fn title_too_long_rejected() {
        let mut tr = ToastTray::new();
        let long_title = "x".repeat(61);
        let err = tr
            .post(mk(
                "t1",
                BannerSeverity::Notice,
                &long_title,
                "body",
                5,
                "t",
            ))
            .unwrap_err();
        assert!(matches!(err, ToastError::TitleTooLong(_, 61)));
    }

    #[test]
    fn body_too_long_rejected() {
        let mut tr = ToastTray::new();
        let long_body = "x".repeat(241);
        let err = tr
            .post(mk(
                "t1",
                BannerSeverity::Notice,
                "title",
                &long_body,
                5,
                "t",
            ))
            .unwrap_err();
        assert!(matches!(err, ToastError::BodyTooLong(_, 241)));
    }

    #[test]
    fn missing_posted_at_rejected() {
        let mut tr = ToastTray::new();
        let err = tr
            .post(mk("t1", BannerSeverity::Notice, "t", "b", 5, ""))
            .unwrap_err();
        assert!(matches!(err, ToastError::MissingPostedAt(ref id) if id == "t1"));
    }

    #[test]
    fn overflow_drops_oldest() {
        let mut tr = ToastTray::new();
        for i in 0..(MAX_TOASTS + 5) {
            let id = format!("t{i}");
            tr.post(mk(&id, BannerSeverity::Notice, "x", "y", 5, "t"))
                .unwrap();
        }
        assert_eq!(tr.toasts.len(), MAX_TOASTS);
        // Oldest 5 dropped; first remaining is t5.
        assert_eq!(tr.toasts[0].id, "t5");
    }

    #[test]
    fn live_count_by_severity() {
        let mut tr = ToastTray::new();
        tr.post(mk("t1", BannerSeverity::Notice, "x", "y", 5, "t"))
            .unwrap();
        tr.post(mk("t2", BannerSeverity::Warn, "x", "y", 5, "t"))
            .unwrap();
        tr.post(mk("t3", BannerSeverity::Warn, "x", "y", 5, "t"))
            .unwrap();
        tr.post(mk("t4", BannerSeverity::Critical, "x", "y", 5, "t"))
            .unwrap();
        assert_eq!(tr.live_count_by_severity(BannerSeverity::Notice), 1);
        assert_eq!(tr.live_count_by_severity(BannerSeverity::Warn), 2);
        assert_eq!(tr.live_count_by_severity(BannerSeverity::Critical), 1);
        assert_eq!(tr.live_count_by_severity(BannerSeverity::Calm), 0);
    }

    #[test]
    fn dismiss_returns_false_when_unknown() {
        let mut tr = ToastTray::new();
        assert!(!tr.dismiss("none", "t"));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut tr = ToastTray::new();
        tr.schema_version = "9.9.9".into();
        assert!(matches!(
            tr.validate().unwrap_err(),
            ToastError::SchemaMismatch
        ));
    }

    #[test]
    fn tray_serde_roundtrip() {
        let mut tr = ToastTray::new();
        tr.post(mk("t1", BannerSeverity::Warn, "Title", "Body", 10, "t"))
            .unwrap();
        let j = serde_json::to_string(&tr).unwrap();
        let back: ToastTray = serde_json::from_str(&j).unwrap();
        assert_eq!(tr, back);
    }
}
