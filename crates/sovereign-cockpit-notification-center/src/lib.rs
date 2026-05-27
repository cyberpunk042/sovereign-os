//! `sovereign-cockpit-notification-center` — persistent operator inbox.
//!
//! Each `Notification` carries (id, severity, title, body, source,
//! read_state, archived, posted_at). Operator marks read / archives /
//! filters. Capacity 500; oldest archived dropped on overflow.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_cockpit_banner_state::BannerSeverity;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max retained notifications.
pub const MAX_NOTIFICATIONS: usize = 500;

/// Read state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ReadState {
    /// Unread.
    Unread,
    /// Read.
    Read,
}

/// One notification.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Notification {
    /// Stable id.
    pub id: String,
    /// Severity.
    pub severity: BannerSeverity,
    /// Title (≤ 80 chars).
    pub title: String,
    /// Body.
    pub body: String,
    /// Source label (e.g. "ips-quarantine", "eval-runner").
    pub source: String,
    /// Read state.
    pub read_state: ReadState,
    /// Archived (hidden by default).
    pub archived: bool,
    /// ISO-8601 UTC posted_at.
    pub posted_at: String,
}

/// Notification center envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct NotificationCenter {
    /// Schema version.
    pub schema_version: String,
    /// Notifications (oldest first).
    pub notifications: Vec<Notification>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum NotificationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("notification id empty")]
    EmptyId,
    /// Empty title.
    #[error("notification {0} title empty")]
    EmptyTitle(String),
    /// Title too long.
    #[error("notification {id} title length {len} > 80")]
    TitleTooLong {
        /// id.
        id: String,
        /// len.
        len: usize,
    },
    /// Duplicate.
    #[error("duplicate notification id: {0}")]
    Duplicate(String),
    /// Unknown.
    #[error("unknown notification id: {0}")]
    Unknown(String),
}

