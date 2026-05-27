//! `sovereign-cockpit-code-gutter` — per-line annotations + width hint.
//!
//! Holds `Annotation` entries keyed by 1-based line number. Many
//! annotation kinds per line are allowed; only the highest-precedence
//! one is rendered (Error > Warning > Info > Breakpoint > DiffModified
//! > DiffAdded > DiffRemoved).
//!
//! `gutter_width_chars(total_lines)` returns the digit count for the
//! line-number column plus 2 (glyph + space), so the chrome can size
//! the gutter without measuring.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Annotation kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Ord, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AnnotationKind {
    /// Removed line.
    DiffRemoved,
    /// Added line.
    DiffAdded,
    /// Modified line.
    DiffModified,
    /// Breakpoint.
    Breakpoint,
    /// Info.
    Info,
    /// Warning.
    Warning,
    /// Error.
    Error,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CodeGutter {
    /// Schema version.
    pub schema_version: String,
    /// Per-line annotations (line → set).
    pub annotations: BTreeMap<u32, Vec<AnnotationKind>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GutterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// line zero.
    #[error("line is 1-based; 0 not allowed")]
    LineZero,
}

impl CodeGutter {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            annotations: BTreeMap::new(),
        }
    }

    /// Add an annotation on `line` (1-based).
    pub fn add(&mut self, line: u32, kind: AnnotationKind) -> Result<(), GutterError> {
        if line == 0 {
            return Err(GutterError::LineZero);
        }
        let v = self.annotations.entry(line).or_default();
        if !v.contains(&kind) {
            v.push(kind);
        }
        Ok(())
    }

    /// Remove a specific kind on `line`. Returns true if removed.
    pub fn remove(&mut self, line: u32, kind: AnnotationKind) -> bool {
        if let Some(v) = self.annotations.get_mut(&line)
            && let Some(pos) = v.iter().position(|k| *k == kind)
        {
            v.remove(pos);
            if v.is_empty() {
                self.annotations.remove(&line);
            }
            return true;
        }
        false
    }

    /// Highest-precedence annotation on `line`, if any.
    pub fn winner(&self, line: u32) -> Option<AnnotationKind> {
        self.annotations
            .get(&line)
            .and_then(|v| v.iter().copied().max())
    }

    /// Gutter width in chars: digit count of total_lines + 2.
    pub fn gutter_width_chars(&self, total_lines: u32) -> u32 {
        let digits = if total_lines == 0 {
            1
        } else {
            let mut n = total_lines;
            let mut d = 0u32;
            while n > 0 {
                d += 1;
                n /= 10;
            }
            d
        };
        digits + 2
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GutterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GutterError::SchemaMismatch);
        }
        if self.annotations.keys().any(|k| *k == 0) {
            return Err(GutterError::LineZero);
        }
        Ok(())
    }
}

impl Default for CodeGutter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_winner() {
        let mut g = CodeGutter::new();
        g.add(10, AnnotationKind::Info).unwrap();
        g.add(10, AnnotationKind::Error).unwrap();
        assert_eq!(g.winner(10), Some(AnnotationKind::Error));
    }

    #[test]
    fn no_duplicates() {
        let mut g = CodeGutter::new();
        g.add(1, AnnotationKind::Warning).unwrap();
        g.add(1, AnnotationKind::Warning).unwrap();
        assert_eq!(g.annotations[&1].len(), 1);
    }

    #[test]
    fn remove_clears_line_when_empty() {
        let mut g = CodeGutter::new();
        g.add(2, AnnotationKind::Breakpoint).unwrap();
        assert!(g.remove(2, AnnotationKind::Breakpoint));
        assert!(!g.annotations.contains_key(&2));
    }

    #[test]
    fn remove_unknown_returns_false() {
        let mut g = CodeGutter::new();
        assert!(!g.remove(2, AnnotationKind::Breakpoint));
    }

    #[test]
    fn line_zero_rejected() {
        let mut g = CodeGutter::new();
        assert!(matches!(
            g.add(0, AnnotationKind::Info).unwrap_err(),
            GutterError::LineZero
        ));
    }

    #[test]
    fn precedence_diff_under_error() {
        let mut g = CodeGutter::new();
        g.add(5, AnnotationKind::DiffAdded).unwrap();
        g.add(5, AnnotationKind::Error).unwrap();
        assert_eq!(g.winner(5), Some(AnnotationKind::Error));
    }

    #[test]
    fn gutter_width_basic() {
        let g = CodeGutter::new();
        assert_eq!(g.gutter_width_chars(0), 3);
        assert_eq!(g.gutter_width_chars(9), 3);
        assert_eq!(g.gutter_width_chars(10), 4);
        assert_eq!(g.gutter_width_chars(999), 5);
        assert_eq!(g.gutter_width_chars(1000), 6);
    }

    #[test]
    fn winner_none_when_empty() {
        let g = CodeGutter::new();
        assert_eq!(g.winner(1), None);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = CodeGutter::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            GutterError::SchemaMismatch
        ));
    }

    #[test]
    fn gutter_serde_roundtrip() {
        let mut g = CodeGutter::new();
        g.add(7, AnnotationKind::Warning).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: CodeGutter = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
