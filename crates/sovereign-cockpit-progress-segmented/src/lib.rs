//! `sovereign-cockpit-progress-segmented` — N-segment pipeline progress.
//!
//! Ordered segments. `advance_to(id)` marks every earlier segment
//! `Completed` and the target `Active`. `complete(id)` marks the
//! target `Completed` (no implicit advance). `fail(id)` marks
//! `Failed`. `rewind(id)` resets the target and every later segment
//! to `Pending`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State of one segment.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// Not started.
    Pending,
    /// In progress.
    Active,
    /// Done.
    Completed,
    /// Failed.
    Failed,
}

/// One segment.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Segment {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Current state.
    pub state: State,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProgressSegmented {
    /// Schema version.
    pub schema_version: String,
    /// Ordered segments.
    pub segments: Vec<Segment>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SegError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("segment id empty")]
    EmptyId,
    /// Duplicate.
    #[error("duplicate segment id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown segment id: {0}")]
    UnknownId(String),
}

impl ProgressSegmented {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            segments: Vec::new(),
        }
    }

    /// Register a segment at the end.
    pub fn push(&mut self, id: &str, label: &str) -> Result<(), SegError> {
        if id.is_empty() { return Err(SegError::EmptyId); }
        if self.segments.iter().any(|s| s.id == id) {
            return Err(SegError::DuplicateId(id.into()));
        }
        self.segments.push(Segment { id: id.into(), label: label.into(), state: State::Pending });
        Ok(())
    }

    fn index_of(&self, id: &str) -> Option<usize> {
        self.segments.iter().position(|s| s.id == id)
    }

    /// Advance to segment, marking earlier as Completed.
    pub fn advance_to(&mut self, id: &str) -> Result<(), SegError> {
        let idx = self.index_of(id).ok_or_else(|| SegError::UnknownId(id.into()))?;
        for (i, s) in self.segments.iter_mut().enumerate() {
            if i < idx {
                if s.state != State::Failed { s.state = State::Completed; }
            } else if i == idx {
                s.state = State::Active;
            }
        }
        Ok(())
    }

    /// Complete a segment without changing later ones.
    pub fn complete(&mut self, id: &str) -> Result<(), SegError> {
        let idx = self.index_of(id).ok_or_else(|| SegError::UnknownId(id.into()))?;
        self.segments[idx].state = State::Completed;
        Ok(())
    }

    /// Fail a segment.
    pub fn fail(&mut self, id: &str) -> Result<(), SegError> {
        let idx = self.index_of(id).ok_or_else(|| SegError::UnknownId(id.into()))?;
        self.segments[idx].state = State::Failed;
        Ok(())
    }

    /// Rewind to segment, resetting it + later ones to Pending.
    pub fn rewind(&mut self, id: &str) -> Result<(), SegError> {
        let idx = self.index_of(id).ok_or_else(|| SegError::UnknownId(id.into()))?;
        for (i, s) in self.segments.iter_mut().enumerate() {
            if i >= idx { s.state = State::Pending; }
        }
        Ok(())
    }

    /// Percent complete = completed / total * 100.
    pub fn percent_complete(&self) -> u8 {
        if self.segments.is_empty() { return 0; }
        let n = self.segments.len() as u32;
        let done = self.segments.iter().filter(|s| s.state == State::Completed).count() as u32;
        ((done * 100) / n) as u8
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SegError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SegError::SchemaMismatch); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in &self.segments {
            if s.id.is_empty() { return Err(SegError::EmptyId); }
            if !seen.insert(s.id.as_str()) { return Err(SegError::DuplicateId(s.id.clone())); }
        }
        Ok(())
    }
}

impl Default for ProgressSegmented {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn three_step() -> ProgressSegmented {
        let mut p = ProgressSegmented::new();
        p.push("a", "A").unwrap();
        p.push("b", "B").unwrap();
        p.push("c", "C").unwrap();
        p
    }

    #[test]
    fn push_dedups() {
        let mut p = ProgressSegmented::new();
        p.push("a", "A").unwrap();
        assert!(matches!(p.push("a", "A").unwrap_err(), SegError::DuplicateId(_)));
    }

    #[test]
    fn advance_marks_earlier_completed() {
        let mut p = three_step();
        p.advance_to("c").unwrap();
        assert_eq!(p.segments[0].state, State::Completed);
        assert_eq!(p.segments[1].state, State::Completed);
        assert_eq!(p.segments[2].state, State::Active);
    }

    #[test]
    fn complete_only_target() {
        let mut p = three_step();
        p.complete("b").unwrap();
        assert_eq!(p.segments[0].state, State::Pending);
        assert_eq!(p.segments[1].state, State::Completed);
        assert_eq!(p.segments[2].state, State::Pending);
    }

    #[test]
    fn fail_marks_failed() {
        let mut p = three_step();
        p.fail("b").unwrap();
        assert_eq!(p.segments[1].state, State::Failed);
    }

    #[test]
    fn advance_preserves_failed() {
        let mut p = three_step();
        p.fail("a").unwrap();
        p.advance_to("c").unwrap();
        assert_eq!(p.segments[0].state, State::Failed);
    }

    #[test]
    fn rewind_resets_to_and_after() {
        let mut p = three_step();
        p.advance_to("c").unwrap();
        p.rewind("b").unwrap();
        assert_eq!(p.segments[0].state, State::Completed);
        assert_eq!(p.segments[1].state, State::Pending);
        assert_eq!(p.segments[2].state, State::Pending);
    }

    #[test]
    fn percent_complete() {
        let mut p = three_step();
        p.complete("a").unwrap();
        assert_eq!(p.percent_complete(), 33);
        p.complete("b").unwrap();
        assert_eq!(p.percent_complete(), 66);
        p.complete("c").unwrap();
        assert_eq!(p.percent_complete(), 100);
    }

    #[test]
    fn unknown_id_rejected() {
        let mut p = three_step();
        assert!(matches!(p.advance_to("nope").unwrap_err(), SegError::UnknownId(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut p = ProgressSegmented::new();
        assert!(matches!(p.push("", "X").unwrap_err(), SegError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = three_step();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), SegError::SchemaMismatch));
    }

    #[test]
    fn progress_serde_roundtrip() {
        let mut p = three_step();
        p.advance_to("b").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: ProgressSegmented = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
