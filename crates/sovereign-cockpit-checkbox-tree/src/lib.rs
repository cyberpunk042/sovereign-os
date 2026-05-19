//! `sovereign-cockpit-checkbox-tree` — tri-state checkbox tree.
//!
//! Each node has Checked / Unchecked / Indeterminate. Toggling a
//! parent sets all descendants to Checked or Unchecked (whichever
//! the parent moves to). Parents whose children are mixed are
//! reported as Indeterminate. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Tri-state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CheckState {
    /// Unchecked.
    Unchecked,
    /// Checked.
    Checked,
    /// Mixed (derived).
    Indeterminate,
}

/// One node.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CheckNode {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Parent id (None = root).
    pub parent_id: Option<String>,
    /// Stored leaf state (Checked or Unchecked only). For non-leaves
    /// this is ignored; compute_state() returns the derived value.
    pub leaf_state: CheckState,
}

/// Tree envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CheckboxTree {
    /// Schema version.
    pub schema_version: String,
    /// Nodes.
    pub nodes: Vec<CheckNode>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CheckTreeError {
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
    #[error("unknown parent {parent} for {child}")]
    UnknownParent {
        /// child.
        child: String,
        /// parent.
        parent: String,
    },
    /// Leaf state Indeterminate (only valid as derived).
    #[error("node {0} stored leaf_state Indeterminate (not allowed)")]
    LeafIndeterminate(String),
    /// Unknown id.
    #[error("unknown node id: {0}")]
    Unknown(String),
}

