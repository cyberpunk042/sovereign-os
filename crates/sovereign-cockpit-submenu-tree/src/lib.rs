//! `sovereign-cockpit-submenu-tree` — hierarchical menu tree.
//!
//! Each `Node { id, label, parent, children, enabled }`. The tree
//! is built incrementally via `add_root(...)` and `add_child(parent,
//! id, label)`. `set_expanded(id, bool)` / `toggle(id)` control
//! visual expansion. `activate(id)` records the currently-active
//! leaf and auto-expands ancestors.
//!
//! `visible_in_order()` yields visible nodes in depth-first display
//! order (only nodes whose ancestors are all expanded).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One node.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Node {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Parent id (None = root).
    pub parent: Option<String>,
    /// Ordered children.
    pub children: Vec<String>,
    /// Enabled.
    pub enabled: bool,
    /// Expanded?
    pub expanded: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SubmenuTree {
    /// Schema version.
    pub schema_version: String,
    /// id → node.
    pub nodes: BTreeMap<String, Node>,
    /// Root ids in order.
    pub roots: Vec<String>,
    /// Currently active id (if any).
    pub active: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TreeError {
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
    #[error("duplicate node id: {0}")]
    DuplicateId(String),
    /// Unknown parent.
    #[error("unknown parent: {0}")]
    UnknownParent(String),
    /// Unknown node.
    #[error("unknown node: {0}")]
    UnknownNode(String),
}

impl SubmenuTree {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            nodes: BTreeMap::new(),
            roots: Vec::new(),
            active: None,
        }
    }

    /// Add root.
    pub fn add_root(&mut self, id: &str, label: &str) -> Result<(), TreeError> {
        if id.is_empty() {
            return Err(TreeError::EmptyId);
        }
        if label.is_empty() {
            return Err(TreeError::EmptyLabel);
        }
        if self.nodes.contains_key(id) {
            return Err(TreeError::DuplicateId(id.into()));
        }
        self.nodes.insert(
            id.into(),
            Node {
                id: id.into(),
                label: label.into(),
                parent: None,
                children: Vec::new(),
                enabled: true,
                expanded: false,
            },
        );
        self.roots.push(id.into());
        Ok(())
    }

    /// Add child.
    pub fn add_child(&mut self, parent_id: &str, id: &str, label: &str) -> Result<(), TreeError> {
        if id.is_empty() {
            return Err(TreeError::EmptyId);
        }
        if label.is_empty() {
            return Err(TreeError::EmptyLabel);
        }
        if !self.nodes.contains_key(parent_id) {
            return Err(TreeError::UnknownParent(parent_id.into()));
        }
        if self.nodes.contains_key(id) {
            return Err(TreeError::DuplicateId(id.into()));
        }
        self.nodes.insert(
            id.into(),
            Node {
                id: id.into(),
                label: label.into(),
                parent: Some(parent_id.into()),
                children: Vec::new(),
                enabled: true,
                expanded: false,
            },
        );
        // Push into parent's children.
        if let Some(p) = self.nodes.get_mut(parent_id) {
            p.children.push(id.into());
        }
        Ok(())
    }

    /// Set expanded.
    pub fn set_expanded(&mut self, id: &str, expanded: bool) -> Result<(), TreeError> {
        let n = self
            .nodes
            .get_mut(id)
            .ok_or_else(|| TreeError::UnknownNode(id.into()))?;
        n.expanded = expanded;
        Ok(())
    }

    /// Toggle expanded.
    pub fn toggle(&mut self, id: &str) -> Result<bool, TreeError> {
        let n = self
            .nodes
            .get_mut(id)
            .ok_or_else(|| TreeError::UnknownNode(id.into()))?;
        n.expanded = !n.expanded;
        Ok(n.expanded)
    }

    /// Activate (auto-expands ancestors).
    pub fn activate(&mut self, id: &str) -> Result<(), TreeError> {
        if !self.nodes.contains_key(id) {
            return Err(TreeError::UnknownNode(id.into()));
        }
        // Walk up and expand.
        let mut ancestors: Vec<String> = Vec::new();
        let mut cur = self.nodes.get(id).and_then(|n| n.parent.clone());
        while let Some(pid) = cur {
            ancestors.push(pid.clone());
            cur = self.nodes.get(&pid).and_then(|n| n.parent.clone());
        }
        for a in &ancestors {
            if let Some(n) = self.nodes.get_mut(a) {
                n.expanded = true;
            }
        }
        self.active = Some(id.into());
        Ok(())
    }

    /// Set enabled.
    pub fn set_enabled(&mut self, id: &str, enabled: bool) -> Result<(), TreeError> {
        let n = self
            .nodes
            .get_mut(id)
            .ok_or_else(|| TreeError::UnknownNode(id.into()))?;
        n.enabled = enabled;
        Ok(())
    }

    /// Depth-first display order — only visible (ancestors expanded).
    pub fn visible_in_order(&self) -> Vec<String> {
        let mut out = Vec::new();
        for r in &self.roots {
            self.dfs_visible(r, &mut out);
        }
        out
    }

    fn dfs_visible(&self, id: &str, out: &mut Vec<String>) {
        let Some(n) = self.nodes.get(id) else {
            return;
        };
        out.push(id.into());
        if n.expanded {
            for c in &n.children {
                self.dfs_visible(c, out);
            }
        }
    }

    /// Path from root to node id.
    pub fn path_to(&self, id: &str) -> Vec<String> {
        let mut out: Vec<String> = Vec::new();
        let mut cur: Option<String> = Some(id.into());
        let mut seen: BTreeSet<String> = BTreeSet::new();
        while let Some(c) = cur {
            if !seen.insert(c.clone()) {
                break;
            }
            let Some(n) = self.nodes.get(&c) else {
                break;
            };
            out.push(c.clone());
            cur = n.parent.clone();
        }
        out.reverse();
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TreeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TreeError::SchemaMismatch);
        }
        for (id, n) in &self.nodes {
            if id.is_empty() {
                return Err(TreeError::EmptyId);
            }
            if n.label.is_empty() {
                return Err(TreeError::EmptyLabel);
            }
            if let Some(p) = &n.parent
                && !self.nodes.contains_key(p)
            {
                return Err(TreeError::UnknownParent(p.clone()));
            }
        }
        Ok(())
    }
}

