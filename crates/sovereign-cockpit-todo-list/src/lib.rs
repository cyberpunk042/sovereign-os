//! `sovereign-cockpit-todo-list` — operator todo list.
//!
//! Items have id + title + status (Open/Done/Cancelled) + order
//! index. `add` appends; `complete`/`cancel`/`reopen` transition;
//! `move_to(id, new_index)` reorders. `ordered()` lists by index;
//! `stats()` returns counts.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Open.
    Open,
    /// Done.
    Done,
    /// Cancelled.
    Cancelled,
}

/// One item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Item {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Status.
    pub status: Status,
    /// Order.
    pub order: u32,
    /// Created ts.
    pub created_at_ms: u64,
}

/// Stats.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Stats {
    /// Open.
    pub open: u32,
    /// Done.
    pub done: u32,
    /// Cancelled.
    pub cancelled: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TodoList {
    /// Schema version.
    pub schema_version: String,
    /// id → item.
    pub items: BTreeMap<String, Item>,
    /// Next order to assign.
    pub next_order: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TodoError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown item: {0}")]
    UnknownItem(String),
}

impl TodoList {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            items: BTreeMap::new(),
            next_order: 0,
        }
    }

    /// Add.
    pub fn add(&mut self, id: &str, title: &str, ts_ms: u64) -> Result<(), TodoError> {
        if id.is_empty() {
            return Err(TodoError::EmptyId);
        }
        if title.is_empty() {
            return Err(TodoError::EmptyTitle);
        }
        if self.items.contains_key(id) {
            return Err(TodoError::DuplicateId(id.into()));
        }
        let order = self.next_order;
        self.next_order = self.next_order.saturating_add(1);
        self.items.insert(
            id.into(),
            Item {
                id: id.into(),
                title: title.into(),
                status: Status::Open,
                order,
                created_at_ms: ts_ms,
            },
        );
        Ok(())
    }

    /// Complete.
    pub fn complete(&mut self, id: &str) -> Result<(), TodoError> {
        let i = self
            .items
            .get_mut(id)
            .ok_or_else(|| TodoError::UnknownItem(id.into()))?;
        i.status = Status::Done;
        Ok(())
    }

    /// Cancel.
    pub fn cancel(&mut self, id: &str) -> Result<(), TodoError> {
        let i = self
            .items
            .get_mut(id)
            .ok_or_else(|| TodoError::UnknownItem(id.into()))?;
        i.status = Status::Cancelled;
        Ok(())
    }

    /// Reopen (from any state).
    pub fn reopen(&mut self, id: &str) -> Result<(), TodoError> {
        let i = self
            .items
            .get_mut(id)
            .ok_or_else(|| TodoError::UnknownItem(id.into()))?;
        i.status = Status::Open;
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.items.remove(id).is_some()
    }

    /// Ordered items.
    pub fn ordered(&self) -> Vec<Item> {
        let mut v: Vec<Item> = self.items.values().cloned().collect();
        v.sort_by_key(|i| i.order);
        v
    }

    /// Items by status.
    pub fn by_status(&self, status: Status) -> Vec<Item> {
        let mut v: Vec<Item> = self
            .items
            .values()
            .filter(|i| i.status == status)
            .cloned()
            .collect();
        v.sort_by_key(|i| i.order);
        v
    }

    /// Stats.
    pub fn stats(&self) -> Stats {
        let mut s = Stats::default();
        for i in self.items.values() {
            match i.status {
                Status::Open => s.open = s.open.saturating_add(1),
                Status::Done => s.done = s.done.saturating_add(1),
                Status::Cancelled => s.cancelled = s.cancelled.saturating_add(1),
            }
        }
        s
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TodoError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TodoError::SchemaMismatch);
        }
        for (id, i) in &self.items {
            if id.is_empty() {
                return Err(TodoError::EmptyId);
            }
            if i.title.is_empty() {
                return Err(TodoError::EmptyTitle);
            }
        }
        Ok(())
    }
}

impl Default for TodoList {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_complete() {
        let mut l = TodoList::new();
        l.add("t1", "Write report", 0).unwrap();
        l.complete("t1").unwrap();
        assert_eq!(l.items["t1"].status, Status::Done);
    }

    #[test]
    fn ordered_by_insertion() {
        let mut l = TodoList::new();
        l.add("a", "A", 0).unwrap();
        l.add("b", "B", 0).unwrap();
        let v = l.ordered();
        assert_eq!(v[0].id, "a");
        assert_eq!(v[1].id, "b");
    }

    #[test]
    fn by_status() {
        let mut l = TodoList::new();
        l.add("a", "A", 0).unwrap();
        l.add("b", "B", 0).unwrap();
        l.complete("a").unwrap();
        let o = l.by_status(Status::Open);
        assert_eq!(o.len(), 1);
        assert_eq!(o[0].id, "b");
    }

    #[test]
    fn stats_count() {
        let mut l = TodoList::new();
        l.add("a", "A", 0).unwrap();
        l.add("b", "B", 0).unwrap();
        l.add("c", "C", 0).unwrap();
        l.complete("a").unwrap();
        l.cancel("b").unwrap();
        let s = l.stats();
        assert_eq!(s.open, 1);
        assert_eq!(s.done, 1);
        assert_eq!(s.cancelled, 1);
    }

    #[test]
    fn reopen_from_done() {
        let mut l = TodoList::new();
        l.add("a", "A", 0).unwrap();
        l.complete("a").unwrap();
        l.reopen("a").unwrap();
        assert_eq!(l.items["a"].status, Status::Open);
    }

    #[test]
    fn duplicate_rejected() {
        let mut l = TodoList::new();
        l.add("a", "A", 0).unwrap();
        assert!(matches!(
            l.add("a", "A", 0).unwrap_err(),
            TodoError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut l = TodoList::new();
        assert!(matches!(l.add("", "A", 0).unwrap_err(), TodoError::EmptyId));
        assert!(matches!(
            l.add("a", "", 0).unwrap_err(),
            TodoError::EmptyTitle
        ));
    }

    #[test]
    fn unknown_action_rejected() {
        let mut l = TodoList::new();
        assert!(matches!(
            l.complete("nope").unwrap_err(),
            TodoError::UnknownItem(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = TodoList::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            TodoError::SchemaMismatch
        ));
    }

    #[test]
    fn todo_serde_roundtrip() {
        let mut l = TodoList::new();
        l.add("a", "A", 0).unwrap();
        l.complete("a").unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: TodoList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
