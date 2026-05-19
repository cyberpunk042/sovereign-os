//! `sovereign-cockpit-drag-drop` — drag/drop session state.
//!
//! Tracks an in-flight drag operation (source / target / valid drop /
//! cursor position). Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Object kind being dragged or dropped.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ObjectKind {
    /// Tab.
    Tab,
    /// PinCard.
    PinCard,
    /// QuickActionSlot.
    QuickActionSlot,
    /// Bookmark.
    Bookmark,
    /// DashboardWidget.
    DashboardWidget,
}

/// Cursor position.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Cursor {
    /// x.
    pub x: i32,
    /// y.
    pub y: i32,
}

/// In-flight drag state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DragSession {
    /// Schema version.
    pub schema_version: String,
    /// Source object id.
    pub source_id: String,
    /// Source kind.
    pub source_kind: ObjectKind,
    /// Optional hovered target id.
    pub target_id: String,
    /// Optional hovered target kind.
    pub target_kind: Option<ObjectKind>,
    /// Is current target a valid drop?
    pub valid_drop: bool,
    /// Current cursor.
    pub cursor: Cursor,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DragDropError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty source_id.
    #[error("source_id empty")]
    EmptySourceId,
    /// Cross-kind drop (forbidden).
    #[error("cross-kind drop forbidden: source {src:?} target {tgt:?}")]
    CrossKindDrop {
        /// source.
        src: ObjectKind,
        /// target.
        tgt: ObjectKind,
    },
}

impl DragSession {
    /// Begin a drag.
    pub fn begin(source_id: &str, source_kind: ObjectKind, cursor: Cursor) -> Result<Self, DragDropError> {
        if source_id.is_empty() { return Err(DragDropError::EmptySourceId); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            source_id: source_id.into(),
            source_kind,
            target_id: String::new(),
            target_kind: None,
            valid_drop: false,
            cursor,
        })
    }

    /// Update hovered target.
    pub fn hover(&mut self, target_id: &str, target_kind: ObjectKind, cursor: Cursor) -> Result<(), DragDropError> {
        self.target_id = target_id.into();
        self.target_kind = Some(target_kind);
        self.cursor = cursor;
        // Same-kind drops are valid; cross-kind drops are not.
        self.valid_drop = target_kind == self.source_kind;
        if !self.valid_drop {
            return Err(DragDropError::CrossKindDrop {
                src: self.source_kind,
                tgt: target_kind,
            });
        }
        Ok(())
    }

    /// Clear target hover (no current drop target).
    pub fn unhover(&mut self) {
        self.target_id.clear();
        self.target_kind = None;
        self.valid_drop = false;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DragDropError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DragDropError::SchemaMismatch);
        }
        if self.source_id.is_empty() { return Err(DragDropError::EmptySourceId); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn begin_drag() {
        let s = DragSession::begin("tab-1", ObjectKind::Tab, Cursor { x: 100, y: 100 }).unwrap();
        assert_eq!(s.source_id, "tab-1");
        assert!(s.target_id.is_empty());
        assert!(!s.valid_drop);
    }

    #[test]
    fn same_kind_hover_valid() {
        let mut s = DragSession::begin("tab-1", ObjectKind::Tab, Cursor { x: 0, y: 0 }).unwrap();
        s.hover("tab-2", ObjectKind::Tab, Cursor { x: 50, y: 50 }).unwrap();
        assert!(s.valid_drop);
        assert_eq!(s.target_id, "tab-2");
    }

    #[test]
    fn cross_kind_hover_rejected() {
        let mut s = DragSession::begin("tab-1", ObjectKind::Tab, Cursor { x: 0, y: 0 }).unwrap();
        let err = s.hover("p-1", ObjectKind::PinCard, Cursor { x: 0, y: 0 }).unwrap_err();
        assert!(matches!(err, DragDropError::CrossKindDrop { .. }));
        assert!(!s.valid_drop);
    }

    #[test]
    fn unhover_clears() {
        let mut s = DragSession::begin("tab-1", ObjectKind::Tab, Cursor { x: 0, y: 0 }).unwrap();
        s.hover("tab-2", ObjectKind::Tab, Cursor { x: 0, y: 0 }).unwrap();
        s.unhover();
        assert!(s.target_id.is_empty());
        assert!(!s.valid_drop);
    }

    #[test]
    fn empty_source_id_rejected() {
        assert!(matches!(
            DragSession::begin("", ObjectKind::Tab, Cursor { x: 0, y: 0 }).unwrap_err(),
            DragDropError::EmptySourceId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = DragSession::begin("a", ObjectKind::Tab, Cursor { x: 0, y: 0 }).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), DragDropError::SchemaMismatch));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(serde_json::to_string(&ObjectKind::PinCard).unwrap(), "\"pin-card\"");
        assert_eq!(serde_json::to_string(&ObjectKind::QuickActionSlot).unwrap(), "\"quick-action-slot\"");
        assert_eq!(serde_json::to_string(&ObjectKind::DashboardWidget).unwrap(), "\"dashboard-widget\"");
    }

    #[test]
    fn session_serde_roundtrip() {
        let s = DragSession::begin("a", ObjectKind::Tab, Cursor { x: 1, y: 2 }).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: DragSession = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
