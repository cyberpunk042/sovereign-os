//! `sovereign-cockpit-popover-stack` — popover z-stack with lineage.
//!
//! Popovers are pushed by id; each carries an optional parent_id
//! (for nested popovers). close(id) closes that popover AND all
//! children. escape() closes only the topmost popover.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One popover.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Popover {
    /// Stable id.
    pub id: String,
    /// Parent id (None = root).
    pub parent_id: Option<String>,
    /// Anchor x.
    pub anchor_x: i32,
    /// Anchor y.
    pub anchor_y: i32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PopoverStack {
    /// Schema version.
    pub schema_version: String,
    /// Stack (bottom→top).
    pub stack: Vec<Popover>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PopoverError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("popover id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate popover id: {0}")]
    DuplicateId(String),
    /// Unknown parent.
    #[error("popover {id} parent {parent} not in stack")]
    UnknownParent {
        /// id.
        id: String,
        /// parent.
        parent: String,
    },
}

impl PopoverStack {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            stack: Vec::new(),
        }
    }

    /// Push a popover.
    pub fn push(&mut self, p: Popover) -> Result<(), PopoverError> {
        if p.id.is_empty() { return Err(PopoverError::EmptyId); }
        if self.stack.iter().any(|x| x.id == p.id) {
            return Err(PopoverError::DuplicateId(p.id));
        }
        if let Some(parent_id) = &p.parent_id {
            if !self.stack.iter().any(|x| &x.id == parent_id) {
                return Err(PopoverError::UnknownParent { id: p.id.clone(), parent: parent_id.clone() });
            }
        }
        self.stack.push(p);
        Ok(())
    }

    /// Close a popover by id (also closes its descendants).
    pub fn close(&mut self, id: &str) {
        // Identify the subtree to remove.
        let mut to_remove: Vec<String> = vec![id.into()];
        let mut idx = 0;
        while idx < to_remove.len() {
            let parent_id = to_remove[idx].clone();
            for p in &self.stack {
                if p.parent_id.as_deref() == Some(parent_id.as_str()) && !to_remove.iter().any(|x| x == &p.id) {
                    to_remove.push(p.id.clone());
                }
            }
            idx += 1;
        }
        self.stack.retain(|p| !to_remove.iter().any(|x| x == &p.id));
    }

    /// Escape — close topmost popover (+ its descendants).
    pub fn escape(&mut self) {
        if let Some(top) = self.stack.last() {
            let id = top.id.clone();
            self.close(&id);
        }
    }

    /// Topmost popover.
    pub fn top(&self) -> Option<&Popover> {
        self.stack.last()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PopoverError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PopoverError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for p in &self.stack {
            if p.id.is_empty() { return Err(PopoverError::EmptyId); }
            if !seen.insert(p.id.as_str()) {
                return Err(PopoverError::DuplicateId(p.id.clone()));
            }
            if let Some(parent_id) = &p.parent_id {
                if !self.stack.iter().any(|x| &x.id == parent_id) {
                    return Err(PopoverError::UnknownParent {
                        id: p.id.clone(),
                        parent: parent_id.clone(),
                    });
                }
            }
        }
        Ok(())
    }
}

impl Default for PopoverStack {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pop(id: &str, parent: Option<&str>) -> Popover {
        Popover {
            id: id.into(),
            parent_id: parent.map(|s| s.into()),
            anchor_x: 0,
            anchor_y: 0,
        }
    }

    #[test]
    fn empty_top_none() {
        let s = PopoverStack::new();
        assert!(s.top().is_none());
    }

    #[test]
    fn push_top_is_last() {
        let mut s = PopoverStack::new();
        s.push(pop("a", None)).unwrap();
        s.push(pop("b", Some("a"))).unwrap();
        assert_eq!(s.top().unwrap().id, "b");
    }

    #[test]
    fn close_removes_descendants() {
        let mut s = PopoverStack::new();
        s.push(pop("a", None)).unwrap();
        s.push(pop("b", Some("a"))).unwrap();
        s.push(pop("c", Some("b"))).unwrap();
        s.close("a");
        assert!(s.stack.is_empty());
    }

    #[test]
    fn close_only_subtree() {
        let mut s = PopoverStack::new();
        s.push(pop("root1", None)).unwrap();
        s.push(pop("root2", None)).unwrap();
        s.push(pop("child2", Some("root2"))).unwrap();
        s.close("root2");
        assert_eq!(s.stack.len(), 1);
        assert_eq!(s.stack[0].id, "root1");
    }

    #[test]
    fn escape_closes_top() {
        let mut s = PopoverStack::new();
        s.push(pop("a", None)).unwrap();
        s.push(pop("b", Some("a"))).unwrap();
        s.escape();
        assert_eq!(s.stack.len(), 1);
        assert_eq!(s.stack[0].id, "a");
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = PopoverStack::new();
        s.push(pop("a", None)).unwrap();
        assert!(matches!(s.push(pop("a", None)).unwrap_err(), PopoverError::DuplicateId(_)));
    }

    #[test]
    fn unknown_parent_rejected() {
        let mut s = PopoverStack::new();
        assert!(matches!(
            s.push(pop("a", Some("ghost"))).unwrap_err(),
            PopoverError::UnknownParent { .. }
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = PopoverStack::new();
        assert!(matches!(s.push(pop("", None)).unwrap_err(), PopoverError::EmptyId));
    }

    #[test]
    fn close_nonexistent_noop() {
        let mut s = PopoverStack::new();
        s.push(pop("a", None)).unwrap();
        s.close("ghost");
        assert_eq!(s.stack.len(), 1);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = PopoverStack::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), PopoverError::SchemaMismatch));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = PopoverStack::new();
        s.push(pop("a", None)).unwrap();
        s.push(pop("b", Some("a"))).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: PopoverStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
