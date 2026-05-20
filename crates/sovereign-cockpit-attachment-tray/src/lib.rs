//! `sovereign-cockpit-attachment-tray` — per-draft attachment list.
//!
//! Each draft id holds a list of attached items: filename, byte
//! size, MIME, and a status (Pending, Uploaded, Failed). Capacity
//! is bounded by a max count and a max total size in bytes; adding
//! beyond either returns the appropriate Rejected verdict.
//!
//! `add(draft, item)` → Accepted / RejectedCount / RejectedSize.
//! `update_status(draft, id, status)`. `remove(draft, id)`.
//! `total_bytes(draft)` reports current usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Upload status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum UploadStatus {
    /// Pending.
    Pending,
    /// Uploaded.
    Uploaded,
    /// Failed.
    Failed,
}

/// One attachment.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Attachment {
    /// Stable id within the draft.
    pub id: String,
    /// Filename.
    pub filename: String,
    /// Size.
    pub size_bytes: u64,
    /// MIME.
    pub mime: String,
    /// Status.
    pub status: UploadStatus,
}

/// Per-draft list.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct DraftAttachments {
    /// Ordered.
    pub items: Vec<Attachment>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AttachmentTray {
    /// Schema version.
    pub schema_version: String,
    /// Max attachments per draft.
    pub max_count: u32,
    /// Max total bytes per draft.
    pub max_total_bytes: u64,
    /// draft_id → attachments.
    pub drafts: BTreeMap<String, DraftAttachments>,
}

/// Add verdict.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum AddVerdict {
    /// Accepted.
    Accepted,
    /// Too many items.
    RejectedCount {
        /// current.
        count: u32,
        /// limit.
        limit: u32,
    },
    /// Total bytes exceeded.
    RejectedSize {
        /// would-be-new total.
        proposed_total: u64,
        /// limit.
        limit: u64,
    },
    /// Duplicate id.
    Duplicate,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TrayError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty draft id.
    #[error("draft id empty")]
    EmptyDraft,
    /// Empty attachment id.
    #[error("attachment id empty")]
    EmptyId,
    /// Empty filename.
    #[error("filename empty")]
    EmptyFilename,
    /// Empty MIME.
    #[error("mime empty")]
    EmptyMime,
    /// Unknown attachment.
    #[error("unknown attachment: {0}")]
    UnknownAttachment(String),
}

impl AttachmentTray {
    /// New with limits.
    pub fn new(max_count: u32, max_total_bytes: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            max_count,
            max_total_bytes,
            drafts: BTreeMap::new(),
        }
    }

    /// Add an attachment to a draft.
    pub fn add(&mut self, draft_id: &str, item: Attachment) -> Result<AddVerdict, TrayError> {
        if draft_id.is_empty() { return Err(TrayError::EmptyDraft); }
        if item.id.is_empty() { return Err(TrayError::EmptyId); }
        if item.filename.is_empty() { return Err(TrayError::EmptyFilename); }
        if item.mime.is_empty() { return Err(TrayError::EmptyMime); }
        let d = self.drafts.entry(draft_id.into()).or_default();
        if d.items.iter().any(|a| a.id == item.id) {
            return Ok(AddVerdict::Duplicate);
        }
        if d.items.len() as u32 >= self.max_count {
            return Ok(AddVerdict::RejectedCount { count: d.items.len() as u32, limit: self.max_count });
        }
        let current_total: u64 = d.items.iter().map(|a| a.size_bytes).sum();
        let proposed = current_total.saturating_add(item.size_bytes);
        if proposed > self.max_total_bytes {
            return Ok(AddVerdict::RejectedSize { proposed_total: proposed, limit: self.max_total_bytes });
        }
        d.items.push(item);
        Ok(AddVerdict::Accepted)
    }

    /// Update an attachment's status.
    pub fn update_status(&mut self, draft_id: &str, id: &str, status: UploadStatus) -> Result<(), TrayError> {
        let d = self.drafts.get_mut(draft_id).ok_or_else(|| TrayError::UnknownAttachment(format!("{draft_id}/{id}")))?;
        let a = d.items.iter_mut().find(|a| a.id == id).ok_or_else(|| TrayError::UnknownAttachment(format!("{draft_id}/{id}")))?;
        a.status = status;
        Ok(())
    }

    /// Remove an attachment. Returns true if removed.
    pub fn remove(&mut self, draft_id: &str, id: &str) -> bool {
        let Some(d) = self.drafts.get_mut(draft_id) else { return false; };
        let before = d.items.len();
        d.items.retain(|a| a.id != id);
        d.items.len() != before
    }

    /// Total bytes for a draft.
    pub fn total_bytes(&self, draft_id: &str) -> u64 {
        self.drafts.get(draft_id).map(|d| d.items.iter().map(|a| a.size_bytes).sum()).unwrap_or(0)
    }

    /// All attachments for a draft.
    pub fn items(&self, draft_id: &str) -> Vec<Attachment> {
        self.drafts.get(draft_id).map(|d| d.items.clone()).unwrap_or_default()
    }

    /// Clear a draft.
    pub fn clear(&mut self, draft_id: &str) -> bool {
        self.drafts.remove(draft_id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TrayError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TrayError::SchemaMismatch); }
        for (id, d) in &self.drafts {
            if id.is_empty() { return Err(TrayError::EmptyDraft); }
            for a in &d.items {
                if a.id.is_empty() { return Err(TrayError::EmptyId); }
                if a.filename.is_empty() { return Err(TrayError::EmptyFilename); }
                if a.mime.is_empty() { return Err(TrayError::EmptyMime); }
            }
        }
        Ok(())
    }
}

