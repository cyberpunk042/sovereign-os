//! `sovereign-cockpit-service-status` — per-service health.
//!
//! Status{Up/Degraded/Down}. set(service, status) records.
//! fleet_status() returns Down if any Down, else Degraded if
//! any Degraded, else Up. counts() returns per-status counts.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Up.
    Up,
    /// Degraded.
    Degraded,
    /// Down.
    Down,
}

/// Counts.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Counts {
    /// Up.
    pub up: u32,
    /// Degraded.
    pub degraded: u32,
    /// Down.
    pub down: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ServiceStatus {
    /// Schema version.
    pub schema_version: String,
    /// service → status.
    pub services: BTreeMap<String, Status>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StatusError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("service empty")]
    EmptyService,
}

impl ServiceStatus {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            services: BTreeMap::new(),
        }
    }

    /// Set status.
    pub fn set(&mut self, service: &str, status: Status) -> Result<(), StatusError> {
        if service.is_empty() {
            return Err(StatusError::EmptyService);
        }
        self.services.insert(service.into(), status);
        Ok(())
    }

    /// Remove a service.
    pub fn remove(&mut self, service: &str) -> bool {
        self.services.remove(service).is_some()
    }

    /// Per-status counts.
    pub fn counts(&self) -> Counts {
        let mut c = Counts {
            up: 0,
            degraded: 0,
            down: 0,
        };
        for s in self.services.values() {
            match s {
                Status::Up => c.up += 1,
                Status::Degraded => c.degraded += 1,
                Status::Down => c.down += 1,
            }
        }
        c
    }

    /// Aggregate fleet status.
    pub fn fleet_status(&self) -> Status {
        let mut has_degraded = false;
        for s in self.services.values() {
            if *s == Status::Down {
                return Status::Down;
            }
            if *s == Status::Degraded {
                has_degraded = true;
            }
        }
        if has_degraded {
            Status::Degraded
        } else {
            Status::Up
        }
    }

    /// Services by status.
    pub fn services_with(&self, status: Status) -> Vec<&str> {
        self.services
            .iter()
            .filter(|(_, s)| **s == status)
            .map(|(k, _)| k.as_str())
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StatusError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(StatusError::SchemaMismatch);
        }
        for k in self.services.keys() {
            if k.is_empty() {
                return Err(StatusError::EmptyService);
            }
        }
        Ok(())
    }
}

impl Default for ServiceStatus {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_fleet_is_up() {
        let s = ServiceStatus::new();
        assert_eq!(s.fleet_status(), Status::Up);
    }

    #[test]
    fn all_up() {
        let mut s = ServiceStatus::new();
        s.set("a", Status::Up).unwrap();
        s.set("b", Status::Up).unwrap();
        assert_eq!(s.fleet_status(), Status::Up);
    }

    #[test]
    fn any_degraded_promotes_to_degraded() {
        let mut s = ServiceStatus::new();
        s.set("a", Status::Up).unwrap();
        s.set("b", Status::Degraded).unwrap();
        assert_eq!(s.fleet_status(), Status::Degraded);
    }

    #[test]
    fn any_down_promotes_to_down() {
        let mut s = ServiceStatus::new();
        s.set("a", Status::Up).unwrap();
        s.set("b", Status::Down).unwrap();
        assert_eq!(s.fleet_status(), Status::Down);
    }

    #[test]
    fn counts() {
        let mut s = ServiceStatus::new();
        s.set("a", Status::Up).unwrap();
        s.set("b", Status::Up).unwrap();
        s.set("c", Status::Degraded).unwrap();
        s.set("d", Status::Down).unwrap();
        let c = s.counts();
        assert_eq!((c.up, c.degraded, c.down), (2, 1, 1));
    }

    #[test]
    fn services_with_filter() {
        let mut s = ServiceStatus::new();
        s.set("a", Status::Up).unwrap();
        s.set("b", Status::Down).unwrap();
        s.set("c", Status::Up).unwrap();
        let up = s.services_with(Status::Up);
        assert_eq!(up, vec!["a", "c"]);
    }

    #[test]
    fn remove_works() {
        let mut s = ServiceStatus::new();
        s.set("a", Status::Up).unwrap();
        assert!(s.remove("a"));
        assert!(!s.remove("a"));
    }

    #[test]
    fn empty_service_rejected() {
        let mut s = ServiceStatus::new();
        assert!(matches!(
            s.set("", Status::Up).unwrap_err(),
            StatusError::EmptyService
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ServiceStatus::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            StatusError::SchemaMismatch
        ));
    }

    #[test]
    fn status_serde_roundtrip() {
        let mut s = ServiceStatus::new();
        s.set("a", Status::Up).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ServiceStatus = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
