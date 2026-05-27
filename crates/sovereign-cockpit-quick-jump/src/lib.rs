//! `sovereign-cockpit-quick-jump` — explicit-shortcut jump registry.
//!
//! Operators type a known short_id (e.g. `@logs`, `#1234`,
//! `dash:main`) into a quick-jump bar to reach a target without
//! navigating. `resolve(short_id)` returns the registered target
//! (or None).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One jump target.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct JumpTarget {
    /// Stable short id (operator types this).
    pub short_id: String,
    /// kind label (dashboard / log / task / …).
    pub kind: String,
    /// Full internal path/route.
    pub full_path: String,
    /// Display label.
    pub label: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QuickJump {
    /// Schema version.
    pub schema_version: String,
    /// short_id → target.
    pub targets: BTreeMap<String, JumpTarget>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum JumpError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty short id.
    #[error("short_id empty")]
    EmptyShortId,
    /// Empty kind.
    #[error("kind empty")]
    EmptyKind,
    /// Empty path.
    #[error("full_path empty")]
    EmptyPath,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate short_id: {0}")]
    DuplicateId(String),
}

impl QuickJump {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            targets: BTreeMap::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, target: JumpTarget) -> Result<(), JumpError> {
        if target.short_id.is_empty() {
            return Err(JumpError::EmptyShortId);
        }
        if target.kind.is_empty() {
            return Err(JumpError::EmptyKind);
        }
        if target.full_path.is_empty() {
            return Err(JumpError::EmptyPath);
        }
        if target.label.is_empty() {
            return Err(JumpError::EmptyLabel);
        }
        if self.targets.contains_key(&target.short_id) {
            return Err(JumpError::DuplicateId(target.short_id));
        }
        self.targets.insert(target.short_id.clone(), target);
        Ok(())
    }

    /// Resolve.
    pub fn resolve(&self, short_id: &str) -> Option<&JumpTarget> {
        self.targets.get(short_id)
    }

    /// Unregister.
    pub fn unregister(&mut self, short_id: &str) -> bool {
        self.targets.remove(short_id).is_some()
    }

    /// Targets matching a kind.
    pub fn by_kind(&self, kind: &str) -> Vec<JumpTarget> {
        self.targets
            .values()
            .filter(|t| t.kind == kind)
            .cloned()
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), JumpError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(JumpError::SchemaMismatch);
        }
        for t in self.targets.values() {
            if t.short_id.is_empty() {
                return Err(JumpError::EmptyShortId);
            }
            if t.kind.is_empty() {
                return Err(JumpError::EmptyKind);
            }
            if t.full_path.is_empty() {
                return Err(JumpError::EmptyPath);
            }
            if t.label.is_empty() {
                return Err(JumpError::EmptyLabel);
            }
        }
        Ok(())
    }
}

impl Default for QuickJump {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn jt(id: &str, kind: &str, path: &str, label: &str) -> JumpTarget {
        JumpTarget {
            short_id: id.into(),
            kind: kind.into(),
            full_path: path.into(),
            label: label.into(),
        }
    }

    #[test]
    fn register_and_resolve() {
        let mut q = QuickJump::new();
        q.register(jt("@logs", "dashboard", "/dashboards/logs", "Logs"))
            .unwrap();
        let t = q.resolve("@logs").unwrap();
        assert_eq!(t.full_path, "/dashboards/logs");
    }

    #[test]
    fn duplicate_rejected() {
        let mut q = QuickJump::new();
        q.register(jt("@logs", "dashboard", "/x", "x")).unwrap();
        assert!(matches!(
            q.register(jt("@logs", "dashboard", "/y", "y")).unwrap_err(),
            JumpError::DuplicateId(_)
        ));
    }

    #[test]
    fn by_kind() {
        let mut q = QuickJump::new();
        q.register(jt("@logs", "dashboard", "/x", "x")).unwrap();
        q.register(jt("#1234", "task", "/t/1234", "Task 1234"))
            .unwrap();
        assert_eq!(q.by_kind("dashboard").len(), 1);
        assert_eq!(q.by_kind("task").len(), 1);
        assert_eq!(q.by_kind("other").len(), 0);
    }

    #[test]
    fn unregister_removes() {
        let mut q = QuickJump::new();
        q.register(jt("@logs", "dashboard", "/x", "x")).unwrap();
        assert!(q.unregister("@logs"));
        assert!(q.resolve("@logs").is_none());
    }

    #[test]
    fn empty_fields_rejected() {
        let mut q = QuickJump::new();
        assert!(matches!(
            q.register(jt("", "k", "p", "l")).unwrap_err(),
            JumpError::EmptyShortId
        ));
        assert!(matches!(
            q.register(jt("s", "", "p", "l")).unwrap_err(),
            JumpError::EmptyKind
        ));
        assert!(matches!(
            q.register(jt("s", "k", "", "l")).unwrap_err(),
            JumpError::EmptyPath
        ));
        assert!(matches!(
            q.register(jt("s", "k", "p", "")).unwrap_err(),
            JumpError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut q = QuickJump::new();
        q.schema_version = "9.9.9".into();
        assert!(matches!(
            q.validate().unwrap_err(),
            JumpError::SchemaMismatch
        ));
    }

    #[test]
    fn jump_serde_roundtrip() {
        let mut q = QuickJump::new();
        q.register(jt("@logs", "dashboard", "/x", "x")).unwrap();
        let j = serde_json::to_string(&q).unwrap();
        let back: QuickJump = serde_json::from_str(&j).unwrap();
        assert_eq!(q, back);
    }
}
