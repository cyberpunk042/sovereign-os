//! `sovereign-cockpit-feature-promo-banner` — feature promotion.
//!
//! Promo{id, title, body, valid_from_ms, valid_until_ms}. Per-user
//! dismissals + snoozes. should_show(promo_id, user_id, now)
//! returns bool.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One promo.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Promo {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Body.
    pub body: String,
    /// Valid from ts.
    pub valid_from_ms: u64,
    /// Valid until ts.
    pub valid_until_ms: u64,
}

/// Per-user state for a promo.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct UserPromoState {
    /// Dismissed permanently.
    pub dismissed: bool,
    /// Snoozed until ts.
    pub snoozed_until_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FeaturePromoBanner {
    /// Schema version.
    pub schema_version: String,
    /// promo id → promo.
    pub promos: BTreeMap<String, Promo>,
    /// (promo, user) → state.
    pub user_state: BTreeMap<String, BTreeMap<String, UserPromoState>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PromoError {
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
    /// Empty.
    #[error("user empty")]
    EmptyUser,
    /// Inverted.
    #[error("valid_from ({f}) >= valid_until ({u})")]
    Inverted {
        /// f.
        f: u64,
        /// u.
        u: u64,
    },
    /// Duplicate.
    #[error("duplicate promo id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown promo: {0}")]
    UnknownPromo(String),
}

impl FeaturePromoBanner {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            promos: BTreeMap::new(),
            user_state: BTreeMap::new(),
        }
    }

    /// Register promo.
    pub fn register(
        &mut self,
        id: &str,
        title: &str,
        body: &str,
        valid_from_ms: u64,
        valid_until_ms: u64,
    ) -> Result<(), PromoError> {
        if id.is_empty() {
            return Err(PromoError::EmptyId);
        }
        if title.is_empty() {
            return Err(PromoError::EmptyTitle);
        }
        if body.is_empty() {
            return Err(PromoError::EmptyBody);
        }
        if valid_from_ms >= valid_until_ms {
            return Err(PromoError::Inverted {
                f: valid_from_ms,
                u: valid_until_ms,
            });
        }
        if self.promos.contains_key(id) {
            return Err(PromoError::DuplicateId(id.into()));
        }
        self.promos.insert(
            id.into(),
            Promo {
                id: id.into(),
                title: title.into(),
                body: body.into(),
                valid_from_ms,
                valid_until_ms,
            },
        );
        Ok(())
    }

    /// Dismiss.
    pub fn dismiss(&mut self, promo_id: &str, user_id: &str) -> Result<(), PromoError> {
        if user_id.is_empty() {
            return Err(PromoError::EmptyUser);
        }
        if !self.promos.contains_key(promo_id) {
            return Err(PromoError::UnknownPromo(promo_id.into()));
        }
        let s = self
            .user_state
            .entry(promo_id.into())
            .or_default()
            .entry(user_id.into())
            .or_default();
        s.dismissed = true;
        Ok(())
    }

    /// Snooze until.
    pub fn snooze(
        &mut self,
        promo_id: &str,
        user_id: &str,
        until_ms: u64,
    ) -> Result<(), PromoError> {
        if user_id.is_empty() {
            return Err(PromoError::EmptyUser);
        }
        if !self.promos.contains_key(promo_id) {
            return Err(PromoError::UnknownPromo(promo_id.into()));
        }
        let s = self
            .user_state
            .entry(promo_id.into())
            .or_default()
            .entry(user_id.into())
            .or_default();
        s.snoozed_until_ms = until_ms;
        Ok(())
    }

    /// Should show?
    pub fn should_show(&self, promo_id: &str, user_id: &str, now_ms: u64) -> bool {
        let Some(p) = self.promos.get(promo_id) else {
            return false;
        };
        if now_ms < p.valid_from_ms || now_ms >= p.valid_until_ms {
            return false;
        }
        if let Some(per_promo) = self.user_state.get(promo_id)
            && let Some(s) = per_promo.get(user_id)
        {
            if s.dismissed {
                return false;
            }
            if now_ms < s.snoozed_until_ms {
                return false;
            }
        }
        true
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PromoError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PromoError::SchemaMismatch);
        }
        for (id, p) in &self.promos {
            if id.is_empty() {
                return Err(PromoError::EmptyId);
            }
            if p.title.is_empty() {
                return Err(PromoError::EmptyTitle);
            }
            if p.body.is_empty() {
                return Err(PromoError::EmptyBody);
            }
            if p.valid_from_ms >= p.valid_until_ms {
                return Err(PromoError::Inverted {
                    f: p.valid_from_ms,
                    u: p.valid_until_ms,
                });
            }
        }
        Ok(())
    }
}

impl Default for FeaturePromoBanner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn show_within_window() {
        let mut p = FeaturePromoBanner::new();
        p.register("f1", "Try this", "New feature", 100, 200)
            .unwrap();
        assert!(p.should_show("f1", "alice", 150));
    }

    #[test]
    fn hide_outside_window() {
        let mut p = FeaturePromoBanner::new();
        p.register("f1", "X", "Y", 100, 200).unwrap();
        assert!(!p.should_show("f1", "alice", 50));
        assert!(!p.should_show("f1", "alice", 250));
    }

    #[test]
    fn dismiss_hides() {
        let mut p = FeaturePromoBanner::new();
        p.register("f1", "X", "Y", 100, 200).unwrap();
        p.dismiss("f1", "alice").unwrap();
        assert!(!p.should_show("f1", "alice", 150));
        // Other users still see it.
        assert!(p.should_show("f1", "bob", 150));
    }

    #[test]
    fn snooze_hides_until_due() {
        let mut p = FeaturePromoBanner::new();
        p.register("f1", "X", "Y", 100, 300).unwrap();
        p.snooze("f1", "alice", 200).unwrap();
        assert!(!p.should_show("f1", "alice", 150));
        assert!(p.should_show("f1", "alice", 250));
    }

    #[test]
    fn duplicate_promo_rejected() {
        let mut p = FeaturePromoBanner::new();
        p.register("f1", "X", "Y", 100, 200).unwrap();
        assert!(matches!(
            p.register("f1", "X", "Y", 100, 200).unwrap_err(),
            PromoError::DuplicateId(_)
        ));
    }

    #[test]
    fn inverted_window_rejected() {
        let mut p = FeaturePromoBanner::new();
        assert!(matches!(
            p.register("f1", "X", "Y", 200, 100).unwrap_err(),
            PromoError::Inverted { .. }
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut p = FeaturePromoBanner::new();
        assert!(matches!(
            p.register("", "X", "Y", 0, 1).unwrap_err(),
            PromoError::EmptyId
        ));
        assert!(matches!(
            p.register("f", "", "Y", 0, 1).unwrap_err(),
            PromoError::EmptyTitle
        ));
        assert!(matches!(
            p.register("f", "X", "", 0, 1).unwrap_err(),
            PromoError::EmptyBody
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = FeaturePromoBanner::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PromoError::SchemaMismatch
        ));
    }

    #[test]
    fn promo_serde_roundtrip() {
        let mut p = FeaturePromoBanner::new();
        p.register("f1", "X", "Y", 100, 200).unwrap();
        p.dismiss("f1", "alice").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: FeaturePromoBanner = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
