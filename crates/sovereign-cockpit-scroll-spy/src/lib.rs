//! `sovereign-cockpit-scroll-spy` — maps scroll position to active section.
//!
//! Section list is `(id, top_px)`, kept sorted by `top_px`. The "active"
//! section at scroll position `pos_px` is the last section whose `top_px`
//! satisfies `top_px <= pos_px + activation_offset_px`. Returns None
//! when the scroll position is above the first section's activation
//! threshold.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One section.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Section {
    /// Section id (stable string).
    pub id: String,
    /// Top offset (px) from scroll container origin.
    pub top_px: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ScrollSpy {
    /// Schema version.
    pub schema_version: String,
    /// Sections, kept sorted by top_px ascending.
    pub sections: Vec<Section>,
    /// Activation offset (px). Section becomes active when its top is
    /// within this many px of the current scroll line.
    pub activation_offset_px: u32,
    /// Last reported active id (for hysteresis-free debug).
    pub last_active: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SpyError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("section id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate section id: {0}")]
    DuplicateId(String),
}

impl ScrollSpy {
    /// New.
    pub fn new(activation_offset_px: u32) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            sections: Vec::new(),
            activation_offset_px,
            last_active: None,
        }
    }

    /// Register a section. Inserts in sorted order.
    pub fn register(&mut self, s: Section) -> Result<(), SpyError> {
        if s.id.is_empty() { return Err(SpyError::EmptyId); }
        if self.sections.iter().any(|x| x.id == s.id) {
            return Err(SpyError::DuplicateId(s.id));
        }
        let pos = self.sections.partition_point(|x| x.top_px <= s.top_px);
        self.sections.insert(pos, s);
        Ok(())
    }

    /// Remove a section by id.
    pub fn unregister(&mut self, id: &str) -> bool {
        if let Some(pos) = self.sections.iter().position(|x| x.id == id) {
            self.sections.remove(pos);
            true
        } else {
            false
        }
    }

    /// Compute active section id at scroll position `pos_px` and persist
    /// it in `last_active`.
    pub fn active_at(&mut self, pos_px: u32) -> Option<String> {
        let thresh = pos_px.saturating_add(self.activation_offset_px);
        let active = self.sections.iter()
            .rev()
            .find(|s| s.top_px <= thresh)
            .map(|s| s.id.clone());
        self.last_active = active.clone();
        active
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SpyError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SpyError::SchemaMismatch); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        let mut prev = 0u32;
        for s in &self.sections {
            if s.id.is_empty() { return Err(SpyError::EmptyId); }
            if !seen.insert(s.id.as_str()) { return Err(SpyError::DuplicateId(s.id.clone())); }
            if s.top_px < prev {
                // sections must be ascending — re-sort would silently mask; treat as invariant.
                return Err(SpyError::DuplicateId(s.id.clone()));
            }
            prev = s.top_px;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sect(id: &str, top: u32) -> Section { Section { id: id.into(), top_px: top } }

    #[test]
    fn register_keeps_sorted() {
        let mut s = ScrollSpy::new(0);
        s.register(sect("c", 300)).unwrap();
        s.register(sect("a", 100)).unwrap();
        s.register(sect("b", 200)).unwrap();
        let ids: Vec<_> = s.sections.iter().map(|x| x.id.clone()).collect();
        assert_eq!(ids, vec!["a", "b", "c"]);
    }

    #[test]
    fn active_at_above_first() {
        let mut s = ScrollSpy::new(0);
        s.register(sect("a", 100)).unwrap();
        // Scroll at 50, activation 0 → 50 < 100, no section active.
        assert_eq!(s.active_at(50), None);
    }

    #[test]
    fn active_at_crosses_first() {
        let mut s = ScrollSpy::new(0);
        s.register(sect("a", 100)).unwrap();
        s.register(sect("b", 200)).unwrap();
        assert_eq!(s.active_at(100), Some("a".into()));
        assert_eq!(s.active_at(199), Some("a".into()));
        assert_eq!(s.active_at(200), Some("b".into()));
    }

    #[test]
    fn activation_offset_pulls_forward() {
        let mut s = ScrollSpy::new(50);
        s.register(sect("a", 100)).unwrap();
        // Pos 50 + offset 50 = 100 ≥ 100 → "a" active.
        assert_eq!(s.active_at(50), Some("a".into()));
        assert_eq!(s.active_at(49), None);
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut s = ScrollSpy::new(0);
        s.register(sect("a", 100)).unwrap();
        assert!(matches!(s.register(sect("a", 200)).unwrap_err(), SpyError::DuplicateId(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = ScrollSpy::new(0);
        assert!(matches!(s.register(sect("", 100)).unwrap_err(), SpyError::EmptyId));
    }

    #[test]
    fn unregister_removes() {
        let mut s = ScrollSpy::new(0);
        s.register(sect("a", 100)).unwrap();
        s.register(sect("b", 200)).unwrap();
        assert!(s.unregister("a"));
        assert_eq!(s.sections.len(), 1);
        assert!(!s.unregister("z"));
    }

    #[test]
    fn last_active_persists() {
        let mut s = ScrollSpy::new(0);
        s.register(sect("a", 100)).unwrap();
        s.active_at(150);
        assert_eq!(s.last_active.as_deref(), Some("a"));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ScrollSpy::new(0);
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SpyError::SchemaMismatch));
    }

    #[test]
    fn spy_serde_roundtrip() {
        let mut s = ScrollSpy::new(20);
        s.register(sect("a", 100)).unwrap();
        s.active_at(120);
        let j = serde_json::to_string(&s).unwrap();
        let back: ScrollSpy = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
