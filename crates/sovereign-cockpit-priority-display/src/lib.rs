//! `sovereign-cockpit-priority-display` — Priority → display tokens.
//!
//! Pure mapping: each `Priority` resolves to `(label, color_token,
//! glyph)` so every chrome surface shows the same chip for the same
//! priority.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Priority.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Ord, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Priority {
    /// Low.
    Low,
    /// Medium.
    Med,
    /// High.
    High,
    /// Critical.
    Critical,
    /// Blocker.
    Blocker,
}

/// Display tokens.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct DisplayTokens {
    /// Display label.
    pub label: &'static str,
    /// Theme color token (e.g. "color.priority.high").
    pub color_token: &'static str,
    /// Single-char glyph.
    pub glyph: &'static str,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PriorityDisplay {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PriorityError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl PriorityDisplay {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    /// Resolve.
    pub fn tokens(&self, p: Priority) -> DisplayTokens {
        match p {
            Priority::Low => DisplayTokens {
                label: "Low",
                color_token: "color.priority.low",
                glyph: "↓",
            },
            Priority::Med => DisplayTokens {
                label: "Medium",
                color_token: "color.priority.med",
                glyph: "=",
            },
            Priority::High => DisplayTokens {
                label: "High",
                color_token: "color.priority.high",
                glyph: "↑",
            },
            Priority::Critical => DisplayTokens {
                label: "Critical",
                color_token: "color.priority.critical",
                glyph: "⚠",
            },
            Priority::Blocker => DisplayTokens {
                label: "Blocker",
                color_token: "color.priority.blocker",
                glyph: "⛔",
            },
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PriorityError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PriorityError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for PriorityDisplay {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ordering() {
        assert!(Priority::Low < Priority::Med);
        assert!(Priority::Med < Priority::High);
        assert!(Priority::High < Priority::Critical);
        assert!(Priority::Critical < Priority::Blocker);
    }

    #[test]
    fn each_priority_has_tokens() {
        let p = PriorityDisplay::new();
        for &x in &[
            Priority::Low,
            Priority::Med,
            Priority::High,
            Priority::Critical,
            Priority::Blocker,
        ] {
            let t = p.tokens(x);
            assert!(!t.label.is_empty());
            assert!(!t.color_token.is_empty());
            assert!(!t.glyph.is_empty());
        }
    }

    #[test]
    fn distinct_labels() {
        let p = PriorityDisplay::new();
        let labels: Vec<_> = [
            Priority::Low,
            Priority::Med,
            Priority::High,
            Priority::Critical,
            Priority::Blocker,
        ]
        .iter()
        .map(|&x| p.tokens(x).label)
        .collect();
        let mut sorted = labels.clone();
        sorted.sort();
        sorted.dedup();
        assert_eq!(sorted.len(), labels.len());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = PriorityDisplay::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PriorityError::SchemaMismatch
        ));
    }

    #[test]
    fn display_serde_roundtrip() {
        let p = PriorityDisplay::new();
        let j = serde_json::to_string(&p).unwrap();
        let back: PriorityDisplay = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
