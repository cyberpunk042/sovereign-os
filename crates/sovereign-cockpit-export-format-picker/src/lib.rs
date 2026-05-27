//! `sovereign-cockpit-export-format-picker` — pick export format.
//!
//! The picker holds a set of registered export formats and per-user
//! defaults. Each format has a label, extension, MIME, and a small
//! capability set (lossless, preserves_formatting, supports_charts).
//! `available_for(filter)` lists formats satisfying a capability
//! filter. `pick_default(user_id)` returns the user's last choice;
//! falling back to first-registered if none.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Format capabilities.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Capabilities {
    /// Lossless representation.
    pub lossless: bool,
    /// Preserves rich text formatting.
    pub preserves_formatting: bool,
    /// Embeds charts / images.
    pub supports_charts: bool,
}

/// One format.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Format {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// File extension (no dot).
    pub extension: String,
    /// MIME type.
    pub mime: String,
    /// Capabilities.
    pub caps: Capabilities,
    /// Display order.
    pub order: u32,
}

/// Capability filter (true = must have).
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct CapFilter {
    /// Require lossless.
    pub need_lossless: bool,
    /// Require preserve_formatting.
    pub need_formatting: bool,
    /// Require supports_charts.
    pub need_charts: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExportFormatPicker {
    /// Schema version.
    pub schema_version: String,
    /// Formats keyed by id.
    pub formats: BTreeMap<String, Format>,
    /// user_id → last picked format id.
    pub user_defaults: BTreeMap<String, String>,
    /// Next display order to assign.
    pub next_order: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PickerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Empty.
    #[error("extension empty")]
    EmptyExtension,
    /// Empty.
    #[error("mime empty")]
    EmptyMime,
    /// Duplicate.
    #[error("duplicate format id: {0}")]
    DuplicateId(String),
    /// Unknown format.
    #[error("unknown format: {0}")]
    UnknownFormat(String),
    /// Empty user.
    #[error("user id empty")]
    EmptyUser,
}

impl ExportFormatPicker {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            formats: BTreeMap::new(),
            user_defaults: BTreeMap::new(),
            next_order: 0,
        }
    }

    /// Register a new format.
    pub fn register(
        &mut self,
        id: &str,
        label: &str,
        extension: &str,
        mime: &str,
        caps: Capabilities,
    ) -> Result<(), PickerError> {
        if id.is_empty() {
            return Err(PickerError::EmptyId);
        }
        if label.is_empty() {
            return Err(PickerError::EmptyLabel);
        }
        if extension.is_empty() {
            return Err(PickerError::EmptyExtension);
        }
        if mime.is_empty() {
            return Err(PickerError::EmptyMime);
        }
        if self.formats.contains_key(id) {
            return Err(PickerError::DuplicateId(id.into()));
        }
        let order = self.next_order;
        self.next_order = self.next_order.wrapping_add(1);
        self.formats.insert(
            id.into(),
            Format {
                id: id.into(),
                label: label.into(),
                extension: extension.into(),
                mime: mime.into(),
                caps,
                order,
            },
        );
        Ok(())
    }

    /// Formats matching a capability filter, in registration order.
    pub fn available_for(&self, filter: &CapFilter) -> Vec<Format> {
        let mut v: Vec<Format> = self
            .formats
            .values()
            .filter(|f| {
                (!filter.need_lossless || f.caps.lossless)
                    && (!filter.need_formatting || f.caps.preserves_formatting)
                    && (!filter.need_charts || f.caps.supports_charts)
            })
            .cloned()
            .collect();
        v.sort_by_key(|f| f.order);
        v
    }

    /// Record this user's pick.
    pub fn record_pick(&mut self, user_id: &str, format_id: &str) -> Result<(), PickerError> {
        if user_id.is_empty() {
            return Err(PickerError::EmptyUser);
        }
        if !self.formats.contains_key(format_id) {
            return Err(PickerError::UnknownFormat(format_id.into()));
        }
        self.user_defaults.insert(user_id.into(), format_id.into());
        Ok(())
    }

    /// User's default (or first-registered if none).
    pub fn pick_default(&self, user_id: &str) -> Option<&Format> {
        if let Some(fid) = self.user_defaults.get(user_id)
            && let Some(f) = self.formats.get(fid)
        {
            return Some(f);
        }
        // Fallback to first-by-order.
        let mut sorted: Vec<&Format> = self.formats.values().collect();
        sorted.sort_by_key(|f| f.order);
        sorted.first().copied()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PickerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PickerError::SchemaMismatch);
        }
        for (id, f) in &self.formats {
            if id.is_empty() {
                return Err(PickerError::EmptyId);
            }
            if f.label.is_empty() {
                return Err(PickerError::EmptyLabel);
            }
            if f.extension.is_empty() {
                return Err(PickerError::EmptyExtension);
            }
            if f.mime.is_empty() {
                return Err(PickerError::EmptyMime);
            }
        }
        Ok(())
    }
}

