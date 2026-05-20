//! `sovereign-cockpit-status-bar-segments` — status bar.
//!
//! Three zones: Left, Center, Right. Each segment has a `priority`
//! — higher priority wins screen real estate when space is tight.
//! `visible_in_zone(zone, max_items)` returns top-priority segments
//! up to `max_items`, ordered by priority desc then label.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Zone.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Zone {
    /// Left.
    Left,
    /// Centre.
    Center,
    /// Right.
    Right,
}

/// One segment.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Segment {
    /// Stable id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Zone.
    pub zone: Zone,
    /// Priority (higher = more important).
    pub priority: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusBarSegments {
    /// Schema version.
    pub schema_version: String,
    /// id → segment.
    pub segments: BTreeMap<String, Segment>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SegmentError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate segment id: {0}")]
    DuplicateId(String),
}

impl StatusBarSegments {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            segments: BTreeMap::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, segment: Segment) -> Result<(), SegmentError> {
        if segment.id.is_empty() { return Err(SegmentError::EmptyId); }
        if segment.label.is_empty() { return Err(SegmentError::EmptyLabel); }
        if self.segments.contains_key(&segment.id) {
            return Err(SegmentError::DuplicateId(segment.id));
        }
        self.segments.insert(segment.id.clone(), segment);
        Ok(())
    }

    /// Update label.
    pub fn set_label(&mut self, id: &str, label: &str) -> Result<bool, SegmentError> {
        if label.is_empty() { return Err(SegmentError::EmptyLabel); }
        let Some(s) = self.segments.get_mut(id) else { return Ok(false); };
        s.label = label.into();
        Ok(true)
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.segments.remove(id).is_some()
    }

    /// Visible in zone (descending priority, alpha tie-break).
    pub fn visible_in_zone(&self, zone: Zone, max_items: usize) -> Vec<Segment> {
        let mut v: Vec<Segment> = self.segments.values()
            .filter(|s| s.zone == zone)
            .cloned()
            .collect();
        v.sort_by(|a, b| b.priority.cmp(&a.priority).then(a.label.cmp(&b.label)));
        v.truncate(max_items);
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SegmentError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SegmentError::SchemaMismatch); }
        for (id, s) in &self.segments {
            if id.is_empty() { return Err(SegmentError::EmptyId); }
            if s.label.is_empty() { return Err(SegmentError::EmptyLabel); }
        }
        Ok(())
    }
}

impl Default for StatusBarSegments {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn seg(id: &str, zone: Zone, priority: u32) -> Segment {
        Segment { id: id.into(), label: id.into(), zone, priority }
    }

    #[test]
    fn visible_sorted_by_priority() {
        let mut s = StatusBarSegments::new();
        s.register(seg("low", Zone::Left, 1)).unwrap();
        s.register(seg("hi", Zone::Left, 10)).unwrap();
        let v = s.visible_in_zone(Zone::Left, 10);
        assert_eq!(v[0].id, "hi");
        assert_eq!(v[1].id, "low");
    }

    #[test]
    fn max_items_truncates() {
        let mut s = StatusBarSegments::new();
        for i in 0..5 {
            s.register(seg(&format!("s{i}"), Zone::Right, i)).unwrap();
        }
        let v = s.visible_in_zone(Zone::Right, 2);
        assert_eq!(v.len(), 2);
        // Top 2 by priority: s4, s3.
        assert_eq!(v[0].id, "s4");
        assert_eq!(v[1].id, "s3");
    }

    #[test]
    fn zone_isolation() {
        let mut s = StatusBarSegments::new();
        s.register(seg("L", Zone::Left, 1)).unwrap();
        s.register(seg("C", Zone::Center, 1)).unwrap();
        s.register(seg("R", Zone::Right, 1)).unwrap();
        assert_eq!(s.visible_in_zone(Zone::Left, 10).len(), 1);
        assert_eq!(s.visible_in_zone(Zone::Center, 10).len(), 1);
        assert_eq!(s.visible_in_zone(Zone::Right, 10).len(), 1);
    }

    #[test]
    fn alpha_tie_break() {
        let mut s = StatusBarSegments::new();
        s.register(seg("b", Zone::Left, 5)).unwrap();
        s.register(seg("a", Zone::Left, 5)).unwrap();
        let v = s.visible_in_zone(Zone::Left, 10);
        assert_eq!(v[0].id, "a");
    }

    #[test]
    fn set_label_returns_bool() {
        let mut s = StatusBarSegments::new();
        s.register(seg("a", Zone::Left, 1)).unwrap();
        assert!(s.set_label("a", "Aye").unwrap());
        assert!(!s.set_label("nope", "x").unwrap());
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = StatusBarSegments::new();
        s.register(seg("a", Zone::Left, 1)).unwrap();
        assert!(matches!(s.register(seg("a", Zone::Right, 1)).unwrap_err(), SegmentError::DuplicateId(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = StatusBarSegments::new();
        let bad = Segment { id: "".into(), label: "X".into(), zone: Zone::Left, priority: 1 };
        assert!(matches!(s.register(bad).unwrap_err(), SegmentError::EmptyId));
        let bad = Segment { id: "a".into(), label: "".into(), zone: Zone::Left, priority: 1 };
        assert!(matches!(s.register(bad).unwrap_err(), SegmentError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = StatusBarSegments::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SegmentError::SchemaMismatch));
    }

    #[test]
    fn statusbar_serde_roundtrip() {
        let mut s = StatusBarSegments::new();
        s.register(seg("a", Zone::Right, 5)).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: StatusBarSegments = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
