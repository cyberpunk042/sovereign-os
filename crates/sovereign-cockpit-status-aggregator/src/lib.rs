//! `sovereign-cockpit-status-aggregator` — subsystem rollup.
//!
//! N subsystems each have a SubsystemStatus (Ok/Degraded/Down/
//! Unknown). headline() returns the worst case. percentages()
//! returns per-status share. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-subsystem status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SubsystemStatus {
    /// Healthy.
    Ok,
    /// Degraded but running.
    Degraded,
    /// Unknown (e.g., no recent heartbeat).
    Unknown,
    /// Down.
    Down,
}

impl SubsystemStatus {
    /// Severity rank (higher = worse).
    pub fn severity(self) -> u8 {
        match self {
            SubsystemStatus::Ok => 0,
            SubsystemStatus::Unknown => 1,
            SubsystemStatus::Degraded => 2,
            SubsystemStatus::Down => 3,
        }
    }
}

/// One subsystem entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Subsystem {
    /// Stable id.
    pub id: String,
    /// Display name.
    pub name: String,
    /// Status.
    pub status: SubsystemStatus,
}

/// Aggregator envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusAggregator {
    /// Schema version.
    pub schema_version: String,
    /// Subsystems.
    pub subsystems: Vec<Subsystem>,
}

/// Per-status percentage breakdown.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Percentages {
    /// Ok %.
    pub ok: u8,
    /// Degraded %.
    pub degraded: u8,
    /// Unknown %.
    pub unknown: u8,
    /// Down %.
    pub down: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AggregatorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("subsystem id empty")]
    EmptyId,
    /// Empty name.
    #[error("subsystem {0} name empty")]
    EmptyName(String),
    /// Duplicate id.
    #[error("duplicate subsystem id: {0}")]
    DuplicateId(String),
}

impl StatusAggregator {
    /// New.
    pub fn new(subsystems: Vec<Subsystem>) -> Result<Self, AggregatorError> {
        check_subs(&subsystems)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            subsystems,
        })
    }

    /// Headline = worst severity. Empty list → Ok.
    pub fn headline(&self) -> SubsystemStatus {
        let mut worst = SubsystemStatus::Ok;
        for s in &self.subsystems {
            if s.status.severity() > worst.severity() {
                worst = s.status;
            }
        }
        worst
    }

    /// Per-status percentage (sums to 100 ± 1 due to integer rounding).
    pub fn percentages(&self) -> Percentages {
        let n = self.subsystems.len() as u32;
        if n == 0 {
            return Percentages { ok: 0, degraded: 0, unknown: 0, down: 0 };
        }
        let mut counts = [0u32; 4];
        for s in &self.subsystems {
            counts[s.status.severity() as usize] += 1;
        }
        let pct = |c: u32| ((c * 100 + n / 2) / n) as u8;
        Percentages {
            ok: pct(counts[0]),
            unknown: pct(counts[1]),
            degraded: pct(counts[2]),
            down: pct(counts[3]),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AggregatorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(AggregatorError::SchemaMismatch);
        }
        check_subs(&self.subsystems)
    }
}

fn check_subs(s: &[Subsystem]) -> Result<(), AggregatorError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for x in s {
        if x.id.is_empty() { return Err(AggregatorError::EmptyId); }
        if x.name.is_empty() { return Err(AggregatorError::EmptyName(x.id.clone())); }
        if !seen.insert(x.id.as_str()) {
            return Err(AggregatorError::DuplicateId(x.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(id: &str, st: SubsystemStatus) -> Subsystem {
        Subsystem { id: id.into(), name: format!("N-{id}"), status: st }
    }

    #[test]
    fn empty_headline_is_ok() {
        let a = StatusAggregator::new(vec![]).unwrap();
        assert_eq!(a.headline(), SubsystemStatus::Ok);
    }

    #[test]
    fn headline_worst_wins_down_over_degraded() {
        let a = StatusAggregator::new(vec![
            s("a", SubsystemStatus::Ok),
            s("b", SubsystemStatus::Degraded),
            s("c", SubsystemStatus::Down),
        ]).unwrap();
        assert_eq!(a.headline(), SubsystemStatus::Down);
    }

    #[test]
    fn headline_degraded_over_unknown() {
        let a = StatusAggregator::new(vec![
            s("a", SubsystemStatus::Unknown),
            s("b", SubsystemStatus::Degraded),
        ]).unwrap();
        assert_eq!(a.headline(), SubsystemStatus::Degraded);
    }

    #[test]
    fn headline_unknown_over_ok() {
        let a = StatusAggregator::new(vec![
            s("a", SubsystemStatus::Ok),
            s("b", SubsystemStatus::Unknown),
        ]).unwrap();
        assert_eq!(a.headline(), SubsystemStatus::Unknown);
    }

    #[test]
    fn percentages_sum_balanced() {
        let a = StatusAggregator::new(vec![
            s("a", SubsystemStatus::Ok),
            s("b", SubsystemStatus::Ok),
            s("c", SubsystemStatus::Degraded),
            s("d", SubsystemStatus::Down),
        ]).unwrap();
        let p = a.percentages();
        assert_eq!(p.ok, 50);
        assert_eq!(p.degraded, 25);
        assert_eq!(p.down, 25);
        assert_eq!(p.unknown, 0);
    }

    #[test]
    fn percentages_empty_zeroes() {
        let a = StatusAggregator::new(vec![]).unwrap();
        let p = a.percentages();
        assert_eq!(p.ok, 0);
        assert_eq!(p.down, 0);
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            StatusAggregator::new(vec![s("a", SubsystemStatus::Ok), s("a", SubsystemStatus::Ok)]).unwrap_err(),
            AggregatorError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = s("a", SubsystemStatus::Ok);
        x.id = String::new();
        assert!(matches!(StatusAggregator::new(vec![x]).unwrap_err(), AggregatorError::EmptyId));
    }

    #[test]
    fn empty_name_rejected() {
        let mut x = s("a", SubsystemStatus::Ok);
        x.name = String::new();
        assert!(matches!(StatusAggregator::new(vec![x]).unwrap_err(), AggregatorError::EmptyName(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut a = StatusAggregator::new(vec![s("a", SubsystemStatus::Ok)]).unwrap();
        a.schema_version = "9.9.9".into();
        assert!(matches!(a.validate().unwrap_err(), AggregatorError::SchemaMismatch));
    }

    #[test]
    fn status_serde_kebab() {
        assert_eq!(serde_json::to_string(&SubsystemStatus::Ok).unwrap(), "\"ok\"");
        assert_eq!(serde_json::to_string(&SubsystemStatus::Degraded).unwrap(), "\"degraded\"");
    }

    #[test]
    fn agg_serde_roundtrip() {
        let a = StatusAggregator::new(vec![s("a", SubsystemStatus::Ok), s("b", SubsystemStatus::Down)]).unwrap();
        let j = serde_json::to_string(&a).unwrap();
        let back: StatusAggregator = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
