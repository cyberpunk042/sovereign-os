//! `sovereign-cockpit-task-stack` — operator-task push/pop stack.
//!
//! `push(task)` adds; `pop()` removes and returns the popped task;
//! `current()` returns the top (active) task; `peek_below()` returns
//! the next-down task for breadcrumb-style display.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One task.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Task {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Started at.
    pub started_at_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TaskStack {
    /// Schema version.
    pub schema_version: String,
    /// Stack (top last).
    pub stack: Vec<Task>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StackError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("task id empty")]
    EmptyId,
    /// Empty label.
    #[error("task label empty")]
    EmptyLabel,
    /// Duplicate id in stack.
    #[error("duplicate task id: {0}")]
    DuplicateId(String),
}

impl TaskStack {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            stack: Vec::new(),
        }
    }

    /// Push.
    pub fn push(&mut self, task: Task) -> Result<(), StackError> {
        if task.id.is_empty() { return Err(StackError::EmptyId); }
        if task.label.is_empty() { return Err(StackError::EmptyLabel); }
        if self.stack.iter().any(|t| t.id == task.id) {
            return Err(StackError::DuplicateId(task.id));
        }
        self.stack.push(task);
        Ok(())
    }

    /// Pop top.
    pub fn pop(&mut self) -> Option<Task> { self.stack.pop() }

    /// Pop a specific task by id.
    pub fn pop_id(&mut self, id: &str) -> Option<Task> {
        if let Some(pos) = self.stack.iter().position(|t| t.id == id) {
            return Some(self.stack.remove(pos));
        }
        None
    }

    /// Current top.
    pub fn current(&self) -> Option<&Task> { self.stack.last() }

    /// Peek the one below the top.
    pub fn peek_below(&self) -> Option<&Task> {
        if self.stack.len() < 2 { return None; }
        self.stack.get(self.stack.len() - 2)
    }

    /// Depth.
    pub fn depth(&self) -> usize { self.stack.len() }

    /// Validate.
    pub fn validate(&self) -> Result<(), StackError> {
        if self.schema_version != SCHEMA_VERSION { return Err(StackError::SchemaMismatch); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.stack {
            if t.id.is_empty() { return Err(StackError::EmptyId); }
            if t.label.is_empty() { return Err(StackError::EmptyLabel); }
            if !seen.insert(t.id.as_str()) {
                return Err(StackError::DuplicateId(t.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for TaskStack {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn task(id: &str) -> Task {
        Task { id: id.into(), label: format!("Task {id}"), started_at_ms: 0 }
    }

    #[test]
    fn push_and_current() {
        let mut s = TaskStack::new();
        s.push(task("a")).unwrap();
        s.push(task("b")).unwrap();
        assert_eq!(s.current().unwrap().id, "b");
        assert_eq!(s.peek_below().unwrap().id, "a");
        assert_eq!(s.depth(), 2);
    }

    #[test]
    fn pop_returns_top() {
        let mut s = TaskStack::new();
        s.push(task("a")).unwrap();
        s.push(task("b")).unwrap();
        assert_eq!(s.pop().unwrap().id, "b");
        assert_eq!(s.current().unwrap().id, "a");
    }

    #[test]
    fn pop_id_specific() {
        let mut s = TaskStack::new();
        s.push(task("a")).unwrap();
        s.push(task("b")).unwrap();
        s.push(task("c")).unwrap();
        assert_eq!(s.pop_id("b").unwrap().id, "b");
        assert_eq!(s.depth(), 2);
        assert_eq!(s.current().unwrap().id, "c");
    }

    #[test]
    fn peek_below_none_when_one() {
        let mut s = TaskStack::new();
        s.push(task("a")).unwrap();
        assert!(s.peek_below().is_none());
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = TaskStack::new();
        s.push(task("a")).unwrap();
        assert!(matches!(s.push(task("a")).unwrap_err(), StackError::DuplicateId(_)));
    }

    #[test]
    fn empty_fields_rejected() {
        let mut s = TaskStack::new();
        let mut bad = task("a");
        bad.id = "".into();
        assert!(matches!(s.push(bad).unwrap_err(), StackError::EmptyId));
        let mut bad2 = task("a");
        bad2.label = "".into();
        assert!(matches!(s.push(bad2).unwrap_err(), StackError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = TaskStack::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), StackError::SchemaMismatch));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = TaskStack::new();
        s.push(task("a")).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: TaskStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
