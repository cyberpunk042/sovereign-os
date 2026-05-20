//! `sovereign-cockpit-stack-trace-viewer` — stack-trace frame viewer.
//!
//! Frame{idx, file, line, fn_name, in_project}. classify rules
//! are pure: frame is in-project iff its file path matches a
//! project prefix. render(collapse_deps) returns a Vec<RenderRow>
//! where contiguous out-of-project frames are folded into a
//! Collapsed{count} row when collapse_deps is true.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Frame.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Frame {
    /// Index from bottom (0 = innermost).
    pub idx: u32,
    /// File path.
    pub file: String,
    /// Line number.
    pub line: u32,
    /// Function name.
    pub fn_name: String,
    /// True iff in-project (computed by classify).
    pub in_project: bool,
}

/// Render row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum RenderRow {
    /// Frame row.
    Frame {
        /// Frame.
        frame: Frame,
    },
    /// Collapsed dep block.
    Collapsed {
        /// Number of frames collapsed.
        count: u32,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StackTraceViewer {
    /// Schema version.
    pub schema_version: String,
    /// Project prefixes for in-project detection.
    pub project_prefixes: Vec<String>,
    /// Frames in display order (top-of-stack first).
    pub frames: Vec<Frame>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StackError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("file empty")]
    EmptyFile,
    /// Empty.
    #[error("fn_name empty")]
    EmptyFn,
}

impl StackTraceViewer {
    /// New.
    pub fn new(project_prefixes: Vec<String>) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            project_prefixes,
            frames: Vec::new(),
        }
    }

    /// Add a frame; classifies in_project against project_prefixes.
    pub fn push(&mut self, file: &str, line: u32, fn_name: &str) -> Result<(), StackError> {
        if file.is_empty() { return Err(StackError::EmptyFile); }
        if fn_name.is_empty() { return Err(StackError::EmptyFn); }
        let in_project = self.project_prefixes.iter().any(|p| file.starts_with(p));
        let idx = self.frames.len() as u32;
        self.frames.push(Frame {
            idx, file: file.into(), line, fn_name: fn_name.into(), in_project,
        });
        Ok(())
    }

    /// Render with optional dep collapsing.
    pub fn render(&self, collapse_deps: bool) -> Vec<RenderRow> {
        if !collapse_deps {
            return self.frames.iter().map(|f| RenderRow::Frame { frame: f.clone() }).collect();
        }
        let mut out = Vec::new();
        let mut run = 0u32;
        for f in &self.frames {
            if !f.in_project {
                run += 1;
            } else {
                if run > 0 {
                    out.push(RenderRow::Collapsed { count: run });
                    run = 0;
                }
                out.push(RenderRow::Frame { frame: f.clone() });
            }
        }
        if run > 0 { out.push(RenderRow::Collapsed { count: run }); }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StackError> {
        if self.schema_version != SCHEMA_VERSION { return Err(StackError::SchemaMismatch); }
        for f in &self.frames {
            if f.file.is_empty() { return Err(StackError::EmptyFile); }
            if f.fn_name.is_empty() { return Err(StackError::EmptyFn); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v() -> StackTraceViewer {
        let mut v = StackTraceViewer::new(vec!["src/".into()]);
        v.push("src/main.rs", 10, "main").unwrap();
        v.push("/dep/foo.rs", 20, "dep::foo").unwrap();
        v.push("/dep/bar.rs", 30, "dep::bar").unwrap();
        v.push("src/lib.rs", 40, "do_thing").unwrap();
        v.push("/dep/baz.rs", 50, "dep::baz").unwrap();
        v
    }

    #[test]
    fn classifies_in_project() {
        let v = v();
        assert!(v.frames[0].in_project);
        assert!(!v.frames[1].in_project);
        assert!(v.frames[3].in_project);
    }

    #[test]
    fn render_no_collapse_returns_all() {
        let v = v();
        let r = v.render(false);
        assert_eq!(r.len(), 5);
        assert!(r.iter().all(|x| matches!(x, RenderRow::Frame { .. })));
    }

    #[test]
    fn render_collapse_folds_runs() {
        let v = v();
        let r = v.render(true);
        // src/main → 2 collapsed → src/lib → 1 collapsed.
        assert_eq!(r.len(), 4);
        match &r[1] {
            RenderRow::Collapsed { count } => assert_eq!(*count, 2),
            _ => panic!(),
        }
        match &r[3] {
            RenderRow::Collapsed { count } => assert_eq!(*count, 1),
            _ => panic!(),
        }
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut v = StackTraceViewer::new(vec![]);
        assert!(matches!(v.push("", 0, "f").unwrap_err(), StackError::EmptyFile));
        assert!(matches!(v.push("file", 0, "").unwrap_err(), StackError::EmptyFn));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut v = StackTraceViewer::new(vec![]);
        v.schema_version = "9.9.9".into();
        assert!(matches!(v.validate().unwrap_err(), StackError::SchemaMismatch));
    }

    #[test]
    fn viewer_serde_roundtrip() {
        let v = v();
        let j = serde_json::to_string(&v).unwrap();
        let back: StackTraceViewer = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }
}
