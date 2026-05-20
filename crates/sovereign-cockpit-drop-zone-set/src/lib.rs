//! `sovereign-cockpit-drop-zone-set` — drop zone registry.
//!
//! Each zone has an `accept_types` set + optional `max_items` cap +
//! current `count`. `decide(zone, item_type)` returns:
//!   * `Accept` — type allowed and zone not full.
//!   * `RejectType { accepted }` — item type not on the list.
//!   * `RejectFull { count, max }` — zone at capacity.
//!   * `Unknown` — zone not registered.
//!
//! `accept(zone, item_type)` calls decide() then increments `count`
//! on Accept (returns the verdict).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One zone.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Zone {
    /// Allowed types.
    pub accept_types: BTreeSet<String>,
    /// Optional cap (None = unlimited).
    pub max_items: Option<u32>,
    /// Current count.
    pub count: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DropZoneSet {
    /// Schema version.
    pub schema_version: String,
    /// zone id → zone.
    pub zones: BTreeMap<String, Zone>,
}

/// Verdict.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum DropVerdict {
    /// Accept.
    Accept,
    /// Type not allowed.
    RejectType {
        /// accepted set.
        accepted: Vec<String>,
    },
    /// At capacity.
    RejectFull {
        /// current.
        count: u32,
        /// max.
        max: u32,
    },
    /// Unknown.
    Unknown,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DropZoneError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("zone id empty")]
    EmptyId,
    /// Empty type.
    #[error("type empty")]
    EmptyType,
    /// Unknown.
    #[error("unknown zone: {0}")]
    UnknownZone(String),
}

impl DropZoneSet {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            zones: BTreeMap::new(),
        }
    }

    /// Register a zone.
    pub fn register(&mut self, id: &str, accept_types: &[&str], max_items: Option<u32>) -> Result<(), DropZoneError> {
        if id.is_empty() { return Err(DropZoneError::EmptyId); }
        let mut set = BTreeSet::new();
        for t in accept_types {
            if t.is_empty() { return Err(DropZoneError::EmptyType); }
            set.insert((*t).into());
        }
        self.zones.insert(id.into(), Zone { accept_types: set, max_items, count: 0 });
        Ok(())
    }

    /// Add an accept-type to an existing zone.
    pub fn add_type(&mut self, zone: &str, item_type: &str) -> Result<bool, DropZoneError> {
        if item_type.is_empty() { return Err(DropZoneError::EmptyType); }
        let z = self.zones.get_mut(zone).ok_or_else(|| DropZoneError::UnknownZone(zone.into()))?;
        Ok(z.accept_types.insert(item_type.into()))
    }

    /// Pure decision.
    pub fn decide(&self, zone: &str, item_type: &str) -> DropVerdict {
        let Some(z) = self.zones.get(zone) else { return DropVerdict::Unknown; };
        if !z.accept_types.contains(item_type) {
            return DropVerdict::RejectType { accepted: z.accept_types.iter().cloned().collect() };
        }
        if let Some(m) = z.max_items {
            if z.count >= m {
                return DropVerdict::RejectFull { count: z.count, max: m };
            }
        }
        DropVerdict::Accept
    }

    /// Accept (mutates count on success).
    pub fn accept(&mut self, zone: &str, item_type: &str) -> DropVerdict {
        let v = self.decide(zone, item_type);
        if v == DropVerdict::Accept {
            if let Some(z) = self.zones.get_mut(zone) {
                z.count = z.count.saturating_add(1);
            }
        }
        v
    }

    /// Decrement (when an item is removed from the zone).
    pub fn release(&mut self, zone: &str) -> Result<u32, DropZoneError> {
        let z = self.zones.get_mut(zone).ok_or_else(|| DropZoneError::UnknownZone(zone.into()))?;
        z.count = z.count.saturating_sub(1);
        Ok(z.count)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DropZoneError> {
        if self.schema_version != SCHEMA_VERSION { return Err(DropZoneError::SchemaMismatch); }
        for (id, z) in &self.zones {
            if id.is_empty() { return Err(DropZoneError::EmptyId); }
            for t in &z.accept_types {
                if t.is_empty() { return Err(DropZoneError::EmptyType); }
            }
        }
        Ok(())
    }
}

impl Default for DropZoneSet {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accept_when_type_matches() {
        let mut s = DropZoneSet::new();
        s.register("trash", &["file", "folder"], None).unwrap();
        assert_eq!(s.decide("trash", "file"), DropVerdict::Accept);
    }

    #[test]
    fn reject_when_type_off_list() {
        let mut s = DropZoneSet::new();
        s.register("trash", &["file"], None).unwrap();
        match s.decide("trash", "folder") {
            DropVerdict::RejectType { accepted } => assert_eq!(accepted, vec!["file"]),
            _ => panic!(),
        }
    }

    #[test]
    fn reject_when_full() {
        let mut s = DropZoneSet::new();
        s.register("slot", &["file"], Some(1)).unwrap();
        assert_eq!(s.accept("slot", "file"), DropVerdict::Accept);
        match s.accept("slot", "file") {
            DropVerdict::RejectFull { count, max } => {
                assert_eq!(count, 1);
                assert_eq!(max, 1);
            }
            _ => panic!(),
        }
    }

    #[test]
    fn unknown_zone() {
        let s = DropZoneSet::new();
        assert_eq!(s.decide("nope", "file"), DropVerdict::Unknown);
    }

    #[test]
    fn accept_increments_count() {
        let mut s = DropZoneSet::new();
        s.register("z", &["file"], Some(10)).unwrap();
        s.accept("z", "file");
        s.accept("z", "file");
        assert_eq!(s.zones["z"].count, 2);
    }

    #[test]
    fn release_decrements() {
        let mut s = DropZoneSet::new();
        s.register("z", &["file"], Some(10)).unwrap();
        s.accept("z", "file");
        s.release("z").unwrap();
        assert_eq!(s.zones["z"].count, 0);
        // Idempotent on 0.
        s.release("z").unwrap();
        assert_eq!(s.zones["z"].count, 0);
    }

    #[test]
    fn add_type_extends_zone() {
        let mut s = DropZoneSet::new();
        s.register("z", &["file"], None).unwrap();
        s.add_type("z", "folder").unwrap();
        assert_eq!(s.decide("z", "folder"), DropVerdict::Accept);
    }

    #[test]
    fn release_unknown_rejected() {
        let mut s = DropZoneSet::new();
        assert!(matches!(s.release("nope").unwrap_err(), DropZoneError::UnknownZone(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = DropZoneSet::new();
        assert!(matches!(s.register("", &["x"], None).unwrap_err(), DropZoneError::EmptyId));
        assert!(matches!(s.register("z", &[""], None).unwrap_err(), DropZoneError::EmptyType));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = DropZoneSet::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), DropZoneError::SchemaMismatch));
    }

    #[test]
    fn zone_serde_roundtrip() {
        let mut s = DropZoneSet::new();
        s.register("z", &["file"], Some(5)).unwrap();
        s.accept("z", "file");
        let j = serde_json::to_string(&s).unwrap();
        let back: DropZoneSet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
