//! `sovereign-cockpit-multi-select-list` — list multi-selection state.
//!
//! Ordered items + anchor + selected set. Click types:
//! * Plain → replace selection.
//! * Toggle (Ctrl/Cmd) → toggle one, anchor moves to clicked.
//! * Range (Shift) → select inclusive range from anchor to clicked.
//! Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Click semantics.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ClickKind {
    /// Plain click — replace.
    Plain,
    /// Ctrl/Cmd click — toggle one.
    Toggle,
    /// Shift click — range from anchor.
    Range,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MultiSelectList {
    /// Schema version.
    pub schema_version: String,
    /// Items in display order.
    pub items: Vec<String>,
    /// Anchor id (None when nothing has been clicked yet).
    pub anchor: Option<String>,
    /// Sorted-on-store selected id set.
    pub selected: BTreeSet<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MultiSelectError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("item id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate item id: {0}")]
    DuplicateId(String),
    /// Unknown id.
    #[error("unknown item id: {0}")]
    Unknown(String),
    /// Selection references unknown id.
    #[error("selection references unknown id: {0}")]
    SelectionUnknown(String),
    /// Anchor references unknown id.
    #[error("anchor references unknown id: {0}")]
    AnchorUnknown(String),
}

impl MultiSelectList {
    /// New list.
    pub fn new(items: Vec<String>) -> Result<Self, MultiSelectError> {
        check_items(&items)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            items,
            anchor: None,
            selected: BTreeSet::new(),
        })
    }

    /// Click `id` with the given semantics.
    pub fn click(&mut self, id: &str, kind: ClickKind) -> Result<(), MultiSelectError> {
        let pos = self.items.iter().position(|x| x == id)
            .ok_or_else(|| MultiSelectError::Unknown(id.into()))?;
        match kind {
            ClickKind::Plain => {
                self.selected.clear();
                self.selected.insert(id.into());
                self.anchor = Some(id.into());
            }
            ClickKind::Toggle => {
                if self.selected.contains(id) {
                    self.selected.remove(id);
                } else {
                    self.selected.insert(id.into());
                }
                self.anchor = Some(id.into());
            }
            ClickKind::Range => {
                let a_pos = self.anchor.as_ref()
                    .and_then(|a| self.items.iter().position(|x| x == a))
                    .unwrap_or(pos);
                let (lo, hi) = if a_pos <= pos { (a_pos, pos) } else { (pos, a_pos) };
                self.selected.clear();
                for it in &self.items[lo..=hi] {
                    self.selected.insert(it.clone());
                }
                // Anchor stays as is.
            }
        }
        Ok(())
    }

    /// Select all items.
    pub fn select_all(&mut self) {
        for it in &self.items {
            self.selected.insert(it.clone());
        }
    }

    /// Clear selection (anchor preserved).
    pub fn clear(&mut self) {
        self.selected.clear();
    }

    /// Count of selected items.
    pub fn count(&self) -> usize {
        self.selected.len()
    }

    /// Is id selected?
    pub fn is_selected(&self, id: &str) -> bool {
        self.selected.contains(id)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MultiSelectError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MultiSelectError::SchemaMismatch);
        }
        check_items(&self.items)?;
        use std::collections::HashSet;
        let ids: HashSet<&str> = self.items.iter().map(String::as_str).collect();
        for s in &self.selected {
            if !ids.contains(s.as_str()) {
                return Err(MultiSelectError::SelectionUnknown(s.clone()));
            }
        }
        if let Some(a) = &self.anchor {
            if !ids.contains(a.as_str()) {
                return Err(MultiSelectError::AnchorUnknown(a.clone()));
            }
        }
        Ok(())
    }
}

fn check_items(items: &[String]) -> Result<(), MultiSelectError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for i in items {
        if i.is_empty() { return Err(MultiSelectError::EmptyId); }
        if !seen.insert(i.as_str()) {
            return Err(MultiSelectError::DuplicateId(i.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn list() -> MultiSelectList {
        MultiSelectList::new(vec!["a".into(), "b".into(), "c".into(), "d".into(), "e".into()]).unwrap()
    }

    #[test]
    fn plain_replace() {
        let mut l = list();
        l.click("a", ClickKind::Plain).unwrap();
        l.click("c", ClickKind::Plain).unwrap();
        assert_eq!(l.count(), 1);
        assert!(l.is_selected("c"));
        assert!(!l.is_selected("a"));
    }

    #[test]
    fn toggle_adds_and_removes() {
        let mut l = list();
        l.click("a", ClickKind::Toggle).unwrap();
        l.click("c", ClickKind::Toggle).unwrap();
        assert_eq!(l.count(), 2);
        l.click("a", ClickKind::Toggle).unwrap();
        assert!(!l.is_selected("a"));
        assert!(l.is_selected("c"));
    }

    #[test]
    fn range_inclusive_from_anchor() {
        let mut l = list();
        l.click("b", ClickKind::Plain).unwrap();
        l.click("d", ClickKind::Range).unwrap();
        assert_eq!(l.count(), 3);
        for id in ["b", "c", "d"] {
            assert!(l.is_selected(id));
        }
    }

    #[test]
    fn range_backward_anchor() {
        let mut l = list();
        l.click("d", ClickKind::Plain).unwrap();
        l.click("b", ClickKind::Range).unwrap();
        assert_eq!(l.count(), 3);
        for id in ["b", "c", "d"] {
            assert!(l.is_selected(id));
        }
    }

    #[test]
    fn range_without_anchor_uses_clicked() {
        let mut l = list();
        l.click("c", ClickKind::Range).unwrap();
        assert_eq!(l.count(), 1);
        assert!(l.is_selected("c"));
    }

    #[test]
    fn select_all_and_clear() {
        let mut l = list();
        l.select_all();
        assert_eq!(l.count(), 5);
        l.clear();
        assert_eq!(l.count(), 0);
    }

    #[test]
    fn unknown_click_rejected() {
        let mut l = list();
        assert!(matches!(l.click("z", ClickKind::Plain).unwrap_err(), MultiSelectError::Unknown(_)));
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            MultiSelectList::new(vec!["a".into(), "a".into()]).unwrap_err(),
            MultiSelectError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        assert!(matches!(
            MultiSelectList::new(vec!["a".into(), String::new()]).unwrap_err(),
            MultiSelectError::EmptyId
        ));
    }

    #[test]
    fn validate_unknown_selection_rejected() {
        let mut l = list();
        l.selected.insert("ghost".into());
        assert!(matches!(l.validate().unwrap_err(), MultiSelectError::SelectionUnknown(_)));
    }

    #[test]
    fn validate_unknown_anchor_rejected() {
        let mut l = list();
        l.anchor = Some("ghost".into());
        assert!(matches!(l.validate().unwrap_err(), MultiSelectError::AnchorUnknown(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = list();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), MultiSelectError::SchemaMismatch));
    }

    #[test]
    fn click_serde_kebab() {
        assert_eq!(serde_json::to_string(&ClickKind::Plain).unwrap(), "\"plain\"");
        assert_eq!(serde_json::to_string(&ClickKind::Toggle).unwrap(), "\"toggle\"");
        assert_eq!(serde_json::to_string(&ClickKind::Range).unwrap(), "\"range\"");
    }

    #[test]
    fn list_serde_roundtrip() {
        let mut l = list();
        l.click("a", ClickKind::Plain).unwrap();
        l.click("c", ClickKind::Toggle).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: MultiSelectList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
