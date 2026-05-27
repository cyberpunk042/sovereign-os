//! `sovereign-cockpit-workspace-switcher` — workspace switcher.
//!
//! Tracks a registry of workspaces and the operator's current
//! active workspace. Each workspace can be `pinned` (always shown
//! at the top in pin order) or unpinned (shown in last-used order).
//! `ordered_for_picker()` returns pinned first (by pin_order),
//! then recents (by last_used_ms desc).
//!
//! Operations:
//!   * `add(id, label)` — register.
//!   * `switch_to(id, ts)` — make active + record last_used.
//!   * `pin(id, pin_order)` / `unpin(id)`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One workspace.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Workspace {
    /// Id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Last used ts (0 if never).
    pub last_used_ms: u64,
    /// Pin order if pinned (None = not pinned).
    pub pin_order: Option<u32>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkspaceSwitcher {
    /// Schema version.
    pub schema_version: String,
    /// id → workspace.
    pub workspaces: BTreeMap<String, Workspace>,
    /// Currently active.
    pub active: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SwitcherError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown workspace: {0}")]
    UnknownWorkspace(String),
}

impl WorkspaceSwitcher {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            workspaces: BTreeMap::new(),
            active: None,
        }
    }

    /// Add.
    pub fn add(&mut self, id: &str, label: &str) -> Result<(), SwitcherError> {
        if id.is_empty() {
            return Err(SwitcherError::EmptyId);
        }
        if label.is_empty() {
            return Err(SwitcherError::EmptyLabel);
        }
        if self.workspaces.contains_key(id) {
            return Err(SwitcherError::DuplicateId(id.into()));
        }
        self.workspaces.insert(
            id.into(),
            Workspace {
                id: id.into(),
                label: label.into(),
                last_used_ms: 0,
                pin_order: None,
            },
        );
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        if self.workspaces.remove(id).is_some() {
            if self.active.as_deref() == Some(id) {
                self.active = None;
            }
            true
        } else {
            false
        }
    }

    /// Switch (records last_used + sets active).
    pub fn switch_to(&mut self, id: &str, ts_ms: u64) -> Result<(), SwitcherError> {
        let w = self
            .workspaces
            .get_mut(id)
            .ok_or_else(|| SwitcherError::UnknownWorkspace(id.into()))?;
        w.last_used_ms = ts_ms;
        self.active = Some(id.into());
        Ok(())
    }

    /// Pin.
    pub fn pin(&mut self, id: &str, pin_order: u32) -> Result<(), SwitcherError> {
        let w = self
            .workspaces
            .get_mut(id)
            .ok_or_else(|| SwitcherError::UnknownWorkspace(id.into()))?;
        w.pin_order = Some(pin_order);
        Ok(())
    }

    /// Unpin.
    pub fn unpin(&mut self, id: &str) -> Result<(), SwitcherError> {
        let w = self
            .workspaces
            .get_mut(id)
            .ok_or_else(|| SwitcherError::UnknownWorkspace(id.into()))?;
        w.pin_order = None;
        Ok(())
    }

    /// Picker order: pinned (by pin_order asc), then recents (last_used desc), then alpha.
    pub fn ordered_for_picker(&self) -> Vec<Workspace> {
        let mut pinned: Vec<Workspace> = self
            .workspaces
            .values()
            .filter(|w| w.pin_order.is_some())
            .cloned()
            .collect();
        pinned.sort_by(|a, b| a.pin_order.cmp(&b.pin_order).then(a.label.cmp(&b.label)));
        let mut others: Vec<Workspace> = self
            .workspaces
            .values()
            .filter(|w| w.pin_order.is_none())
            .cloned()
            .collect();
        others.sort_by(|a, b| {
            b.last_used_ms
                .cmp(&a.last_used_ms)
                .then(a.label.cmp(&b.label))
        });
        pinned.extend(others);
        pinned
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SwitcherError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SwitcherError::SchemaMismatch);
        }
        for (id, w) in &self.workspaces {
            if id.is_empty() {
                return Err(SwitcherError::EmptyId);
            }
            if w.label.is_empty() {
                return Err(SwitcherError::EmptyLabel);
            }
        }
        Ok(())
    }
}

impl Default for WorkspaceSwitcher {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_switch() {
        let mut s = WorkspaceSwitcher::new();
        s.add("w1", "Workspace 1").unwrap();
        s.switch_to("w1", 100).unwrap();
        assert_eq!(s.active.as_deref(), Some("w1"));
        assert_eq!(s.workspaces["w1"].last_used_ms, 100);
    }

    #[test]
    fn pin_appears_first() {
        let mut s = WorkspaceSwitcher::new();
        s.add("a", "A").unwrap();
        s.add("b", "B").unwrap();
        s.switch_to("a", 100).unwrap();
        // a recent; pin b → b should appear first.
        s.pin("b", 0).unwrap();
        let o = s.ordered_for_picker();
        assert_eq!(o[0].id, "b");
        assert_eq!(o[1].id, "a");
    }

    #[test]
    fn pin_order_respected() {
        let mut s = WorkspaceSwitcher::new();
        s.add("a", "A").unwrap();
        s.add("b", "B").unwrap();
        s.add("c", "C").unwrap();
        s.pin("c", 0).unwrap();
        s.pin("a", 1).unwrap();
        let o = s.ordered_for_picker();
        assert_eq!(o[0].id, "c");
        assert_eq!(o[1].id, "a");
        assert_eq!(o[2].id, "b"); // unpinned
    }

    #[test]
    fn recents_descending() {
        let mut s = WorkspaceSwitcher::new();
        s.add("old", "Old").unwrap();
        s.add("new", "New").unwrap();
        s.switch_to("old", 100).unwrap();
        s.switch_to("new", 200).unwrap();
        let o = s.ordered_for_picker();
        assert_eq!(o[0].id, "new");
        assert_eq!(o[1].id, "old");
    }

    #[test]
    fn unpin_demotes() {
        let mut s = WorkspaceSwitcher::new();
        s.add("a", "A").unwrap();
        s.pin("a", 0).unwrap();
        s.unpin("a").unwrap();
        assert!(s.workspaces["a"].pin_order.is_none());
    }

    #[test]
    fn remove_clears_active() {
        let mut s = WorkspaceSwitcher::new();
        s.add("a", "A").unwrap();
        s.switch_to("a", 0).unwrap();
        assert!(s.remove("a"));
        assert!(s.active.is_none());
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = WorkspaceSwitcher::new();
        s.add("a", "A").unwrap();
        assert!(matches!(
            s.add("a", "A").unwrap_err(),
            SwitcherError::DuplicateId(_)
        ));
    }

    #[test]
    fn switch_unknown_rejected() {
        let mut s = WorkspaceSwitcher::new();
        assert!(matches!(
            s.switch_to("nope", 0).unwrap_err(),
            SwitcherError::UnknownWorkspace(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = WorkspaceSwitcher::new();
        assert!(matches!(
            s.add("", "X").unwrap_err(),
            SwitcherError::EmptyId
        ));
        assert!(matches!(
            s.add("a", "").unwrap_err(),
            SwitcherError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = WorkspaceSwitcher::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SwitcherError::SchemaMismatch
        ));
    }

    #[test]
    fn switcher_serde_roundtrip() {
        let mut s = WorkspaceSwitcher::new();
        s.add("a", "A").unwrap();
        s.switch_to("a", 100).unwrap();
        s.pin("a", 0).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: WorkspaceSwitcher = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
