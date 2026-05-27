//! `sovereign-cockpit-tap-target` — a11y tap regions.
//!
//! Each target has width/height px + aria_label. register
//! rejects too-small targets (< min_size_px) and empty labels.
//! audit() returns ids that violate current min size (if min
//! is later raised).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Target.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Target {
    /// Width (px).
    pub width_px: u32,
    /// Height (px).
    pub height_px: u32,
    /// ARIA label.
    pub aria_label: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TapTargetRegistry {
    /// Schema version.
    pub schema_version: String,
    /// Minimum side in px.
    pub min_size_px: u32,
    /// id → target.
    pub targets: BTreeMap<String, Target>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TargetError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("aria_label empty")]
    EmptyLabel,
    /// Zero min.
    #[error("min_size_px must be >= 1")]
    ZeroMin,
    /// Too small.
    #[error("target {id} {dim}px below minimum {min}px")]
    TooSmall {
        /// Id.
        id: String,
        /// Smallest dimension.
        dim: u32,
        /// Minimum.
        min: u32,
    },
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl TapTargetRegistry {
    /// New.
    pub fn new(min_size_px: u32) -> Result<Self, TargetError> {
        if min_size_px == 0 {
            return Err(TargetError::ZeroMin);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            min_size_px,
            targets: BTreeMap::new(),
        })
    }

    /// Register a target.
    pub fn register(
        &mut self,
        id: &str,
        width_px: u32,
        height_px: u32,
        aria_label: &str,
    ) -> Result<(), TargetError> {
        if id.is_empty() {
            return Err(TargetError::EmptyId);
        }
        if aria_label.is_empty() {
            return Err(TargetError::EmptyLabel);
        }
        let smallest = width_px.min(height_px);
        if smallest < self.min_size_px {
            return Err(TargetError::TooSmall {
                id: id.into(),
                dim: smallest,
                min: self.min_size_px,
            });
        }
        if self.targets.contains_key(id) {
            return Err(TargetError::DuplicateId(id.into()));
        }
        self.targets.insert(
            id.into(),
            Target {
                width_px,
                height_px,
                aria_label: aria_label.into(),
            },
        );
        Ok(())
    }

    /// Audit — return ids whose current size is below min_size_px.
    pub fn audit(&self) -> Vec<&str> {
        self.targets
            .iter()
            .filter(|(_, t)| t.width_px.min(t.height_px) < self.min_size_px)
            .map(|(k, _)| k.as_str())
            .collect()
    }

    /// Raise minimum size.
    pub fn set_min_size_px(&mut self, n: u32) -> Result<(), TargetError> {
        if n == 0 {
            return Err(TargetError::ZeroMin);
        }
        self.min_size_px = n;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TargetError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TargetError::SchemaMismatch);
        }
        if self.min_size_px == 0 {
            return Err(TargetError::ZeroMin);
        }
        for (id, t) in &self.targets {
            if id.is_empty() {
                return Err(TargetError::EmptyId);
            }
            if t.aria_label.is_empty() {
                return Err(TargetError::EmptyLabel);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_ok() {
        let mut r = TapTargetRegistry::new(44).unwrap();
        r.register("btn", 44, 44, "submit").unwrap();
        assert!(r.audit().is_empty());
    }

    #[test]
    fn too_small_rejected() {
        let mut r = TapTargetRegistry::new(44).unwrap();
        assert!(matches!(
            r.register("btn", 30, 40, "submit").unwrap_err(),
            TargetError::TooSmall {
                dim: 30,
                min: 44,
                ..
            }
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut r = TapTargetRegistry::new(44).unwrap();
        assert!(matches!(
            r.register("", 44, 44, "x").unwrap_err(),
            TargetError::EmptyId
        ));
        assert!(matches!(
            r.register("btn", 44, 44, "").unwrap_err(),
            TargetError::EmptyLabel
        ));
        assert!(matches!(
            TapTargetRegistry::new(0).unwrap_err(),
            TargetError::ZeroMin
        ));
    }

    #[test]
    fn duplicate_rejected() {
        let mut r = TapTargetRegistry::new(44).unwrap();
        r.register("btn", 44, 44, "x").unwrap();
        assert!(matches!(
            r.register("btn", 44, 44, "y").unwrap_err(),
            TargetError::DuplicateId(_)
        ));
    }

    #[test]
    fn audit_after_min_raise() {
        let mut r = TapTargetRegistry::new(44).unwrap();
        r.register("a", 44, 44, "x").unwrap();
        r.register("b", 50, 50, "y").unwrap();
        r.set_min_size_px(48).unwrap();
        // "a" now too small.
        assert_eq!(r.audit(), vec!["a"]);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = TapTargetRegistry::new(44).unwrap();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            TargetError::SchemaMismatch
        ));
    }

    #[test]
    fn registry_serde_roundtrip() {
        let mut r = TapTargetRegistry::new(44).unwrap();
        r.register("btn", 44, 44, "submit").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: TapTargetRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
