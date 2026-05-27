//! `sovereign-cockpit-whats-new-feed` — release-notes feed.
//!
//! Each `Entry { id, title, body, published_at_ms, severity }` is
//! a published release-note item. Per user, the cockpit tracks the
//! `last_seen_published_at_ms` watermark; `unread(user, now)`
//! returns entries newer than that watermark, sorted newest first.
//! `mark_all_read(user, now_ms)` advances the watermark to `now`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity for filtering / highlighting.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Info.
    Info,
    /// Notice.
    Notice,
    /// Critical.
    Critical,
}

/// One entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Stable id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Body.
    pub body: String,
    /// Published ts.
    pub published_at_ms: u64,
    /// Severity.
    pub severity: Severity,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WhatsNewFeed {
    /// Schema version.
    pub schema_version: String,
    /// id → entry.
    pub entries: BTreeMap<String, Entry>,
    /// user → last-seen watermark.
    pub last_seen: BTreeMap<String, u64>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FeedError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("entry id empty")]
    EmptyId,
    /// Empty title.
    #[error("entry title empty")]
    EmptyTitle,
    /// Empty body.
    #[error("entry body empty")]
    EmptyBody,
    /// Duplicate.
    #[error("duplicate entry id: {0}")]
    DuplicateId(String),
    /// Empty user.
    #[error("user id empty")]
    EmptyUser,
}

impl WhatsNewFeed {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: BTreeMap::new(),
            last_seen: BTreeMap::new(),
        }
    }

    /// Publish an entry.
    pub fn publish(&mut self, entry: Entry) -> Result<(), FeedError> {
        if entry.id.is_empty() {
            return Err(FeedError::EmptyId);
        }
        if entry.title.is_empty() {
            return Err(FeedError::EmptyTitle);
        }
        if entry.body.is_empty() {
            return Err(FeedError::EmptyBody);
        }
        if self.entries.contains_key(&entry.id) {
            return Err(FeedError::DuplicateId(entry.id));
        }
        self.entries.insert(entry.id.clone(), entry);
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.entries.remove(id).is_some()
    }

    /// All entries newest first.
    pub fn all_newest_first(&self) -> Vec<Entry> {
        let mut v: Vec<Entry> = self.entries.values().cloned().collect();
        v.sort_by(|a, b| {
            b.published_at_ms
                .cmp(&a.published_at_ms)
                .then(a.id.cmp(&b.id))
        });
        v
    }

    /// Unread entries for a user (newest first).
    pub fn unread(&self, user_id: &str) -> Vec<Entry> {
        let watermark = self.last_seen.get(user_id).copied().unwrap_or(0);
        let mut v: Vec<Entry> = self
            .entries
            .values()
            .filter(|e| e.published_at_ms > watermark)
            .cloned()
            .collect();
        v.sort_by(|a, b| {
            b.published_at_ms
                .cmp(&a.published_at_ms)
                .then(a.id.cmp(&b.id))
        });
        v
    }

    /// Mark all read up to now.
    pub fn mark_all_read(&mut self, user_id: &str, now_ms: u64) -> Result<(), FeedError> {
        if user_id.is_empty() {
            return Err(FeedError::EmptyUser);
        }
        // Only advance the watermark — never roll it back.
        let entry = self.last_seen.entry(user_id.into()).or_insert(0);
        if now_ms > *entry {
            *entry = now_ms;
        }
        Ok(())
    }

    /// Unread count.
    pub fn unread_count(&self, user_id: &str) -> u64 {
        self.unread(user_id).len() as u64
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FeedError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FeedError::SchemaMismatch);
        }
        for (id, e) in &self.entries {
            if id.is_empty() {
                return Err(FeedError::EmptyId);
            }
            if e.title.is_empty() {
                return Err(FeedError::EmptyTitle);
            }
            if e.body.is_empty() {
                return Err(FeedError::EmptyBody);
            }
        }
        for u in self.last_seen.keys() {
            if u.is_empty() {
                return Err(FeedError::EmptyUser);
            }
        }
        Ok(())
    }
}

impl Default for WhatsNewFeed {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(id: &str, ts: u64) -> Entry {
        Entry {
            id: id.into(),
            title: id.into(),
            body: format!("body of {id}"),
            published_at_ms: ts,
            severity: Severity::Info,
        }
    }

    #[test]
    fn all_newest_first() {
        let mut f = WhatsNewFeed::new();
        f.publish(e("a", 100)).unwrap();
        f.publish(e("b", 200)).unwrap();
        let v = f.all_newest_first();
        assert_eq!(v[0].id, "b");
        assert_eq!(v[1].id, "a");
    }

    #[test]
    fn unread_for_new_user() {
        let mut f = WhatsNewFeed::new();
        f.publish(e("a", 100)).unwrap();
        f.publish(e("b", 200)).unwrap();
        assert_eq!(f.unread_count("alice"), 2);
    }

    #[test]
    fn mark_all_read_advances() {
        let mut f = WhatsNewFeed::new();
        f.publish(e("a", 100)).unwrap();
        f.publish(e("b", 200)).unwrap();
        f.mark_all_read("alice", 150).unwrap();
        // Only "b" is newer than 150.
        let u = f.unread("alice");
        assert_eq!(u.len(), 1);
        assert_eq!(u[0].id, "b");
    }

    #[test]
    fn mark_all_read_never_regresses() {
        let mut f = WhatsNewFeed::new();
        f.publish(e("a", 100)).unwrap();
        f.publish(e("b", 200)).unwrap();
        f.mark_all_read("alice", 300).unwrap();
        // Try to roll back — watermark stays.
        f.mark_all_read("alice", 100).unwrap();
        assert_eq!(f.last_seen["alice"], 300);
    }

    #[test]
    fn after_full_read_zero() {
        let mut f = WhatsNewFeed::new();
        f.publish(e("a", 100)).unwrap();
        f.mark_all_read("alice", 1_000_000).unwrap();
        assert_eq!(f.unread_count("alice"), 0);
    }

    #[test]
    fn duplicate_rejected() {
        let mut f = WhatsNewFeed::new();
        f.publish(e("a", 1)).unwrap();
        assert!(matches!(
            f.publish(e("a", 2)).unwrap_err(),
            FeedError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut f = WhatsNewFeed::new();
        assert!(matches!(
            f.publish(Entry {
                id: "".into(),
                ..e("a", 1)
            })
            .unwrap_err(),
            FeedError::EmptyId
        ));
        assert!(matches!(
            f.publish(Entry {
                title: "".into(),
                ..e("b", 1)
            })
            .unwrap_err(),
            FeedError::EmptyTitle
        ));
        assert!(matches!(
            f.publish(Entry {
                body: "".into(),
                ..e("c", 1)
            })
            .unwrap_err(),
            FeedError::EmptyBody
        ));
        assert!(matches!(
            f.mark_all_read("", 0).unwrap_err(),
            FeedError::EmptyUser
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = WhatsNewFeed::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FeedError::SchemaMismatch
        ));
    }

    #[test]
    fn feed_serde_roundtrip() {
        let mut f = WhatsNewFeed::new();
        f.publish(e("a", 100)).unwrap();
        f.mark_all_read("alice", 50).unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: WhatsNewFeed = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
