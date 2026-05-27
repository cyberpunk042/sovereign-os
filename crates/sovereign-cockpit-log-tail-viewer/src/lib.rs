//! `sovereign-cockpit-log-tail-viewer` — bounded log tail.
//!
//! Cockpit log tails are bounded ring buffers — fixed `capacity`
//! lines. `push(level, ts_ms, source, message)` appends; once full,
//! oldest lines are dropped. `view(filter)` returns lines matching
//! the filter in chronological order. Filters compose: level floor
//! + source allowlist + substring search.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Log level (ordered).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum LogLevel {
    /// trace.
    Trace,
    /// debug.
    Debug,
    /// info.
    Info,
    /// warn.
    Warn,
    /// error.
    Error,
}

/// One log line.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LogLine {
    /// Level.
    pub level: LogLevel,
    /// Timestamp.
    pub ts_ms: u64,
    /// Source label.
    pub source: String,
    /// Message text.
    pub message: String,
}

/// Filter.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Filter {
    /// Minimum level to include (None = all).
    pub min_level: Option<LogLevel>,
    /// Sources to include (empty = all).
    pub sources: Vec<String>,
    /// Substring (case-insensitive) match on message; empty = no filter.
    pub substring: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LogTailViewer {
    /// Schema version.
    pub schema_version: String,
    /// Max lines retained.
    pub capacity: usize,
    /// Ring buffer.
    pub lines: VecDeque<LogLine>,
    /// Lines dropped (over capacity).
    pub dropped: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LogTailError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty source.
    #[error("source empty")]
    EmptySource,
    /// Empty message.
    #[error("message empty")]
    EmptyMessage,
    /// Zero capacity.
    #[error("capacity must be > 0")]
    ZeroCapacity,
}

