//! `sovereign-cockpit-clipboard-history` — recent-copy ring buffer.
//!
//! Bounded FIFO; oldest dropped on overflow. Each entry has a kind +
//! body + copied_at. Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max clipboard entries.
pub const MAX_ENTRIES: usize = 100;

/// Entry kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EntryKind {
    /// Free text.
    Text,
    /// URL / link.
    Link,
    /// Trace id.
    TraceId,
    /// Command output snippet.
    CommandOutput,
    /// Code snippet.
    Code,
}

/// One clipboard entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClipboardEntry {
    /// Kind.
    pub kind: EntryKind,
    /// Body (≤ 8000 chars).
    pub body: String,
    /// ISO-8601 UTC.
    pub copied_at: String,
}

/// Clipboard history.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClipboardHistory {
    /// Schema version.
    pub schema_version: String,
    /// Entries (newest last).
    pub entries: Vec<ClipboardEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ClipboardError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Body too long.
    #[error("body length {0} > 8000")]
    BodyTooLong(usize),
    /// Body empty.
    #[error("body empty")]
    EmptyBody,
    /// Empty timestamp.
    #[error("copied_at empty")]
    MissingTimestamp,
}

impl ClipboardHistory {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
        }
    }

    /// Push an entry.
    pub fn push(&mut self, entry: ClipboardEntry) -> Result<(), ClipboardError> {
        check_shape(&entry)?;
        self.entries.push(entry);
        while self.entries.len() > MAX_ENTRIES {
            self.entries.remove(0);
        }
        Ok(())
    }

    /// Most recent entry of a given kind.
    pub fn latest_of_kind(&self, kind: EntryKind) -> Option<&ClipboardEntry> {
        self.entries.iter().rev().find(|e| e.kind == kind)
    }

    /// Filter by kind.
    pub fn by_kind(&self, kind: EntryKind) -> Vec<&ClipboardEntry> {
        self.entries.iter().filter(|e| e.kind == kind).collect()
    }

    /// Clear all.
    pub fn clear(&mut self) { self.entries.clear(); }

    /// Validate.
    pub fn validate(&self) -> Result<(), ClipboardError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ClipboardError::SchemaMismatch);
        }
        for e in &self.entries {
            check_shape(e)?;
        }
        Ok(())
    }
}

fn check_shape(e: &ClipboardEntry) -> Result<(), ClipboardError> {
    if e.body.is_empty() { return Err(ClipboardError::EmptyBody); }
    let n = e.body.chars().count();
    if n > 8000 { return Err(ClipboardError::BodyTooLong(n)); }
    if e.copied_at.is_empty() { return Err(ClipboardError::MissingTimestamp); }
    Ok(())
}

impl Default for ClipboardHistory {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(kind: EntryKind, body: &str) -> ClipboardEntry {
        ClipboardEntry {
            kind,
            body: body.into(),
            copied_at: "2026-05-19T03:00:00Z".into(),
        }
    }

    #[test]
    fn empty_history_validates() {
        ClipboardHistory::new().validate().unwrap();
    }

    #[test]
    fn push_and_lookup() {
        let mut h = ClipboardHistory::new();
        h.push(e(EntryKind::Text, "hello")).unwrap();
        h.push(e(EntryKind::Link, "https://example.org")).unwrap();
        assert_eq!(h.entries.len(), 2);
        assert_eq!(h.latest_of_kind(EntryKind::Link).unwrap().body, "https://example.org");
    }

    #[test]
    fn by_kind_filters() {
        let mut h = ClipboardHistory::new();
        h.push(e(EntryKind::Text, "a")).unwrap();
        h.push(e(EntryKind::Code, "fn main() {}")).unwrap();
        h.push(e(EntryKind::Text, "b")).unwrap();
        assert_eq!(h.by_kind(EntryKind::Text).len(), 2);
        assert_eq!(h.by_kind(EntryKind::Code).len(), 1);
        assert_eq!(h.by_kind(EntryKind::Link).len(), 0);
    }

    #[test]
    fn overflow_drops_oldest() {
        let mut h = ClipboardHistory::new();
        for i in 0..(MAX_ENTRIES + 5) {
            h.push(e(EntryKind::Text, &format!("entry-{i}"))).unwrap();
        }
        assert_eq!(h.entries.len(), MAX_ENTRIES);
        assert_eq!(h.entries[0].body, "entry-5");
    }

    #[test]
    fn empty_body_rejected() {
        let mut h = ClipboardHistory::new();
        assert!(matches!(h.push(e(EntryKind::Text, "")).unwrap_err(), ClipboardError::EmptyBody));
    }

    #[test]
    fn body_too_long_rejected() {
        let mut h = ClipboardHistory::new();
        let long = "x".repeat(8001);
        assert!(matches!(h.push(e(EntryKind::Text, &long)).unwrap_err(), ClipboardError::BodyTooLong(8001)));
    }

    #[test]
    fn clear_empties() {
        let mut h = ClipboardHistory::new();
        h.push(e(EntryKind::Text, "x")).unwrap();
        h.clear();
        assert!(h.entries.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = ClipboardHistory::new();
        h.schema_version = "9.9.9".into();
        assert!(matches!(h.validate().unwrap_err(), ClipboardError::SchemaMismatch));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(serde_json::to_string(&EntryKind::Text).unwrap(), "\"text\"");
        assert_eq!(serde_json::to_string(&EntryKind::TraceId).unwrap(), "\"trace-id\"");
        assert_eq!(serde_json::to_string(&EntryKind::CommandOutput).unwrap(), "\"command-output\"");
    }

    #[test]
    fn history_serde_roundtrip() {
        let mut h = ClipboardHistory::new();
        h.push(e(EntryKind::Text, "x")).unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: ClipboardHistory = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
