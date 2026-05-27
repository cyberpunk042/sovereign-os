//! `sovereign-cockpit-workspace-state` — workspace layout snapshot.
//!
//! Pane{id, kind, scroll_y}. State{panes, active_pane, named_snapshots}.
//! save(name) clones the current panes+active into named_snapshots.
//! restore(name) replaces panes+active from the snapshot.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Pane.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pane {
    /// Stable id.
    pub id: String,
    /// Kind label (e.g. "log", "graph").
    pub kind: String,
    /// Scroll offset.
    pub scroll_y: u32,
}

/// Snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Snapshot {
    /// Panes.
    pub panes: Vec<Pane>,
    /// Active pane id (must reference a pane in the same snapshot).
    pub active_pane: Option<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkspaceState {
    /// Schema version.
    pub schema_version: String,
    /// Current panes.
    pub panes: Vec<Pane>,
    /// Active.
    pub active_pane: Option<String>,
    /// Named snapshots.
    pub named_snapshots: BTreeMap<String, Snapshot>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum WorkspaceError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty kind.
    #[error("kind empty")]
    EmptyKind,
    /// Duplicate pane id.
    #[error("duplicate pane id: {0}")]
    DuplicatePane(String),
    /// Unknown.
    #[error("unknown id: {0}")]
    Unknown(String),
    /// Snapshot not found.
    #[error("snapshot not found: {0}")]
    SnapshotMissing(String),
}

impl WorkspaceState {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            panes: Vec::new(),
            active_pane: None,
            named_snapshots: BTreeMap::new(),
        }
    }

    /// Add a pane.
    pub fn add_pane(&mut self, id: &str, kind: &str) -> Result<(), WorkspaceError> {
        if id.is_empty() {
            return Err(WorkspaceError::EmptyId);
        }
        if kind.is_empty() {
            return Err(WorkspaceError::EmptyKind);
        }
        if self.panes.iter().any(|p| p.id == id) {
            return Err(WorkspaceError::DuplicatePane(id.into()));
        }
        self.panes.push(Pane {
            id: id.into(),
            kind: kind.into(),
            scroll_y: 0,
        });
        Ok(())
    }

    /// Set active pane.
    pub fn set_active(&mut self, id: &str) -> Result<(), WorkspaceError> {
        if !self.panes.iter().any(|p| p.id == id) {
            return Err(WorkspaceError::Unknown(id.into()));
        }
        self.active_pane = Some(id.into());
        Ok(())
    }

    /// Set scroll for a pane.
    pub fn set_scroll(&mut self, id: &str, scroll_y: u32) -> Result<(), WorkspaceError> {
        let p = self
            .panes
            .iter_mut()
            .find(|p| p.id == id)
            .ok_or_else(|| WorkspaceError::Unknown(id.into()))?;
        p.scroll_y = scroll_y;
        Ok(())
    }

    /// Save a named snapshot.
    pub fn save(&mut self, name: &str) -> Result<(), WorkspaceError> {
        if name.is_empty() {
            return Err(WorkspaceError::EmptyId);
        }
        self.named_snapshots.insert(
            name.into(),
            Snapshot {
                panes: self.panes.clone(),
                active_pane: self.active_pane.clone(),
            },
        );
        Ok(())
    }

    /// Restore a named snapshot.
    pub fn restore(&mut self, name: &str) -> Result<(), WorkspaceError> {
        let snap = self
            .named_snapshots
            .get(name)
            .ok_or_else(|| WorkspaceError::SnapshotMissing(name.into()))?
            .clone();
        self.panes = snap.panes;
        self.active_pane = snap.active_pane;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), WorkspaceError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(WorkspaceError::SchemaMismatch);
        }
        for p in &self.panes {
            if p.id.is_empty() {
                return Err(WorkspaceError::EmptyId);
            }
            if p.kind.is_empty() {
                return Err(WorkspaceError::EmptyKind);
            }
        }
        if let Some(a) = &self.active_pane {
            if !self.panes.iter().any(|p| &p.id == a) {
                return Err(WorkspaceError::Unknown(a.clone()));
            }
        }
        Ok(())
    }
}

impl Default for WorkspaceState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_activate() {
        let mut w = WorkspaceState::new();
        w.add_pane("p1", "log").unwrap();
        w.add_pane("p2", "graph").unwrap();
        w.set_active("p2").unwrap();
        assert_eq!(w.active_pane.as_deref(), Some("p2"));
    }

    #[test]
    fn save_then_restore() {
        let mut w = WorkspaceState::new();
        w.add_pane("p1", "log").unwrap();
        w.set_scroll("p1", 100).unwrap();
        w.save("clean").unwrap();
        w.set_scroll("p1", 9999).unwrap();
        w.restore("clean").unwrap();
        assert_eq!(w.panes[0].scroll_y, 100);
    }

    #[test]
    fn restore_unknown_snapshot_rejected() {
        let mut w = WorkspaceState::new();
        assert!(matches!(
            w.restore("nope").unwrap_err(),
            WorkspaceError::SnapshotMissing(_)
        ));
    }

    #[test]
    fn duplicate_pane_rejected() {
        let mut w = WorkspaceState::new();
        w.add_pane("p1", "log").unwrap();
        assert!(matches!(
            w.add_pane("p1", "log").unwrap_err(),
            WorkspaceError::DuplicatePane(_)
        ));
    }

    #[test]
    fn unknown_pane_rejected() {
        let mut w = WorkspaceState::new();
        assert!(matches!(
            w.set_active("nope").unwrap_err(),
            WorkspaceError::Unknown(_)
        ));
        assert!(matches!(
            w.set_scroll("nope", 0).unwrap_err(),
            WorkspaceError::Unknown(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut w = WorkspaceState::new();
        assert!(matches!(
            w.add_pane("", "x").unwrap_err(),
            WorkspaceError::EmptyId
        ));
        assert!(matches!(
            w.add_pane("x", "").unwrap_err(),
            WorkspaceError::EmptyKind
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut w = WorkspaceState::new();
        w.schema_version = "9.9.9".into();
        assert!(matches!(
            w.validate().unwrap_err(),
            WorkspaceError::SchemaMismatch
        ));
    }

    #[test]
    fn workspace_serde_roundtrip() {
        let mut w = WorkspaceState::new();
        w.add_pane("p1", "log").unwrap();
        w.save("x").unwrap();
        let j = serde_json::to_string(&w).unwrap();
        let back: WorkspaceState = serde_json::from_str(&j).unwrap();
        assert_eq!(w, back);
    }
}
