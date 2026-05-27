//! `sovereign-cockpit-banner-bus` — single-slot priority banner bus.
//!
//! Only one banner is shown at a time. `post(banner)`:
//!
//!   * If slot empty → install banner.
//!   * Else if `banner.priority > current.priority` → install banner,
//!     push current to the back-queue.
//!   * Else → enqueue banner.
//!
//! `dismiss(id)`:
//!   * If `id` matches current → pop highest-priority queued and
//!     install (else slot becomes empty).
//!   * Else if `id` is in the queue → remove.
//!   * Else → no-op.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One banner.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Banner {
    /// Stable id.
    pub id: String,
    /// Display title.
    pub title: String,
    /// Body.
    pub body: String,
    /// Priority (higher wins).
    pub priority: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BannerBus {
    /// Schema version.
    pub schema_version: String,
    /// Currently shown.
    pub current: Option<Banner>,
    /// Queued behind.
    pub queued: Vec<Banner>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BusError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("banner id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate banner id: {0}")]
    DuplicateId(String),
}

impl BannerBus {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            current: None,
            queued: Vec::new(),
        }
    }

    /// Post.
    pub fn post(&mut self, b: Banner) -> Result<(), BusError> {
        if b.id.is_empty() {
            return Err(BusError::EmptyId);
        }
        if self.current.as_ref().is_some_and(|c| c.id == b.id) {
            return Err(BusError::DuplicateId(b.id));
        }
        if self.queued.iter().any(|x| x.id == b.id) {
            return Err(BusError::DuplicateId(b.id));
        }
        match self.current.take() {
            None => self.current = Some(b),
            Some(c) => {
                if b.priority > c.priority {
                    self.queued.push(c);
                    self.current = Some(b);
                } else {
                    self.current = Some(c);
                    self.queued.push(b);
                }
            }
        }
        Ok(())
    }

    /// Dismiss.
    pub fn dismiss(&mut self, id: &str) -> bool {
        if self.current.as_ref().is_some_and(|c| c.id == id) {
            self.current = None;
            self.promote_next();
            return true;
        }
        if let Some(pos) = self.queued.iter().position(|b| b.id == id) {
            self.queued.remove(pos);
            return true;
        }
        false
    }

    fn promote_next(&mut self) {
        if self.queued.is_empty() {
            return;
        }
        // Pick highest priority; tie-break by FIFO (lowest index).
        let mut best = 0usize;
        for i in 1..self.queued.len() {
            if self.queued[i].priority > self.queued[best].priority {
                best = i;
            }
        }
        let next = self.queued.remove(best);
        self.current = Some(next);
    }

    /// Current banner.
    pub fn current(&self) -> Option<&Banner> {
        self.current.as_ref()
    }

    /// Queued banners (in arrival order).
    pub fn queued(&self) -> &[Banner] {
        &self.queued
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BusError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BusError::SchemaMismatch);
        }
        if let Some(c) = &self.current
            && c.id.is_empty()
        {
            return Err(BusError::EmptyId);
        }
        for b in &self.queued {
            if b.id.is_empty() {
                return Err(BusError::EmptyId);
            }
        }
        Ok(())
    }
}

impl Default for BannerBus {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b(id: &str, prio: u32) -> Banner {
        Banner {
            id: id.into(),
            title: id.into(),
            body: "".into(),
            priority: prio,
        }
    }

    #[test]
    fn post_to_empty_slot() {
        let mut bus = BannerBus::new();
        bus.post(b("a", 1)).unwrap();
        assert_eq!(bus.current().unwrap().id, "a");
        assert!(bus.queued().is_empty());
    }

    #[test]
    fn higher_priority_replaces() {
        let mut bus = BannerBus::new();
        bus.post(b("a", 1)).unwrap();
        bus.post(b("b", 5)).unwrap();
        assert_eq!(bus.current().unwrap().id, "b");
        assert_eq!(bus.queued().len(), 1);
        assert_eq!(bus.queued()[0].id, "a");
    }

    #[test]
    fn lower_priority_queues() {
        let mut bus = BannerBus::new();
        bus.post(b("a", 5)).unwrap();
        bus.post(b("b", 1)).unwrap();
        assert_eq!(bus.current().unwrap().id, "a");
        assert_eq!(bus.queued()[0].id, "b");
    }

    #[test]
    fn dismiss_current_promotes_highest_queued() {
        let mut bus = BannerBus::new();
        bus.post(b("a", 10)).unwrap();
        bus.post(b("b", 1)).unwrap();
        bus.post(b("c", 5)).unwrap();
        bus.dismiss("a");
        assert_eq!(bus.current().unwrap().id, "c");
    }

    #[test]
    fn dismiss_empties_when_no_queue() {
        let mut bus = BannerBus::new();
        bus.post(b("a", 1)).unwrap();
        bus.dismiss("a");
        assert!(bus.current().is_none());
    }

    #[test]
    fn dismiss_queued_removes_from_queue() {
        let mut bus = BannerBus::new();
        bus.post(b("a", 10)).unwrap();
        bus.post(b("b", 1)).unwrap();
        bus.dismiss("b");
        assert_eq!(bus.current().unwrap().id, "a");
        assert!(bus.queued().is_empty());
    }

    #[test]
    fn dismiss_unknown_returns_false() {
        let mut bus = BannerBus::new();
        assert!(!bus.dismiss("nope"));
    }

    #[test]
    fn duplicate_post_rejected() {
        let mut bus = BannerBus::new();
        bus.post(b("a", 1)).unwrap();
        assert!(matches!(
            bus.post(b("a", 5)).unwrap_err(),
            BusError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut bus = BannerBus::new();
        assert!(matches!(bus.post(b("", 1)).unwrap_err(), BusError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut bus = BannerBus::new();
        bus.schema_version = "9.9.9".into();
        assert!(matches!(
            bus.validate().unwrap_err(),
            BusError::SchemaMismatch
        ));
    }

    #[test]
    fn bus_serde_roundtrip() {
        let mut bus = BannerBus::new();
        bus.post(b("a", 5)).unwrap();
        bus.post(b("b", 1)).unwrap();
        let j = serde_json::to_string(&bus).unwrap();
        let back: BannerBus = serde_json::from_str(&j).unwrap();
        assert_eq!(bus, back);
    }
}
