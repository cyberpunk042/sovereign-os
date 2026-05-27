//! `sovereign-cockpit-hint-card` — recommendation hint UI state.
//!
//! Each hint has dismissed flag + last_dismissed_ms. should_show(
//! now) returns true iff not dismissed OR cooldown_ms has
//! elapsed since dismiss. dismiss(now) marks dismissed. accept
//! records acceptance and disables the hint.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Hint record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Hint {
    /// Title.
    pub title: String,
    /// Body.
    pub body: String,
    /// Dismissed?
    pub dismissed: bool,
    /// Last dismiss ts ms.
    pub last_dismissed_ms: u64,
    /// Accepted (one-way).
    pub accepted: bool,
    /// Dismiss count.
    pub dismisses: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HintCard {
    /// Schema version.
    pub schema_version: String,
    /// id → hint.
    pub hints: BTreeMap<String, Hint>,
    /// Cooldown ms before redisplay after dismiss.
    pub cooldown_ms: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HintError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Empty.
    #[error("body empty")]
    EmptyBody,
    /// Zero cooldown.
    #[error("cooldown_ms must be >= 1")]
    ZeroCooldown,
    /// Duplicate.
    #[error("duplicate hint id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown hint: {0}")]
    UnknownHint(String),
}

impl HintCard {
    /// New.
    pub fn new(cooldown_ms: u64) -> Result<Self, HintError> {
        if cooldown_ms == 0 {
            return Err(HintError::ZeroCooldown);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            hints: BTreeMap::new(),
            cooldown_ms,
        })
    }

    /// Add a hint.
    pub fn add(&mut self, id: &str, title: &str, body: &str) -> Result<(), HintError> {
        if id.is_empty() {
            return Err(HintError::EmptyId);
        }
        if title.is_empty() {
            return Err(HintError::EmptyTitle);
        }
        if body.is_empty() {
            return Err(HintError::EmptyBody);
        }
        if self.hints.contains_key(id) {
            return Err(HintError::DuplicateId(id.into()));
        }
        self.hints.insert(
            id.into(),
            Hint {
                title: title.into(),
                body: body.into(),
                dismissed: false,
                last_dismissed_ms: 0,
                accepted: false,
                dismisses: 0,
            },
        );
        Ok(())
    }

    /// Should this hint be shown now?
    pub fn should_show(&self, id: &str, now_ms: u64) -> bool {
        let Some(h) = self.hints.get(id) else {
            return false;
        };
        if h.accepted {
            return false;
        }
        if !h.dismissed {
            return true;
        }
        now_ms.saturating_sub(h.last_dismissed_ms) >= self.cooldown_ms
    }

    /// Dismiss.
    pub fn dismiss(&mut self, id: &str, now_ms: u64) -> Result<(), HintError> {
        let h = self
            .hints
            .get_mut(id)
            .ok_or_else(|| HintError::UnknownHint(id.into()))?;
        h.dismissed = true;
        h.last_dismissed_ms = now_ms;
        h.dismisses = h.dismisses.saturating_add(1);
        Ok(())
    }

    /// Accept (one-way).
    pub fn accept(&mut self, id: &str) -> Result<(), HintError> {
        let h = self
            .hints
            .get_mut(id)
            .ok_or_else(|| HintError::UnknownHint(id.into()))?;
        h.accepted = true;
        Ok(())
    }

    /// Reset a hint (clear dismissed/accepted).
    pub fn reset(&mut self, id: &str) -> Result<(), HintError> {
        let h = self
            .hints
            .get_mut(id)
            .ok_or_else(|| HintError::UnknownHint(id.into()))?;
        h.dismissed = false;
        h.accepted = false;
        h.last_dismissed_ms = 0;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HintError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HintError::SchemaMismatch);
        }
        if self.cooldown_ms == 0 {
            return Err(HintError::ZeroCooldown);
        }
        for (id, h) in &self.hints {
            if id.is_empty() {
                return Err(HintError::EmptyId);
            }
            if h.title.is_empty() {
                return Err(HintError::EmptyTitle);
            }
            if h.body.is_empty() {
                return Err(HintError::EmptyBody);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_shows() {
        let mut h = HintCard::new(60_000).unwrap();
        h.add("tip1", "Title", "Body").unwrap();
        assert!(h.should_show("tip1", 0));
    }

    #[test]
    fn dismiss_hides_within_cooldown() {
        let mut h = HintCard::new(60_000).unwrap();
        h.add("tip1", "Title", "Body").unwrap();
        h.dismiss("tip1", 0).unwrap();
        assert!(!h.should_show("tip1", 30_000));
    }

    #[test]
    fn cooldown_elapses() {
        let mut h = HintCard::new(60_000).unwrap();
        h.add("tip1", "Title", "Body").unwrap();
        h.dismiss("tip1", 0).unwrap();
        assert!(h.should_show("tip1", 70_000));
    }

    #[test]
    fn accept_hides_permanently() {
        let mut h = HintCard::new(60_000).unwrap();
        h.add("tip1", "Title", "Body").unwrap();
        h.accept("tip1").unwrap();
        assert!(!h.should_show("tip1", 999_999_999));
    }

    #[test]
    fn reset_clears() {
        let mut h = HintCard::new(60_000).unwrap();
        h.add("tip1", "Title", "Body").unwrap();
        h.accept("tip1").unwrap();
        h.reset("tip1").unwrap();
        assert!(h.should_show("tip1", 0));
    }

    #[test]
    fn unknown_hint_not_shown() {
        let h = HintCard::new(60_000).unwrap();
        assert!(!h.should_show("nope", 0));
    }

    #[test]
    fn duplicate_rejected() {
        let mut h = HintCard::new(60_000).unwrap();
        h.add("a", "t", "b").unwrap();
        assert!(matches!(
            h.add("a", "t", "b").unwrap_err(),
            HintError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut h = HintCard::new(60_000).unwrap();
        assert!(matches!(
            h.add("", "t", "b").unwrap_err(),
            HintError::EmptyId
        ));
        assert!(matches!(
            HintCard::new(0).unwrap_err(),
            HintError::ZeroCooldown
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = HintCard::new(60_000).unwrap();
        h.schema_version = "9.9.9".into();
        assert!(matches!(
            h.validate().unwrap_err(),
            HintError::SchemaMismatch
        ));
    }

    #[test]
    fn card_serde_roundtrip() {
        let mut h = HintCard::new(60_000).unwrap();
        h.add("tip1", "Title", "Body").unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: HintCard = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