impl CheckboxTree {
    /// New tree.
    pub fn new(nodes: Vec<CheckNode>) -> Result<Self, CheckTreeError> {
        check_nodes(&nodes)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            nodes,
        })
    }

    /// Children of a node id.
    fn children(&self, id: &str) -> Vec<&CheckNode> {
        self.nodes.iter().filter(|n| n.parent_id.as_deref() == Some(id)).collect()
    }

    /// Is `id` a leaf? (No children registered.)
    pub fn is_leaf(&self, id: &str) -> bool {
        !self.nodes.iter().any(|n| n.parent_id.as_deref() == Some(id))
    }

    /// Compute the effective state.
    pub fn compute_state(&self, id: &str) -> Option<CheckState> {
        let node = self.nodes.iter().find(|n| n.id == id)?;
        if self.is_leaf(id) {
            return Some(node.leaf_state);
        }
        let kids = self.children(id);
        let mut any_checked = false;
        let mut any_unchecked = false;
        for k in &kids {
            match self.compute_state(&k.id) {
                Some(CheckState::Checked) => any_checked = true,
                Some(CheckState::Unchecked) => any_unchecked = true,
                Some(CheckState::Indeterminate) => return Some(CheckState::Indeterminate),
                None => {}
            }
        }
        Some(match (any_checked, any_unchecked) {
            (true, true) => CheckState::Indeterminate,
            (true, false) => CheckState::Checked,
            (false, true) => CheckState::Unchecked,
            (false, false) => CheckState::Unchecked,
        })
    }

    /// Toggle a node. Computes current state via compute_state; flips
    /// Checked ↔ Unchecked (Indeterminate becomes Checked). For
    /// non-leaves, the target state propagates to all descendants.
    pub fn toggle(&mut self, id: &str) -> Result<CheckState, CheckTreeError> {
        let cur = self.compute_state(id)
            .ok_or_else(|| CheckTreeError::Unknown(id.into()))?;
        let target = match cur {
            CheckState::Checked => CheckState::Unchecked,
            CheckState::Unchecked | CheckState::Indeterminate => CheckState::Checked,
        };
        self.set_subtree(id, target);
        Ok(target)
    }

    /// Recursively set leaf_state on all descendants (and on the node
    /// itself if it's a leaf).
    fn set_subtree(&mut self, id: &str, state: CheckState) {
        if self.is_leaf(id) {
            if let Some(n) = self.nodes.iter_mut().find(|n| n.id == id) {
                n.leaf_state = state;
            }
            return;
        }
        let child_ids: Vec<String> = self.children(id).iter().map(|n| n.id.clone()).collect();
        for c in child_ids {
            self.set_subtree(&c, state);
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CheckTreeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CheckTreeError::SchemaMismatch);
        }
        check_nodes(&self.nodes)?;
        for n in &self.nodes {
            if self.is_leaf(&n.id) && n.leaf_state == CheckState::Indeterminate {
                return Err(CheckTreeError::LeafIndeterminate(n.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_nodes(nodes: &[CheckNode]) -> Result<(), CheckTreeError> {
    use std::collections::HashSet;
    let mut ids: HashSet<&str> = HashSet::new();
    for n in nodes {
        if n.id.is_empty() { return Err(CheckTreeError::EmptyId); }
        if n.label.is_empty() { return Err(CheckTreeError::EmptyLabel(n.id.clone())); }
        if !ids.insert(n.id.as_str()) { return Err(CheckTreeError::DuplicateId(n.id.clone())); }
    }
    for n in nodes {
        if let Some(p) = &n.parent_id {
            if !ids.contains(p.as_str()) {
                return Err(CheckTreeError::UnknownParent { child: n.id.clone(), parent: p.clone() });
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(id: &str, parent: Option<&str>, st: CheckState) -> CheckNode {
        CheckNode {
            id: id.into(),
            label: format!("L-{id}"),
            parent_id: parent.map(|s| s.into()),
            leaf_state: st,
        }
    }

    fn tree() -> CheckboxTree {
        CheckboxTree::new(vec![
            node("root", None, CheckState::Unchecked),
            node("a", Some("root"), CheckState::Unchecked),
            node("b", Some("root"), CheckState::Unchecked),
            node("a1", Some("a"), CheckState::Unchecked),
            node("a2", Some("a"), CheckState::Unchecked),
        ]).unwrap()
    }

    #[test]
    fn all_unchecked_returns_unchecked() {
        let t = tree();
        assert_eq!(t.compute_state("root"), Some(CheckState::Unchecked));
    }

    #[test]
    fn toggle_root_checks_all_leaves() {
        let mut t = tree();
        assert_eq!(t.toggle("root").unwrap(), CheckState::Checked);
        assert_eq!(t.compute_state("a1"), Some(CheckState::Checked));
        assert_eq!(t.compute_state("a2"), Some(CheckState::Checked));
        assert_eq!(t.compute_state("b"), Some(CheckState::Checked));
    }

    #[test]
    fn toggle_leaf_only_flips_leaf() {
        let mut t = tree();
        assert_eq!(t.toggle("a1").unwrap(), CheckState::Checked);
        assert_eq!(t.compute_state("a1"), Some(CheckState::Checked));
        assert_eq!(t.compute_state("a2"), Some(CheckState::Unchecked));
        assert_eq!(t.compute_state("a"), Some(CheckState::Indeterminate));
        assert_eq!(t.compute_state("root"), Some(CheckState::Indeterminate));
    }

    #[test]
    fn toggle_indeterminate_goes_checked() {
        let mut t = tree();
        t.toggle("a1").unwrap();
        // root is Indeterminate now; toggle root.
        assert_eq!(t.toggle("root").unwrap(), CheckState::Checked);
        assert_eq!(t.compute_state("a2"), Some(CheckState::Checked));
    }

    #[test]
    fn toggle_checked_root_unchecks_all() {
        let mut t = tree();
        t.toggle("root").unwrap();
        assert_eq!(t.toggle("root").unwrap(), CheckState::Unchecked);
        assert_eq!(t.compute_state("a1"), Some(CheckState::Unchecked));
    }

    #[test]
    fn is_leaf_correct() {
        let t = tree();
        assert!(!t.is_leaf("root"));
        assert!(!t.is_leaf("a"));
        assert!(t.is_leaf("a1"));
        assert!(t.is_leaf("b"));
    }

    #[test]
    fn unknown_parent_rejected() {
        assert!(matches!(
            CheckboxTree::new(vec![node("a", Some("ghost"), CheckState::Unchecked)]).unwrap_err(),
            CheckTreeError::UnknownParent { .. }
        ));
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            CheckboxTree::new(vec![
                node("a", None, CheckState::Unchecked),
                node("a", None, CheckState::Unchecked),
            ]).unwrap_err(),
            CheckTreeError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut n = node("a", None, CheckState::Unchecked);
        n.id = String::new();
        assert!(matches!(CheckboxTree::new(vec![n]).unwrap_err(), CheckTreeError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut n = node("a", None, CheckState::Unchecked);
        n.label = String::new();
        assert!(matches!(CheckboxTree::new(vec![n]).unwrap_err(), CheckTreeError::EmptyLabel(_)));
    }

    #[test]
    fn leaf_indeterminate_rejected_on_validate() {
        let t = CheckboxTree::new(vec![
            node("leaf", None, CheckState::Indeterminate),
        ]).unwrap();
        assert!(matches!(t.validate().unwrap_err(), CheckTreeError::LeafIndeterminate(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = tree();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), CheckTreeError::SchemaMismatch));
    }

    #[test]
    fn state_serde_kebab() {
        assert_eq!(serde_json::to_string(&CheckState::Indeterminate).unwrap(), "\"indeterminate\"");
        assert_eq!(serde_json::to_string(&CheckState::Unchecked).unwrap(), "\"unchecked\"");
    }

    #[test]
    fn tree_serde_roundtrip() {
        let t = tree();
        let j = serde_json::to_string(&t).unwrap();
        let back: CheckboxTree = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
