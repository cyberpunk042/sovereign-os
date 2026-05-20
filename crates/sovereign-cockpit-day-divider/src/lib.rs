//! `sovereign-cockpit-day-divider` — bucket-by-day grouping.
//!
//! classify(now_ms, item_ms) returns a Bucket. The buckets are
//! computed against now_ms with whole-day granularity (epoch days
//! = ts_ms / 86_400_000). Today = same epoch day; Yesterday = one
//! day prior; EarlierThisWeek = within 2..=6 days prior; Older =
//! everything older (or future).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

const DAY_MS: u64 = 86_400_000;

/// Bucket.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Bucket {
    /// Today.
    Today,
    /// Yesterday.
    Yesterday,
    /// Earlier this week (2..=6 days ago).
    EarlierThisWeek,
    /// Older.
    Older,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DividerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// Epoch-day for ms timestamp.
pub fn epoch_day(ts_ms: u64) -> u64 { ts_ms / DAY_MS }

/// Classify a timestamp against now.
pub fn classify(now_ms: u64, item_ms: u64) -> Bucket {
    let now_day = epoch_day(now_ms);
    let item_day = epoch_day(item_ms);
    if item_day == now_day { return Bucket::Today; }
    if item_day + 1 == now_day { return Bucket::Yesterday; }
    if item_day + 1 < now_day && item_day + 6 >= now_day { return Bucket::EarlierThisWeek; }
    Bucket::Older
}

/// Group sorted items (newest-first) into (Bucket, item_ms) pairs.
pub fn group(now_ms: u64, items_ms: &[u64]) -> Vec<(Bucket, Vec<u64>)> {
    let mut out: Vec<(Bucket, Vec<u64>)> = Vec::new();
    for &ts in items_ms {
        let b = classify(now_ms, ts);
        match out.last_mut() {
            Some((cur_b, vec)) if *cur_b == b => vec.push(ts),
            _ => out.push((b, vec![ts])),
        }
    }
    out
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), DividerError> {
    if s != SCHEMA_VERSION { return Err(DividerError::SchemaMismatch); }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const D: u64 = 86_400_000;

    #[test]
    fn today_classified() {
        let now = 100 * D + 1000;
        let item = 100 * D + 500;
        assert_eq!(classify(now, item), Bucket::Today);
    }

    #[test]
    fn yesterday_classified() {
        let now = 100 * D;
        let item = 99 * D + 100;
        assert_eq!(classify(now, item), Bucket::Yesterday);
    }

    #[test]
    fn earlier_this_week() {
        let now = 100 * D;
        let item = 95 * D;
        assert_eq!(classify(now, item), Bucket::EarlierThisWeek);
    }

    #[test]
    fn older_beyond_week() {
        let now = 100 * D;
        let item = 50 * D;
        assert_eq!(classify(now, item), Bucket::Older);
    }

    #[test]
    fn group_keeps_contiguous_buckets() {
        let now = 100 * D;
        let items = vec![
            100 * D + 1000,
            100 * D + 500,
            99 * D + 100,
            95 * D,
        ];
        let g = group(now, &items);
        assert_eq!(g.len(), 3);
        assert_eq!(g[0].0, Bucket::Today);
        assert_eq!(g[1].0, Bucket::Yesterday);
        assert_eq!(g[2].0, Bucket::EarlierThisWeek);
    }

    #[test]
    fn epoch_day_helper() {
        assert_eq!(epoch_day(0), 0);
        assert_eq!(epoch_day(D), 1);
        assert_eq!(epoch_day(2 * D - 1), 1);
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            DividerError::SchemaMismatch
        ));
    }

    #[test]
    fn bucket_serde_roundtrip() {
        let b = Bucket::Yesterday;
        let j = serde_json::to_string(&b).unwrap();
        let back: Bucket = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
