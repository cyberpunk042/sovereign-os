//! `sovereign-cockpit-focus-trap` — modal focus-trap state.
//!
//! While a modal/overlay is open the cockpit must keep keyboard focus
//! inside it (Tab wraps forward, Shift+Tab wraps backward, Escape
//! dismisses). This crate models that state — ordered focusable ids
//! and the active index. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Action signalled by a key event.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum FocusAction {
    /// Tab: forward, wrapping.
    Next,
    /// Shift+Tab: backward, wrapping.
    Prev,
    /// Escape: dismiss the trap.
    Dismiss,
}

/// One focusable element.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Focusable {
    /// Stable id (button/input/link/etc.).
    pub id: String,
    /// Display label (for accessibility surfaces).
    pub label: String,
    /// Is this focusable currently enabled? Disabled ones are skipped.
    pub enabled: bool,
}

/// Focus-trap state envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FocusTrap {
    /// Schema version.
    pub schema_version: String,
    /// Owning modal id (for routing dismiss signal).
    pub owner_id: String,
    /// Ordered focusables.
    pub items: Vec<Focusable>,
    /// Index of currently-focused element (None = no enabled items).
    pub active: Option<usize>,
    /// Has the operator pressed Escape this frame?
    pub dismissed: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FocusTrapError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty owner id.
    #[error("owner_id empty")]
    EmptyOwnerId,
    /// Empty item id.
    #[error("focusable id empty")]
    EmptyId,
    /// Empty item label.
    #[error("focusable {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate focusable id: {0}")]
    DuplicateId(String),
    /// Active index out of range.
    #[error("active {active} out of range (len {len})")]
    ActiveOutOfRange {
        /// active.
        active: usize,
        /// len.
        len: usize,
    },
    /// Active element disabled.
    #[error("active index {0} points at disabled focusable")]
    ActiveDisabled(usize),
}

impl FocusTrap {
    /// New trap. Selects first enabled focusable if any.
    pub fn new(owner_id: &str, items: Vec<Focusable>) -> Result<Self, FocusTrapError> {
        if owner_id.is_empty() {
            return Err(FocusTrapError::EmptyOwnerId);
        }
        check_items(&items)?;
        let active = items.iter().position(|f| f.enabled);
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            owner_id: owner_id.into(),
            items,
            active,
            dismissed: false,
        })
    }

    /// Apply a key action. Returns the new active id (or None for
    /// dismissal / empty trap).
    pub fn apply(&mut self, action: FocusAction) -> Option<&str> {
        match action {
            FocusAction::Dismiss => {
                self.dismissed = true;
                None
            }
            FocusAction::Next => {
                self.step(true);
                self.active.map(|i| self.items[i].id.as_str())
            }
            FocusAction::Prev => {
                self.step(false);
                self.active.map(|i| self.items[i].id.as_str())
            }
        }
    }

    fn step(&mut self, forward: bool) {
        let n = self.items.len();
        if n == 0 {
            self.active = None;
            return;
        }
        let enabled_count = self.items.iter().filter(|f| f.enabled).count();
        if enabled_count == 0 {
            self.active = None;
            return;
        }
        let start = self.active.unwrap_or(0);
        for offset in 1..=n {
            let idx = if forward {
                (start + offset) % n
            } else {
                (start + n - offset) % n
            };
            if self.items[idx].enabled {
                self.active = Some(idx);
                return;
            }
        }
    }

    /// Currently-focused id (None if empty or dismissed cleared).
    pub fn focused(&self) -> Option<&str> {
        self.active.map(|i| self.items[i].id.as_str())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FocusTrapError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FocusTrapError::SchemaMismatch);
        }
        if self.owner_id.is_empty() {
            return Err(FocusTrapError::EmptyOwnerId);
        }
        check_items(&self.items)?;
        if let Some(a) = self.active {
            if a >= self.items.len() {
                return Err(FocusTrapError::ActiveOutOfRange {
                    active: a,
                    len: self.items.len(),
                });
            }
            if !self.items[a].enabled {
                return Err(FocusTrapError::ActiveDisabled(a));
            }
        }
        Ok(())
    }
}

