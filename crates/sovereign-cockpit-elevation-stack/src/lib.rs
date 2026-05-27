//! `sovereign-cockpit-elevation-stack` — z-index for floating UI.
//!
//! Layer kinds have a base z-index: Dropdown=1000, Sticky=1100,
//! Banner=1200, Tooltip=1300, Modal=1400, Popover=1500,
//! Toast=1600. push(id, kind) assigns z = base + sequence
//! within that kind. pop(id) removes; on_top() returns the
//! highest-z element across all kinds.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Layer kind.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "kebab-case")]
pub enum Kind {
    /// Dropdown.
    Dropdown,
    /// Sticky.
    Sticky,
    /// Banner.
    Banner,
    /// Tooltip.
    Tooltip,
    /// Modal.
    Modal,
    /// Popover.
    Popover,
    /// Toast.
    Toast,
}

impl Kind {
    /// Base z-index.
    pub fn base(self) -> u32 {
        match self {
            Kind::Dropdown => 1000,
            Kind::Sticky => 1100,
            Kind::Banner => 1200,
            Kind::Tooltip => 1300,
            Kind::Modal => 1400,
            Kind::Popover => 1500,
            Kind::Toast => 1600,
        }
    }
}

/// Layer.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Layer {
    /// Id.
    pub id: String,
    /// Kind.
    pub kind: Kind,
    /// Assigned z-index.
    pub z: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ElevationStack {
    /// Schema version.
    pub schema_version: String,
    /// id → layer.
    pub layers: BTreeMap<String, Layer>,
    /// Next sequence per kind base.
    pub next_seq: BTreeMap<u32, u32>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StackError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown id: {0}")]
    UnknownId(String),
}

impl ElevationStack {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            layers: BTreeMap::new(),
            next_seq: BTreeMap::new(),
        }
    }

    /// Push a layer; returns assigned z.
    pub fn push(&mut self, id: &str, kind: Kind) -> Result<u32, StackError> {
        if id.is_empty() {
            return Err(StackError::EmptyId);
        }
        if self.layers.contains_key(id) {
            return Err(StackError::DuplicateId(id.into()));
        }
        let base = kind.base();
        let seq = self.next_seq.entry(base).or_insert(0);
        let z = base.saturating_add(*seq);
        *seq = seq.saturating_add(1);
        self.layers.insert(
            id.into(),
            Layer {
                id: id.into(),
                kind,
                z,
            },
        );
        Ok(z)
    }

    /// Pop a layer.
    pub fn pop(&mut self, id: &str) -> Result<(), StackError> {
        if self.layers.remove(id).is_none() {
            return Err(StackError::UnknownId(id.into()));
        }
        Ok(())
    }

    /// On-top layer (highest z).
    pub fn on_top(&self) -> Option<&Layer> {
        self.layers.values().max_by_key(|l| l.z)
    }

    /// Z of layer.
    pub fn z_of(&self, id: &str) -> Option<u32> {
        self.layers.get(id).map(|l| l.z)
    }

    /// Count.
    pub fn len(&self) -> usize {
        self.layers.len()
    }

    /// Empty.
    pub fn is_empty(&self) -> bool {
        self.layers.is_empty()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StackError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(StackError::SchemaMismatch);
        }
        for (id, _) in &self.layers {
            if id.is_empty() {
                return Err(StackError::EmptyId);
            }
        }
        Ok(())
    }
}

impl Default for ElevationStack {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_no_top() {
        let s = ElevationStack::new();
        assert!(s.on_top().is_none());
    }

    #[test]
    fn assigns_base_z() {
        let mut s = ElevationStack::new();
        let z = s.push("m1", Kind::Modal).unwrap();
        assert_eq!(z, 1400);
    }

    #[test]
    fn increments_within_kind() {
        let mut s = ElevationStack::new();
        let z1 = s.push("m1", Kind::Modal).unwrap();
        let z2 = s.push("m2", Kind::Modal).unwrap();
        assert_eq!(z1, 1400);
        assert_eq!(z2, 1401);
    }

    #[test]
    fn kinds_ordered() {
        let mut s = ElevationStack::new();
        s.push("d", Kind::Dropdown).unwrap();
        s.push("m", Kind::Modal).unwrap();
        s.push("t", Kind::Toast).unwrap();
        assert_eq!(s.on_top().unwrap().id, "t");
    }

    #[test]
    fn pop_removes() {
        let mut s = ElevationStack::new();
        s.push("a", Kind::Modal).unwrap();
        s.pop("a").unwrap();
        assert!(s.is_empty());
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = ElevationStack::new();
        s.push("a", Kind::Modal).unwrap();
        assert!(matches!(
            s.push("a", Kind::Modal).unwrap_err(),
            StackError::DuplicateId(_)
        ));
    }

    #[test]
    fn unknown_pop_rejected() {
        let mut s = ElevationStack::new();
        assert!(matches!(
            s.pop("nope").unwrap_err(),
            StackError::UnknownId(_)
        ));
    }

    #[test]
    fn z_of_lookup() {
        let mut s = ElevationStack::new();
        s.push("a", Kind::Tooltip).unwrap();
        assert_eq!(s.z_of("a"), Some(1300));
        assert_eq!(s.z_of("nope"), None);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ElevationStack::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            StackError::SchemaMismatch
        ));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = ElevationStack::new();
        s.push("a", Kind::Modal).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ElevationStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
