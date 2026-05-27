//! `sovereign-cockpit-tree-view` — hierarchical tree-view state.
//!
//! Holds a tree of nodes (id → optional parent_id) with per-node
//! `expanded` and a single-selection cursor. `visible_rows()`
//! projects parent → its visible descendants into a flat row list
//! suitable for direct virtualized rendering.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One node.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Node {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Parent id (None = root).
    pub parent_id: Option<String>,
    /// Expanded? (no effect on leaves)
    pub expanded: bool,
}

/// Flat visible row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct VisibleRow {
    /// Node id.
    pub id: String,
    /// Depth (root = 0).
    pub depth: u32,
    /// Has children?
    pub has_children: bool,
    /// Currently expanded?
    pub expanded: bool,
}

/// Tree-view state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TreeView {
    /// Schema version.
    pub schema_version: String,
    /// All nodes (order = render order among siblings).
    pub nodes: Vec<Node>,
    /// Single-selection cursor (id).
    pub selected: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TreeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("node id empty")]
    EmptyId,
    /// Empty label.
    #[error("node {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate node id: {0}")]
    DuplicateId(String),
    /// Unknown parent.
    #[error("node {child} references unknown parent {parent}")]
    UnknownParent {
        /// child.
        child: String,
        /// parent.
        parent: String,
    },
    /// Selection points at unknown id.
    #[error("selection {0} references unknown node")]
    UnknownSelection(String),
    /// Unknown id passed to operation.
    #[error("unknown node id: {0}")]
    Unknown(String),
    /// Cycle in parent chain.
    #[error("cycle detected involving node {0}")]
    Cycle(String),
}

impl TreeView {
    /// New tree from a node list.
    pub fn new(nodes: Vec<Node>) -> Result<Self, TreeError> {
        check_nodes(&nodes)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            nodes,
            selected: None,
        })
    }

    /// Expand a node.
    pub fn expand(&mut self, id: &str) -> Result<(), TreeError> {
        let n = self
            .nodes
            .iter_mut()
            .find(|n| n.id == id)
            .ok_or_else(|| TreeError::Unknown(id.into()))?;
        n.expanded = true;
        Ok(())
    }

    /// Collapse a node.
    pub fn collapse(&mut self, id: &str) -> Result<(), TreeError> {
        let n = self
            .nodes
            .iter_mut()
            .find(|n| n.id == id)
            .ok_or_else(|| TreeError::Unknown(id.into()))?;
        n.expanded = false;
        Ok(())
    }

    /// Select a node.
    pub fn select(&mut self, id: &str) -> Result<(), TreeError> {
        if !self.nodes.iter().any(|n| n.id == id) {
            return Err(TreeError::Unknown(id.into()));
        }
        self.selected = Some(id.into());
        Ok(())
    }

    /// Clear selection.
    pub fn clear_selection(&mut self) {
        self.selected = None;
    }

    /// Project to flat visible rows in DFS order.
    pub fn visible_rows(&self) -> Vec<VisibleRow> {
        let mut out: Vec<VisibleRow> = Vec::new();
        let roots: Vec<&Node> = self
            .nodes
            .iter()
            .filter(|n| n.parent_id.is_none())
            .collect();
        for r in roots {
            self.dfs(r, 0, &mut out);
        }
        out
    }

    fn dfs(&self, n: &Node, depth: u32, out: &mut Vec<VisibleRow>) {
        let children: Vec<&Node> = self
            .nodes
            .iter()
            .filter(|x| x.parent_id.as_deref() == Some(n.id.as_str()))
            .collect();
        out.push(VisibleRow {
            id: n.id.clone(),
            depth,
            has_children: !children.is_empty(),
            expanded: n.expanded,
        });
        if n.expanded {
            for c in children {
                self.dfs(c, depth + 1, out);
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TreeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TreeError::SchemaMismatch);
        }
        check_nodes(&self.nodes)?;
        if let Some(s) = &self.selected {
            if !self.nodes.iter().any(|n| &n.id == s) {
                return Err(TreeError::UnknownSelection(s.clone()));
            }
        }
        Ok(())
    }
}

