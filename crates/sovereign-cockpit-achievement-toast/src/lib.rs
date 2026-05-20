//! `sovereign-cockpit-achievement-toast` — earned-achievement toast.
//!
//! Achievement{id, title, tier}. earn(id, …, now_ms) enqueues iff
//! id not yet earned (achievements are unique). show(now) returns
//! the front of the queue when no toast is actively showing OR the
//! current one's show_until has passed. ack drops the current item.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeSet, VecDeque};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Tier.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Tier {
    /// Bronze.
    Bronze,
    /// Silver.
    Silver,
    /// Gold.
    Gold,
    /// Platinum.
    Platinum,
}

/// Achievement record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Achievement {
    /// Stable id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Tier.
    pub tier: Tier,
    /// Earned ts ms.
    pub earned_at_ms: u64,
    /// Show-until ts ms (set when actively shown).
    pub show_until_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AchievementToast {
    /// Schema version.
    pub schema_version: String,
    /// Visible duration ms.
    pub duration_ms: u64,
    /// Earned-once set.
    pub earned_ids: BTreeSet<String>,
    /// Pending queue.
    pub queue: VecDeque<Achievement>,
    /// Currently showing.
    pub showing: Option<Achievement>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero duration.
    #[error("duration_ms must be >= 1")]
    ZeroDuration,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty title.
    #[error("title empty")]
    EmptyTitle,
    /// Already.
    #[error("already earned: {0}")]
    AlreadyEarned(String),
}

impl AchievementToast {
    /// New.
    pub fn new(duration_ms: u64) -> Result<Self, AchError> {
        if duration_ms == 0 { return Err(AchError::ZeroDuration); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            duration_ms,
            earned_ids: BTreeSet::new(),
            queue: VecDeque::new(),
            showing: None,
        })
    }

    /// Earn — enqueue unless already earned.
    pub fn earn(&mut self, id: &str, title: &str, tier: Tier, now_ms: u64) -> Result<(), AchError> {
        if id.is_empty() { return Err(AchError::EmptyId); }
        if title.is_empty() { return Err(AchError::EmptyTitle); }
        if self.earned_ids.contains(id) {
            return Err(AchError::AlreadyEarned(id.into()));
        }
        self.earned_ids.insert(id.into());
        self.queue.push_back(Achievement {
            id: id.into(),
            title: title.into(),
            tier,
            earned_at_ms: now_ms,
            show_until_ms: 0,
        });
        Ok(())
    }

    /// Promote next item to showing if slot is free / current expired.
    /// Returns Some(&Achievement) if showing.
    pub fn show(&mut self, now_ms: u64) -> Option<&Achievement> {
        // Expire current if past show_until.
        if let Some(a) = &self.showing {
            if a.show_until_ms <= now_ms {
                self.showing = None;
            }
        }
        if self.showing.is_none() {
            if let Some(mut next) = self.queue.pop_front() {
                next.show_until_ms = now_ms.saturating_add(self.duration_ms);
                self.showing = Some(next);
            }
        }
        self.showing.as_ref()
    }

    /// Ack the current toast (dismiss explicitly).
    pub fn ack(&mut self) { self.showing = None; }

    /// Validate.
    pub fn validate(&self) -> Result<(), AchError> {
        if self.schema_version != SCHEMA_VERSION { return Err(AchError::SchemaMismatch); }
        if self.duration_ms == 0 { return Err(AchError::ZeroDuration); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn earn_enqueues() {
        let mut t = AchievementToast::new(1000).unwrap();
        t.earn("a", "First Step", Tier::Bronze, 0).unwrap();
        assert_eq!(t.queue.len(), 1);
    }

    #[test]
    fn show_promotes_from_queue() {
        let mut t = AchievementToast::new(1000).unwrap();
        t.earn("a", "First", Tier::Bronze, 0).unwrap();
        let a = t.show(0).unwrap();
        assert_eq!(a.id, "a");
        assert_eq!(a.show_until_ms, 1000);
    }

    #[test]
    fn show_returns_same_until_expiry() {
        let mut t = AchievementToast::new(1000).unwrap();
        t.earn("a", "First", Tier::Bronze, 0).unwrap();
        t.earn("b", "Second", Tier::Silver, 0).unwrap();
        assert_eq!(t.show(100).unwrap().id, "a");
        assert_eq!(t.show(500).unwrap().id, "a");
        // After expiry, next promotes.
        assert_eq!(t.show(1500).unwrap().id, "b");
    }

    #[test]
    fn ack_dismisses_current() {
        let mut t = AchievementToast::new(1000).unwrap();
        t.earn("a", "First", Tier::Bronze, 0).unwrap();
        t.earn("b", "Second", Tier::Silver, 0).unwrap();
        t.show(0);
        t.ack();
        // Next show promotes b.
        assert_eq!(t.show(100).unwrap().id, "b");
    }

    #[test]
    fn already_earned_rejected() {
        let mut t = AchievementToast::new(1000).unwrap();
        t.earn("a", "x", Tier::Bronze, 0).unwrap();
        assert!(matches!(t.earn("a", "x", Tier::Gold, 0).unwrap_err(), AchError::AlreadyEarned(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut t = AchievementToast::new(1000).unwrap();
        assert!(matches!(t.earn("", "x", Tier::Bronze, 0).unwrap_err(), AchError::EmptyId));
        assert!(matches!(t.earn("a", "", Tier::Bronze, 0).unwrap_err(), AchError::EmptyTitle));
    }

    #[test]
    fn zero_duration_rejected() {
        assert!(matches!(AchievementToast::new(0).unwrap_err(), AchError::ZeroDuration));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = AchievementToast::new(1000).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), AchError::SchemaMismatch));
    }

    #[test]
    fn toast_serde_roundtrip() {
        let mut t = AchievementToast::new(500).unwrap();
        t.earn("a", "x", Tier::Gold, 1).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: AchievementToast = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
