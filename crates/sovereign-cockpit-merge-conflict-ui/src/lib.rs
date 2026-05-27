//! `sovereign-cockpit-merge-conflict-ui` — merge conflict UI.
//!
//! Each `Hunk { id, base, ours, theirs, resolution }`. Resolution
//! transitions: Unresolved → AcceptOurs / AcceptTheirs / Manual{
//! body }. `mark_all_unresolved()` resets; `count_unresolved()`
//! gates the "merge complete" button.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Resolution.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Resolution {
    /// Unresolved.
    Unresolved,
    /// Accept ours.
    AcceptOurs,
    /// Accept theirs.
    AcceptTheirs,
    /// Accept both (ours then theirs).
    AcceptBoth,
    /// Manual.
    Manual {
        /// resolved body.
        body: String,
    },
}

/// One conflict hunk.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Hunk {
    /// Id.
    pub id: String,
    /// Base text.
    pub base: String,
    /// Our side.
    pub ours: String,
    /// Their side.
    pub theirs: String,
    /// Resolution.
    pub resolution: Resolution,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MergeConflictUi {
    /// Schema version.
    pub schema_version: String,
    /// Hunks in order.
    pub hunks: Vec<Hunk>,
    /// Indexed for fast lookup.
    pub by_id: BTreeMap<String, usize>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MergeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("hunk id empty")]
    EmptyId,
    /// Empty manual body.
    #[error("manual body empty")]
    EmptyBody,
    /// Duplicate.
    #[error("duplicate hunk id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown hunk: {0}")]
    UnknownHunk(String),
}

impl MergeConflictUi {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            hunks: Vec::new(),
            by_id: BTreeMap::new(),
        }
    }

    /// Add a hunk (defaults to Unresolved).
    pub fn add(
        &mut self,
        id: &str,
        base: &str,
        ours: &str,
        theirs: &str,
    ) -> Result<(), MergeError> {
        if id.is_empty() {
            return Err(MergeError::EmptyId);
        }
        if self.by_id.contains_key(id) {
            return Err(MergeError::DuplicateId(id.into()));
        }
        let idx = self.hunks.len();
        self.hunks.push(Hunk {
            id: id.into(),
            base: base.into(),
            ours: ours.into(),
            theirs: theirs.into(),
            resolution: Resolution::Unresolved,
        });
        self.by_id.insert(id.into(), idx);
        Ok(())
    }

    /// Set resolution.
    pub fn resolve(&mut self, id: &str, resolution: Resolution) -> Result<(), MergeError> {
        if let Resolution::Manual { body } = &resolution {
            if body.is_empty() {
                return Err(MergeError::EmptyBody);
            }
        }
        let idx = self
            .by_id
            .get(id)
            .copied()
            .ok_or_else(|| MergeError::UnknownHunk(id.into()))?;
        self.hunks[idx].resolution = resolution;
        Ok(())
    }

    /// Count of unresolved hunks.
    pub fn count_unresolved(&self) -> usize {
        self.hunks
            .iter()
            .filter(|h| matches!(h.resolution, Resolution::Unresolved))
            .count()
    }

    /// Are all resolved?
    pub fn is_complete(&self) -> bool {
        self.count_unresolved() == 0 && !self.hunks.is_empty()
    }

    /// Reset all to unresolved.
    pub fn mark_all_unresolved(&mut self) {
        for h in self.hunks.iter_mut() {
            h.resolution = Resolution::Unresolved;
        }
    }

    /// Render the final merged text (concatenated, resolution-applied).
    pub fn render_merged(&self) -> String {
        let mut s = String::new();
        for h in &self.hunks {
            match &h.resolution {
                Resolution::Unresolved => {
                    // Leave a placeholder.
                    s.push_str("<<<<<<< UNRESOLVED ");
                    s.push_str(&h.id);
                    s.push_str(" >>>>>>>\n");
                }
                Resolution::AcceptOurs => s.push_str(&h.ours),
                Resolution::AcceptTheirs => s.push_str(&h.theirs),
                Resolution::AcceptBoth => {
                    s.push_str(&h.ours);
                    s.push_str(&h.theirs);
                }
                Resolution::Manual { body } => s.push_str(body),
            }
        }
        s
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MergeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MergeError::SchemaMismatch);
        }
        for h in &self.hunks {
            if h.id.is_empty() {
                return Err(MergeError::EmptyId);
            }
            if let Resolution::Manual { body } = &h.resolution {
                if body.is_empty() {
                    return Err(MergeError::EmptyBody);
                }
            }
        }
        Ok(())
    }
}

impl Default for MergeConflictUi {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_count_unresolved() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "o", "t").unwrap();
        m.add("h2", "b", "o", "t").unwrap();
        assert_eq!(m.count_unresolved(), 2);
        assert!(!m.is_complete());
    }

    #[test]
    fn resolve_marks_complete() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "o", "t").unwrap();
        m.resolve("h1", Resolution::AcceptOurs).unwrap();
        assert!(m.is_complete());
    }

    #[test]
    fn render_merged_accept_ours() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "base", "OURS", "theirs").unwrap();
        m.resolve("h1", Resolution::AcceptOurs).unwrap();
        assert_eq!(m.render_merged(), "OURS");
    }

    #[test]
    fn render_merged_accept_both() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "A", "B").unwrap();
        m.resolve("h1", Resolution::AcceptBoth).unwrap();
        assert_eq!(m.render_merged(), "AB");
    }

    #[test]
    fn render_merged_manual() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "o", "t").unwrap();
        m.resolve(
            "h1",
            Resolution::Manual {
                body: "custom".into(),
            },
        )
        .unwrap();
        assert_eq!(m.render_merged(), "custom");
    }

    #[test]
    fn render_unresolved_uses_placeholder() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "o", "t").unwrap();
        assert!(m.render_merged().contains("UNRESOLVED h1"));
    }

    #[test]
    fn manual_empty_body_rejected() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "o", "t").unwrap();
        assert!(matches!(
            m.resolve("h1", Resolution::Manual { body: "".into() })
                .unwrap_err(),
            MergeError::EmptyBody
        ));
    }

    #[test]
    fn duplicate_rejected() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "o", "t").unwrap();
        assert!(matches!(
            m.add("h1", "b", "o", "t").unwrap_err(),
            MergeError::DuplicateId(_)
        ));
    }

    #[test]
    fn unknown_resolve_rejected() {
        let mut m = MergeConflictUi::new();
        assert!(matches!(
            m.resolve("nope", Resolution::AcceptOurs).unwrap_err(),
            MergeError::UnknownHunk(_)
        ));
    }

    #[test]
    fn mark_all_unresolved_resets() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "o", "t").unwrap();
        m.resolve("h1", Resolution::AcceptOurs).unwrap();
        m.mark_all_unresolved();
        assert_eq!(m.count_unresolved(), 1);
    }

    #[test]
    fn empty_id_rejected() {
        let mut m = MergeConflictUi::new();
        assert!(matches!(
            m.add("", "b", "o", "t").unwrap_err(),
            MergeError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = MergeConflictUi::new();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            MergeError::SchemaMismatch
        ));
    }

    #[test]
    fn merge_serde_roundtrip() {
        let mut m = MergeConflictUi::new();
        m.add("h1", "b", "o", "t").unwrap();
        m.resolve("h1", Resolution::AcceptBoth).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: MergeConflictUi = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
