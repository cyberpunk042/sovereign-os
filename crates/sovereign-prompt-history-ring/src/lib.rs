//! `sovereign-prompt-history-ring` — operator prompt-recall buffer.
//!
//! Bounded FIFO of recent prompts. `push()` dedups consecutive
//! identicals. `prev()` / `next()` walks the cursor for ↑/↓ recall.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Maximum entries retained.
pub const MAX_ENTRIES: usize = 500;

/// History ring.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PromptHistoryRing {
    /// Schema version.
    pub schema_version: String,
    /// Prompts oldest first.
    pub entries: Vec<String>,
    /// Current cursor position for ↑/↓ (None = at end).
    pub cursor: Option<usize>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HistoryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty entry.
    #[error("empty entry")]
    EmptyEntry,
}

impl PromptHistoryRing {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
            cursor: None,
        }
    }

    /// Add a prompt. Dedups against the most recent entry.
    pub fn push(&mut self, prompt: &str) -> Result<(), HistoryError> {
        if prompt.is_empty() {
            return Err(HistoryError::EmptyEntry);
        }
        if let Some(last) = self.entries.last()
            && last == prompt
        {
            return Ok(());
        } // dedupe consecutive
        self.entries.push(prompt.into());
        while self.entries.len() > MAX_ENTRIES {
            self.entries.remove(0);
        }
        self.cursor = None;
        Ok(())
    }

    /// Move cursor to the previous (older) entry; returns the entry text.
    /// Returns None when no older entry exists.
    pub fn prev(&mut self) -> Option<&str> {
        if self.entries.is_empty() {
            return None;
        }
        let new_cursor = match self.cursor {
            None => self.entries.len() - 1,
            Some(0) => return Some(self.entries[0].as_str()),
            Some(n) => n - 1,
        };
        self.cursor = Some(new_cursor);
        Some(self.entries[new_cursor].as_str())
    }

    /// Move cursor to the next (newer) entry; returns the entry text or
    /// None when cursor walks off the end.
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Option<&str> {
        let cur = self.cursor?;
        if cur + 1 >= self.entries.len() {
            self.cursor = None;
            return None;
        }
        self.cursor = Some(cur + 1);
        Some(self.entries[cur + 1].as_str())
    }

    /// Reset cursor to "at end".
    pub fn reset_cursor(&mut self) {
        self.cursor = None;
    }

    /// Count entries.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Is empty.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HistoryError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HistoryError::SchemaMismatch);
        }
        for e in &self.entries {
            if e.is_empty() {
                return Err(HistoryError::EmptyEntry);
            }
        }
        Ok(())
    }
}

impl Default for PromptHistoryRing {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_ring_validates() {
        PromptHistoryRing::new().validate().unwrap();
    }

    #[test]
    fn push_appends() {
        let mut r = PromptHistoryRing::new();
        r.push("hello").unwrap();
        r.push("world").unwrap();
        assert_eq!(r.len(), 2);
    }

    #[test]
    fn consecutive_duplicates_deduped() {
        let mut r = PromptHistoryRing::new();
        r.push("a").unwrap();
        r.push("a").unwrap();
        r.push("a").unwrap();
        assert_eq!(r.len(), 1);
    }

    #[test]
    fn non_consecutive_duplicates_kept() {
        let mut r = PromptHistoryRing::new();
        r.push("a").unwrap();
        r.push("b").unwrap();
        r.push("a").unwrap();
        assert_eq!(r.len(), 3);
    }

    #[test]
    fn empty_push_rejected() {
        let mut r = PromptHistoryRing::new();
        assert!(matches!(r.push("").unwrap_err(), HistoryError::EmptyEntry));
    }

    #[test]
    fn prev_walks_backward() {
        let mut r = PromptHistoryRing::new();
        r.push("a").unwrap();
        r.push("b").unwrap();
        r.push("c").unwrap();
        assert_eq!(r.prev(), Some("c"));
        assert_eq!(r.prev(), Some("b"));
        assert_eq!(r.prev(), Some("a"));
        // At first entry, prev returns same.
        assert_eq!(r.prev(), Some("a"));
    }

    #[test]
    fn next_walks_forward() {
        let mut r = PromptHistoryRing::new();
        r.push("a").unwrap();
        r.push("b").unwrap();
        r.push("c").unwrap();
        r.prev(); // c
        r.prev(); // b
        r.prev(); // a
        assert_eq!(r.next(), Some("b"));
        assert_eq!(r.next(), Some("c"));
        // At end, next returns None.
        assert_eq!(r.next(), None);
    }

    #[test]
    fn prev_on_empty_returns_none() {
        let mut r = PromptHistoryRing::new();
        assert_eq!(r.prev(), None);
    }

    #[test]
    fn push_resets_cursor() {
        let mut r = PromptHistoryRing::new();
        r.push("a").unwrap();
        r.push("b").unwrap();
        r.prev(); // cursor=1
        r.push("c").unwrap();
        // After push, cursor reset to None → prev returns most recent (c).
        assert_eq!(r.prev(), Some("c"));
    }

    #[test]
    fn overflow_drops_oldest() {
        let mut r = PromptHistoryRing::new();
        for i in 0..(MAX_ENTRIES + 5) {
            r.push(&format!("p{i}")).unwrap();
        }
        assert_eq!(r.len(), MAX_ENTRIES);
        assert_eq!(r.entries[0], "p5");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = PromptHistoryRing::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            HistoryError::SchemaMismatch
        ));
    }

    #[test]
    fn ring_serde_roundtrip() {
        let mut r = PromptHistoryRing::new();
        r.push("a").unwrap();
        r.push("b").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: PromptHistoryRing = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
