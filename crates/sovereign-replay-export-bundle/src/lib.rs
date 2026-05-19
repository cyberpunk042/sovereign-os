//! `sovereign-replay-export-bundle` — exportable replay session bundle.
//!
//! Packs `ConversationThread + ReplayCursor + BookmarkSet` into one
//! envelope. Cross-validates that the cursor + bookmarks reference the
//! bundled thread by id.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_conversation_thread::ConversationThread;
use sovereign_replay_cursor::ReplayCursor;
use sovereign_replay_bookmark_set::BookmarkSet;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Export bundle envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExportBundle {
    /// Schema version.
    pub schema_version: String,
    /// Thread.
    pub thread: ConversationThread,
    /// Cursor.
    pub cursor: ReplayCursor,
    /// Bookmarks.
    pub bookmarks: BookmarkSet,
    /// ISO-8601 UTC export time.
    pub exported_at: String,
    /// Operator MS003 fingerprint of exporter.
    pub exported_by: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ExportError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// exported_at empty.
    #[error("exported_at missing")]
    MissingTimestamp,
    /// exported_by empty.
    #[error("exported_by missing")]
    MissingExporter,
    /// Cursor thread_id != bundled thread.
    #[error("cursor thread_id {cursor} != bundle thread {thread}")]
    CursorThreadMismatch {
        /// cursor.
        cursor: String,
        /// thread.
        thread: String,
    },
    /// Bookmark references an unknown thread.
    #[error("bookmark {label} thread_id {thread} != bundle thread {bundle_thread}")]
    BookmarkThreadMismatch {
        /// label.
        label: String,
        /// thread.
        thread: String,
        /// bundle_thread.
        bundle_thread: String,
    },
}

impl ExportBundle {
    /// Build.
    pub fn build(thread: ConversationThread, cursor: ReplayCursor, bookmarks: BookmarkSet, at: &str, by: &str) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            thread, cursor, bookmarks,
            exported_at: at.into(),
            exported_by: by.into(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ExportError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ExportError::SchemaMismatch);
        }
        if self.exported_at.is_empty() { return Err(ExportError::MissingTimestamp); }
        if self.exported_by.is_empty() { return Err(ExportError::MissingExporter); }
        if self.cursor.thread_id != self.thread.thread_id {
            return Err(ExportError::CursorThreadMismatch {
                cursor: self.cursor.thread_id.clone(),
                thread: self.thread.thread_id.clone(),
            });
        }
        for b in &self.bookmarks.bookmarks {
            if b.thread_id != self.thread.thread_id {
                return Err(ExportError::BookmarkThreadMismatch {
                    label: b.label.clone(),
                    thread: b.thread_id.clone(),
                    bundle_thread: self.thread.thread_id.clone(),
                });
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_conversation_thread::{Turn, TurnRole};
    use sovereign_replay_bookmark_set::{Bookmark, ColorTag};
    use sovereign_execution_mode_registry::ExecutionMode;

    fn thread() -> ConversationThread {
        let mut t = ConversationThread::new("th-1", "t");
        t.append(Turn {
            index: 0, role: TurnRole::Operator,
            tokens_in: 0, tokens_out: 0, provider: "p".into(),
            started_at: "t".into(), completed_at: "t".into(),
            branch_id: "main".into(), text: "hi".into(),
        });
        t
    }

    fn cursor(thread_id: &str) -> ReplayCursor {
        let mut t = ConversationThread::new(thread_id, "t");
        t.append(Turn {
            index: 0, role: TurnRole::Operator,
            tokens_in: 0, tokens_out: 0, provider: "p".into(),
            started_at: "t".into(), completed_at: "t".into(),
            branch_id: "main".into(), text: "hi".into(),
        });
        ReplayCursor::open(&t, ExecutionMode::Replay).unwrap()
    }

    #[test]
    fn ok_bundle_validates() {
        let bundle = ExportBundle::build(thread(), cursor("th-1"), BookmarkSet::new(), "t", "op");
        bundle.validate().unwrap();
    }

    #[test]
    fn cursor_thread_mismatch_caught() {
        let bundle = ExportBundle::build(thread(), cursor("th-other"), BookmarkSet::new(), "t", "op");
        match bundle.validate().unwrap_err() {
            ExportError::CursorThreadMismatch { cursor, thread } => {
                assert_eq!(cursor, "th-other");
                assert_eq!(thread, "th-1");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn bookmark_thread_mismatch_caught() {
        let mut bookmarks = BookmarkSet::new();
        bookmarks.bookmarks.push(Bookmark {
            label: "wrong".into(),
            thread_id: "th-other".into(),
            turn_index: 0,
            color: ColorTag::Blue,
            note: String::new(),
        });
        let bundle = ExportBundle::build(thread(), cursor("th-1"), bookmarks, "t", "op");
        assert!(matches!(bundle.validate().unwrap_err(), ExportError::BookmarkThreadMismatch { .. }));
    }

    #[test]
    fn missing_timestamp_caught() {
        let bundle = ExportBundle::build(thread(), cursor("th-1"), BookmarkSet::new(), "", "op");
        assert!(matches!(bundle.validate().unwrap_err(), ExportError::MissingTimestamp));
    }

    #[test]
    fn missing_exporter_caught() {
        let bundle = ExportBundle::build(thread(), cursor("th-1"), BookmarkSet::new(), "t", "");
        assert!(matches!(bundle.validate().unwrap_err(), ExportError::MissingExporter));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut bundle = ExportBundle::build(thread(), cursor("th-1"), BookmarkSet::new(), "t", "op");
        bundle.schema_version = "9.9.9".into();
        assert!(matches!(bundle.validate().unwrap_err(), ExportError::SchemaMismatch));
    }

    #[test]
    fn bundle_serde_roundtrip() {
        let bundle = ExportBundle::build(thread(), cursor("th-1"), BookmarkSet::new(), "2026-05-19T03:00:00Z", "op-fp");
        let j = serde_json::to_string(&bundle).unwrap();
        let back: ExportBundle = serde_json::from_str(&j).unwrap();
        assert_eq!(bundle, back);
    }
}
