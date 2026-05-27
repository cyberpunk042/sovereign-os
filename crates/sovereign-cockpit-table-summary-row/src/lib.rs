//! `sovereign-cockpit-table-summary-row` — column-aggregator footer row.
//!
//! Each column declares an `Aggregator`. `compute(rows)` returns a
//! parallel `Vec<SummaryCell>` of computed values. `rows` is a
//! Vec<Vec<i64>> — caller pre-normalizes; non-applicable columns get
//! `Aggregator::None` and yield `SummaryCell::None`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Aggregator.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Aggregator {
    /// No summary.
    None,
    /// Sum.
    Sum,
    /// Average (integer floor).
    Avg,
    /// Min.
    Min,
    /// Max.
    Max,
    /// Count of rows (ignores per-row value).
    Count,
}

/// One summary cell.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum SummaryCell {
    /// No summary.
    None,
    /// Value.
    Value {
        /// computed integer.
        value: i64,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TableSummaryRow {
    /// Schema version.
    pub schema_version: String,
    /// Per-column aggregators in column order.
    pub aggregators: Vec<Aggregator>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SummaryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Row width mismatch.
    #[error("row width {0} != column count {1}")]
    WidthMismatch(usize, usize),
}

impl TableSummaryRow {
    /// New.
    pub fn new(aggregators: Vec<Aggregator>) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            aggregators,
        }
    }

    /// Compute summary row.
    pub fn compute(&self, rows: &[Vec<i64>]) -> Result<Vec<SummaryCell>, SummaryError> {
        let n = self.aggregators.len();
        for row in rows {
            if row.len() != n {
                return Err(SummaryError::WidthMismatch(row.len(), n));
            }
        }
        let mut out = Vec::with_capacity(n);
        for (col, agg) in self.aggregators.iter().enumerate() {
            let cell = match agg {
                Aggregator::None => SummaryCell::None,
                Aggregator::Sum => SummaryCell::Value {
                    value: rows.iter().map(|r| r[col]).fold(0i64, i64::saturating_add),
                },
                Aggregator::Avg => {
                    if rows.is_empty() {
                        SummaryCell::Value { value: 0 }
                    } else {
                        let sum: i64 = rows.iter().map(|r| r[col]).fold(0, i64::saturating_add);
                        SummaryCell::Value {
                            value: sum / rows.len() as i64,
                        }
                    }
                }
                Aggregator::Min => match rows.iter().map(|r| r[col]).min() {
                    Some(v) => SummaryCell::Value { value: v },
                    None => SummaryCell::None,
                },
                Aggregator::Max => match rows.iter().map(|r| r[col]).max() {
                    Some(v) => SummaryCell::Value { value: v },
                    None => SummaryCell::None,
                },
                Aggregator::Count => SummaryCell::Value {
                    value: rows.len() as i64,
                },
            };
            out.push(cell);
        }
        Ok(out)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SummaryError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SummaryError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sum_avg_count() {
        let s = TableSummaryRow::new(vec![Aggregator::Sum, Aggregator::Avg, Aggregator::Count]);
        let out = s
            .compute(&[vec![1, 10, 0], vec![2, 20, 0], vec![3, 30, 0]])
            .unwrap();
        assert_eq!(out[0], SummaryCell::Value { value: 6 });
        assert_eq!(out[1], SummaryCell::Value { value: 20 });
        assert_eq!(out[2], SummaryCell::Value { value: 3 });
    }

    #[test]
    fn min_max_with_data() {
        let s = TableSummaryRow::new(vec![Aggregator::Min, Aggregator::Max]);
        let out = s.compute(&[vec![5, 5], vec![1, 9], vec![3, 7]]).unwrap();
        assert_eq!(out[0], SummaryCell::Value { value: 1 });
        assert_eq!(out[1], SummaryCell::Value { value: 9 });
    }

    #[test]
    fn min_max_empty_is_none() {
        let s = TableSummaryRow::new(vec![Aggregator::Min, Aggregator::Max]);
        let out = s.compute(&[]).unwrap();
        assert_eq!(out[0], SummaryCell::None);
        assert_eq!(out[1], SummaryCell::None);
    }

    #[test]
    fn none_yields_none() {
        let s = TableSummaryRow::new(vec![Aggregator::None]);
        let out = s.compute(&[vec![5], vec![10]]).unwrap();
        assert_eq!(out[0], SummaryCell::None);
    }

    #[test]
    fn width_mismatch_rejected() {
        let s = TableSummaryRow::new(vec![Aggregator::Sum, Aggregator::Sum]);
        assert!(matches!(
            s.compute(&[vec![1]]).unwrap_err(),
            SummaryError::WidthMismatch(_, _)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = TableSummaryRow::new(vec![]);
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SummaryError::SchemaMismatch
        ));
    }

    #[test]
    fn summary_serde_roundtrip() {
        let s = TableSummaryRow::new(vec![Aggregator::Sum, Aggregator::None]);
        let j = serde_json::to_string(&s).unwrap();
        let back: TableSummaryRow = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
