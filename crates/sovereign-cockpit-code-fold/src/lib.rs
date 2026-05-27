//! `sovereign-cockpit-code-fold` — code-fold regions.
//!
//! Region{id, start_line, end_line, folded}. add registers
//! (start<=end). toggle(id) flips folded. visible_lines(total)
//! returns the line numbers visible after applying current
//! folds (skipping start+1..=end of each folded region).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Region.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Region {
    /// Id.
    pub id: String,
    /// Start line (1-based).
    pub start_line: u32,
    /// End line (1-based, >= start).
    pub end_line: u32,
    /// Folded.
    pub folded: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CodeFold {
    /// Schema version.
    pub schema_version: String,
    /// id → region.
    pub regions: BTreeMap<String, Region>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FoldError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Bad range.
    #[error("start_line must be <= end_line and >= 1")]
    BadRange,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown id: {0}")]
    UnknownId(String),
}

impl CodeFold {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            regions: BTreeMap::new(),
        }
    }

    /// Add region (unfolded).
    pub fn add(&mut self, id: &str, start_line: u32, end_line: u32) -> Result<(), FoldError> {
        if id.is_empty() {
            return Err(FoldError::EmptyId);
        }
        if start_line == 0 || start_line > end_line {
            return Err(FoldError::BadRange);
        }
        if self.regions.contains_key(id) {
            return Err(FoldError::DuplicateId(id.into()));
        }
        self.regions.insert(
            id.into(),
            Region {
                id: id.into(),
                start_line,
                end_line,
                folded: false,
            },
        );
        Ok(())
    }

    /// Toggle folded.
    pub fn toggle(&mut self, id: &str) -> Result<bool, FoldError> {
        let r = self
            .regions
            .get_mut(id)
            .ok_or_else(|| FoldError::UnknownId(id.into()))?;
        r.folded = !r.folded;
        Ok(r.folded)
    }

    /// Set folded explicitly.
    pub fn set_folded(&mut self, id: &str, folded: bool) -> Result<(), FoldError> {
        let r = self
            .regions
            .get_mut(id)
            .ok_or_else(|| FoldError::UnknownId(id.into()))?;
        r.folded = folded;
        Ok(())
    }

    /// Visible line numbers (1..=total_lines, skipping hidden lines).
    pub fn visible_lines(&self, total_lines: u32) -> Vec<u32> {
        // Mark hidden lines.
        let mut hidden = vec![false; total_lines as usize + 1]; // 1-based.
        for r in self.regions.values() {
            if !r.folded {
                continue;
            }
            // Hide start_line+1 .. end_line (start_line itself remains as fold-anchor).
            let lo = (r.start_line + 1).min(total_lines + 1) as usize;
            let hi = r.end_line.min(total_lines) as usize;
            if lo <= hi {
                for i in lo..=hi {
                    hidden[i] = true;
                }
            }
        }
        (1..=total_lines).filter(|&l| !hidden[l as usize]).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FoldError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FoldError::SchemaMismatch);
        }
        for r in self.regions.values() {
            if r.id.is_empty() {
                return Err(FoldError::EmptyId);
            }
            if r.start_line == 0 || r.start_line > r.end_line {
                return Err(FoldError::BadRange);
            }
        }
        Ok(())
    }
}

impl Default for CodeFold {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_toggle() {
        let mut f = CodeFold::new();
        f.add("r1", 3, 7).unwrap();
        assert!(f.toggle("r1").unwrap()); // now folded
        assert!(!f.toggle("r1").unwrap()); // unfolded
    }

    #[test]
    fn visible_lines_no_folds() {
        let f = CodeFold::new();
        let v = f.visible_lines(5);
        assert_eq!(v, vec![1, 2, 3, 4, 5]);
    }

    #[test]
    fn folded_hides_body() {
        let mut f = CodeFold::new();
        f.add("r1", 3, 7).unwrap();
        f.set_folded("r1", true).unwrap();
        let v = f.visible_lines(10);
        // Lines 4..=7 hidden; 1,2,3,8,9,10 visible.
        assert_eq!(v, vec![1, 2, 3, 8, 9, 10]);
    }

    #[test]
    fn multiple_folds() {
        let mut f = CodeFold::new();
        f.add("a", 2, 4).unwrap();
        f.add("b", 6, 8).unwrap();
        f.set_folded("a", true).unwrap();
        f.set_folded("b", true).unwrap();
        let v = f.visible_lines(10);
        // Hidden: 3,4 (from a) and 7,8 (from b). Visible: 1,2,5,6,9,10.
        assert_eq!(v, vec![1, 2, 5, 6, 9, 10]);
    }

    #[test]
    fn bad_range_rejected() {
        let mut f = CodeFold::new();
        assert!(matches!(f.add("a", 0, 5).unwrap_err(), FoldError::BadRange));
        assert!(matches!(f.add("a", 5, 3).unwrap_err(), FoldError::BadRange));
    }

    #[test]
    fn unknown_toggle_rejected() {
        let mut f = CodeFold::new();
        assert!(matches!(
            f.toggle("nope").unwrap_err(),
            FoldError::UnknownId(_)
        ));
    }

    #[test]
    fn duplicate_rejected() {
        let mut f = CodeFold::new();
        f.add("a", 1, 5).unwrap();
        assert!(matches!(
            f.add("a", 6, 10).unwrap_err(),
            FoldError::DuplicateId(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = CodeFold::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FoldError::SchemaMismatch
        ));
    }

    #[test]
    fn fold_serde_roundtrip() {
        let mut f = CodeFold::new();
        f.add("r1", 1, 5).unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: CodeFold = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
