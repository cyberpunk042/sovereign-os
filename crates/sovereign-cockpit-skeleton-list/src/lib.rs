//! `sovereign-cockpit-skeleton-list` — list-shape skeleton loader.
//!
//! Renders N placeholder rows with deterministic-but-randomized
//! widths (60%, 80%, 100% of container) so the loading state
//! doesn't look like a uniform stripe. Transitions to Loaded when
//! data arrives.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Loading state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LoadState {
    /// Skeleton displayed.
    Loading,
    /// Loaded — skeleton hidden.
    Loaded,
    /// Failed — error UI shown.
    Failed,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkeletonList {
    /// Schema version.
    pub schema_version: String,
    /// Row count to render in Loading.
    pub row_count: u32,
    /// Seed for deterministic width pattern.
    pub seed: u64,
    /// Current state.
    pub state: LoadState,
    /// Error message (when Failed).
    pub error: Option<String>,
}

/// One placeholder row.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkeletonRow {
    /// Row index.
    pub index: u32,
    /// Width as percent of container [60..=100].
    pub width_pct: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SkeletonError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// row_count zero.
    #[error("row_count is zero")]
    RowCountZero,
}

impl SkeletonList {
    /// New (Loading state, default 6 rows).
    pub fn new(row_count: u32, seed: u64) -> Result<Self, SkeletonError> {
        if row_count == 0 { return Err(SkeletonError::RowCountZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            row_count,
            seed,
            state: LoadState::Loading,
            error: None,
        })
    }

    /// Mark loaded.
    pub fn loaded(&mut self) {
        self.state = LoadState::Loaded;
        self.error = None;
    }

    /// Mark failed.
    pub fn failed(&mut self, msg: &str) {
        self.state = LoadState::Failed;
        self.error = Some(msg.into());
    }

    /// Compute rows (only meaningful in Loading state).
    pub fn rows(&self) -> Vec<SkeletonRow> {
        let mut out: Vec<SkeletonRow> = Vec::with_capacity(self.row_count as usize);
        for i in 0..self.row_count {
            // Deterministic pseudo-random pattern: hash(seed, i) % 5 → 60/70/80/90/100.
            let h = self.seed.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(i as u64);
            let bucket = (h >> 16) % 5;
            let width_pct = 60 + (bucket * 10) as u8;
            out.push(SkeletonRow { index: i, width_pct });
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SkeletonError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SkeletonError::SchemaMismatch);
        }
        if self.row_count == 0 { return Err(SkeletonError::RowCountZero); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn row_count_zero_rejected() {
        assert!(matches!(SkeletonList::new(0, 42).unwrap_err(), SkeletonError::RowCountZero));
    }

    #[test]
    fn initial_loading() {
        let s = SkeletonList::new(6, 42).unwrap();
        assert_eq!(s.state, LoadState::Loading);
    }

    #[test]
    fn loaded_clears_error() {
        let mut s = SkeletonList::new(6, 42).unwrap();
        s.failed("net");
        s.loaded();
        assert_eq!(s.state, LoadState::Loaded);
        assert!(s.error.is_none());
    }

    #[test]
    fn failed_records_error() {
        let mut s = SkeletonList::new(6, 42).unwrap();
        s.failed("timeout");
        assert_eq!(s.state, LoadState::Failed);
        assert_eq!(s.error.as_deref(), Some("timeout"));
    }

    #[test]
    fn rows_returns_n() {
        let s = SkeletonList::new(10, 42).unwrap();
        assert_eq!(s.rows().len(), 10);
    }

    #[test]
    fn rows_width_in_expected_range() {
        let s = SkeletonList::new(50, 42).unwrap();
        for r in s.rows() {
            assert!(r.width_pct >= 60 && r.width_pct <= 100);
            // multiples of 10.
            assert_eq!(r.width_pct % 10, 0);
        }
    }

    #[test]
    fn rows_deterministic_per_seed() {
        let a = SkeletonList::new(20, 42).unwrap().rows();
        let b = SkeletonList::new(20, 42).unwrap().rows();
        assert_eq!(a, b);
    }

    #[test]
    fn rows_differ_per_seed() {
        let a: Vec<u8> = SkeletonList::new(20, 1).unwrap().rows().iter().map(|r| r.width_pct).collect();
        let b: Vec<u8> = SkeletonList::new(20, 2).unwrap().rows().iter().map(|r| r.width_pct).collect();
        assert_ne!(a, b);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SkeletonList::new(6, 42).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SkeletonError::SchemaMismatch));
    }

    #[test]
    fn state_serde_kebab() {
        assert_eq!(serde_json::to_string(&LoadState::Loading).unwrap(), "\"loading\"");
    }

    #[test]
    fn skeleton_serde_roundtrip() {
        let s = SkeletonList::new(6, 42).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SkeletonList = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
