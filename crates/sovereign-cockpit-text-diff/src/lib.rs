//! `sovereign-cockpit-text-diff` — line-level diff projection.
//!
//! Simple approach: find longest common prefix + longest common
//! suffix. Middle of `before` becomes Removed, middle of `after`
//! becomes Added. Sufficient for the small in-cockpit diffs (large
//! diffs delegated to a server-side diff engine).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One diff row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum DiffRow {
    /// Same in both.
    Same {
        /// line.
        line: String,
    },
    /// Added in after.
    Added {
        /// line.
        line: String,
    },
    /// Removed from before.
    Removed {
        /// line.
        line: String,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TextDiff {
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

impl TextDiff {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    /// Diff before vs after at line granularity.
    pub fn diff(before: &[String], after: &[String]) -> Vec<DiffRow> {
        let n = before.len();
        let m = after.len();
        // Longest common prefix.
        let mut prefix = 0usize;
        while prefix < n && prefix < m && before[prefix] == after[prefix] {
            prefix += 1;
        }
        // Longest common suffix (not overlapping the prefix).
        let mut suffix = 0usize;
        while suffix < n - prefix
            && suffix < m - prefix
            && before[n - 1 - suffix] == after[m - 1 - suffix]
        {
            suffix += 1;
        }
        let mut out: Vec<DiffRow> = Vec::with_capacity(n + m);
        for line in &before[..prefix] {
            out.push(DiffRow::Same { line: line.clone() });
        }
        for line in &before[prefix..n - suffix] {
            out.push(DiffRow::Removed { line: line.clone() });
        }
        for line in &after[prefix..m - suffix] {
            out.push(DiffRow::Added { line: line.clone() });
        }
        for line in &after[m - suffix..] {
            out.push(DiffRow::Same { line: line.clone() });
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DiffError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DiffError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for TextDiff {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lines(v: &[&str]) -> Vec<String> {
        v.iter().map(|s| (*s).to_string()).collect()
    }

    #[test]
    fn identical_all_same() {
        let r = TextDiff::diff(&lines(&["a", "b", "c"]), &lines(&["a", "b", "c"]));
        for row in &r {
            assert!(matches!(row, DiffRow::Same { .. }));
        }
    }

    #[test]
    fn pure_addition() {
        let r = TextDiff::diff(&lines(&[]), &lines(&["a", "b"]));
        for row in &r {
            assert!(matches!(row, DiffRow::Added { .. }));
        }
    }

    #[test]
    fn pure_removal() {
        let r = TextDiff::diff(&lines(&["a", "b"]), &lines(&[]));
        for row in &r {
            assert!(matches!(row, DiffRow::Removed { .. }));
        }
    }

    #[test]
    fn middle_change() {
        let b = lines(&["a", "old", "c"]);
        let a = lines(&["a", "new", "c"]);
        let r = TextDiff::diff(&b, &a);
        // Expect: Same a, Removed old, Added new, Same c
        assert_eq!(r.len(), 4);
        assert!(matches!(&r[0], DiffRow::Same { line } if line == "a"));
        assert!(matches!(&r[1], DiffRow::Removed { line } if line == "old"));
        assert!(matches!(&r[2], DiffRow::Added { line } if line == "new"));
        assert!(matches!(&r[3], DiffRow::Same { line } if line == "c"));
    }

    #[test]
    fn longer_after() {
        let b = lines(&["a", "c"]);
        let a = lines(&["a", "b", "c"]);
        let r = TextDiff::diff(&b, &a);
        assert!(
            r.iter()
                .any(|x| matches!(x, DiffRow::Added { line } if line == "b"))
        );
    }

    #[test]
    fn longer_before() {
        let b = lines(&["a", "b", "c"]);
        let a = lines(&["a", "c"]);
        let r = TextDiff::diff(&b, &a);
        assert!(
            r.iter()
                .any(|x| matches!(x, DiffRow::Removed { line } if line == "b"))
        );
    }

    #[test]
    fn both_empty_returns_empty() {
        let r = TextDiff::diff(&[], &[]);
        assert!(r.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = TextDiff::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DiffError::SchemaMismatch
        ));
    }

    #[test]
    fn row_serde_kebab() {
        let r = DiffRow::Added { line: "x".into() };
        assert!(
            serde_json::to_string(&r)
                .unwrap()
                .contains("\"kind\":\"added\"")
        );
    }

    #[test]
    fn diff_serde_roundtrip() {
        let rows = TextDiff::diff(&lines(&["a", "b"]), &lines(&["a", "c"]));
        let j = serde_json::to_string(&rows).unwrap();
        let back: Vec<DiffRow> = serde_json::from_str(&j).unwrap();
        assert_eq!(rows, back);
    }
}
