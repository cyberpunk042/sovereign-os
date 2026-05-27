//! `sovereign-cockpit-changelog-pane` — versioned changelog with read state.
//!
//! Entry{version, title, kind Added/Changed/Fixed/Deprecated/Removed/
//! Security, body, published_at_ms}. add inserts in published-asc
//! order (sorted on each add for simplicity). mark_read(version)
//! flags entry; unread_count returns count of unread entries.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Kind.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Kind {
    /// Added.
    Added,
    /// Changed.
    Changed,
    /// Fixed.
    Fixed,
    /// Deprecated.
    Deprecated,
    /// Removed.
    Removed,
    /// Security.
    Security,
}

/// Entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Version string (semver-like).
    pub version: String,
    /// Title.
    pub title: String,
    /// Kind.
    pub kind: Kind,
    /// Body.
    pub body: String,
    /// Published ts ms.
    pub published_at_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChangelogPane {
    /// Schema version.
    pub schema_version: String,
    /// Entries (sorted by published_at_ms asc).
    pub entries: Vec<Entry>,
    /// Set of read versions.
    pub read: BTreeSet<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ChangelogError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("version empty")]
    EmptyVersion,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Duplicate.
    #[error("duplicate version: {0}")]
    Duplicate(String),
    /// Unknown.
    #[error("unknown version: {0}")]
    Unknown(String),
}

impl ChangelogPane {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
            read: BTreeSet::new(),
        }
    }

    /// Add.
    pub fn add(&mut self, e: Entry) -> Result<(), ChangelogError> {
        if e.version.is_empty() {
            return Err(ChangelogError::EmptyVersion);
        }
        if e.title.is_empty() {
            return Err(ChangelogError::EmptyTitle);
        }
        if self.entries.iter().any(|x| x.version == e.version) {
            return Err(ChangelogError::Duplicate(e.version));
        }
        self.entries.push(e);
        self.entries
            .sort_by(|a, b| a.published_at_ms.cmp(&b.published_at_ms));
        Ok(())
    }

    /// Mark a version as read.
    pub fn mark_read(&mut self, version: &str) -> Result<(), ChangelogError> {
        if !self.entries.iter().any(|x| x.version == version) {
            return Err(ChangelogError::Unknown(version.into()));
        }
        self.read.insert(version.into());
        Ok(())
    }

    /// Unread count.
    pub fn unread_count(&self) -> usize {
        self.entries
            .iter()
            .filter(|e| !self.read.contains(&e.version))
            .count()
    }

    /// Unread entries (in display order).
    pub fn unread(&self) -> Vec<&Entry> {
        self.entries
            .iter()
            .filter(|e| !self.read.contains(&e.version))
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ChangelogError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ChangelogError::SchemaMismatch);
        }
        for e in &self.entries {
            if e.version.is_empty() {
                return Err(ChangelogError::EmptyVersion);
            }
            if e.title.is_empty() {
                return Err(ChangelogError::EmptyTitle);
            }
        }
        Ok(())
    }
}

impl Default for ChangelogPane {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(v: &str, t: &str, k: Kind, ts: u64) -> Entry {
        Entry {
            version: v.into(),
            title: t.into(),
            kind: k,
            body: "body".into(),
            published_at_ms: ts,
        }
    }

    #[test]
    fn add_sorts_by_published_at() {
        let mut c = ChangelogPane::new();
        c.add(e("v3", "c", Kind::Changed, 300)).unwrap();
        c.add(e("v1", "a", Kind::Added, 100)).unwrap();
        c.add(e("v2", "b", Kind::Fixed, 200)).unwrap();
        let versions: Vec<&str> = c.entries.iter().map(|e| e.version.as_str()).collect();
        assert_eq!(versions, vec!["v1", "v2", "v3"]);
    }

    #[test]
    fn unread_count_initial() {
        let mut c = ChangelogPane::new();
        c.add(e("v1", "a", Kind::Added, 0)).unwrap();
        c.add(e("v2", "b", Kind::Fixed, 1)).unwrap();
        assert_eq!(c.unread_count(), 2);
    }

    #[test]
    fn mark_read_decrements() {
        let mut c = ChangelogPane::new();
        c.add(e("v1", "a", Kind::Added, 0)).unwrap();
        c.mark_read("v1").unwrap();
        assert_eq!(c.unread_count(), 0);
    }

    #[test]
    fn mark_unknown_rejected() {
        let mut c = ChangelogPane::new();
        assert!(matches!(
            c.mark_read("nope").unwrap_err(),
            ChangelogError::Unknown(_)
        ));
    }

    #[test]
    fn duplicate_rejected() {
        let mut c = ChangelogPane::new();
        c.add(e("v1", "a", Kind::Added, 0)).unwrap();
        assert!(matches!(
            c.add(e("v1", "a", Kind::Added, 0)).unwrap_err(),
            ChangelogError::Duplicate(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut c = ChangelogPane::new();
        assert!(matches!(
            c.add(e("", "t", Kind::Added, 0)).unwrap_err(),
            ChangelogError::EmptyVersion
        ));
        assert!(matches!(
            c.add(e("v", "", Kind::Added, 0)).unwrap_err(),
            ChangelogError::EmptyTitle
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ChangelogPane::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            ChangelogError::SchemaMismatch
        ));
    }

    #[test]
    fn changelog_serde_roundtrip() {
        let mut c = ChangelogPane::new();
        c.add(e("v1", "a", Kind::Added, 0)).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: ChangelogPane = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
