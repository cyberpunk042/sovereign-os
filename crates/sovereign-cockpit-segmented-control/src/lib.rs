//! `sovereign-cockpit-segmented-control` — horizontal pill selector.
//!
//! 2-6 segments, exactly one selected. select(id), next(), prev()
//! navigate through enabled segments only, wrapping.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Minimum / maximum segment counts.
pub const MIN_SEGMENTS: usize = 2;
/// Max segment count.
pub const MAX_SEGMENTS: usize = 6;

/// One segment.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Segment {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Enabled?
    pub enabled: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SegmentedControl {
    /// Schema version.
    pub schema_version: String,
    /// Segments.
    pub segments: Vec<Segment>,
    /// Active segment id.
    pub active: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SegmentedError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Too few or too many segments.
    #[error("segment count {0} out of [2, 6]")]
    BadCount(usize),
    /// Empty id.
    #[error("segment id empty")]
    EmptyId,
    /// Empty label.
    #[error("segment {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate segment id: {0}")]
    DuplicateId(String),
    /// Unknown active id.
    #[error("active id {0} not in segments")]
    UnknownActive(String),
    /// Active segment disabled.
    #[error("active segment {0} is disabled")]
    ActiveDisabled(String),
    /// No enabled segment to select.
    #[error("no enabled segments")]
    NoEnabled,
}

impl SegmentedControl {
    /// New. Initial active = first enabled segment.
    pub fn new(segments: Vec<Segment>) -> Result<Self, SegmentedError> {
        check_segments(&segments)?;
        let first_enabled = segments
            .iter()
            .find(|s| s.enabled)
            .ok_or(SegmentedError::NoEnabled)?;
        let active = first_enabled.id.clone();
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            segments,
            active,
        })
    }

    /// Select by id (must be enabled).
    pub fn select(&mut self, id: &str) -> Result<(), SegmentedError> {
        let s = self
            .segments
            .iter()
            .find(|s| s.id == id)
            .ok_or_else(|| SegmentedError::UnknownActive(id.into()))?;
        if !s.enabled {
            return Err(SegmentedError::ActiveDisabled(id.into()));
        }
        self.active = id.into();
        Ok(())
    }

    /// Next enabled segment (wraps).
    pub fn next(&mut self) -> &str {
        let enabled: Vec<usize> = self
            .segments
            .iter()
            .enumerate()
            .filter_map(|(i, s)| if s.enabled { Some(i) } else { None })
            .collect();
        if enabled.is_empty() {
            return &self.active;
        }
        let cur = enabled
            .iter()
            .position(|&i| self.segments[i].id == self.active);
        let next_idx = match cur {
            Some(p) => enabled[(p + 1) % enabled.len()],
            None => enabled[0],
        };
        self.active = self.segments[next_idx].id.clone();
        &self.active
    }

    /// Previous enabled segment (wraps).
    pub fn prev(&mut self) -> &str {
        let enabled: Vec<usize> = self
            .segments
            .iter()
            .enumerate()
            .filter_map(|(i, s)| if s.enabled { Some(i) } else { None })
            .collect();
        if enabled.is_empty() {
            return &self.active;
        }
        let cur = enabled
            .iter()
            .position(|&i| self.segments[i].id == self.active);
        let prev_idx = match cur {
            Some(p) => enabled[(p + enabled.len() - 1) % enabled.len()],
            None => *enabled.last().unwrap(),
        };
        self.active = self.segments[prev_idx].id.clone();
        &self.active
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SegmentedError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SegmentedError::SchemaMismatch);
        }
        check_segments(&self.segments)?;
        let active = self
            .segments
            .iter()
            .find(|s| s.id == self.active)
            .ok_or_else(|| SegmentedError::UnknownActive(self.active.clone()))?;
        if !active.enabled {
            return Err(SegmentedError::ActiveDisabled(self.active.clone()));
        }
        Ok(())
    }
}

fn check_segments(s: &[Segment]) -> Result<(), SegmentedError> {
    if s.len() < MIN_SEGMENTS || s.len() > MAX_SEGMENTS {
        return Err(SegmentedError::BadCount(s.len()));
    }
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for seg in s {
        if seg.id.is_empty() {
            return Err(SegmentedError::EmptyId);
        }
        if seg.label.is_empty() {
            return Err(SegmentedError::EmptyLabel(seg.id.clone()));
        }
        if !seen.insert(seg.id.as_str()) {
            return Err(SegmentedError::DuplicateId(seg.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(id: &str, enabled: bool) -> Segment {
        Segment {
            id: id.into(),
            label: format!("L-{id}"),
            enabled,
        }
    }

    #[test]
    fn too_few_rejected() {
        assert!(matches!(
            SegmentedControl::new(vec![s("a", true)]).unwrap_err(),
            SegmentedError::BadCount(1)
        ));
    }

    #[test]
    fn too_many_rejected() {
        let segs: Vec<Segment> = (0..7).map(|i| s(&format!("s{i}"), true)).collect();
        assert!(matches!(
            SegmentedControl::new(segs).unwrap_err(),
            SegmentedError::BadCount(7)
        ));
    }

    #[test]
    fn initial_active_first_enabled() {
        let c = SegmentedControl::new(vec![s("a", false), s("b", true), s("c", true)]).unwrap();
        assert_eq!(c.active, "b");
    }

    #[test]
    fn no_enabled_rejected() {
        assert!(matches!(
            SegmentedControl::new(vec![s("a", false), s("b", false)]).unwrap_err(),
            SegmentedError::NoEnabled
        ));
    }

    #[test]
    fn select_enabled() {
        let mut c = SegmentedControl::new(vec![s("a", true), s("b", true)]).unwrap();
        c.select("b").unwrap();
        assert_eq!(c.active, "b");
    }

    #[test]
    fn select_disabled_rejected() {
        let mut c = SegmentedControl::new(vec![s("a", true), s("b", false)]).unwrap();
        assert!(matches!(
            c.select("b").unwrap_err(),
            SegmentedError::ActiveDisabled(_)
        ));
    }

    #[test]
    fn next_wraps() {
        let mut c = SegmentedControl::new(vec![s("a", true), s("b", true), s("c", true)]).unwrap();
        c.next();
        assert_eq!(c.active, "b");
        c.next();
        assert_eq!(c.active, "c");
        c.next();
        assert_eq!(c.active, "a");
    }

    #[test]
    fn prev_wraps() {
        let mut c = SegmentedControl::new(vec![s("a", true), s("b", true)]).unwrap();
        c.prev();
        assert_eq!(c.active, "b");
    }

    #[test]
    fn next_skips_disabled() {
        let mut c = SegmentedControl::new(vec![s("a", true), s("b", false), s("c", true)]).unwrap();
        c.next();
        assert_eq!(c.active, "c");
    }

    #[test]
    fn duplicate_rejected() {
        assert!(matches!(
            SegmentedControl::new(vec![s("a", true), s("a", true)]).unwrap_err(),
            SegmentedError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = s("a", true);
        x.id = String::new();
        assert!(matches!(
            SegmentedControl::new(vec![x, s("b", true)]).unwrap_err(),
            SegmentedError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = SegmentedControl::new(vec![s("a", true), s("b", true)]).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            SegmentedError::SchemaMismatch
        ));
    }

    #[test]
    fn control_serde_roundtrip() {
        let c = SegmentedControl::new(vec![s("a", true), s("b", true), s("c", true)]).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: SegmentedControl = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
