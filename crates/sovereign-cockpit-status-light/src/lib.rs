//! `sovereign-cockpit-status-light` — multi-subject status registry.
//!
//! Each subject has a `(tone, reason, last_update_ts)`. Tones in
//! worst→best ordering:
//!
//!   `Offline > Degraded > Unknown > Healthy`
//!
//! `worst()` reports the worst observed tone across all subjects
//! (defaults to Healthy when empty). `stale(id, now, ttl_ms)`
//! returns true when the last update is older than `ttl_ms`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Status tone.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Tone {
    /// Healthy.
    Healthy,
    /// Unknown / not reporting.
    Unknown,
    /// Degraded.
    Degraded,
    /// Offline.
    Offline,
}

/// One light.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Light {
    /// Tone.
    pub tone: Tone,
    /// Reason label.
    pub reason: String,
    /// Last update ts (ms).
    pub last_update_ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusLight {
    /// Schema version.
    pub schema_version: String,
    /// id → light.
    pub lights: BTreeMap<String, Light>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LightError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("subject id empty")]
    EmptyId,
}

fn rank(t: Tone) -> u8 {
    match t {
        Tone::Healthy => 0,
        Tone::Unknown => 1,
        Tone::Degraded => 2,
        Tone::Offline => 3,
    }
}

impl StatusLight {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            lights: BTreeMap::new(),
        }
    }

    /// Set.
    pub fn set(
        &mut self,
        id: &str,
        tone: Tone,
        reason: &str,
        now_ms: u64,
    ) -> Result<(), LightError> {
        if id.is_empty() {
            return Err(LightError::EmptyId);
        }
        self.lights.insert(
            id.into(),
            Light {
                tone,
                reason: reason.into(),
                last_update_ts_ms: now_ms,
            },
        );
        Ok(())
    }

    /// Tone for a subject.
    pub fn tone_of(&self, id: &str) -> Option<Tone> {
        self.lights.get(id).map(|l| l.tone)
    }

    /// Worst tone across all subjects (Healthy when empty).
    pub fn worst(&self) -> Tone {
        self.lights
            .values()
            .map(|l| l.tone)
            .max_by_key(|t| rank(*t))
            .unwrap_or(Tone::Healthy)
    }

    /// Stale?
    pub fn stale(&self, id: &str, now_ms: u64, ttl_ms: u64) -> bool {
        match self.lights.get(id) {
            Some(l) => now_ms.saturating_sub(l.last_update_ts_ms) > ttl_ms,
            None => true,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LightError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LightError::SchemaMismatch);
        }
        for id in self.lights.keys() {
            if id.is_empty() {
                return Err(LightError::EmptyId);
            }
        }
        Ok(())
    }
}

impl Default for StatusLight {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ordering_offline_worst() {
        assert!(rank(Tone::Offline) > rank(Tone::Degraded));
        assert!(rank(Tone::Degraded) > rank(Tone::Unknown));
        assert!(rank(Tone::Unknown) > rank(Tone::Healthy));
    }

    #[test]
    fn empty_worst_is_healthy() {
        let l = StatusLight::new();
        assert_eq!(l.worst(), Tone::Healthy);
    }

    #[test]
    fn worst_picks_offline() {
        let mut l = StatusLight::new();
        l.set("a", Tone::Healthy, "ok", 0).unwrap();
        l.set("b", Tone::Offline, "down", 0).unwrap();
        l.set("c", Tone::Degraded, "slow", 0).unwrap();
        assert_eq!(l.worst(), Tone::Offline);
    }

    #[test]
    fn tone_of_unknown_subject() {
        let l = StatusLight::new();
        assert_eq!(l.tone_of("missing"), None);
    }

    #[test]
    fn stale_when_old() {
        let mut l = StatusLight::new();
        l.set("a", Tone::Healthy, "ok", 0).unwrap();
        assert!(!l.stale("a", 500, 1000));
        assert!(l.stale("a", 2000, 1000));
    }

    #[test]
    fn stale_when_unknown_id() {
        let l = StatusLight::new();
        assert!(l.stale("nope", 100, 1000));
    }

    #[test]
    fn empty_id_rejected() {
        let mut l = StatusLight::new();
        assert!(matches!(
            l.set("", Tone::Healthy, "x", 0).unwrap_err(),
            LightError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = StatusLight::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            LightError::SchemaMismatch
        ));
    }

    #[test]
    fn light_serde_roundtrip() {
        let mut l = StatusLight::new();
        l.set("a", Tone::Degraded, "slow", 100).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: StatusLight = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
