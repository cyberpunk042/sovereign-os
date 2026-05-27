//! `sovereign-cockpit-clipboard-buffer` — in-engine clipboard ring.
//!
//! Capped FIFO of recent copies. Each entry is text or an image
//! reference. `paste(index)` returns the n-th most recent (0 = head).
//! Total payload size capped to prevent unbounded memory growth.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Entry payload.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Payload {
    /// Text.
    Text {
        /// content.
        content: String,
    },
    /// Image (path or URL).
    Image {
        /// reference.
        reference: String,
    },
}

impl Payload {
    /// Byte size estimate.
    pub fn size(&self) -> usize {
        match self {
            Payload::Text { content } => content.len(),
            Payload::Image { reference } => reference.len(),
        }
    }
}

/// One entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Payload.
    pub payload: Payload,
    /// ISO-8601 UTC.
    pub copied_at: String,
}

/// Ring envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClipboardBuffer {
    /// Schema version.
    pub schema_version: String,
    /// Entries, MRU first.
    pub entries: Vec<Entry>,
    /// Max entry count.
    pub max_entries: u32,
    /// Max total payload bytes.
    pub max_total_bytes: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ClipboardBufferError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// max_entries zero.
    #[error("max_entries is zero")]
    MaxEntriesZero,
    /// max_total_bytes zero.
    #[error("max_total_bytes is zero")]
    MaxTotalZero,
    /// Single payload exceeds max_total_bytes.
    #[error("payload {0} bytes exceeds max_total_bytes {1}")]
    PayloadTooLarge(usize, u32),
    /// Index out of range on paste.
    #[error("paste index {0} out of range (entries {1})")]
    IndexOutOfRange(usize, usize),
}

impl ClipboardBuffer {
    /// New buffer.
    pub fn new(max_entries: u32, max_total_bytes: u32) -> Result<Self, ClipboardBufferError> {
        if max_entries == 0 {
            return Err(ClipboardBufferError::MaxEntriesZero);
        }
        if max_total_bytes == 0 {
            return Err(ClipboardBufferError::MaxTotalZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
            max_entries,
            max_total_bytes,
        })
    }

    /// Push a copy (becomes head).
    pub fn copy(&mut self, payload: Payload, at: &str) -> Result<(), ClipboardBufferError> {
        let sz = payload.size();
        if sz > self.max_total_bytes as usize {
            return Err(ClipboardBufferError::PayloadTooLarge(
                sz,
                self.max_total_bytes,
            ));
        }
        self.entries.insert(
            0,
            Entry {
                payload,
                copied_at: at.into(),
            },
        );
        // Trim count.
        while self.entries.len() > self.max_entries as usize {
            self.entries.pop();
        }
        // Trim by total size.
        while self.total_bytes() > self.max_total_bytes as usize && self.entries.len() > 1 {
            self.entries.pop();
        }
        Ok(())
    }

    /// Total size of entries.
    pub fn total_bytes(&self) -> usize {
        self.entries.iter().map(|e| e.payload.size()).sum()
    }

    /// Paste from index (0 = most recent).
    pub fn paste(&self, index: usize) -> Result<&Entry, ClipboardBufferError> {
        if index >= self.entries.len() {
            return Err(ClipboardBufferError::IndexOutOfRange(
                index,
                self.entries.len(),
            ));
        }
        Ok(&self.entries[index])
    }

    /// Most recent (head).
    pub fn head(&self) -> Option<&Entry> {
        self.entries.first()
    }

    /// Clear.
    pub fn clear(&mut self) {
        self.entries.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ClipboardBufferError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ClipboardBufferError::SchemaMismatch);
        }
        if self.max_entries == 0 {
            return Err(ClipboardBufferError::MaxEntriesZero);
        }
        if self.max_total_bytes == 0 {
            return Err(ClipboardBufferError::MaxTotalZero);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn text(s: &str) -> Payload {
        Payload::Text { content: s.into() }
    }
    fn img(r: &str) -> Payload {
        Payload::Image {
            reference: r.into(),
        }
    }

    #[test]
    fn zero_limits_rejected() {
        assert!(matches!(
            ClipboardBuffer::new(0, 100).unwrap_err(),
            ClipboardBufferError::MaxEntriesZero
        ));
        assert!(matches!(
            ClipboardBuffer::new(1, 0).unwrap_err(),
            ClipboardBufferError::MaxTotalZero
        ));
    }

    #[test]
    fn copy_paste_head() {
        let mut b = ClipboardBuffer::new(5, 1024).unwrap();
        b.copy(text("hello"), "t1").unwrap();
        match &b.paste(0).unwrap().payload {
            Payload::Text { content } => assert_eq!(content, "hello"),
            _ => panic!(),
        }
    }

    #[test]
    fn copy_pushes_to_head() {
        let mut b = ClipboardBuffer::new(5, 1024).unwrap();
        b.copy(text("a"), "t1").unwrap();
        b.copy(text("b"), "t2").unwrap();
        match &b.head().unwrap().payload {
            Payload::Text { content } => assert_eq!(content, "b"),
            _ => panic!(),
        }
    }

    #[test]
    fn max_entries_evicts_oldest() {
        let mut b = ClipboardBuffer::new(2, 1024).unwrap();
        b.copy(text("a"), "t1").unwrap();
        b.copy(text("b"), "t2").unwrap();
        b.copy(text("c"), "t3").unwrap();
        assert_eq!(b.entries.len(), 2);
        // "a" should be gone.
        for e in &b.entries {
            match &e.payload {
                Payload::Text { content } => assert!(content != "a"),
                _ => panic!(),
            }
        }
    }

    #[test]
    fn max_total_bytes_trims_old_entries() {
        let mut b = ClipboardBuffer::new(10, 10).unwrap();
        b.copy(text("12345"), "t1").unwrap();
        b.copy(text("67890"), "t2").unwrap();
        b.copy(text("ABCDE"), "t3").unwrap();
        assert!(b.total_bytes() <= 10);
        assert!(b.entries.len() < 3);
    }

    #[test]
    fn single_payload_too_large_rejected() {
        let mut b = ClipboardBuffer::new(5, 5).unwrap();
        assert!(matches!(
            b.copy(text("XXXXXXXXXX"), "t").unwrap_err(),
            ClipboardBufferError::PayloadTooLarge(10, 5)
        ));
    }

    #[test]
    fn paste_out_of_range_rejected() {
        let b = ClipboardBuffer::new(5, 1024).unwrap();
        assert!(matches!(
            b.paste(0).unwrap_err(),
            ClipboardBufferError::IndexOutOfRange(0, 0)
        ));
    }

    #[test]
    fn clear_empties() {
        let mut b = ClipboardBuffer::new(5, 1024).unwrap();
        b.copy(text("a"), "t").unwrap();
        b.clear();
        assert!(b.entries.is_empty());
    }

    #[test]
    fn image_payload_size_correct() {
        let p = img("/tmp/x.png");
        assert_eq!(p.size(), 10);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = ClipboardBuffer::new(5, 1024).unwrap();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            ClipboardBufferError::SchemaMismatch
        ));
    }

    #[test]
    fn payload_serde_kebab() {
        let j = serde_json::to_string(&text("x")).unwrap();
        assert!(j.contains("\"kind\":\"text\""));
        let j = serde_json::to_string(&img("/x.png")).unwrap();
        assert!(j.contains("\"kind\":\"image\""));
    }

    #[test]
    fn buffer_serde_roundtrip() {
        let mut b = ClipboardBuffer::new(5, 1024).unwrap();
        b.copy(text("hello"), "t").unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: ClipboardBuffer = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
