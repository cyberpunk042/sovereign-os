//! `sovereign-cockpit-day-schedule` — single-day blocks.
//!
//! Block{id, start_min, end_min, label}. add rejects 0..=1440
//! out-of-range, start>=end, and overlaps with existing. remove
//! drops; blocks_sorted yields ascending start_min.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Block.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Block {
    /// Id.
    pub id: String,
    /// Start minute of day [0..1440).
    pub start_min: u32,
    /// End minute (exclusive) [0..=1440].
    pub end_min: u32,
    /// Label.
    pub label: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DaySchedule {
    /// Schema version.
    pub schema_version: String,
    /// id → block.
    pub blocks: BTreeMap<String, Block>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ScheduleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Bad range.
    #[error("invalid time range")]
    BadRange,
    /// Conflict.
    #[error("conflicts with block: {0}")]
    Conflict(String),
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl DaySchedule {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            blocks: BTreeMap::new(),
        }
    }

    fn overlaps(a_start: u32, a_end: u32, b_start: u32, b_end: u32) -> bool {
        a_start < b_end && b_start < a_end
    }

    /// Add block.
    pub fn add(
        &mut self,
        id: &str,
        start_min: u32,
        end_min: u32,
        label: &str,
    ) -> Result<(), ScheduleError> {
        if id.is_empty() {
            return Err(ScheduleError::EmptyId);
        }
        if label.is_empty() {
            return Err(ScheduleError::EmptyLabel);
        }
        if start_min >= end_min || end_min > 1440 || start_min >= 1440 {
            return Err(ScheduleError::BadRange);
        }
        if self.blocks.contains_key(id) {
            return Err(ScheduleError::DuplicateId(id.into()));
        }
        for (other_id, other) in &self.blocks {
            if Self::overlaps(start_min, end_min, other.start_min, other.end_min) {
                return Err(ScheduleError::Conflict(other_id.clone()));
            }
        }
        self.blocks.insert(
            id.into(),
            Block {
                id: id.into(),
                start_min,
                end_min,
                label: label.into(),
            },
        );
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.blocks.remove(id).is_some()
    }

    /// Blocks sorted by start_min asc.
    pub fn blocks_sorted(&self) -> Vec<&Block> {
        let mut all: Vec<&Block> = self.blocks.values().collect();
        all.sort_by_key(|b| b.start_min);
        all
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ScheduleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ScheduleError::SchemaMismatch);
        }
        for (id, b) in &self.blocks {
            if id.is_empty() {
                return Err(ScheduleError::EmptyId);
            }
            if b.label.is_empty() {
                return Err(ScheduleError::EmptyLabel);
            }
            if b.start_min >= b.end_min || b.end_min > 1440 {
                return Err(ScheduleError::BadRange);
            }
        }
        Ok(())
    }
}

impl Default for DaySchedule {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_disjoint() {
        let mut s = DaySchedule::new();
        s.add("a", 60, 120, "Morning").unwrap();
        s.add("b", 600, 660, "Lunch").unwrap();
        assert_eq!(s.blocks.len(), 2);
    }

    #[test]
    fn add_overlap_rejected() {
        let mut s = DaySchedule::new();
        s.add("a", 60, 120, "x").unwrap();
        assert!(matches!(
            s.add("b", 100, 150, "y").unwrap_err(),
            ScheduleError::Conflict(_)
        ));
    }

    #[test]
    fn edge_touch_allowed() {
        let mut s = DaySchedule::new();
        s.add("a", 60, 120, "x").unwrap();
        s.add("b", 120, 180, "y").unwrap();
        assert_eq!(s.blocks.len(), 2);
    }

    #[test]
    fn sorted_by_start() {
        let mut s = DaySchedule::new();
        s.add("c", 600, 660, "c").unwrap();
        s.add("a", 60, 120, "a").unwrap();
        s.add("b", 300, 360, "b").unwrap();
        let order: Vec<&str> = s.blocks_sorted().iter().map(|b| b.id.as_str()).collect();
        assert_eq!(order, vec!["a", "b", "c"]);
    }

    #[test]
    fn bad_range_rejected() {
        let mut s = DaySchedule::new();
        assert!(matches!(
            s.add("a", 100, 50, "x").unwrap_err(),
            ScheduleError::BadRange
        ));
        assert!(matches!(
            s.add("a", 100, 1500, "x").unwrap_err(),
            ScheduleError::BadRange
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = DaySchedule::new();
        assert!(matches!(
            s.add("", 60, 120, "x").unwrap_err(),
            ScheduleError::EmptyId
        ));
        assert!(matches!(
            s.add("i", 60, 120, "").unwrap_err(),
            ScheduleError::EmptyLabel
        ));
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut s = DaySchedule::new();
        s.add("a", 60, 120, "x").unwrap();
        assert!(matches!(
            s.add("a", 200, 300, "y").unwrap_err(),
            ScheduleError::DuplicateId(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = DaySchedule::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            ScheduleError::SchemaMismatch
        ));
    }

    #[test]
    fn schedule_serde_roundtrip() {
        let mut s = DaySchedule::new();
        s.add("a", 60, 120, "x").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: DaySchedule = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
