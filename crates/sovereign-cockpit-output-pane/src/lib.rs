//! `sovereign-cockpit-output-pane` — captured stdout/stderr pane.
//!
//! Line{stream, ts_ms, text}. push_stdout / push_stderr append a
//! line; bounded by max_lines (front-evicted). filter(opts) returns
//! references to lines matching the active stream/substring filter.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Stream.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Stream {
    /// stdout.
    Stdout,
    /// stderr.
    Stderr,
}

/// Line.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Line {
    /// Stream.
    pub stream: Stream,
    /// Captured ts ms.
    pub ts_ms: u64,
    /// Body (no trailing newline).
    pub text: String,
}

/// Filter.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Filter {
    /// Restrict to a stream.
    pub stream: Option<Stream>,
    /// Substring match (empty = no filter).
    pub contains: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct OutputPane {
    /// Schema version.
    pub schema_version: String,
    /// Max retained lines.
    pub max_lines: u32,
    /// Lines (front=oldest).
    pub lines: VecDeque<Line>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum OutputError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero cap.
    #[error("max_lines must be >= 1")]
    ZeroCap,
}

impl OutputPane {
    /// New.
    pub fn new(max_lines: u32) -> Result<Self, OutputError> {
        if max_lines == 0 {
            return Err(OutputError::ZeroCap);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            max_lines,
            lines: VecDeque::new(),
        })
    }

    /// Append stdout.
    pub fn push_stdout(&mut self, ts_ms: u64, text: &str) {
        self.push(Stream::Stdout, ts_ms, text);
    }

    /// Append stderr.
    pub fn push_stderr(&mut self, ts_ms: u64, text: &str) {
        self.push(Stream::Stderr, ts_ms, text);
    }

    fn push(&mut self, stream: Stream, ts_ms: u64, text: &str) {
        self.lines.push_back(Line {
            stream,
            ts_ms,
            text: text.into(),
        });
        while self.lines.len() > self.max_lines as usize {
            self.lines.pop_front();
        }
    }

    /// Clear.
    pub fn clear(&mut self) {
        self.lines.clear();
    }

    /// Filtered view.
    pub fn filter(&self, f: &Filter) -> Vec<&Line> {
        self.lines
            .iter()
            .filter(|l| {
                if let Some(s) = f.stream
                    && l.stream != s
                {
                    return false;
                }
                if !f.contains.is_empty() && !l.text.contains(&f.contains) {
                    return false;
                }
                true
            })
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), OutputError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(OutputError::SchemaMismatch);
        }
        if self.max_lines == 0 {
            return Err(OutputError::ZeroCap);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn push_appends() {
        let mut p = OutputPane::new(10).unwrap();
        p.push_stdout(0, "hello");
        p.push_stderr(1, "world");
        assert_eq!(p.lines.len(), 2);
        assert_eq!(p.lines[0].stream, Stream::Stdout);
        assert_eq!(p.lines[1].stream, Stream::Stderr);
    }

    #[test]
    fn bounded_evicts_front() {
        let mut p = OutputPane::new(2).unwrap();
        p.push_stdout(0, "a");
        p.push_stdout(1, "b");
        p.push_stdout(2, "c");
        assert_eq!(p.lines.len(), 2);
        assert_eq!(p.lines[0].text, "b");
        assert_eq!(p.lines[1].text, "c");
    }

    #[test]
    fn filter_by_stream() {
        let mut p = OutputPane::new(10).unwrap();
        p.push_stdout(0, "out1");
        p.push_stderr(1, "err1");
        p.push_stdout(2, "out2");
        let f = Filter {
            stream: Some(Stream::Stdout),
            contains: String::new(),
        };
        let r = p.filter(&f);
        assert_eq!(r.len(), 2);
        assert!(r.iter().all(|l| l.stream == Stream::Stdout));
    }

    #[test]
    fn filter_by_substring() {
        let mut p = OutputPane::new(10).unwrap();
        p.push_stdout(0, "ERROR connection refused");
        p.push_stdout(1, "INFO connected");
        p.push_stderr(2, "ERROR auth failed");
        let f = Filter {
            stream: None,
            contains: "ERROR".into(),
        };
        let r = p.filter(&f);
        assert_eq!(r.len(), 2);
    }

    #[test]
    fn clear_drops_all() {
        let mut p = OutputPane::new(10).unwrap();
        p.push_stdout(0, "x");
        p.clear();
        assert!(p.lines.is_empty());
    }

    #[test]
    fn zero_cap_rejected() {
        assert!(matches!(
            OutputPane::new(0).unwrap_err(),
            OutputError::ZeroCap
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = OutputPane::new(10).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            OutputError::SchemaMismatch
        ));
    }

    #[test]
    fn pane_serde_roundtrip() {
        let mut p = OutputPane::new(10).unwrap();
        p.push_stdout(0, "hi");
        let j = serde_json::to_string(&p).unwrap();
        let back: OutputPane = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
