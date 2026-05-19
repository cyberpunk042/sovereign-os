//! `sovereign-replay-bookmark-set` — operator-named anchor points.
//!
//! Each `Bookmark` references a turn in a `ConversationThread` by
//! (thread_id, turn_index). The cockpit shows them as colored chips
//! along the replay scrubber; clicking one calls `ReplayCursor::jump_to`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_conversation_thread::ConversationThread;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 6 color tags for visual grouping.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ColorTag {
    /// Red — error / regression marker.
    Red,
    /// Orange — caution.
    Orange,
    /// Yellow — review.
    Yellow,
    /// Green — known-good.
    Green,
    /// Blue — note.
    Blue,
    /// Purple — pinned highlight.
    Purple,
}

/// One bookmark.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Bookmark {
    /// Operator label (non-empty).
    pub label: String,
    /// Thread id.
    pub thread_id: String,
    /// Turn index within thread.
    pub turn_index: u32,
    /// Color tag.
    pub color: ColorTag,
    /// Operator note.
    pub note: String,
}

/// Bookmark set envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BookmarkSet {
    /// Schema version.
    pub schema_version: String,
    /// Bookmarks.
    pub bookmarks: Vec<Bookmark>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BookmarkError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty label.
    #[error("bookmark label empty")]
    EmptyLabel,
    /// Empty thread_id.
    #[error("bookmark {0} thread_id empty")]
    EmptyThreadId(String),
    /// Duplicate label.
    #[error("duplicate bookmark label: {0}")]
    DuplicateLabel(String),
    /// turn_index out of range for the supplied thread.
    #[error("bookmark {label} turn_index {idx} >= turn count {total}")]
    OutOfRange {
        /// label.
        label: String,
        /// idx.
        idx: u32,
        /// total.
        total: u32,
    },
}

impl BookmarkSet {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            bookmarks: Vec::new(),
        }
    }

    /// Add a bookmark validated against the matching thread.
    pub fn add(&mut self, b: Bookmark, thread: &ConversationThread) -> Result<(), BookmarkError> {
        if b.label.is_empty() { return Err(BookmarkError::EmptyLabel); }
        if b.thread_id.is_empty() { return Err(BookmarkError::EmptyThreadId(b.label)); }
        if self.bookmarks.iter().any(|x| x.label == b.label) {
            return Err(BookmarkError::DuplicateLabel(b.label));
        }
        if b.thread_id == thread.thread_id && b.turn_index >= thread.turns.len() as u32 {
            return Err(BookmarkError::OutOfRange {
                label: b.label,
                idx: b.turn_index,
                total: thread.turns.len() as u32,
            });
        }
        self.bookmarks.push(b);
        Ok(())
    }

    /// Look up by label.
    pub fn get(&self, label: &str) -> Option<&Bookmark> {
        self.bookmarks.iter().find(|b| b.label == label)
    }

    /// All bookmarks for a thread, ordered by turn_index.
    pub fn for_thread(&self, thread_id: &str) -> Vec<&Bookmark> {
        let mut v: Vec<&Bookmark> = self.bookmarks.iter().filter(|b| b.thread_id == thread_id).collect();
        v.sort_by_key(|b| b.turn_index);
        v
    }

    /// Validate (without thread context — basic shape only).
    pub fn validate(&self) -> Result<(), BookmarkError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BookmarkError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for b in &self.bookmarks {
            if b.label.is_empty() { return Err(BookmarkError::EmptyLabel); }
            if b.thread_id.is_empty() { return Err(BookmarkError::EmptyThreadId(b.label.clone())); }
            if !seen.insert(b.label.as_str()) {
                return Err(BookmarkError::DuplicateLabel(b.label.clone()));
            }
        }
        Ok(())
    }
}

impl Default for BookmarkSet {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_conversation_thread::{Turn, TurnRole};

    fn turn(role: TurnRole) -> Turn {
        Turn {
            index: 0, role,
            tokens_in: 0, tokens_out: 0,
            provider: "p".into(),
            started_at: "t".into(),
            completed_at: "t".into(),
            branch_id: "main".into(),
            text: String::new(),
        }
    }

    fn thread_3() -> ConversationThread {
        let mut t = ConversationThread::new("th-1", "t");
        t.append(turn(TurnRole::Operator));
        t.append(turn(TurnRole::Model));
        t.append(turn(TurnRole::Tool));
        t
    }

    fn b(label: &str, idx: u32) -> Bookmark {
        Bookmark {
            label: label.into(),
            thread_id: "th-1".into(),
            turn_index: idx,
            color: ColorTag::Blue,
            note: String::new(),
        }
    }

    #[test]
    fn empty_set_validates() {
        BookmarkSet::new().validate().unwrap();
    }

    #[test]
    fn add_and_lookup() {
        let mut s = BookmarkSet::new();
        let t = thread_3();
        s.add(b("start", 0), &t).unwrap();
        s.add(b("end", 2), &t).unwrap();
        assert!(s.get("start").is_some());
        assert!(s.get("end").is_some());
    }

    #[test]
    fn out_of_range_rejected() {
        let mut s = BookmarkSet::new();
        let t = thread_3();
        let err = s.add(b("bad", 99), &t).unwrap_err();
        assert!(matches!(err, BookmarkError::OutOfRange { .. }));
    }

    #[test]
    fn duplicate_label_rejected() {
        let mut s = BookmarkSet::new();
        let t = thread_3();
        s.add(b("x", 0), &t).unwrap();
        let err = s.add(b("x", 1), &t).unwrap_err();
        assert!(matches!(err, BookmarkError::DuplicateLabel(_)));
    }

    #[test]
    fn empty_label_rejected() {
        let mut s = BookmarkSet::new();
        let t = thread_3();
        let err = s.add(b("", 0), &t).unwrap_err();
        assert!(matches!(err, BookmarkError::EmptyLabel));
    }

    #[test]
    fn for_thread_sorts_by_turn_index() {
        let mut s = BookmarkSet::new();
        let t = thread_3();
        s.add(b("c", 2), &t).unwrap();
        s.add(b("a", 0), &t).unwrap();
        s.add(b("b", 1), &t).unwrap();
        let v = s.for_thread("th-1");
        let labels: Vec<&str> = v.iter().map(|b| b.label.as_str()).collect();
        assert_eq!(labels, vec!["a", "b", "c"]);
    }

    #[test]
    fn for_thread_filters_by_thread_id() {
        let mut s = BookmarkSet::new();
        let t = thread_3();
        s.add(b("x", 0), &t).unwrap();
        // Bookmark on different thread (no validation against this thread's bounds).
        s.bookmarks.push(Bookmark {
            label: "other".into(),
            thread_id: "th-other".into(),
            turn_index: 100,
            color: ColorTag::Red,
            note: String::new(),
        });
        assert_eq!(s.for_thread("th-1").len(), 1);
        assert_eq!(s.for_thread("th-other").len(), 1);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = BookmarkSet::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), BookmarkError::SchemaMismatch));
    }

    #[test]
    fn color_serde_kebab() {
        assert_eq!(serde_json::to_string(&ColorTag::Red).unwrap(), "\"red\"");
        assert_eq!(serde_json::to_string(&ColorTag::Purple).unwrap(), "\"purple\"");
    }

    #[test]
    fn set_serde_roundtrip() {
        let mut s = BookmarkSet::new();
        let t = thread_3();
        s.add(b("x", 1), &t).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: BookmarkSet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
