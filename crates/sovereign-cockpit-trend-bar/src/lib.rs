//! `sovereign-cockpit-trend-bar` — segmented proportional bar.
//!
//! Segment{label, value}. add appends; render returns
//! Vec<RenderedSegment{label, width_bp}> with each segment's
//! width in basis points (0..=10000). Total widths sum to 10000
//! when total>0; empty when all values are 0.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Segment.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Segment {
    /// Label.
    pub label: String,
    /// Value.
    pub value: u64,
}

/// Rendered segment.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RenderedSegment {
    /// Label.
    pub label: String,
    /// Width in basis points (0..=10000).
    pub width_bp: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TrendBar {
    /// Schema version.
    pub schema_version: String,
    /// Segments.
    pub segments: Vec<Segment>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TrendError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate label: {0}")]
    DuplicateLabel(String),
}

impl TrendBar {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            segments: Vec::new(),
        }
    }

    /// Add segment.
    pub fn add(&mut self, label: &str, value: u64) -> Result<(), TrendError> {
        if label.is_empty() {
            return Err(TrendError::EmptyLabel);
        }
        if self.segments.iter().any(|s| s.label == label) {
            return Err(TrendError::DuplicateLabel(label.into()));
        }
        self.segments.push(Segment {
            label: label.into(),
            value,
        });
        Ok(())
    }

    /// Set value on existing segment.
    pub fn set(&mut self, label: &str, value: u64) -> Result<(), TrendError> {
        if label.is_empty() {
            return Err(TrendError::EmptyLabel);
        }
        if let Some(s) = self.segments.iter_mut().find(|s| s.label == label) {
            s.value = value;
            return Ok(());
        }
        self.segments.push(Segment {
            label: label.into(),
            value,
        });
        Ok(())
    }

    /// Total value.
    pub fn total(&self) -> u64 {
        self.segments.iter().map(|s| s.value).sum()
    }

    /// Render proportional widths.
    pub fn render(&self) -> Vec<RenderedSegment> {
        let total = self.total();
        if total == 0 {
            return self
                .segments
                .iter()
                .map(|s| RenderedSegment {
                    label: s.label.clone(),
                    width_bp: 0,
                })
                .collect();
        }
        // First-pass widths.
        let mut widths: Vec<u32> = self
            .segments
            .iter()
            .map(|s| ((s.value as u128 * 10_000) / total as u128) as u32)
            .collect();
        // Adjust last to make sum exactly 10000.
        let sum: u32 = widths.iter().sum();
        if !widths.is_empty() && sum != 10_000 {
            let diff = 10_000i64 - sum as i64;
            let last = widths.last_mut().unwrap();
            *last = (*last as i64 + diff).max(0) as u32;
        }
        self.segments
            .iter()
            .zip(widths)
            .map(|(s, w)| RenderedSegment {
                label: s.label.clone(),
                width_bp: w,
            })
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TrendError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TrendError::SchemaMismatch);
        }
        for s in &self.segments {
            if s.label.is_empty() {
                return Err(TrendError::EmptyLabel);
            }
        }
        Ok(())
    }
}

impl Default for TrendBar {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn proportions_sum_to_10000() {
        let mut b = TrendBar::new();
        b.add("pass", 60).unwrap();
        b.add("warn", 30).unwrap();
        b.add("fail", 10).unwrap();
        let r = b.render();
        let sum: u32 = r.iter().map(|s| s.width_bp).sum();
        assert_eq!(sum, 10_000);
    }

    #[test]
    fn even_distribution() {
        let mut b = TrendBar::new();
        b.add("a", 1).unwrap();
        b.add("b", 1).unwrap();
        b.add("c", 1).unwrap();
        b.add("d", 1).unwrap();
        let r = b.render();
        assert_eq!(r[0].width_bp, 2500);
    }

    #[test]
    fn zero_total_all_zero() {
        let mut b = TrendBar::new();
        b.add("a", 0).unwrap();
        b.add("b", 0).unwrap();
        let r = b.render();
        assert!(r.iter().all(|s| s.width_bp == 0));
    }

    #[test]
    fn set_creates_or_updates() {
        let mut b = TrendBar::new();
        b.set("a", 10).unwrap();
        assert_eq!(b.total(), 10);
        b.set("a", 50).unwrap();
        assert_eq!(b.total(), 50);
    }

    #[test]
    fn duplicate_add_rejected() {
        let mut b = TrendBar::new();
        b.add("a", 1).unwrap();
        assert!(matches!(
            b.add("a", 2).unwrap_err(),
            TrendError::DuplicateLabel(_)
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut b = TrendBar::new();
        assert!(matches!(b.add("", 1).unwrap_err(), TrendError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = TrendBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            TrendError::SchemaMismatch
        ));
    }

    #[test]
    fn bar_serde_roundtrip() {
        let mut b = TrendBar::new();
        b.add("a", 1).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: TrendBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
