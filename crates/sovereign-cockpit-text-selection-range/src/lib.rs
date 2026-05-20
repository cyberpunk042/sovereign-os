//! `sovereign-cockpit-text-selection-range` — multi-range selection.
//!
//! Text in a single document is selected by half-open `[start, end)`
//! byte offsets. Multiple disjoint ranges may exist (e.g. shift+
//! click extends; Ctrl+drag adds a non-adjacent range). `add(start,
//! end)` normalizes (start < end) and merges with any overlapping
//! existing range; `remove_overlap(start, end)` clips ranges
//! intersecting the given window; `total_selected()` reports the
//! sum of selected byte counts.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One half-open range [start, end).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct Range {
    /// Inclusive start.
    pub start: u64,
    /// Exclusive end.
    pub end: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TextSelectionRange {
    /// Schema version.
    pub schema_version: String,
    /// Disjoint, sorted ranges.
    pub ranges: Vec<Range>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SelectionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty range.
    #[error("range start({start}) >= end({end})")]
    EmptyRange {
        /// start.
        start: u64,
        /// end.
        end: u64,
    },
}

impl TextSelectionRange {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            ranges: Vec::new(),
        }
    }

    /// Add (merging with overlapping/adjacent).
    pub fn add(&mut self, start: u64, end: u64) -> Result<(), SelectionError> {
        if start >= end { return Err(SelectionError::EmptyRange { start, end }); }
        let mut new = Range { start, end };
        // Merge with any overlapping or adjacent ranges (adjacent = touching).
        let mut kept = Vec::with_capacity(self.ranges.len() + 1);
        for r in self.ranges.drain(..) {
            if r.end < new.start || r.start > new.end {
                kept.push(r);
            } else {
                new.start = new.start.min(r.start);
                new.end = new.end.max(r.end);
            }
        }
        kept.push(new);
        kept.sort();
        self.ranges = kept;
        Ok(())
    }

    /// Remove portions of existing ranges that overlap [start, end).
    pub fn remove_overlap(&mut self, start: u64, end: u64) -> Result<(), SelectionError> {
        if start >= end { return Err(SelectionError::EmptyRange { start, end }); }
        let mut out = Vec::new();
        for r in self.ranges.drain(..) {
            if r.end <= start || r.start >= end {
                out.push(r); // disjoint
            } else {
                if r.start < start {
                    out.push(Range { start: r.start, end: start });
                }
                if r.end > end {
                    out.push(Range { start: end, end: r.end });
                }
            }
        }
        out.sort();
        self.ranges = out;
        Ok(())
    }

    /// Clear all.
    pub fn clear(&mut self) {
        self.ranges.clear();
    }

    /// Total bytes selected.
    pub fn total_selected(&self) -> u64 {
        self.ranges.iter().map(|r| r.end - r.start).sum()
    }

    /// Is the offset inside a selected range?
    pub fn contains(&self, offset: u64) -> bool {
        self.ranges.iter().any(|r| offset >= r.start && offset < r.end)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SelectionError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SelectionError::SchemaMismatch); }
        for r in &self.ranges {
            if r.start >= r.end {
                return Err(SelectionError::EmptyRange { start: r.start, end: r.end });
            }
        }
        Ok(())
    }
}

impl Default for TextSelectionRange {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_single() {
        let mut s = TextSelectionRange::new();
        s.add(10, 20).unwrap();
        assert_eq!(s.ranges, vec![Range { start: 10, end: 20 }]);
    }

    #[test]
    fn add_disjoint() {
        let mut s = TextSelectionRange::new();
        s.add(10, 20).unwrap();
        s.add(30, 40).unwrap();
        assert_eq!(s.ranges.len(), 2);
    }

    #[test]
    fn add_overlap_merges() {
        let mut s = TextSelectionRange::new();
        s.add(10, 20).unwrap();
        s.add(15, 25).unwrap();
        assert_eq!(s.ranges, vec![Range { start: 10, end: 25 }]);
    }

    #[test]
    fn add_adjacent_merges() {
        let mut s = TextSelectionRange::new();
        s.add(10, 20).unwrap();
        s.add(20, 30).unwrap();
        assert_eq!(s.ranges, vec![Range { start: 10, end: 30 }]);
    }

    #[test]
    fn add_chains_merge() {
        let mut s = TextSelectionRange::new();
        s.add(0, 10).unwrap();
        s.add(20, 30).unwrap();
        s.add(5, 25).unwrap();
        // All three merge.
        assert_eq!(s.ranges, vec![Range { start: 0, end: 30 }]);
    }

    #[test]
    fn remove_overlap_splits() {
        let mut s = TextSelectionRange::new();
        s.add(0, 100).unwrap();
        s.remove_overlap(40, 60).unwrap();
        assert_eq!(s.ranges, vec![
            Range { start: 0, end: 40 },
            Range { start: 60, end: 100 },
        ]);
    }

    #[test]
    fn remove_overlap_outside_noop() {
        let mut s = TextSelectionRange::new();
        s.add(0, 10).unwrap();
        s.remove_overlap(100, 200).unwrap();
        assert_eq!(s.ranges.len(), 1);
    }

    #[test]
    fn contains_works() {
        let mut s = TextSelectionRange::new();
        s.add(5, 10).unwrap();
        assert!(s.contains(5));
        assert!(s.contains(9));
        assert!(!s.contains(10)); // exclusive
        assert!(!s.contains(4));
    }

    #[test]
    fn total_selected() {
        let mut s = TextSelectionRange::new();
        s.add(0, 10).unwrap();
        s.add(20, 25).unwrap();
        assert_eq!(s.total_selected(), 15);
    }

    #[test]
    fn empty_range_rejected() {
        let mut s = TextSelectionRange::new();
        assert!(matches!(s.add(10, 10).unwrap_err(), SelectionError::EmptyRange { .. }));
        assert!(matches!(s.add(20, 10).unwrap_err(), SelectionError::EmptyRange { .. }));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = TextSelectionRange::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SelectionError::SchemaMismatch));
    }

    #[test]
    fn selection_serde_roundtrip() {
        let mut s = TextSelectionRange::new();
        s.add(0, 10).unwrap();
        s.add(20, 30).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: TextSelectionRange = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