impl LogTailViewer {
    /// New with capacity.
    pub fn new(capacity: usize) -> Result<Self, LogTailError> {
        if capacity == 0 {
            return Err(LogTailError::ZeroCapacity);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            lines: VecDeque::with_capacity(capacity),
            dropped: 0,
        })
    }

    /// Push a line.
    pub fn push(
        &mut self,
        level: LogLevel,
        ts_ms: u64,
        source: &str,
        message: &str,
    ) -> Result<(), LogTailError> {
        if source.is_empty() {
            return Err(LogTailError::EmptySource);
        }
        if message.is_empty() {
            return Err(LogTailError::EmptyMessage);
        }
        if self.lines.len() == self.capacity {
            self.lines.pop_front();
            self.dropped = self.dropped.saturating_add(1);
        }
        self.lines.push_back(LogLine {
            level,
            ts_ms,
            source: source.into(),
            message: message.into(),
        });
        Ok(())
    }

    /// All currently-retained lines (chronological).
    pub fn all(&self) -> Vec<LogLine> {
        self.lines.iter().cloned().collect()
    }

    /// Filtered view.
    pub fn view(&self, filter: &Filter) -> Vec<LogLine> {
        let q = filter.substring.to_lowercase();
        self.lines
            .iter()
            .filter(|l| {
                if let Some(min) = filter.min_level {
                    if l.level < min {
                        return false;
                    }
                }
                if !filter.sources.is_empty() && !filter.sources.iter().any(|s| s == &l.source) {
                    return false;
                }
                if !q.is_empty() && !l.message.to_lowercase().contains(&q) {
                    return false;
                }
                true
            })
            .cloned()
            .collect()
    }

    /// Drop all lines (keep capacity).
    pub fn clear(&mut self) {
        self.lines.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LogTailError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LogTailError::SchemaMismatch);
        }
        if self.capacity == 0 {
            return Err(LogTailError::ZeroCapacity);
        }
        for l in &self.lines {
            if l.source.is_empty() {
                return Err(LogTailError::EmptySource);
            }
            if l.message.is_empty() {
                return Err(LogTailError::EmptyMessage);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn push_within_capacity() {
        let mut v = LogTailViewer::new(10).unwrap();
        v.push(LogLevel::Info, 0, "core", "hello").unwrap();
        assert_eq!(v.all().len(), 1);
        assert_eq!(v.dropped, 0);
    }

    #[test]
    fn ring_drops_oldest() {
        let mut v = LogTailViewer::new(2).unwrap();
        v.push(LogLevel::Info, 0, "core", "a").unwrap();
        v.push(LogLevel::Info, 1, "core", "b").unwrap();
        v.push(LogLevel::Info, 2, "core", "c").unwrap();
        let all = v.all();
        assert_eq!(all.len(), 2);
        assert_eq!(all[0].message, "b");
        assert_eq!(all[1].message, "c");
        assert_eq!(v.dropped, 1);
    }

    #[test]
    fn filter_by_level_floor() {
        let mut v = LogTailViewer::new(10).unwrap();
        v.push(LogLevel::Debug, 0, "core", "low").unwrap();
        v.push(LogLevel::Warn, 1, "core", "high").unwrap();
        let f = Filter {
            min_level: Some(LogLevel::Warn),
            ..Filter::default()
        };
        let r = v.view(&f);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].message, "high");
    }

    #[test]
    fn filter_by_source() {
        let mut v = LogTailViewer::new(10).unwrap();
        v.push(LogLevel::Info, 0, "core", "a").unwrap();
        v.push(LogLevel::Info, 1, "net", "b").unwrap();
        let f = Filter {
            sources: vec!["net".into()],
            ..Filter::default()
        };
        let r = v.view(&f);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].source, "net");
    }

    #[test]
    fn filter_by_substring_case_insensitive() {
        let mut v = LogTailViewer::new(10).unwrap();
        v.push(LogLevel::Info, 0, "core", "Hello World").unwrap();
        v.push(LogLevel::Info, 1, "core", "Goodbye").unwrap();
        let f = Filter {
            substring: "WORLD".into(),
            ..Filter::default()
        };
        let r = v.view(&f);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].message, "Hello World");
    }

    #[test]
    fn filters_compose() {
        let mut v = LogTailViewer::new(10).unwrap();
        v.push(LogLevel::Debug, 0, "core", "noise").unwrap();
        v.push(LogLevel::Warn, 1, "core", "interesting").unwrap();
        v.push(LogLevel::Warn, 2, "net", "interesting").unwrap();
        let f = Filter {
            min_level: Some(LogLevel::Warn),
            sources: vec!["net".into()],
            substring: "inter".into(),
        };
        let r = v.view(&f);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].source, "net");
    }

    #[test]
    fn clear_keeps_capacity() {
        let mut v = LogTailViewer::new(5).unwrap();
        v.push(LogLevel::Info, 0, "core", "a").unwrap();
        v.clear();
        assert!(v.all().is_empty());
        assert_eq!(v.capacity, 5);
    }

    #[test]
    fn zero_capacity_rejected() {
        assert!(matches!(
            LogTailViewer::new(0).unwrap_err(),
            LogTailError::ZeroCapacity
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut v = LogTailViewer::new(5).unwrap();
        assert!(matches!(
            v.push(LogLevel::Info, 0, "", "m").unwrap_err(),
            LogTailError::EmptySource
        ));
        assert!(matches!(
            v.push(LogLevel::Info, 0, "s", "").unwrap_err(),
            LogTailError::EmptyMessage
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut v = LogTailViewer::new(5).unwrap();
        v.schema_version = "9.9.9".into();
        assert!(matches!(
            v.validate().unwrap_err(),
            LogTailError::SchemaMismatch
        ));
    }

    #[test]
    fn logtail_serde_roundtrip() {
        let mut v = LogTailViewer::new(5).unwrap();
        v.push(LogLevel::Warn, 100, "core", "hello").unwrap();
        let j = serde_json::to_string(&v).unwrap();
        let back: LogTailViewer = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }
}
