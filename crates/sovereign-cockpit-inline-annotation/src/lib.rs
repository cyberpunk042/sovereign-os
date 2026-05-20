//! `sovereign-cockpit-inline-annotation` — sticky text annotations.
//!
//! Annotation{id, start, end, body}. apply_insert(pos, len)
//! shifts annotations whose start>=pos by +len; end>=pos by
//! +len. apply_delete(pos, len) clamps/removes overlapping
//! annotations.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Annotation.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Annotation {
    /// Id.
    pub id: String,
    /// Start char offset.
    pub start: u32,
    /// End char offset (exclusive).
    pub end: u32,
    /// Body text.
    pub body: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InlineAnnotations {
    /// Schema version.
    pub schema_version: String,
    /// id → annotation.
    pub annotations: BTreeMap<String, Annotation>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AnnotationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("body empty")]
    EmptyBody,
    /// Bad range.
    #[error("start must be < end")]
    BadRange,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl InlineAnnotations {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            annotations: BTreeMap::new(),
        }
    }

    /// Add.
    pub fn add(&mut self, id: &str, start: u32, end: u32, body: &str) -> Result<(), AnnotationError> {
        if id.is_empty() { return Err(AnnotationError::EmptyId); }
        if body.is_empty() { return Err(AnnotationError::EmptyBody); }
        if start >= end { return Err(AnnotationError::BadRange); }
        if self.annotations.contains_key(id) {
            return Err(AnnotationError::DuplicateId(id.into()));
        }
        self.annotations.insert(id.into(), Annotation {
            id: id.into(),
            start,
            end,
            body: body.into(),
        });
        Ok(())
    }

    /// Apply text insertion of `len` chars at `pos`.
    pub fn apply_insert(&mut self, pos: u32, len: u32) {
        for a in self.annotations.values_mut() {
            if a.start >= pos { a.start = a.start.saturating_add(len); }
            if a.end >= pos { a.end = a.end.saturating_add(len); }
        }
    }

    /// Apply text deletion of `len` chars at `pos`. Annotations fully
    /// inside the deleted range are removed; partially overlapping
    /// ones are clamped.
    pub fn apply_delete(&mut self, pos: u32, len: u32) {
        let cut_end = pos.saturating_add(len);
        let mut to_remove: Vec<String> = Vec::new();
        for (id, a) in self.annotations.iter_mut() {
            // Fully inside [pos, cut_end] → remove.
            if a.start >= pos && a.end <= cut_end {
                to_remove.push(id.clone());
                continue;
            }
            // Shift down anything after cut.
            if a.start >= cut_end {
                a.start = a.start.saturating_sub(len);
                a.end = a.end.saturating_sub(len);
                continue;
            }
            // Partial overlap: clamp.
            if a.end > pos && a.end <= cut_end {
                a.end = pos;
            }
            if a.start >= pos && a.start < cut_end {
                a.start = pos;
            }
            if a.end > cut_end {
                // End extends past delete window — shift end back by len.
                a.end = a.end.saturating_sub(len);
            }
            // Drop if degenerate.
            if a.start >= a.end {
                to_remove.push(id.clone());
            }
        }
        for id in to_remove { self.annotations.remove(&id); }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AnnotationError> {
        if self.schema_version != SCHEMA_VERSION { return Err(AnnotationError::SchemaMismatch); }
        for (id, a) in &self.annotations {
            if id.is_empty() { return Err(AnnotationError::EmptyId); }
            if a.body.is_empty() { return Err(AnnotationError::EmptyBody); }
            if a.start >= a.end { return Err(AnnotationError::BadRange); }
        }
        Ok(())
    }
}

impl Default for InlineAnnotations {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_insert_shifts() {
        let mut a = InlineAnnotations::new();
        a.add("ann1", 10, 20, "comment").unwrap();
        a.apply_insert(5, 3);
        let ann = a.annotations.get("ann1").unwrap();
        assert_eq!(ann.start, 13);
        assert_eq!(ann.end, 23);
    }

    #[test]
    fn insert_after_does_not_shift() {
        let mut a = InlineAnnotations::new();
        a.add("ann1", 10, 20, "c").unwrap();
        a.apply_insert(30, 5);
        let ann = a.annotations.get("ann1").unwrap();
        assert_eq!(ann.start, 10);
        assert_eq!(ann.end, 20);
    }

    #[test]
    fn delete_fully_inside_removes() {
        let mut a = InlineAnnotations::new();
        a.add("ann1", 10, 20, "c").unwrap();
        a.apply_delete(5, 25); // covers 5..30
        assert!(a.annotations.is_empty());
    }

    #[test]
    fn delete_after_shifts_down() {
        let mut a = InlineAnnotations::new();
        a.add("ann1", 30, 40, "c").unwrap();
        a.apply_delete(10, 5);
        let ann = a.annotations.get("ann1").unwrap();
        assert_eq!(ann.start, 25);
        assert_eq!(ann.end, 35);
    }

    #[test]
    fn bad_inputs_rejected() {
        let mut a = InlineAnnotations::new();
        assert!(matches!(a.add("", 0, 5, "x").unwrap_err(), AnnotationError::EmptyId));
        assert!(matches!(a.add("i", 0, 5, "").unwrap_err(), AnnotationError::EmptyBody));
        assert!(matches!(a.add("i", 5, 5, "x").unwrap_err(), AnnotationError::BadRange));
        a.add("i", 0, 5, "x").unwrap();
        assert!(matches!(a.add("i", 0, 5, "x").unwrap_err(), AnnotationError::DuplicateId(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut a = InlineAnnotations::new();
        a.schema_version = "9.9.9".into();
        assert!(matches!(a.validate().unwrap_err(), AnnotationError::SchemaMismatch));
    }

    #[test]
    fn ann_serde_roundtrip() {
        let mut a = InlineAnnotations::new();
        a.add("ann1", 0, 5, "x").unwrap();
        let j = serde_json::to_string(&a).unwrap();
        let back: InlineAnnotations = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