impl Default for AttachmentTray {
    fn default() -> Self { Self::new(10, 100 * 1024 * 1024) }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn att(id: &str, size: u64) -> Attachment {
        Attachment {
            id: id.into(),
            filename: format!("{id}.bin"),
            size_bytes: size,
            mime: "application/octet-stream".into(),
            status: UploadStatus::Pending,
        }
    }

    #[test]
    fn add_accepts_within_limits() {
        let mut t = AttachmentTray::new(3, 1_000);
        assert_eq!(t.add("d", att("a", 100)).unwrap(), AddVerdict::Accepted);
        assert_eq!(t.total_bytes("d"), 100);
    }

    #[test]
    fn reject_count() {
        let mut t = AttachmentTray::new(2, 10_000);
        t.add("d", att("a", 1)).unwrap();
        t.add("d", att("b", 1)).unwrap();
        match t.add("d", att("c", 1)).unwrap() {
            AddVerdict::RejectedCount { count, limit } => {
                assert_eq!(count, 2);
                assert_eq!(limit, 2);
            }
            _ => panic!(),
        }
    }

    #[test]
    fn reject_size() {
        let mut t = AttachmentTray::new(10, 100);
        t.add("d", att("a", 80)).unwrap();
        match t.add("d", att("b", 50)).unwrap() {
            AddVerdict::RejectedSize { proposed_total, limit } => {
                assert_eq!(proposed_total, 130);
                assert_eq!(limit, 100);
            }
            _ => panic!(),
        }
    }

    #[test]
    fn duplicate_id() {
        let mut t = AttachmentTray::new(10, 10_000);
        t.add("d", att("a", 1)).unwrap();
        assert_eq!(t.add("d", att("a", 1)).unwrap(), AddVerdict::Duplicate);
    }

    #[test]
    fn update_status_changes() {
        let mut t = AttachmentTray::new(10, 10_000);
        t.add("d", att("a", 1)).unwrap();
        t.update_status("d", "a", UploadStatus::Uploaded).unwrap();
        assert_eq!(t.items("d")[0].status, UploadStatus::Uploaded);
    }

    #[test]
    fn update_unknown_rejected() {
        let mut t = AttachmentTray::new(10, 10_000);
        assert!(matches!(t.update_status("d", "a", UploadStatus::Uploaded).unwrap_err(), TrayError::UnknownAttachment(_)));
    }

    #[test]
    fn remove_works() {
        let mut t = AttachmentTray::new(10, 10_000);
        t.add("d", att("a", 1)).unwrap();
        assert!(t.remove("d", "a"));
        assert!(!t.remove("d", "a"));
    }

    #[test]
    fn clear_removes_draft() {
        let mut t = AttachmentTray::new(10, 10_000);
        t.add("d", att("a", 1)).unwrap();
        assert!(t.clear("d"));
        assert!(t.items("d").is_empty());
    }

    #[test]
    fn drafts_independent() {
        let mut t = AttachmentTray::new(1, 10_000);
        t.add("d1", att("a", 1)).unwrap();
        // d2 still has room.
        assert_eq!(t.add("d2", att("a", 1)).unwrap(), AddVerdict::Accepted);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut t = AttachmentTray::new(10, 10_000);
        assert!(matches!(t.add("", att("a", 1)).unwrap_err(), TrayError::EmptyDraft));
        assert!(matches!(t.add("d", att("", 1)).unwrap_err(), TrayError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = AttachmentTray::new(10, 10_000);
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TrayError::SchemaMismatch));
    }

    #[test]
    fn tray_serde_roundtrip() {
        let mut t = AttachmentTray::new(10, 10_000);
        t.add("d", att("a", 1)).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: AttachmentTray = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
