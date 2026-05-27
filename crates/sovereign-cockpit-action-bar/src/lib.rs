//! `sovereign-cockpit-action-bar` — bottom action-bar state.
//!
//! 3 slots: primary (right-aligned, prominent), secondary
//! (left-aligned, less prominent), tertiary (inline, low key).
//! Each slot is Option<ActionSlot> with label + enabled + danger.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One slot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionSlot {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Enabled?
    pub enabled: bool,
    /// Danger styling (red)?
    pub danger: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionBar {
    /// Schema version.
    pub schema_version: String,
    /// Primary (right).
    pub primary: Option<ActionSlot>,
    /// Secondary (left).
    pub secondary: Option<ActionSlot>,
    /// Tertiary (inline).
    pub tertiary: Option<ActionSlot>,
}

/// Slot kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SlotKind {
    /// Primary.
    Primary,
    /// Secondary.
    Secondary,
    /// Tertiary.
    Tertiary,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ActionBarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("slot id empty")]
    EmptyId,
    /// Empty label.
    #[error("slot {0} label empty")]
    EmptyLabel(String),
    /// Same id reused across slots.
    #[error("duplicate slot id across bar: {0}")]
    DuplicateAcrossSlots(String),
}

impl ActionBar {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            primary: None,
            secondary: None,
            tertiary: None,
        }
    }

    /// Set a slot.
    pub fn set(&mut self, kind: SlotKind, slot: ActionSlot) -> Result<(), ActionBarError> {
        check_slot(&slot)?;
        // Disallow same id across different slots.
        let id = slot.id.clone();
        let collides = match kind {
            SlotKind::Primary => self.id_in_other(&id, &[SlotKind::Secondary, SlotKind::Tertiary]),
            SlotKind::Secondary => self.id_in_other(&id, &[SlotKind::Primary, SlotKind::Tertiary]),
            SlotKind::Tertiary => self.id_in_other(&id, &[SlotKind::Primary, SlotKind::Secondary]),
        };
        if collides {
            return Err(ActionBarError::DuplicateAcrossSlots(id));
        }
        match kind {
            SlotKind::Primary => self.primary = Some(slot),
            SlotKind::Secondary => self.secondary = Some(slot),
            SlotKind::Tertiary => self.tertiary = Some(slot),
        }
        Ok(())
    }

    fn id_in_other(&self, id: &str, others: &[SlotKind]) -> bool {
        for k in others {
            let s = match k {
                SlotKind::Primary => &self.primary,
                SlotKind::Secondary => &self.secondary,
                SlotKind::Tertiary => &self.tertiary,
            };
            if let Some(s) = s {
                if s.id == id {
                    return true;
                }
            }
        }
        false
    }

    /// Clear a slot.
    pub fn clear_slot(&mut self, kind: SlotKind) {
        match kind {
            SlotKind::Primary => self.primary = None,
            SlotKind::Secondary => self.secondary = None,
            SlotKind::Tertiary => self.tertiary = None,
        }
    }

    /// Clear all slots.
    pub fn clear_all(&mut self) {
        self.primary = None;
        self.secondary = None;
        self.tertiary = None;
    }

    /// Render order: secondary, tertiary, primary (right-aligned).
    pub fn render_order(&self) -> Vec<&ActionSlot> {
        let mut out: Vec<&ActionSlot> = Vec::new();
        if let Some(s) = &self.secondary {
            out.push(s);
        }
        if let Some(s) = &self.tertiary {
            out.push(s);
        }
        if let Some(s) = &self.primary {
            out.push(s);
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ActionBarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ActionBarError::SchemaMismatch);
        }
        for s in [&self.primary, &self.secondary, &self.tertiary] {
            if let Some(s) = s {
                check_slot(s)?;
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in [&self.primary, &self.secondary, &self.tertiary] {
            if let Some(s) = s {
                if !seen.insert(s.id.as_str()) {
                    return Err(ActionBarError::DuplicateAcrossSlots(s.id.clone()));
                }
            }
        }
        Ok(())
    }
}

fn check_slot(s: &ActionSlot) -> Result<(), ActionBarError> {
    if s.id.is_empty() {
        return Err(ActionBarError::EmptyId);
    }
    if s.label.is_empty() {
        return Err(ActionBarError::EmptyLabel(s.id.clone()));
    }
    Ok(())
}

impl Default for ActionBar {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn slot(id: &str, enabled: bool, danger: bool) -> ActionSlot {
        ActionSlot {
            id: id.into(),
            label: format!("L-{id}"),
            enabled,
            danger,
        }
    }

    #[test]
    fn set_and_render_order() {
        let mut b = ActionBar::new();
        b.set(SlotKind::Primary, slot("save", true, false)).unwrap();
        b.set(SlotKind::Secondary, slot("cancel", true, false))
            .unwrap();
        b.set(SlotKind::Tertiary, slot("help", true, false))
            .unwrap();
        let r = b.render_order();
        // Order: secondary, tertiary, primary.
        let ids: Vec<&str> = r.iter().map(|s| s.id.as_str()).collect();
        assert_eq!(ids, vec!["cancel", "help", "save"]);
    }

    #[test]
    fn clear_slot() {
        let mut b = ActionBar::new();
        b.set(SlotKind::Primary, slot("save", true, false)).unwrap();
        b.clear_slot(SlotKind::Primary);
        assert!(b.primary.is_none());
    }

    #[test]
    fn clear_all() {
        let mut b = ActionBar::new();
        b.set(SlotKind::Primary, slot("a", true, false)).unwrap();
        b.set(SlotKind::Secondary, slot("b", true, false)).unwrap();
        b.clear_all();
        assert!(b.primary.is_none());
        assert!(b.secondary.is_none());
    }

    #[test]
    fn duplicate_id_across_slots_rejected() {
        let mut b = ActionBar::new();
        b.set(SlotKind::Primary, slot("x", true, false)).unwrap();
        assert!(matches!(
            b.set(SlotKind::Secondary, slot("x", true, false))
                .unwrap_err(),
            ActionBarError::DuplicateAcrossSlots(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut b = ActionBar::new();
        assert!(matches!(
            b.set(SlotKind::Primary, slot("", true, false)).unwrap_err(),
            ActionBarError::EmptyId
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut b = ActionBar::new();
        let mut s = slot("a", true, false);
        s.label = String::new();
        assert!(matches!(
            b.set(SlotKind::Primary, s).unwrap_err(),
            ActionBarError::EmptyLabel(_)
        ));
    }

    #[test]
    fn replacing_same_slot_with_same_id_ok() {
        let mut b = ActionBar::new();
        b.set(SlotKind::Primary, slot("x", true, false)).unwrap();
        b.set(SlotKind::Primary, slot("x", false, true)).unwrap();
        assert_eq!(b.primary.as_ref().unwrap().danger, true);
    }

    #[test]
    fn empty_render_order() {
        let b = ActionBar::new();
        assert!(b.render_order().is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = ActionBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            ActionBarError::SchemaMismatch
        ));
    }

    #[test]
    fn slot_kind_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&SlotKind::Primary).unwrap(),
            "\"primary\""
        );
    }

    #[test]
    fn bar_serde_roundtrip() {
        let mut b = ActionBar::new();
        b.set(SlotKind::Primary, slot("save", true, false)).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: ActionBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