impl Default for SubmenuTree {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn small_tree() -> SubmenuTree {
        let mut t = SubmenuTree::new();
        t.add_root("file", "File").unwrap();
        t.add_child("file", "open", "Open").unwrap();
        t.add_child("file", "save", "Save").unwrap();
        t.add_root("edit", "Edit").unwrap();
        t.add_child("edit", "copy", "Copy").unwrap();
        t
    }

    #[test]
    fn collapsed_only_roots_visible() {
        let t = small_tree();
        let v = t.visible_in_order();
        assert_eq!(v, vec!["file", "edit"]);
    }

    #[test]
    fn expanded_shows_children() {
        let mut t = small_tree();
        t.set_expanded("file", true).unwrap();
        let v = t.visible_in_order();
        assert_eq!(v, vec!["file", "open", "save", "edit"]);
    }

    #[test]
    fn activate_expands_ancestors() {
        let mut t = small_tree();
        t.activate("save").unwrap();
        let v = t.visible_in_order();
        assert!(v.contains(&"save".to_string()));
        assert_eq!(t.active.as_deref(), Some("save"));
        assert!(t.nodes["file"].expanded);
    }

    #[test]
    fn path_to_traces_ancestors() {
        let t = small_tree();
        assert_eq!(t.path_to("open"), vec!["file", "open"]);
        assert_eq!(t.path_to("file"), vec!["file"]);
    }

    #[test]
    fn toggle_flips() {
        let mut t = small_tree();
        assert!(t.toggle("file").unwrap());
        assert!(!t.toggle("file").unwrap());
    }

    #[test]
    fn duplicate_rejected() {
        let mut t = SubmenuTree::new();
        t.add_root("a", "A").unwrap();
        assert!(matches!(
            t.add_root("a", "A").unwrap_err(),
            TreeError::DuplicateId(_)
        ));
        assert!(matches!(
            t.add_child("a", "a", "A").unwrap_err(),
            TreeError::DuplicateId(_)
        ));
    }

    #[test]
    fn unknown_parent_rejected() {
        let mut t = SubmenuTree::new();
        assert!(matches!(
            t.add_child("nope", "x", "X").unwrap_err(),
            TreeError::UnknownParent(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut t = SubmenuTree::new();
        assert!(matches!(
            t.add_root("", "X").unwrap_err(),
            TreeError::EmptyId
        ));
        assert!(matches!(
            t.add_root("x", "").unwrap_err(),
            TreeError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = SubmenuTree::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            TreeError::SchemaMismatch
        ));
    }

    #[test]
    fn tree_serde_roundtrip() {
        let mut t = small_tree();
        t.activate("copy").unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: SubmenuTree = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
