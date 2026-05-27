//! `sovereign-cockpit-freshness-badge` — cached-data freshness badge.
//!
//! State{fetched_at_ms, fresh_ttl_ms, stale_ttl_ms,
//! revalidating, last_error}. classify(now) yields:
//! - Fresh        : now <= fetched_at + fresh_ttl
//! - Stale        : fetched_at + fresh_ttl < now <= fetched_at + stale_ttl
//! - Expired      : now > fetched_at + stale_ttl AND not revalidating
//! - Revalidating : revalidating flag set (regardless of age)
//! - Failed       : last_error.is_some() AND now > fetched_at + fresh_ttl
//!
//! Order checked: Revalidating beats Failed beats Expired beats Stale beats Fresh.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Outcome.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Freshness {
    /// Within fresh_ttl.
    Fresh,
    /// Within stale_ttl but past fresh_ttl.
    Stale,
    /// Past stale_ttl.
    Expired,
    /// A refetch is in flight.
    Revalidating,
    /// Last refetch failed.
    Failed,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FreshnessBadge {
    /// Schema version.
    pub schema_version: String,
    /// fetched_at_ms.
    pub fetched_at_ms: u64,
    /// Window during which value is fresh.
    pub fresh_ttl_ms: u64,
    /// Outer window before fully expired (must be >= fresh_ttl_ms).
    pub stale_ttl_ms: u64,
    /// Currently refetching.
    pub revalidating: bool,
    /// Optional last-fetch error.
    pub last_error: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FreshnessError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// stale_ttl < fresh_ttl.
    #[error("stale_ttl_ms must be >= fresh_ttl_ms")]
    InvalidTtls,
}

impl FreshnessBadge {
    /// New.
    pub fn new(
        fetched_at_ms: u64,
        fresh_ttl_ms: u64,
        stale_ttl_ms: u64,
    ) -> Result<Self, FreshnessError> {
        if stale_ttl_ms < fresh_ttl_ms {
            return Err(FreshnessError::InvalidTtls);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            fetched_at_ms,
            fresh_ttl_ms,
            stale_ttl_ms,
            revalidating: false,
            last_error: None,
        })
    }

    /// Mark revalidation in progress.
    pub fn start_revalidate(&mut self) {
        self.revalidating = true;
    }

    /// Commit a successful refetch.
    pub fn complete_revalidate(&mut self, now_ms: u64) {
        self.revalidating = false;
        self.last_error = None;
        self.fetched_at_ms = now_ms;
    }

    /// Record a refetch failure.
    pub fn fail_revalidate(&mut self, err: &str) {
        self.revalidating = false;
        self.last_error = Some(err.into());
    }

    /// Classify.
    pub fn classify(&self, now_ms: u64) -> Freshness {
        if self.revalidating {
            return Freshness::Revalidating;
        }
        let age = now_ms.saturating_sub(self.fetched_at_ms);
        if self.last_error.is_some() && age > self.fresh_ttl_ms {
            return Freshness::Failed;
        }
        if age <= self.fresh_ttl_ms {
            return Freshness::Fresh;
        }
        if age <= self.stale_ttl_ms {
            return Freshness::Stale;
        }
        Freshness::Expired
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FreshnessError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FreshnessError::SchemaMismatch);
        }
        if self.stale_ttl_ms < self.fresh_ttl_ms {
            return Err(FreshnessError::InvalidTtls);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b() -> FreshnessBadge {
        FreshnessBadge::new(0, 1000, 5000).unwrap()
    }

    #[test]
    fn fresh_within_ttl() {
        let s = b();
        assert_eq!(s.classify(500), Freshness::Fresh);
        assert_eq!(s.classify(1000), Freshness::Fresh);
    }

    #[test]
    fn stale_between() {
        let s = b();
        assert_eq!(s.classify(2000), Freshness::Stale);
        assert_eq!(s.classify(5000), Freshness::Stale);
    }

    #[test]
    fn expired_beyond_stale() {
        let s = b();
        assert_eq!(s.classify(6000), Freshness::Expired);
    }

    #[test]
    fn revalidating_beats_all() {
        let mut s = b();
        s.start_revalidate();
        assert_eq!(s.classify(100), Freshness::Revalidating);
        assert_eq!(s.classify(10_000), Freshness::Revalidating);
    }

    #[test]
    fn failed_after_fresh_ttl() {
        let mut s = b();
        s.fail_revalidate("timeout");
        // Still fresh ⇒ surface as Fresh (last fetch was good enough).
        assert_eq!(s.classify(500), Freshness::Fresh);
        // After fresh_ttl, the error surfaces.
        assert_eq!(s.classify(2000), Freshness::Failed);
    }

    #[test]
    fn complete_revalidate_resets() {
        let mut s = b();
        s.start_revalidate();
        s.complete_revalidate(10_000);
        assert_eq!(s.classify(10_500), Freshness::Fresh);
        assert!(s.last_error.is_none());
    }

    #[test]
    fn invalid_ttls_rejected() {
        assert!(matches!(
            FreshnessBadge::new(0, 100, 50).unwrap_err(),
            FreshnessError::InvalidTtls
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = b();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            FreshnessError::SchemaMismatch
        ));
    }

    #[test]
    fn badge_serde_roundtrip() {
        let mut s = b();
        s.start_revalidate();
        let j = serde_json::to_string(&s).unwrap();
        let back: FreshnessBadge = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
