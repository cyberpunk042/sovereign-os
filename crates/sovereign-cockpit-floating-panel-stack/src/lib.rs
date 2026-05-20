//! `sovereign-cockpit-floating-panel-stack` — floating panel z-stack.
//!
//! Each panel has an id + title + z (assigned in registration order).
//! `bring_to_front(id)` updates z to be greater than all others.
//! `focused` is the topmost visible panel; `set_minimized(id, bool)`
//! affects visibility. `close(id)` removes.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One panel.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Panel {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Z (higher = on top).
    pub z: u64,
    /// Minimized (hidden but kept).
    pub minimized: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FloatingPanelStack {
    /// Schema version.
    pub schema_version: String,
    /// id → panel.
    pub panels: BTreeMap<String, Panel>,
    /// Next z to assign.
    pub next_z: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PanelError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Duplicate.
    #[error("duplicate panel id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown panel: {0}")]
    UnknownPanel(String),
}

impl FloatingPanelStack {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            panels: BTreeMap::new(),
            next_z: 1,
        }
    }

    /// Open a new panel (top of stack).
    pub fn open(&mut self, id: &str, title: &str) -> Result<u64, PanelError> {
        if id.is_empty() { return Err(PanelError::EmptyId); }
        if title.is_empty() { return Err(PanelError::EmptyTitle); }
        if self.panels.contains_key(id) {
            return Err(PanelError::DuplicateId(id.into()));
        }
        let z = self.next_z;
        self.next_z = self.next_z.saturating_add(1);
        self.panels.insert(id.into(), Panel {
            id: id.into(),
            title: title.into(),
            z,
            minimized: false,
        });
        Ok(z)
    }

    /// Bring to front (returns new z).
    pub fn bring_to_front(&mut self, id: &str) -> Result<u64, PanelError> {
        if !self.panels.contains_key(id) {
            return Err(PanelError::UnknownPanel(id.into()));
        }
        let z = self.next_z;
        self.next_z = self.next_z.saturating_add(1);
        self.panels.get_mut(id).unwrap().z = z;
        Ok(z)
    }

    /// Minimize / restore.
    pub fn set_minimized(&mut self, id: &str, minimized: bool) -> Result<(), PanelError> {
        let p = self.panels.get_mut(id).ok_or_else(|| PanelError::UnknownPanel(id.into()))?;
        p.minimized = minimized;
        Ok(())
    }

    /// Close.
    pub fn close(&mut self, id: &str) -> bool {
        self.panels.remove(id).is_some()
    }

    /// Focused (topmost non-minimized).
    pub fn focused(&self) -> Option<Panel> {
        self.panels.values()
            .filter(|p| !p.minimized)
            .max_by(|a, b| a.z.cmp(&b.z).then(a.id.cmp(&b.id)))
            .cloned()
    }

    /// Stack order (front-to-back).
    pub fn z_order(&self) -> Vec<Panel> {
        let mut v: Vec<Panel> = self.panels.values().cloned().collect();
        v.sort_by(|a, b| b.z.cmp(&a.z).then(a.id.cmp(&b.id)));
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PanelError> {
        if self.schema_version != SCHEMA_VERSION { return Err(PanelError::SchemaMismatch); }
        for (id, p) in &self.panels {
            if id.is_empty() { return Err(PanelError::EmptyId); }
            if p.title.is_empty() { return Err(PanelError::EmptyTitle); }
        }
        Ok(())
    }
}

impl Default for FloatingPanelStack {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn open_assigns_increasing_z() {
        let mut s = FloatingPanelStack::new();
        let z1 = s.open("a", "A").unwrap();
        let z2 = s.open("b", "B").unwrap();
        assert!(z2 > z1);
    }

    #[test]
    fn focused_is_topmost() {
        let mut s = FloatingPanelStack::new();
        s.open("a", "A").unwrap();
        s.open("b", "B").unwrap();
        assert_eq!(s.focused().unwrap().id, "b");
    }

    #[test]
    fn bring_to_front_updates_focus() {
        let mut s = FloatingPanelStack::new();
        s.open("a", "A").unwrap();
        s.open("b", "B").unwrap();
        s.bring_to_front("a").unwrap();
        assert_eq!(s.focused().unwrap().id, "a");
    }

    #[test]
    fn minimized_excluded_from_focus() {
        let mut s = FloatingPanelStack::new();
        s.open("a", "A").unwrap();
        s.open("b", "B").unwrap();
        s.set_minimized("b", true).unwrap();
        // b was on top but minimized; focused = a.
        assert_eq!(s.focused().unwrap().id, "a");
    }

    #[test]
    fn close_removes() {
        let mut s = FloatingPanelStack::new();
        s.open("a", "A").unwrap();
        assert!(s.close("a"));
        assert!(s.focused().is_none());
    }

    #[test]
    fn z_order_top_first() {
        let mut s = FloatingPanelStack::new();
        s.open("a", "A").unwrap();
        s.open("b", "B").unwrap();
        s.open("c", "C").unwrap();
        let o = s.z_order();
        assert_eq!(o[0].id, "c");
        assert_eq!(o[2].id, "a");
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = FloatingPanelStack::new();
        s.open("a", "A").unwrap();
        assert!(matches!(s.open("a", "A").unwrap_err(), PanelError::DuplicateId(_)));
    }

    #[test]
    fn unknown_actions_rejected() {
        let mut s = FloatingPanelStack::new();
        assert!(matches!(s.bring_to_front("nope").unwrap_err(), PanelError::UnknownPanel(_)));
        assert!(matches!(s.set_minimized("nope", true).unwrap_err(), PanelError::UnknownPanel(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = FloatingPanelStack::new();
        assert!(matches!(s.open("", "A").unwrap_err(), PanelError::EmptyId));
        assert!(matches!(s.open("a", "").unwrap_err(), PanelError::EmptyTitle));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = FloatingPanelStack::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), PanelError::SchemaMismatch));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = FloatingPanelStack::new();
        s.open("a", "A").unwrap();
        s.open("b", "B").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: FloatingPanelStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
