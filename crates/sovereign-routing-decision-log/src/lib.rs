//! `sovereign-routing-decision-log` — append-only router decision audit.
//!
//! Each `RoutingEntry` records (trace_id, selected_provider, bundle,
//! mode, reason, elapsed_ms, at). The replay engine reads this in
//! order; the cockpit timeline visualizes it.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_profile_bundles::BundleName;
use sovereign_provider_catalog::ProviderId;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One routing decision.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RoutingEntry {
    /// M049 trace_id.
    pub trace_id: String,
    /// Provider selected.
    pub selected_provider: ProviderId,
    /// Bundle at routing time.
    pub bundle: BundleName,
    /// Mode at routing time.
    pub mode: ExecutionMode,
    /// Short reason ("only-online-provider", "preferred-by-bundle", etc.).
    pub reason: String,
    /// Milliseconds elapsed during the routing call itself.
    pub elapsed_ms: u32,
    /// ISO-8601 UTC.
    pub at: String,
}

/// Log envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RoutingDecisionLog {
    /// Schema version.
    pub schema_version: String,
    /// Entries in append order.
    pub entries: Vec<RoutingEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RoutingError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty trace_id.
    #[error("trace_id missing")]
    MissingTraceId,
    /// Empty reason.
    #[error("reason missing")]
    MissingReason,
    /// Empty timestamp.
    #[error("at missing")]
    MissingTimestamp,
    /// Timestamp regression.
    #[error("entry {idx} at {at} precedes previous {prev}")]
    TimestampRegress {
        /// idx.
        idx: usize,
        /// at.
        at: String,
        /// prev.
        prev: String,
    },
}

impl RoutingDecisionLog {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
        }
    }

    /// Append a routing entry.
    pub fn record(&mut self, e: RoutingEntry) -> Result<(), RoutingError> {
        if e.trace_id.is_empty() { return Err(RoutingError::MissingTraceId); }
        if e.reason.is_empty() { return Err(RoutingError::MissingReason); }
        if e.at.is_empty() { return Err(RoutingError::MissingTimestamp); }
        if let Some(last) = self.entries.last() {
            if e.at < last.at {
                return Err(RoutingError::TimestampRegress {
                    idx: self.entries.len(),
                    at: e.at,
                    prev: last.at.clone(),
                });
            }
        }
        self.entries.push(e);
        Ok(())
    }

    /// Count entries per provider.
    pub fn count_by_provider(&self, provider: ProviderId) -> usize {
        self.entries.iter().filter(|e| e.selected_provider == provider).count()
    }

    /// Most-recent provider.
    pub fn latest_provider(&self) -> Option<ProviderId> {
        self.entries.last().map(|e| e.selected_provider)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RoutingError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RoutingError::SchemaMismatch);
        }
        let mut prev_at: Option<&str> = None;
        for (idx, e) in self.entries.iter().enumerate() {
            if e.trace_id.is_empty() { return Err(RoutingError::MissingTraceId); }
            if e.reason.is_empty() { return Err(RoutingError::MissingReason); }
            if e.at.is_empty() { return Err(RoutingError::MissingTimestamp); }
            if let Some(p) = prev_at {
                if e.at.as_str() < p {
                    return Err(RoutingError::TimestampRegress { idx, at: e.at.clone(), prev: p.into() });
                }
            }
            prev_at = Some(&e.at);
        }
        Ok(())
    }
}

impl Default for RoutingDecisionLog {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entry(provider: ProviderId, at: &str) -> RoutingEntry {
        RoutingEntry {
            trace_id: "tr".into(),
            selected_provider: provider,
            bundle: BundleName::Careful,
            mode: ExecutionMode::Execute,
            reason: "preferred-by-bundle".into(),
            elapsed_ms: 1,
            at: at.into(),
        }
    }

    #[test]
    fn empty_log_validates() {
        RoutingDecisionLog::new().validate().unwrap();
    }

    #[test]
    fn record_appends() {
        let mut l = RoutingDecisionLog::new();
        l.record(entry(ProviderId::LocalOllama, "t1")).unwrap();
        l.record(entry(ProviderId::CloudAnthropic, "t2")).unwrap();
        assert_eq!(l.entries.len(), 2);
    }

    #[test]
    fn count_by_provider() {
        let mut l = RoutingDecisionLog::new();
        l.record(entry(ProviderId::LocalOllama, "t1")).unwrap();
        l.record(entry(ProviderId::LocalOllama, "t2")).unwrap();
        l.record(entry(ProviderId::CloudAnthropic, "t3")).unwrap();
        assert_eq!(l.count_by_provider(ProviderId::LocalOllama), 2);
        assert_eq!(l.count_by_provider(ProviderId::CloudAnthropic), 1);
        assert_eq!(l.count_by_provider(ProviderId::Mock), 0);
    }

    #[test]
    fn latest_provider() {
        let mut l = RoutingDecisionLog::new();
        assert_eq!(l.latest_provider(), None);
        l.record(entry(ProviderId::LocalOllama, "t1")).unwrap();
        l.record(entry(ProviderId::CloudAnthropic, "t2")).unwrap();
        assert_eq!(l.latest_provider(), Some(ProviderId::CloudAnthropic));
    }

    #[test]
    fn missing_trace_id_rejected() {
        let mut l = RoutingDecisionLog::new();
        let mut e = entry(ProviderId::Mock, "t");
        e.trace_id = String::new();
        assert!(matches!(l.record(e).unwrap_err(), RoutingError::MissingTraceId));
    }

    #[test]
    fn missing_reason_rejected() {
        let mut l = RoutingDecisionLog::new();
        let mut e = entry(ProviderId::Mock, "t");
        e.reason = String::new();
        assert!(matches!(l.record(e).unwrap_err(), RoutingError::MissingReason));
    }

    #[test]
    fn timestamp_regression_rejected() {
        let mut l = RoutingDecisionLog::new();
        l.record(entry(ProviderId::Mock, "2026-05-19T03:00:05Z")).unwrap();
        let err = l.record(entry(ProviderId::Mock, "2026-05-19T03:00:00Z")).unwrap_err();
        assert!(matches!(err, RoutingError::TimestampRegress { .. }));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = RoutingDecisionLog::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), RoutingError::SchemaMismatch));
    }

    #[test]
    fn log_serde_roundtrip() {
        let mut l = RoutingDecisionLog::new();
        l.record(entry(ProviderId::LocalVllm, "t")).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: RoutingDecisionLog = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