impl Default for ExportFormatPicker {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p() -> ExportFormatPicker {
        let mut p = ExportFormatPicker::new();
        p.register(
            "csv",
            "CSV",
            "csv",
            "text/csv",
            Capabilities {
                lossless: true,
                ..Capabilities::default()
            },
        )
        .unwrap();
        p.register(
            "json",
            "JSON",
            "json",
            "application/json",
            Capabilities {
                lossless: true,
                ..Capabilities::default()
            },
        )
        .unwrap();
        p.register(
            "pdf",
            "PDF",
            "pdf",
            "application/pdf",
            Capabilities {
                lossless: false,
                preserves_formatting: true,
                supports_charts: true,
            },
        )
        .unwrap();
        p
    }

    #[test]
    fn register_and_available_all() {
        let p = p();
        let v = p.available_for(&CapFilter::default());
        assert_eq!(v.len(), 3);
        assert_eq!(v[0].id, "csv");
        assert_eq!(v[2].id, "pdf");
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut p = p();
        assert!(matches!(
            p.register("csv", "x", "csv", "text/csv", Capabilities::default())
                .unwrap_err(),
            PickerError::DuplicateId(_)
        ));
    }

    #[test]
    fn filter_by_lossless() {
        let p = p();
        let v = p.available_for(&CapFilter {
            need_lossless: true,
            ..CapFilter::default()
        });
        assert_eq!(v.len(), 2);
        assert!(v.iter().all(|f| f.id == "csv" || f.id == "json"));
    }

    #[test]
    fn filter_by_charts() {
        let p = p();
        let v = p.available_for(&CapFilter {
            need_charts: true,
            ..CapFilter::default()
        });
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].id, "pdf");
    }

    #[test]
    fn user_default_first_registered() {
        let p = p();
        assert_eq!(p.pick_default("alice").unwrap().id, "csv");
    }

    #[test]
    fn record_pick_changes_default() {
        let mut p = p();
        p.record_pick("alice", "pdf").unwrap();
        assert_eq!(p.pick_default("alice").unwrap().id, "pdf");
    }

    #[test]
    fn record_unknown_format_rejected() {
        let mut p = p();
        assert!(matches!(
            p.record_pick("alice", "nope").unwrap_err(),
            PickerError::UnknownFormat(_)
        ));
    }

    #[test]
    fn empty_user_rejected() {
        let mut p = p();
        assert!(matches!(
            p.record_pick("", "csv").unwrap_err(),
            PickerError::EmptyUser
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut p = ExportFormatPicker::new();
        assert!(matches!(
            p.register("", "x", "y", "z", Capabilities::default())
                .unwrap_err(),
            PickerError::EmptyId
        ));
        assert!(matches!(
            p.register("a", "", "y", "z", Capabilities::default())
                .unwrap_err(),
            PickerError::EmptyLabel
        ));
        assert!(matches!(
            p.register("a", "x", "", "z", Capabilities::default())
                .unwrap_err(),
            PickerError::EmptyExtension
        ));
        assert!(matches!(
            p.register("a", "x", "y", "", Capabilities::default())
                .unwrap_err(),
            PickerError::EmptyMime
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ExportFormatPicker::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PickerError::SchemaMismatch
        ));
    }

    #[test]
    fn picker_serde_roundtrip() {
        let mut p = p();
        p.record_pick("alice", "pdf").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: ExportFormatPicker = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
