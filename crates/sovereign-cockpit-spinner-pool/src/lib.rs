//! `sovereign-cockpit-spinner-pool` — concurrent spinner aggregator.
//!
//! Tracks N concurrent spinners. show_status(now_ms) returns the
//! operator-facing label, suppressing flicker for spinners younger
//! than min_visible_ms.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One spinner.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Spinner {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Wall-clock ms when started.
    pub started_at_ms: u64,
    /// Cancellable by operator?
    pub cancellable: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SpinnerPool {
    /// Schema version.
    pub schema_version: String,
    /// Active spinners.
    pub spinners: Vec<Spinner>,
    /// Minimum visible ms to suppress flicker.
    pub min_visible_ms: u32,
}

/// Status to render.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum SpinnerStatus {
    /// No visible spinner.
    Hidden,
    /// One specific spinner.
    Single {
        /// id.
        id: String,
        /// label.
        label: String,
        /// cancellable.
        cancellable: bool,
    },
    /// Multiple — generic label.
    Multi {
        /// count.
        count: u32,
        /// label.
        label: String,
    },
}

/// Errors.
#[derive(Debug, Error)]
pub enum SpinnerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("spinner id empty")]
    EmptyId,
    /// Empty label.
    #[error("spinner {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate spinner id: {0}")]
    DuplicateId(String),
    /// Unknown id.
    #[error("unknown spinner id: {0}")]
    Unknown(String),
}

impl SpinnerPool {
    /// New.
    pub fn new(min_visible_ms: u32) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            spinners: Vec::new(),
            min_visible_ms,
        }
    }

    /// Start a spinner.
    pub fn start(&mut self, s: Spinner) -> Result<(), SpinnerError> {
        if s.id.is_empty() { return Err(SpinnerError::EmptyId); }
        if s.label.is_empty() { return Err(SpinnerError::EmptyLabel(s.id.clone())); }
        if self.spinners.iter().any(|x| x.id == s.id) {
            return Err(SpinnerError::DuplicateId(s.id));
        }
        self.spinners.push(s);
        Ok(())
    }

    /// Stop.
    pub fn stop(&mut self, id: &str) -> Result<(), SpinnerError> {
        let pos = self.spinners.iter().position(|s| s.id == id)
            .ok_or_else(|| SpinnerError::Unknown(id.into()))?;
        self.spinners.remove(pos);
        Ok(())
    }

    /// Compute display status.
    pub fn show_status(&self, now_ms: u64) -> SpinnerStatus {
        // Filter to spinners visible for >= min_visible_ms.
        let visible: Vec<&Spinner> = self.spinners.iter()
            .filter(|s| now_ms.saturating_sub(s.started_at_ms) >= self.min_visible_ms as u64)
            .collect();
        match visible.len() {
            0 => SpinnerStatus::Hidden,
            1 => {
                let s = visible[0];
                SpinnerStatus::Single {
                    id: s.id.clone(),
                    label: s.label.clone(),
                    cancellable: s.cancellable,
                }
            }
            n => SpinnerStatus::Multi {
                count: n as u32,
                label: format!("{n} background tasks…"),
            },
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SpinnerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SpinnerError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in &self.spinners {
            if s.id.is_empty() { return Err(SpinnerError::EmptyId); }
            if s.label.is_empty() { return Err(SpinnerError::EmptyLabel(s.id.clone())); }
            if !seen.insert(s.id.as_str()) {
                return Err(SpinnerError::DuplicateId(s.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for SpinnerPool {
    fn default() -> Self { Self::new(200) }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spin(id: &str, started: u64) -> Spinner {
        Spinner {
            id: id.into(),
            label: format!("L-{id}"),
            started_at_ms: started,
            cancellable: false,
        }
    }

    #[test]
    fn empty_pool_hidden() {
        let p = SpinnerPool::new(200);
        assert!(matches!(p.show_status(1000), SpinnerStatus::Hidden));
    }

    #[test]
    fn young_spinner_suppressed() {
        let mut p = SpinnerPool::new(200);
        p.start(spin("a", 100)).unwrap();
        assert!(matches!(p.show_status(150), SpinnerStatus::Hidden));
    }

    #[test]
    fn mature_spinner_visible_single() {
        let mut p = SpinnerPool::new(200);
        p.start(spin("a", 100)).unwrap();
        let s = p.show_status(500);
        assert!(matches!(s, SpinnerStatus::Single { .. }));
    }

    #[test]
    fn multi_spinners_aggregated() {
        let mut p = SpinnerPool::new(200);
        p.start(spin("a", 100)).unwrap();
        p.start(spin("b", 100)).unwrap();
        let s = p.show_status(500);
        match s {
            SpinnerStatus::Multi { count, .. } => assert_eq!(count, 2),
            _ => panic!(),
        }
    }

    #[test]
    fn stop_removes() {
        let mut p = SpinnerPool::new(200);
        p.start(spin("a", 100)).unwrap();
        p.stop("a").unwrap();
        assert!(p.spinners.is_empty());
    }

    #[test]
    fn stop_unknown_rejected() {
        let mut p = SpinnerPool::new(200);
        assert!(matches!(p.stop("none").unwrap_err(), SpinnerError::Unknown(_)));
    }

    #[test]
    fn duplicate_rejected() {
        let mut p = SpinnerPool::new(200);
        p.start(spin("a", 100)).unwrap();
        assert!(matches!(p.start(spin("a", 100)).unwrap_err(), SpinnerError::DuplicateId(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut p = SpinnerPool::new(200);
        assert!(matches!(p.start(spin("", 100)).unwrap_err(), SpinnerError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut p = SpinnerPool::new(200);
        let mut s = spin("a", 100);
        s.label = String::new();
        assert!(matches!(p.start(s).unwrap_err(), SpinnerError::EmptyLabel(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = SpinnerPool::new(200);
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), SpinnerError::SchemaMismatch));
    }

    #[test]
    fn status_serde_kebab() {
        let s = SpinnerStatus::Hidden;
        assert!(serde_json::to_string(&s).unwrap().contains("\"kind\":\"hidden\""));
    }

    #[test]
    fn pool_serde_roundtrip() {
        let mut p = SpinnerPool::new(200);
        p.start(spin("a", 100)).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: SpinnerPool = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
