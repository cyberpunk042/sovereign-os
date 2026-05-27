//! `sovereign-cockpit-side-panel-state` — drawer state.
//!
//! 4 modes (Closed/Peek/Open/Pinned), active_tab id, remembered
//! width per non-Closed mode, and an MRU tab list. Pure UX
//! descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Panel mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PanelMode {
    /// Hidden.
    Closed,
    /// Hover preview only.
    Peek,
    /// Open, can be closed by clicking outside.
    Open,
    /// Pinned (persistent, layout reserves space).
    Pinned,
}

/// One tab.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tab {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SidePanelState {
    /// Schema version.
    pub schema_version: String,
    /// Tabs.
    pub tabs: Vec<Tab>,
    /// Active tab id (None when no tabs).
    pub active: Option<String>,
    /// MRU tab ids (most recent first).
    pub mru: Vec<String>,
    /// Current mode.
    pub mode: PanelMode,
    /// Remembered width for non-Closed modes (px).
    pub width_px: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SidePanelError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("tab id empty")]
    EmptyId,
    /// Empty label.
    #[error("tab {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate tab id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown tab id: {0}")]
    Unknown(String),
    /// width zero.
    #[error("width_px zero")]
    WidthZero,
}

impl SidePanelState {
    /// New (initial mode Closed; first tab becomes active if any).
    pub fn new(tabs: Vec<Tab>, width_px: u32) -> Result<Self, SidePanelError> {
        if width_px == 0 {
            return Err(SidePanelError::WidthZero);
        }
        check_tabs(&tabs)?;
        let active = tabs.first().map(|t| t.id.clone());
        let mru = tabs.iter().map(|t| t.id.clone()).collect();
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            tabs,
            active,
            mru,
            mode: PanelMode::Closed,
            width_px,
        })
    }

    /// Select a tab (must exist). Updates MRU.
    pub fn select(&mut self, id: &str) -> Result<(), SidePanelError> {
        if !self.tabs.iter().any(|t| t.id == id) {
            return Err(SidePanelError::Unknown(id.into()));
        }
        self.active = Some(id.into());
        self.mru.retain(|x| x != id);
        self.mru.insert(0, id.into());
        Ok(())
    }

    /// Open / close / pin.
    pub fn set_mode(&mut self, mode: PanelMode) {
        self.mode = mode;
    }

    /// Toggle open ↔ closed (closes whatever non-closed mode it was in).
    pub fn toggle(&mut self) {
        self.mode = match self.mode {
            PanelMode::Closed => PanelMode::Open,
            _ => PanelMode::Closed,
        };
    }

    /// Toggle pin (Pinned ↔ Open). No-op when Closed.
    pub fn toggle_pin(&mut self) {
        self.mode = match self.mode {
            PanelMode::Pinned => PanelMode::Open,
            PanelMode::Open | PanelMode::Peek => PanelMode::Pinned,
            PanelMode::Closed => PanelMode::Closed,
        };
    }

    /// Resize.
    pub fn resize(&mut self, px: u32) -> Result<(), SidePanelError> {
        if px == 0 {
            return Err(SidePanelError::WidthZero);
        }
        self.width_px = px;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SidePanelError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SidePanelError::SchemaMismatch);
        }
        if self.width_px == 0 {
            return Err(SidePanelError::WidthZero);
        }
        check_tabs(&self.tabs)?;
        if let Some(a) = &self.active
            && !self.tabs.iter().any(|t| &t.id == a)
        {
            return Err(SidePanelError::Unknown(a.clone()));
        }
        Ok(())
    }
}

fn check_tabs(tabs: &[Tab]) -> Result<(), SidePanelError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for t in tabs {
        if t.id.is_empty() {
            return Err(SidePanelError::EmptyId);
        }
        if t.label.is_empty() {
            return Err(SidePanelError::EmptyLabel(t.id.clone()));
        }
        if !seen.insert(t.id.as_str()) {
            return Err(SidePanelError::DuplicateId(t.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(id: &str) -> Tab {
        Tab {
            id: id.into(),
            label: format!("L-{id}"),
        }
    }

    #[test]
    fn empty_tabs_active_none() {
        let s = SidePanelState::new(vec![], 200).unwrap();
        assert!(s.active.is_none());
    }

    #[test]
    fn first_tab_active() {
        let s = SidePanelState::new(vec![t("a"), t("b")], 200).unwrap();
        assert_eq!(s.active.as_deref(), Some("a"));
    }

    #[test]
    fn select_moves_to_mru_head() {
        let mut s = SidePanelState::new(vec![t("a"), t("b"), t("c")], 200).unwrap();
        s.select("c").unwrap();
        assert_eq!(s.mru[0], "c");
        assert_eq!(s.active.as_deref(), Some("c"));
    }

    #[test]
    fn select_unknown_rejected() {
        let mut s = SidePanelState::new(vec![t("a")], 200).unwrap();
        assert!(matches!(
            s.select("z").unwrap_err(),
            SidePanelError::Unknown(_)
        ));
    }

    #[test]
    fn toggle_flips_open_closed() {
        let mut s = SidePanelState::new(vec![t("a")], 200).unwrap();
        s.toggle();
        assert_eq!(s.mode, PanelMode::Open);
        s.toggle();
        assert_eq!(s.mode, PanelMode::Closed);
    }

    #[test]
    fn toggle_pin_cycles() {
        let mut s = SidePanelState::new(vec![t("a")], 200).unwrap();
        s.set_mode(PanelMode::Open);
        s.toggle_pin();
        assert_eq!(s.mode, PanelMode::Pinned);
        s.toggle_pin();
        assert_eq!(s.mode, PanelMode::Open);
    }

    #[test]
    fn toggle_pin_noop_when_closed() {
        let mut s = SidePanelState::new(vec![t("a")], 200).unwrap();
        s.toggle_pin();
        assert_eq!(s.mode, PanelMode::Closed);
    }

    #[test]
    fn resize_changes_width() {
        let mut s = SidePanelState::new(vec![t("a")], 200).unwrap();
        s.resize(400).unwrap();
        assert_eq!(s.width_px, 400);
    }

    #[test]
    fn resize_zero_rejected() {
        let mut s = SidePanelState::new(vec![t("a")], 200).unwrap();
        assert!(matches!(
            s.resize(0).unwrap_err(),
            SidePanelError::WidthZero
        ));
    }

    #[test]
    fn duplicate_tab_rejected() {
        assert!(matches!(
            SidePanelState::new(vec![t("a"), t("a")], 200).unwrap_err(),
            SidePanelError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = t("a");
        x.id = String::new();
        assert!(matches!(
            SidePanelState::new(vec![x], 200).unwrap_err(),
            SidePanelError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SidePanelState::new(vec![t("a")], 200).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SidePanelError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&PanelMode::Pinned).unwrap(),
            "\"pinned\""
        );
        assert_eq!(serde_json::to_string(&PanelMode::Peek).unwrap(), "\"peek\"");
    }

    #[test]
    fn state_serde_roundtrip() {
        let mut s = SidePanelState::new(vec![t("a"), t("b")], 200).unwrap();
        s.set_mode(PanelMode::Pinned);
        let j = serde_json::to_string(&s).unwrap();
        let back: SidePanelState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
