//! `sovereign-cockpit-side-by-side-diff` — two-pane diff alignment.
//!
//! Given unified hunks (`Kind`: Context, Add, Remove, Change),
//! produce a Vec<AlignedPair> where:
//!   * Context appears on both sides with `Context` kind.
//!   * Add appears only on the right (left=`Spacer`).
//!   * Remove appears only on the left (right=`Spacer`).
//!   * Change uses `Modified` on both sides.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Hunk kind from caller.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum HunkKind {
    /// Unchanged.
    Context {
        /// the line.
        text: String,
    },
    /// Added (right only).
    Add {
        /// the line.
        text: String,
    },
    /// Removed (left only).
    Remove {
        /// the line.
        text: String,
    },
    /// Changed (paired).
    Change {
        /// left.
        left: String,
        /// right.
        right: String,
    },
}

/// Cell kind in the aligned output.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Cell {
    /// Spacer (no line on this side).
    Spacer,
    /// Unchanged.
    Context {
        /// line.
        text: String,
    },
    /// Modified.
    Modified {
        /// line.
        text: String,
    },
    /// Added.
    Added {
        /// line.
        text: String,
    },
    /// Removed.
    Removed {
        /// line.
        text: String,
    },
}

/// One aligned pair.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AlignedPair {
    /// left cell.
    pub left: Cell,
    /// right cell.
    pub right: Cell,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SideBySideDiff {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DiffError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl SideBySideDiff {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    /// Align.
    pub fn align(&self, hunks: &[HunkKind]) -> Vec<AlignedPair> {
        hunks
            .iter()
            .map(|h| match h {
                HunkKind::Context { text } => AlignedPair {
                    left: Cell::Context { text: text.clone() },
                    right: Cell::Context { text: text.clone() },
                },
                HunkKind::Add { text } => AlignedPair {
                    left: Cell::Spacer,
                    right: Cell::Added { text: text.clone() },
                },
                HunkKind::Remove { text } => AlignedPair {
                    left: Cell::Removed { text: text.clone() },
                    right: Cell::Spacer,
                },
                HunkKind::Change { left, right } => AlignedPair {
                    left: Cell::Modified { text: left.clone() },
                    right: Cell::Modified {
                        text: right.clone(),
                    },
                },
            })
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DiffError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DiffError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for SideBySideDiff {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn context_paired() {
        let d = SideBySideDiff::new();
        let out = d.align(&[HunkKind::Context {
            text: "unchanged".into(),
        }]);
        assert_eq!(
            out,
            vec![AlignedPair {
                left: Cell::Context {
                    text: "unchanged".into()
                },
                right: Cell::Context {
                    text: "unchanged".into()
                },
            }]
        );
    }

    #[test]
    fn add_right_only() {
        let d = SideBySideDiff::new();
        let out = d.align(&[HunkKind::Add { text: "new".into() }]);
        assert_eq!(out[0].left, Cell::Spacer);
        assert_eq!(out[0].right, Cell::Added { text: "new".into() });
    }

    #[test]
    fn remove_left_only() {
        let d = SideBySideDiff::new();
        let out = d.align(&[HunkKind::Remove { text: "old".into() }]);
        assert_eq!(out[0].left, Cell::Removed { text: "old".into() });
        assert_eq!(out[0].right, Cell::Spacer);
    }

    #[test]
    fn change_paired_modified() {
        let d = SideBySideDiff::new();
        let out = d.align(&[HunkKind::Change {
            left: "a".into(),
            right: "b".into(),
        }]);
        assert_eq!(out[0].left, Cell::Modified { text: "a".into() });
        assert_eq!(out[0].right, Cell::Modified { text: "b".into() });
    }

    #[test]
    fn mixed_sequence() {
        let d = SideBySideDiff::new();
        let out = d.align(&[
            HunkKind::Context { text: "x".into() },
            HunkKind::Add { text: "y".into() },
            HunkKind::Remove { text: "z".into() },
            HunkKind::Change {
                left: "a".into(),
                right: "b".into(),
            },
        ]);
        assert_eq!(out.len(), 4);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = SideBySideDiff::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DiffError::SchemaMismatch
        ));
    }

    #[test]
    fn diff_serde_roundtrip() {
        let d = SideBySideDiff::new();
        let j = serde_json::to_string(&d).unwrap();
        let back: SideBySideDiff = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