fn check_items(items: &[Focusable]) -> Result<(), FocusTrapError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for f in items {
        if f.id.is_empty() {
            return Err(FocusTrapError::EmptyId);
        }
        if f.label.is_empty() {
            return Err(FocusTrapError::EmptyLabel(f.id.clone()));
        }
        if !seen.insert(f.id.as_str()) {
            return Err(FocusTrapError::DuplicateId(f.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn f(id: &str, enabled: bool) -> Focusable {
        Focusable {
            id: id.into(),
            label: format!("Label-{id}"),
            enabled,
        }
    }

    #[test]
    fn empty_owner_rejected() {
        assert!(matches!(
            FocusTrap::new("", vec![f("a", true)]).unwrap_err(),
            FocusTrapError::EmptyOwnerId
        ));
    }

    #[test]
    fn empty_items_active_none() {
        let t = FocusTrap::new("modal-1", vec![]).unwrap();
        assert!(t.active.is_none());
        t.validate().unwrap();
    }

    #[test]
    fn first_enabled_focused_initially() {
        let t = FocusTrap::new("modal-1", vec![f("a", false), f("b", true), f("c", true)]).unwrap();
        assert_eq!(t.focused(), Some("b"));
    }

    #[test]
    fn next_wraps() {
        let mut t = FocusTrap::new("m", vec![f("a", true), f("b", true), f("c", true)]).unwrap();
        assert_eq!(t.apply(FocusAction::Next), Some("b"));
        assert_eq!(t.apply(FocusAction::Next), Some("c"));
        assert_eq!(t.apply(FocusAction::Next), Some("a"));
    }

    #[test]
    fn prev_wraps() {
        let mut t = FocusTrap::new("m", vec![f("a", true), f("b", true), f("c", true)]).unwrap();
        assert_eq!(t.apply(FocusAction::Prev), Some("c"));
        assert_eq!(t.apply(FocusAction::Prev), Some("b"));
        assert_eq!(t.apply(FocusAction::Prev), Some("a"));
    }

    #[test]
    fn skips_disabled() {
        let mut t = FocusTrap::new("m", vec![f("a", true), f("b", false), f("c", true)]).unwrap();
        assert_eq!(t.apply(FocusAction::Next), Some("c"));
        assert_eq!(t.apply(FocusAction::Next), Some("a"));
    }

    #[test]
    fn all_disabled_no_focus() {
        let mut t = FocusTrap::new("m", vec![f("a", false), f("b", false)]).unwrap();
        assert!(t.focused().is_none());
        assert_eq!(t.apply(FocusAction::Next), None);
    }

    #[test]
    fn dismiss_sets_flag() {
        let mut t = FocusTrap::new("m", vec![f("a", true)]).unwrap();
        assert!(!t.dismissed);
        assert_eq!(t.apply(FocusAction::Dismiss), None);
        assert!(t.dismissed);
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            FocusTrap::new("m", vec![f("a", true), f("a", true)]).unwrap_err(),
            FocusTrapError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = f("a", true);
        x.id = String::new();
        assert!(matches!(
            FocusTrap::new("m", vec![x]).unwrap_err(),
            FocusTrapError::EmptyId
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut x = f("a", true);
        x.label = String::new();
        assert!(matches!(
            FocusTrap::new("m", vec![x]).unwrap_err(),
            FocusTrapError::EmptyLabel(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = FocusTrap::new("m", vec![f("a", true)]).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), FocusTrapError::SchemaMismatch));
    }

    #[test]
    fn action_serde_kebab() {
        assert_eq!(serde_json::to_string(&FocusAction::Next).unwrap(), "\"next\"");
        assert_eq!(serde_json::to_string(&FocusAction::Prev).unwrap(), "\"prev\"");
        assert_eq!(serde_json::to_string(&FocusAction::Dismiss).unwrap(), "\"dismiss\"");
    }

    #[test]
    fn trap_serde_roundtrip() {
        let t = FocusTrap::new("m", vec![f("a", true), f("b", true)]).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: FocusTrap = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
