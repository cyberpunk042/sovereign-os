//! `sovereign-cockpit-usage-meter` — multi-metric usage display.
//!
//! Per-metric: label, unit, used, limit. usage_bp = used*10000/
//! limit (capped at u32::MAX, shows >10000 when over-limit).
//! over_limit() lists metrics with used>=limit. add/remove/set
//! mutators.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Metric.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Metric {
    /// Label.
    pub label: String,
    /// Unit suffix.
    pub unit: String,
    /// Used.
    pub used: u64,
    /// Limit (>=1).
    pub limit: u64,
}

impl Metric {
    /// Usage in bp (may exceed 10000).
    pub fn usage_bp(&self) -> u32 {
        let ratio = (self.used as u128 * 10_000) / self.limit as u128;
        ratio.min(u32::MAX as u128) as u32
    }

    /// Over limit?
    pub fn is_over(&self) -> bool { self.used >= self.limit }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UsageMeter {
    /// Schema version.
    pub schema_version: String,
    /// id → metric.
    pub metrics: BTreeMap<String, Metric>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum UsageError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Zero limit.
    #[error("limit must be >= 1")]
    ZeroLimit,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown id: {0}")]
    UnknownId(String),
}

impl UsageMeter {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            metrics: BTreeMap::new(),
        }
    }

    /// Add metric.
    pub fn add(&mut self, id: &str, label: &str, unit: &str, limit: u64) -> Result<(), UsageError> {
        if id.is_empty() { return Err(UsageError::EmptyId); }
        if label.is_empty() { return Err(UsageError::EmptyLabel); }
        if limit == 0 { return Err(UsageError::ZeroLimit); }
        if self.metrics.contains_key(id) { return Err(UsageError::DuplicateId(id.into())); }
        self.metrics.insert(id.into(), Metric {
            label: label.into(),
            unit: unit.into(),
            used: 0,
            limit,
        });
        Ok(())
    }

    /// Remove metric.
    pub fn remove(&mut self, id: &str) -> bool {
        self.metrics.remove(id).is_some()
    }

    /// Set used.
    pub fn set_used(&mut self, id: &str, used: u64) -> Result<(), UsageError> {
        let m = self.metrics.get_mut(id).ok_or_else(|| UsageError::UnknownId(id.into()))?;
        m.used = used;
        Ok(())
    }

    /// Charge n.
    pub fn charge(&mut self, id: &str, n: u64) -> Result<(), UsageError> {
        let m = self.metrics.get_mut(id).ok_or_else(|| UsageError::UnknownId(id.into()))?;
        m.used = m.used.saturating_add(n);
        Ok(())
    }

    /// Over-limit metric ids.
    pub fn over_limit(&self) -> Vec<&str> {
        self.metrics.iter().filter(|(_, m)| m.is_over()).map(|(k, _)| k.as_str()).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), UsageError> {
        if self.schema_version != SCHEMA_VERSION { return Err(UsageError::SchemaMismatch); }
        for (id, m) in &self.metrics {
            if id.is_empty() { return Err(UsageError::EmptyId); }
            if m.label.is_empty() { return Err(UsageError::EmptyLabel); }
            if m.limit == 0 { return Err(UsageError::ZeroLimit); }
        }
        Ok(())
    }
}

impl Default for UsageMeter {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_charge() {
        let mut u = UsageMeter::new();
        u.add("tokens", "Tokens", "", 1000).unwrap();
        u.charge("tokens", 500).unwrap();
        let m = u.metrics.get("tokens").unwrap();
        assert_eq!(m.usage_bp(), 5000);
        assert!(!m.is_over());
    }

    #[test]
    fn over_limit_flag() {
        let mut u = UsageMeter::new();
        u.add("tokens", "Tokens", "", 1000).unwrap();
        u.set_used("tokens", 1500).unwrap();
        assert_eq!(u.over_limit(), vec!["tokens"]);
        let m = u.metrics.get("tokens").unwrap();
        assert!(m.is_over());
        assert_eq!(m.usage_bp(), 15000);
    }

    #[test]
    fn remove_works() {
        let mut u = UsageMeter::new();
        u.add("a", "X", "", 100).unwrap();
        assert!(u.remove("a"));
        assert!(!u.remove("a"));
    }

    #[test]
    fn duplicate_rejected() {
        let mut u = UsageMeter::new();
        u.add("a", "X", "", 100).unwrap();
        assert!(matches!(u.add("a", "Y", "", 100).unwrap_err(), UsageError::DuplicateId(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut u = UsageMeter::new();
        assert!(matches!(u.add("", "X", "", 100).unwrap_err(), UsageError::EmptyId));
        assert!(matches!(u.add("a", "", "", 100).unwrap_err(), UsageError::EmptyLabel));
        assert!(matches!(u.add("a", "X", "", 0).unwrap_err(), UsageError::ZeroLimit));
    }

    #[test]
    fn unknown_id_rejected() {
        let mut u = UsageMeter::new();
        assert!(matches!(u.set_used("nope", 0).unwrap_err(), UsageError::UnknownId(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut u = UsageMeter::new();
        u.schema_version = "9.9.9".into();
        assert!(matches!(u.validate().unwrap_err(), UsageError::SchemaMismatch));
    }

    #[test]
    fn meter_serde_roundtrip() {
        let mut u = UsageMeter::new();
        u.add("a", "X", "", 100).unwrap();
        let j = serde_json::to_string(&u).unwrap();
        let back: UsageMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(u, back);
    }
}