fn check_nodes(nodes: &[Node]) -> Result<(), TreeError> {
    use std::collections::{HashMap, HashSet};
    let mut ids: HashSet<&str> = HashSet::new();
    let mut parents: HashMap<&str, Option<&str>> = HashMap::new();
    for n in nodes {
        if n.id.is_empty() {
            return Err(TreeError::EmptyId);
        }
        if n.label.is_empty() {
            return Err(TreeError::EmptyLabel(n.id.clone()));
        }
        if !ids.insert(n.id.as_str()) {
            return Err(TreeError::DuplicateId(n.id.clone()));
        }
        parents.insert(n.id.as_str(), n.parent_id.as_deref());
    }
    for n in nodes {
        if let Some(p) = &n.parent_id {
            if !ids.contains(p.as_str()) {
                return Err(TreeError::UnknownParent {
                    child: n.id.clone(),
                    parent: p.clone(),
                });
            }
        }
    }
    // Cycle detection: walk parent chain from each node; bail on revisit.
    for n in nodes {
        let mut seen: HashSet<&str> = HashSet::new();
        let mut cur = n.parent_id.as_deref();
        while let Some(c) = cur {
            if c == n.id.as_str() || !seen.insert(c) {
                return Err(TreeError::Cycle(n.id.clone()));
            }
            cur = parents.get(c).and_then(|p| *p);
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(id: &str, parent: Option<&str>, expanded: bool) -> Node {
        Node {
            id: id.into(),
            label: format!("L-{id}"),
            parent_id: parent.map(|s| s.into()),
            expanded,
        }
    }

    #[test]
    fn empty_validates() {
        TreeView::new(vec![]).unwrap().validate().unwrap();
    }

    #[test]
    fn single_root() {
        let t = TreeView::new(vec![node("a", None, false)]).unwrap();
        let rows = t.visible_rows();
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].depth, 0);
        assert!(!rows[0].has_children);
    }

    #[test]
    fn collapsed_hides_children() {
        let t = TreeView::new(vec![node("a", None, false), node("b", Some("a"), false)]).unwrap();
        assert_eq!(t.visible_rows().len(), 1);
    }

    #[test]
    fn expanded_shows_children() {
        let t = TreeView::new(vec![
            node("a", None, true),
            node("b", Some("a"), false),
            node("c", Some("a"), false),
        ])
        .unwrap();
        let rows = t.visible_rows();
        assert_eq!(rows.len(), 3);
        assert_eq!(rows[0].depth, 0);
        assert_eq!(rows[1].depth, 1);
        assert_eq!(rows[2].depth, 1);
    }

    #[test]
    fn deep_expansion_dfs_order() {
        let t = TreeView::new(vec![
            node("a", None, true),
            node("b", Some("a"), true),
            node("c", Some("b"), false),
            node("d", Some("a"), false),
        ])
        .unwrap();
        let rows = t.visible_rows();
        let ids: Vec<&str> = rows.iter().map(|r| r.id.as_str()).collect();
        assert_eq!(ids, vec!["a", "b", "c", "d"]);
    }

    #[test]
    fn expand_collapse() {
        let mut t =
            TreeView::new(vec![node("a", None, false), node("b", Some("a"), false)]).unwrap();
        t.expand("a").unwrap();
        assert_eq!(t.visible_rows().len(), 2);
        t.collapse("a").unwrap();
        assert_eq!(t.visible_rows().len(), 1);
    }

    #[test]
    fn select_and_clear() {
        let mut t = TreeView::new(vec![node("a", None, false)]).unwrap();
        t.select("a").unwrap();
        assert_eq!(t.selected.as_deref(), Some("a"));
        t.clear_selection();
        assert!(t.selected.is_none());
    }

    #[test]
    fn select_unknown_rejected() {
        let mut t = TreeView::new(vec![node("a", None, false)]).unwrap();
        assert!(matches!(t.select("z").unwrap_err(), TreeError::Unknown(_)));
    }

    #[test]
    fn unknown_parent_rejected() {
        assert!(matches!(
            TreeView::new(vec![node("a", Some("ghost"), false)]).unwrap_err(),
            TreeError::UnknownParent { .. }
        ));
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            TreeView::new(vec![node("a", None, false), node("a", None, false)]).unwrap_err(),
            TreeError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut n = node("a", None, false);
        n.id = String::new();
        assert!(matches!(
            TreeView::new(vec![n]).unwrap_err(),
            TreeError::EmptyId
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut n = node("a", None, false);
        n.label = String::new();
        assert!(matches!(
            TreeView::new(vec![n]).unwrap_err(),
            TreeError::EmptyLabel(_)
        ));
    }

    #[test]
    fn cycle_detected() {
        // a -> b -> a
        let nodes = vec![node("a", Some("b"), false), node("b", Some("a"), false)];
        assert!(matches!(
            TreeView::new(nodes).unwrap_err(),
            TreeError::Cycle(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TreeView::new(vec![node("a", None, false)]).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            TreeError::SchemaMismatch
        ));
    }

    #[test]
    fn tree_serde_roundtrip() {
        let t = TreeView::new(vec![node("a", None, true), node("b", Some("a"), false)]).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: TreeView = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
