//! `sovereign-cockpit-export-bundle` — operator multi-item export.
//!
//! Each `Bundle` carries (name, items, format, created_at, created_by).
//! 4 item kinds: ConversationThread / DashboardSnapshot / PinBoard /
//! ReplaySession. 3 formats: Json / Markdown / Zip.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Item kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ItemKind {
    /// Full conversation thread.
    ConversationThread,
    /// Dashboard snapshot.
    DashboardSnapshot,
    /// Pin board card set.
    PinBoard,
    /// Replay session.
    ReplaySession,
}

/// Export format.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Format {
    /// JSON.
    Json,
    /// Markdown.
    Markdown,
    /// Zip archive.
    Zip,
}

/// One item reference.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ItemRef {
    /// Kind.
    pub kind: ItemKind,
    /// Subject id.
    pub subject_id: String,
}

/// Export bundle.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExportBundle {
    /// Schema version.
    pub schema_version: String,
    /// Bundle name (≤ 80).
    pub name: String,
    /// Items.
    pub items: Vec<ItemRef>,
    /// Format.
    pub format: Format,
    /// ISO-8601 UTC created.
    pub created_at: String,
    /// Operator MS003 fingerprint.
    pub created_by: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BundleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty name.
    #[error("bundle name empty")]
    EmptyName,
    /// Name too long.
    #[error("bundle name length {0} > 80")]
    NameTooLong(usize),
    /// Empty items.
    #[error("bundle has no items")]
    NoItems,
    /// Empty subject_id in item.
    #[error("item subject_id empty")]
    EmptySubjectId,
    /// Empty created_at / created_by.
    #[error("missing required field: {0}")]
    MissingField(&'static str),
}

impl ExportBundle {
    /// New.
    pub fn new(name: &str, format: Format, created_at: &str, created_by: &str) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            name: name.into(),
            items: Vec::new(),
            format,
            created_at: created_at.into(),
            created_by: created_by.into(),
        }
    }

    /// Add an item.
    pub fn add_item(&mut self, item: ItemRef) -> Result<(), BundleError> {
        if item.subject_id.is_empty() { return Err(BundleError::EmptySubjectId); }
        self.items.push(item);
        Ok(())
    }

    /// Item count.
    pub fn item_count(&self) -> usize { self.items.len() }

    /// Item count by kind.
    pub fn count_by_kind(&self, kind: ItemKind) -> usize {
        self.items.iter().filter(|i| i.kind == kind).count()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BundleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BundleError::SchemaMismatch);
        }
        if self.name.is_empty() { return Err(BundleError::EmptyName); }
        let n = self.name.chars().count();
        if n > 80 { return Err(BundleError::NameTooLong(n)); }
        if self.items.is_empty() { return Err(BundleError::NoItems); }
        for it in &self.items {
            if it.subject_id.is_empty() { return Err(BundleError::EmptySubjectId); }
        }
        if self.created_at.is_empty() { return Err(BundleError::MissingField("created_at")); }
        if self.created_by.is_empty() { return Err(BundleError::MissingField("created_by")); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b() -> ExportBundle {
        let mut b = ExportBundle::new("my-bundle", Format::Json, "2026-05-19T03:00:00Z", "op-fp");
        b.add_item(ItemRef { kind: ItemKind::ConversationThread, subject_id: "th-1".into() }).unwrap();
        b
    }

    #[test]
    fn ok_bundle_validates() {
        b().validate().unwrap();
    }

    #[test]
    fn empty_items_rejected() {
        let mut bundle = ExportBundle::new("x", Format::Json, "t", "op");
        assert!(matches!(bundle.validate().unwrap_err(), BundleError::NoItems));
        let _ = bundle.add_item(ItemRef { kind: ItemKind::PinBoard, subject_id: "p".into() });
    }

    #[test]
    fn empty_name_rejected() {
        let mut bundle = b();
        bundle.name = String::new();
        assert!(matches!(bundle.validate().unwrap_err(), BundleError::EmptyName));
    }

    #[test]
    fn name_too_long_rejected() {
        let mut bundle = b();
        bundle.name = "x".repeat(81);
        assert!(matches!(bundle.validate().unwrap_err(), BundleError::NameTooLong(81)));
    }

    #[test]
    fn item_count_by_kind() {
        let mut bundle = b();
        bundle.add_item(ItemRef { kind: ItemKind::DashboardSnapshot, subject_id: "d-1".into() }).unwrap();
        bundle.add_item(ItemRef { kind: ItemKind::ConversationThread, subject_id: "th-2".into() }).unwrap();
        assert_eq!(bundle.count_by_kind(ItemKind::ConversationThread), 2);
        assert_eq!(bundle.count_by_kind(ItemKind::DashboardSnapshot), 1);
        assert_eq!(bundle.count_by_kind(ItemKind::ReplaySession), 0);
    }

    #[test]
    fn empty_subject_id_rejected_on_add() {
        let mut bundle = b();
        let err = bundle.add_item(ItemRef { kind: ItemKind::PinBoard, subject_id: String::new() }).unwrap_err();
        assert!(matches!(err, BundleError::EmptySubjectId));
    }

    #[test]
    fn missing_created_at_caught() {
        let mut bundle = b();
        bundle.created_at = String::new();
        assert!(matches!(bundle.validate().unwrap_err(), BundleError::MissingField("created_at")));
    }

    #[test]
    fn missing_created_by_caught() {
        let mut bundle = b();
        bundle.created_by = String::new();
        assert!(matches!(bundle.validate().unwrap_err(), BundleError::MissingField("created_by")));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut bundle = b();
        bundle.schema_version = "9.9.9".into();
        assert!(matches!(bundle.validate().unwrap_err(), BundleError::SchemaMismatch));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(serde_json::to_string(&ItemKind::ConversationThread).unwrap(), "\"conversation-thread\"");
        assert_eq!(serde_json::to_string(&ItemKind::DashboardSnapshot).unwrap(), "\"dashboard-snapshot\"");
    }

    #[test]
    fn format_serde_kebab() {
        assert_eq!(serde_json::to_string(&Format::Json).unwrap(), "\"json\"");
        assert_eq!(serde_json::to_string(&Format::Markdown).unwrap(), "\"markdown\"");
        assert_eq!(serde_json::to_string(&Format::Zip).unwrap(), "\"zip\"");
    }

    #[test]
    fn bundle_serde_roundtrip() {
        let bundle = b();
        let j = serde_json::to_string(&bundle).unwrap();
        let back: ExportBundle = serde_json::from_str(&j).unwrap();
        assert_eq!(bundle, back);
    }
}
