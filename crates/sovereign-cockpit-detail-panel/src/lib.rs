//! `sovereign-cockpit-detail-panel` — inspector for selected item.
//!
//! Operator clicks an item; this panel shows fields + actions. Tracks
//! (subject_kind, subject_id, width_px, collapsed). Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 8 inspectable subject kinds.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SubjectKind {
    /// Conversation turn.
    Turn,
    /// Dashboard widget.
    DashboardWidget,
    /// Replay step.
    ReplayStep,
    /// Bookmark.
    Bookmark,
    /// Pin card.
    PinCard,
    /// Notification.
    Notification,
    /// Share link.
    ShareLink,
    /// Tab.
    Tab,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DetailPanel {
    /// Schema version.
    pub schema_version: String,
    /// Currently-selected subject kind (None = nothing selected).
    pub subject_kind: Option<SubjectKind>,
    /// Selected subject id (empty when nothing).
    pub subject_id: String,
    /// Panel width (px). 280..720.
    pub width_px: u16,
    /// Operator collapsed the panel.
    pub collapsed: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DetailPanelError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Width out of range.
    #[error("width_px {0} outside 280..=720")]
    WidthOutOfRange(u16),
    /// Subject_id present without subject_kind.
    #[error("subject_id set without subject_kind")]
    OrphanSubjectId,
    /// Subject_kind set without subject_id.
    #[error("subject_kind set without subject_id")]
    OrphanSubjectKind,
}

impl DetailPanel {
    /// Default state — collapsed, 360px, nothing selected.
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            subject_kind: None,
            subject_id: String::new(),
            width_px: 360,
            collapsed: true,
        }
    }

    /// Select a subject (opens panel).
    pub fn select(&mut self, kind: SubjectKind, id: &str) {
        self.subject_kind = Some(kind);
        self.subject_id = id.into();
        self.collapsed = false;
    }

    /// Clear selection.
    pub fn clear(&mut self) {
        self.subject_kind = None;
        self.subject_id.clear();
    }

    /// Collapse the panel.
    pub fn collapse(&mut self) { self.collapsed = true; }

    /// Expand the panel.
    pub fn expand(&mut self) { self.collapsed = false; }

    /// Set width with clamp 280..=720.
    pub fn set_width(&mut self, w: u16) -> u16 {
        self.width_px = w.clamp(280, 720);
        self.width_px
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DetailPanelError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DetailPanelError::SchemaMismatch);
        }
        if self.width_px < 280 || self.width_px > 720 {
            return Err(DetailPanelError::WidthOutOfRange(self.width_px));
        }
        match (self.subject_kind, self.subject_id.is_empty()) {
            (Some(_), true) => Err(DetailPanelError::OrphanSubjectKind),
            (None, false) => Err(DetailPanelError::OrphanSubjectId),
            _ => Ok(()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        DetailPanel::default_state().validate().unwrap();
    }

    #[test]
    fn select_opens_panel() {
        let mut p = DetailPanel::default_state();
        p.select(SubjectKind::Turn, "turn-7");
        assert_eq!(p.subject_kind, Some(SubjectKind::Turn));
        assert_eq!(p.subject_id, "turn-7");
        assert!(!p.collapsed);
        p.validate().unwrap();
    }

    #[test]
    fn clear_returns_to_no_selection() {
        let mut p = DetailPanel::default_state();
        p.select(SubjectKind::Turn, "turn-7");
        p.clear();
        assert!(p.subject_kind.is_none());
        assert!(p.subject_id.is_empty());
        p.validate().unwrap();
    }

    #[test]
    fn collapse_expand() {
        let mut p = DetailPanel::default_state();
        assert!(p.collapsed);
        p.expand();
        assert!(!p.collapsed);
        p.collapse();
        assert!(p.collapsed);
    }

    #[test]
    fn set_width_clamps() {
        let mut p = DetailPanel::default_state();
        assert_eq!(p.set_width(100), 280);
        assert_eq!(p.set_width(900), 720);
        assert_eq!(p.set_width(400), 400);
    }

    #[test]
    fn width_out_of_range_caught() {
        let mut p = DetailPanel::default_state();
        p.width_px = 100;
        assert!(matches!(p.validate().unwrap_err(), DetailPanelError::WidthOutOfRange(100)));
    }

    #[test]
    fn orphan_subject_kind_caught() {
        let mut p = DetailPanel::default_state();
        p.subject_kind = Some(SubjectKind::Turn);
        // subject_id still empty.
        assert!(matches!(p.validate().unwrap_err(), DetailPanelError::OrphanSubjectKind));
    }

    #[test]
    fn orphan_subject_id_caught() {
        let mut p = DetailPanel::default_state();
        p.subject_id = "x".into();
        // subject_kind still None.
        assert!(matches!(p.validate().unwrap_err(), DetailPanelError::OrphanSubjectId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = DetailPanel::default_state();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), DetailPanelError::SchemaMismatch));
    }

    #[test]
    fn subject_kind_serde_kebab() {
        assert_eq!(serde_json::to_string(&SubjectKind::DashboardWidget).unwrap(), "\"dashboard-widget\"");
        assert_eq!(serde_json::to_string(&SubjectKind::ShareLink).unwrap(), "\"share-link\"");
    }

    #[test]
    fn panel_serde_roundtrip() {
        let mut p = DetailPanel::default_state();
        p.select(SubjectKind::Notification, "n-1");
        let j = serde_json::to_string(&p).unwrap();
        let back: DetailPanel = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