impl NotificationCenter {
    /// New empty center.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            notifications: Vec::new(),
        }
    }

    /// Post a notification.
    pub fn post(&mut self, n: Notification) -> Result<(), NotificationError> {
        check_shape(&n)?;
        if self.notifications.iter().any(|x| x.id == n.id) {
            return Err(NotificationError::Duplicate(n.id));
        }
        self.notifications.push(n);
        // Overflow: drop oldest archived first, then oldest unarchived.
        while self.notifications.len() > MAX_NOTIFICATIONS {
            if let Some(pos) = self.notifications.iter().position(|x| x.archived) {
                self.notifications.remove(pos);
            } else {
                self.notifications.remove(0);
            }
        }
        Ok(())
    }

    /// Mark read.
    pub fn mark_read(&mut self, id: &str) -> Result<(), NotificationError> {
        let n = self
            .notifications
            .iter_mut()
            .find(|n| n.id == id)
            .ok_or_else(|| NotificationError::Unknown(id.into()))?;
        n.read_state = ReadState::Read;
        Ok(())
    }

    /// Mark unread.
    pub fn mark_unread(&mut self, id: &str) -> Result<(), NotificationError> {
        let n = self
            .notifications
            .iter_mut()
            .find(|n| n.id == id)
            .ok_or_else(|| NotificationError::Unknown(id.into()))?;
        n.read_state = ReadState::Unread;
        Ok(())
    }

    /// Archive.
    pub fn archive(&mut self, id: &str) -> Result<(), NotificationError> {
        let n = self
            .notifications
            .iter_mut()
            .find(|n| n.id == id)
            .ok_or_else(|| NotificationError::Unknown(id.into()))?;
        n.archived = true;
        Ok(())
    }

    /// Unread count.
    pub fn unread_count(&self) -> usize {
        self.notifications
            .iter()
            .filter(|n| !n.archived && n.read_state == ReadState::Unread)
            .count()
    }

    /// Visible (non-archived) notifications.
    pub fn inbox(&self) -> Vec<&Notification> {
        self.notifications.iter().filter(|n| !n.archived).collect()
    }

    /// Filter by source.
    pub fn by_source(&self, source: &str) -> Vec<&Notification> {
        self.notifications
            .iter()
            .filter(|n| n.source == source)
            .collect()
    }

    /// Filter by severity.
    pub fn by_severity(&self, sev: BannerSeverity) -> Vec<&Notification> {
        self.notifications
            .iter()
            .filter(|n| n.severity == sev)
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), NotificationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(NotificationError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for n in &self.notifications {
            check_shape(n)?;
            if !seen.insert(n.id.as_str()) {
                return Err(NotificationError::Duplicate(n.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_shape(n: &Notification) -> Result<(), NotificationError> {
    if n.id.is_empty() {
        return Err(NotificationError::EmptyId);
    }
    if n.title.is_empty() {
        return Err(NotificationError::EmptyTitle(n.id.clone()));
    }
    let len = n.title.chars().count();
    if len > 80 {
        return Err(NotificationError::TitleTooLong {
            id: n.id.clone(),
            len,
        });
    }
    Ok(())
}

impl Default for NotificationCenter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn n(id: &str, sev: BannerSeverity, source: &str) -> Notification {
        Notification {
            id: id.into(),
            severity: sev,
            title: format!("Title for {id}"),
            body: "Body".into(),
            source: source.into(),
            read_state: ReadState::Unread,
            archived: false,
            posted_at: "2026-05-19T03:00:00Z".into(),
        }
    }

    #[test]
    fn empty_center_validates() {
        NotificationCenter::new().validate().unwrap();
    }

    #[test]
    fn post_and_inbox() {
        let mut c = NotificationCenter::new();
        c.post(n("a", BannerSeverity::Notice, "ips")).unwrap();
        c.post(n("b", BannerSeverity::Warn, "ips")).unwrap();
        assert_eq!(c.inbox().len(), 2);
        assert_eq!(c.unread_count(), 2);
    }

    #[test]
    fn mark_read_decrements_unread() {
        let mut c = NotificationCenter::new();
        c.post(n("a", BannerSeverity::Notice, "ips")).unwrap();
        c.mark_read("a").unwrap();
        assert_eq!(c.unread_count(), 0);
        c.mark_unread("a").unwrap();
        assert_eq!(c.unread_count(), 1);
    }

    #[test]
    fn archive_hides_from_inbox() {
        let mut c = NotificationCenter::new();
        c.post(n("a", BannerSeverity::Notice, "ips")).unwrap();
        c.archive("a").unwrap();
        assert_eq!(c.inbox().len(), 0);
        assert_eq!(c.unread_count(), 0);
    }

    #[test]
    fn duplicate_rejected() {
        let mut c = NotificationCenter::new();
        c.post(n("a", BannerSeverity::Notice, "ips")).unwrap();
        assert!(matches!(
            c.post(n("a", BannerSeverity::Warn, "ips")).unwrap_err(),
            NotificationError::Duplicate(_)
        ));
    }

    #[test]
    fn by_source_filters() {
        let mut c = NotificationCenter::new();
        c.post(n("a", BannerSeverity::Notice, "ips")).unwrap();
        c.post(n("b", BannerSeverity::Notice, "eval")).unwrap();
        c.post(n("c", BannerSeverity::Notice, "ips")).unwrap();
        assert_eq!(c.by_source("ips").len(), 2);
        assert_eq!(c.by_source("eval").len(), 1);
    }

    #[test]
    fn by_severity_filters() {
        let mut c = NotificationCenter::new();
        c.post(n("a", BannerSeverity::Notice, "ips")).unwrap();
        c.post(n("b", BannerSeverity::Critical, "ips")).unwrap();
        assert_eq!(c.by_severity(BannerSeverity::Critical).len(), 1);
    }

    #[test]
    fn title_too_long_rejected() {
        let mut c = NotificationCenter::new();
        let mut bad = n("a", BannerSeverity::Notice, "x");
        bad.title = "x".repeat(81);
        assert!(matches!(
            c.post(bad).unwrap_err(),
            NotificationError::TitleTooLong { .. }
        ));
    }

    #[test]
    fn unknown_mark_read_rejected() {
        let mut c = NotificationCenter::new();
        assert!(matches!(
            c.mark_read("none").unwrap_err(),
            NotificationError::Unknown(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = NotificationCenter::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            NotificationError::SchemaMismatch
        ));
    }

    #[test]
    fn center_serde_roundtrip() {
        let mut c = NotificationCenter::new();
        c.post(n("a", BannerSeverity::Notice, "ips")).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: NotificationCenter = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
