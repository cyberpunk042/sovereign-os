//! `sovereign-cockpit-reorderable-list` — drag-to-reorder state.
//!
//! Maintains an ordered `Vec<String>` of stable ids and a transient
//! `drag` cursor `(from, over)`. The committed order is whatever the
//! `ids` vec currently is; visual previews during drag use `drag` to
//! offset rendering, but `commit_drop()` mutates `ids` to the final
//! state in one operation.
//!
//! `move_to(from, to)` is the non-gesture shorthand: clamps `to` to
//! the valid insertion range and shifts in O(n).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// In-flight drag.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct DragCursor {
    /// Source index when the drag started.
    pub from: usize,
    /// Current hover insertion index.
    pub over: usize,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReorderableList {
    /// Schema version.
    pub schema_version: String,
    /// Ordered ids.
    pub ids: Vec<String>,
    /// Active drag.
    pub drag: Option<DragCursor>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ReorderError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Out of bounds.
    #[error("index {0} out of bounds (len {1})")]
    OutOfBounds(usize, usize),
    /// No drag.
    #[error("no active drag")]
    NoDrag,
}

impl ReorderableList {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            ids: Vec::new(),
            drag: None,
        }
    }

    /// Append.
    pub fn push(&mut self, id: &str) -> Result<(), ReorderError> {
        if id.is_empty() {
            return Err(ReorderError::EmptyId);
        }
        if self.ids.iter().any(|x| x == id) {
            return Err(ReorderError::DuplicateId(id.into()));
        }
        self.ids.push(id.into());
        Ok(())
    }

    /// Begin drag.
    pub fn begin_drag(&mut self, from: usize) -> Result<(), ReorderError> {
        if from >= self.ids.len() {
            return Err(ReorderError::OutOfBounds(from, self.ids.len()));
        }
        self.drag = Some(DragCursor { from, over: from });
        Ok(())
    }

    /// Hover.
    pub fn hover(&mut self, over: usize) -> Result<(), ReorderError> {
        if over > self.ids.len() {
            return Err(ReorderError::OutOfBounds(over, self.ids.len()));
        }
        match self.drag {
            Some(d) => {
                self.drag = Some(DragCursor { from: d.from, over });
                Ok(())
            }
            None => Err(ReorderError::NoDrag),
        }
    }

    /// Commit drop. Returns the resulting (from, to) pair, with `to`
    /// adjusted for removal.
    pub fn commit_drop(&mut self) -> Result<(usize, usize), ReorderError> {
        let d = self.drag.take().ok_or(ReorderError::NoDrag)?;
        let from = d.from;
        let mut to = d.over;
        // Remove-then-insert: if to > from, the target shifts left by 1.
        if to > from {
            to -= 1;
        }
        if to >= self.ids.len() {
            to = self.ids.len() - 1;
        }
        let item = self.ids.remove(from);
        self.ids.insert(to, item);
        Ok((from, to))
    }

    /// Cancel drag.
    pub fn cancel_drag(&mut self) {
        self.drag = None;
    }

    /// Move directly.
    pub fn move_to(&mut self, from: usize, to: usize) -> Result<(), ReorderError> {
        if from >= self.ids.len() {
            return Err(ReorderError::OutOfBounds(from, self.ids.len()));
        }
        let mut to = to.min(self.ids.len().saturating_sub(1));
        let item = self.ids.remove(from);
        if to >= self.ids.len() {
            to = self.ids.len();
        }
        self.ids.insert(to, item);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ReorderError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ReorderError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for id in &self.ids {
            if id.is_empty() {
                return Err(ReorderError::EmptyId);
            }
            if !seen.insert(id.as_str()) {
                return Err(ReorderError::DuplicateId(id.clone()));
            }
        }
        if let Some(d) = self.drag {
            if d.from >= self.ids.len() {
                return Err(ReorderError::OutOfBounds(d.from, self.ids.len()));
            }
            if d.over > self.ids.len() {
                return Err(ReorderError::OutOfBounds(d.over, self.ids.len()));
            }
        }
        Ok(())
    }
}

impl Default for ReorderableList {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn list(items: &[&str]) -> ReorderableList {
        let mut l = ReorderableList::new();
        for x in items {
            l.push(x).unwrap();
        }
        l
    }

    #[test]
    fn push_dedups() {
        let mut l = ReorderableList::new();
        l.push("a").unwrap();
        assert!(matches!(
            l.push("a").unwrap_err(),
            ReorderError::DuplicateId(_)
        ));
    }

    #[test]
    fn begin_drag_oob_rejected() {
        let mut l = list(&["a", "b"]);
        assert!(matches!(
            l.begin_drag(9).unwrap_err(),
            ReorderError::OutOfBounds(_, _)
        ));
    }

    #[test]
    fn hover_without_drag_rejected() {
        let mut l = list(&["a"]);
        assert!(matches!(l.hover(0).unwrap_err(), ReorderError::NoDrag));
    }

    #[test]
    fn commit_drop_moves_forward() {
        let mut l = list(&["a", "b", "c"]);
        l.begin_drag(0).unwrap();
        l.hover(3).unwrap();
        let (f, t) = l.commit_drop().unwrap();
        assert_eq!((f, t), (0, 2));
        assert_eq!(l.ids, vec!["b", "c", "a"]);
    }

    #[test]
    fn commit_drop_moves_backward() {
        let mut l = list(&["a", "b", "c"]);
        l.begin_drag(2).unwrap();
        l.hover(0).unwrap();
        l.commit_drop().unwrap();
        assert_eq!(l.ids, vec!["c", "a", "b"]);
    }

    #[test]
    fn move_to_clamps() {
        let mut l = list(&["a", "b", "c"]);
        l.move_to(0, 99).unwrap();
        assert_eq!(l.ids, vec!["b", "c", "a"]);
    }

    #[test]
    fn cancel_drops_drag() {
        let mut l = list(&["a", "b"]);
        l.begin_drag(0).unwrap();
        l.cancel_drag();
        assert!(l.drag.is_none());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = ReorderableList::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            ReorderError::SchemaMismatch
        ));
    }

    #[test]
    fn list_serde_roundtrip() {
        let mut l = list(&["a", "b", "c"]);
        l.begin_drag(1).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: ReorderableList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
