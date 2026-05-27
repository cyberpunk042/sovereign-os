//! `sovereign-cockpit-action-throttle` — per-action minimum-spacing gate.
//!
//! Each action_id declares a `min_spacing_ms`. The throttle tracks the
//! last-fire timestamp (epoch ms) per action and refuses if a new fire
//! request arrives sooner than `min_spacing_ms`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One throttle rule.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ThrottleRule {
    /// Action id.
    pub action_id: String,
    /// Minimum spacing in milliseconds.
    pub min_spacing_ms: u32,
}

/// Throttle state envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionThrottle {
    /// Schema version.
    pub schema_version: String,
    /// Rules.
    pub rules: Vec<ThrottleRule>,
    /// Last-fire epoch-ms per action_id.
    pub last_fired: HashMap<String, u64>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ThrottleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty action_id.
    #[error("rule action_id empty")]
    EmptyActionId,
    /// Spacing zero (would allow infinite fires).
    #[error("rule {0} min_spacing_ms zero")]
    ZeroSpacing(String),
    /// Duplicate rule.
    #[error("duplicate rule for action_id {0}")]
    Duplicate(String),
    /// Throttled — too soon since last fire.
    #[error(
        "action {action_id} throttled: last fired at {last_ms}, requested at {now_ms}, min spacing {spacing_ms} ms"
    )]
    Throttled {
        /// action.
        action_id: String,
        /// last fired.
        last_ms: u64,
        /// now.
        now_ms: u64,
        /// spacing.
        spacing_ms: u32,
    },
    /// Action id unknown to throttle.
    #[error("no throttle rule for action_id: {0}")]
    Unknown(String),
}

impl ActionThrottle {
    /// New empty throttle.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            rules: Vec::new(),
            last_fired: HashMap::new(),
        }
    }

    /// Add a throttle rule.
    pub fn add(&mut self, rule: ThrottleRule) -> Result<(), ThrottleError> {
        if rule.action_id.is_empty() {
            return Err(ThrottleError::EmptyActionId);
        }
        if rule.min_spacing_ms == 0 {
            return Err(ThrottleError::ZeroSpacing(rule.action_id));
        }
        if self.rules.iter().any(|r| r.action_id == rule.action_id) {
            return Err(ThrottleError::Duplicate(rule.action_id));
        }
        self.rules.push(rule);
        Ok(())
    }

    /// Attempt to fire an action at the given epoch-ms.
    /// Returns Ok(()) on success and updates last_fired. Returns Throttled
    /// when min_spacing not elapsed. Returns Unknown if no rule exists.
    pub fn try_fire(&mut self, action_id: &str, now_ms: u64) -> Result<(), ThrottleError> {
        let rule = self
            .rules
            .iter()
            .find(|r| r.action_id == action_id)
            .ok_or_else(|| ThrottleError::Unknown(action_id.into()))?;
        let spacing = rule.min_spacing_ms;
        let last = self.last_fired.get(action_id).copied().unwrap_or(0);
        if last != 0 && now_ms < last + spacing as u64 {
            return Err(ThrottleError::Throttled {
                action_id: action_id.into(),
                last_ms: last,
                now_ms,
                spacing_ms: spacing,
            });
        }
        self.last_fired.insert(action_id.into(), now_ms);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ThrottleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ThrottleError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for r in &self.rules {
            if r.action_id.is_empty() {
                return Err(ThrottleError::EmptyActionId);
            }
            if r.min_spacing_ms == 0 {
                return Err(ThrottleError::ZeroSpacing(r.action_id.clone()));
            }
            if !seen.insert(r.action_id.as_str()) {
                return Err(ThrottleError::Duplicate(r.action_id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for ActionThrottle {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn r(id: &str, spacing: u32) -> ThrottleRule {
        ThrottleRule {
            action_id: id.into(),
            min_spacing_ms: spacing,
        }
    }

    #[test]
    fn empty_throttle_validates() {
        ActionThrottle::new().validate().unwrap();
    }

    #[test]
    fn first_fire_ok() {
        let mut t = ActionThrottle::new();
        t.add(r("mode-switch", 500)).unwrap();
        t.try_fire("mode-switch", 1_000).unwrap();
    }

    #[test]
    fn second_fire_within_spacing_throttled() {
        let mut t = ActionThrottle::new();
        t.add(r("mode-switch", 500)).unwrap();
        t.try_fire("mode-switch", 1_000).unwrap();
        let err = t.try_fire("mode-switch", 1_200).unwrap_err();
        assert!(matches!(err, ThrottleError::Throttled { .. }));
    }

    #[test]
    fn second_fire_after_spacing_ok() {
        let mut t = ActionThrottle::new();
        t.add(r("mode-switch", 500)).unwrap();
        t.try_fire("mode-switch", 1_000).unwrap();
        t.try_fire("mode-switch", 1_500).unwrap();
    }

    #[test]
    fn unknown_action_rejected() {
        let mut t = ActionThrottle::new();
        let err = t.try_fire("unknown", 0).unwrap_err();
        assert!(matches!(err, ThrottleError::Unknown(_)));
    }

    #[test]
    fn duplicate_rule_rejected() {
        let mut t = ActionThrottle::new();
        t.add(r("x", 500)).unwrap();
        let err = t.add(r("x", 1000)).unwrap_err();
        assert!(matches!(err, ThrottleError::Duplicate(_)));
    }

    #[test]
    fn zero_spacing_rejected() {
        let mut t = ActionThrottle::new();
        let err = t.add(r("x", 0)).unwrap_err();
        assert!(matches!(err, ThrottleError::ZeroSpacing(_)));
    }

    #[test]
    fn empty_action_id_rejected() {
        let mut t = ActionThrottle::new();
        let err = t.add(r("", 500)).unwrap_err();
        assert!(matches!(err, ThrottleError::EmptyActionId));
    }

    #[test]
    fn distinct_actions_have_separate_buckets() {
        let mut t = ActionThrottle::new();
        t.add(r("a", 500)).unwrap();
        t.add(r("b", 500)).unwrap();
        t.try_fire("a", 1_000).unwrap();
        t.try_fire("b", 1_000).unwrap();
        // Both fired at the same time.
        let err = t.try_fire("a", 1_100).unwrap_err();
        assert!(matches!(err, ThrottleError::Throttled { .. }));
        // "b" still throttled too.
        let err2 = t.try_fire("b", 1_100).unwrap_err();
        assert!(matches!(err2, ThrottleError::Throttled { .. }));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = ActionThrottle::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            ThrottleError::SchemaMismatch
        ));
    }

    #[test]
    fn throttle_serde_roundtrip() {
        let mut t = ActionThrottle::new();
        t.add(r("a", 500)).unwrap();
        t.try_fire("a", 1_000).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: ActionThrottle = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
