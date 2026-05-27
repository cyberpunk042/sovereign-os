//! `sovereign-eval-result-summary` — single eval-suite run summary.
//!
//! Fields: suite_id, window (started/finished), case counts, per-dimension
//! averages. `pass_rate_bps()` returns the pass rate as basis points
//! (out of 10_000).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_eval_plane::EvalDimension;
use sovereign_eval_suite_catalog::SuiteId;
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One run summary.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct EvalResultSummary {
    /// Schema version.
    pub schema_version: String,
    /// Suite executed.
    pub suite_id: SuiteId,
    /// ISO-8601 UTC.
    pub started_at: String,
    /// ISO-8601 UTC.
    pub finished_at: String,
    /// Total cases run.
    pub total_cases: u32,
    /// Cases passed.
    pub passed: u32,
    /// Cases failed.
    pub failed: u32,
    /// Average score per evaluated dimension (keyed by dim name).
    pub dim_avg: BTreeMap<String, f32>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SummaryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// passed + failed != total_cases.
    #[error("sum mismatch: passed={passed} + failed={failed} != total={total}")]
    SumMismatch {
        /// passed.
        passed: u32,
        /// failed.
        failed: u32,
        /// total.
        total: u32,
    },
    /// Empty timestamp.
    #[error("missing timestamp: {0}")]
    MissingTimestamp(&'static str),
    /// finished_at < started_at.
    #[error("finished_at {finished} precedes started_at {started}")]
    FinishedBeforeStarted {
        /// started.
        started: String,
        /// finished.
        finished: String,
    },
    /// dim_avg score outside 0..=1.
    #[error("dim {dim} avg {avg} outside 0..=1")]
    AvgOutOfRange {
        /// dim.
        dim: String,
        /// avg.
        avg: f32,
    },
}

fn dim_key(d: EvalDimension) -> &'static str {
    match d {
        EvalDimension::Correctness => "correctness",
        EvalDimension::Evidence => "evidence",
        EvalDimension::TestPass => "test-pass",
        EvalDimension::SchemaValidity => "schema-validity",
        EvalDimension::Risk => "risk",
        EvalDimension::Cost => "cost",
        EvalDimension::Latency => "latency",
        _ => "human-burden",
    }
}

impl EvalResultSummary {
    /// New summary.
    pub fn new(
        suite_id: SuiteId,
        started_at: &str,
        finished_at: &str,
        passed: u32,
        failed: u32,
    ) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            suite_id,
            started_at: started_at.into(),
            finished_at: finished_at.into(),
            total_cases: passed + failed,
            passed,
            failed,
            dim_avg: BTreeMap::new(),
        }
    }

    /// Set a per-dimension average score (0..=1).
    pub fn set_dim_avg(&mut self, dim: EvalDimension, avg: f32) {
        self.dim_avg.insert(dim_key(dim).into(), avg);
    }

    /// Pass rate as basis points (0..=10_000). 0 if total_cases is 0.
    pub fn pass_rate_bps(&self) -> u32 {
        if self.total_cases == 0 {
            return 0;
        }
        ((self.passed as u64 * 10_000) / self.total_cases as u64) as u32
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SummaryError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SummaryError::SchemaMismatch);
        }
        if self.started_at.is_empty() {
            return Err(SummaryError::MissingTimestamp("started_at"));
        }
        if self.finished_at.is_empty() {
            return Err(SummaryError::MissingTimestamp("finished_at"));
        }
        if self.finished_at < self.started_at {
            return Err(SummaryError::FinishedBeforeStarted {
                started: self.started_at.clone(),
                finished: self.finished_at.clone(),
            });
        }
        if self.passed + self.failed != self.total_cases {
            return Err(SummaryError::SumMismatch {
                passed: self.passed,
                failed: self.failed,
                total: self.total_cases,
            });
        }
        for (d, avg) in &self.dim_avg {
            if *avg < 0.0 || *avg > 1.0 {
                return Err(SummaryError::AvgOutOfRange {
                    dim: d.clone(),
                    avg: *avg,
                });
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s() -> EvalResultSummary {
        let mut s = EvalResultSummary::new(
            SuiteId::Smoke,
            "2026-05-19T03:00:00Z",
            "2026-05-19T03:00:10Z",
            8,
            2,
        );
        s.set_dim_avg(EvalDimension::Correctness, 0.9);
        s.set_dim_avg(EvalDimension::SchemaValidity, 1.0);
        s
    }

    #[test]
    fn ok_validates() {
        s().validate().unwrap();
    }

    #[test]
    fn pass_rate_8_of_10_eq_8000() {
        assert_eq!(s().pass_rate_bps(), 8000);
    }

    #[test]
    fn zero_cases_zero_pass_rate() {
        let summary = EvalResultSummary::new(SuiteId::Smoke, "t", "t", 0, 0);
        assert_eq!(summary.pass_rate_bps(), 0);
    }

    #[test]
    fn sum_mismatch_caught() {
        let mut x = s();
        x.total_cases = 99;
        assert!(matches!(
            x.validate().unwrap_err(),
            SummaryError::SumMismatch { .. }
        ));
    }

    #[test]
    fn finished_before_started_caught() {
        let mut x = s();
        x.finished_at = "2026-05-19T02:00:00Z".into();
        assert!(matches!(
            x.validate().unwrap_err(),
            SummaryError::FinishedBeforeStarted { .. }
        ));
    }

    #[test]
    fn empty_started_at_caught() {
        let mut x = s();
        x.started_at = String::new();
        assert!(matches!(
            x.validate().unwrap_err(),
            SummaryError::MissingTimestamp("started_at")
        ));
    }

    #[test]
    fn avg_out_of_range_caught() {
        let mut x = s();
        x.set_dim_avg(EvalDimension::Cost, 1.5);
        assert!(matches!(
            x.validate().unwrap_err(),
            SummaryError::AvgOutOfRange { .. }
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut x = s();
        x.schema_version = "9.9.9".into();
        assert!(matches!(
            x.validate().unwrap_err(),
            SummaryError::SchemaMismatch
        ));
    }

    #[test]
    fn summary_serde_roundtrip() {
        let x = s();
        let j = serde_json::to_string(&x).unwrap();
        let back: EvalResultSummary = serde_json::from_str(&j).unwrap();
        assert_eq!(x, back);
    }
}
