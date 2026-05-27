//! `sovereign-cockpit-aria-live-router` — route cockpit messages to ARIA live regions.
//!
//! Severity → Region:
//!   - Info, Success → Polite
//!   - Warn, Error   → Assertive
//!
//! Each region has a per-message dedup window. If the same text was
//! announced within `dedup_ms`, the new push returns
//! `RouteResult::Suppressed`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity of a cockpit message.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Informational.
    Info,
    /// Success / completion.
    Success,
    /// Warning.
    Warn,
    /// Error.
    Error,
}

/// ARIA live region.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LiveRegion {
    /// aria-live=polite.
    Polite,
    /// aria-live=assertive.
    Assertive,
}

/// One announced message.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Announcement {
    /// ts ms (monotonic).
    pub ts_ms: u64,
    /// region.
    pub region: LiveRegion,
    /// text.
    pub text: String,
}

/// Routing outcome.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum RouteResult {
    /// Announced to the named region.
    Announced {
        /// region.
        region: LiveRegion,
    },
    /// Suppressed (identical text within dedup window).
    Suppressed {
        /// region.
        region: LiveRegion,
        /// ms since the last identical announcement.
        last_age_ms: u64,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AriaLiveRouter {
    /// Schema version.
    pub schema_version: String,
    /// Dedup window (ms).
    pub dedup_ms: u64,
    /// Recent announcements, ts-ascending.
    pub recent: Vec<Announcement>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RouterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty text.
    #[error("empty text")]
    EmptyText,
    /// Non-monotonic.
    #[error("non-monotonic ts: prev {prev} > new {new}")]
    NonMonotonic {
        /// prev.
        prev: u64,
        /// new.
        new: u64,
    },
}

impl AriaLiveRouter {
    /// New.
    pub fn new(dedup_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            dedup_ms,
            recent: Vec::new(),
        }
    }

    /// Map severity to region.
    pub fn region_for(sev: Severity) -> LiveRegion {
        match sev {
            Severity::Info | Severity::Success => LiveRegion::Polite,
            Severity::Warn | Severity::Error => LiveRegion::Assertive,
        }
    }

    /// Route a message.
    pub fn announce(
        &mut self,
        sev: Severity,
        text: &str,
        now_ms: u64,
    ) -> Result<RouteResult, RouterError> {
        if text.is_empty() {
            return Err(RouterError::EmptyText);
        }
        if let Some(last) = self.recent.last()
            && now_ms < last.ts_ms
        {
            return Err(RouterError::NonMonotonic {
                prev: last.ts_ms,
                new: now_ms,
            });
        }
        let region = Self::region_for(sev);
        let cutoff = now_ms.saturating_sub(self.dedup_ms);
        if let Some(prev) = self
            .recent
            .iter()
            .rev()
            .find(|a| a.region == region && a.text == text && a.ts_ms >= cutoff)
        {
            return Ok(RouteResult::Suppressed {
                region,
                last_age_ms: now_ms.saturating_sub(prev.ts_ms),
            });
        }
        self.recent.push(Announcement {
            ts_ms: now_ms,
            region,
            text: text.into(),
        });
        // Cap recent buffer to last 256 to bound memory; older auto-expire via dedup anyway.
        if self.recent.len() > 256 {
            let drop = self.recent.len() - 256;
            self.recent.drain(0..drop);
        }
        Ok(RouteResult::Announced { region })
    }

    /// Drop announcements older than dedup window prior to now.
    pub fn rotate(&mut self, now_ms: u64) {
        let cutoff = now_ms.saturating_sub(self.dedup_ms);
        self.recent.retain(|a| a.ts_ms >= cutoff);
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RouterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RouterError::SchemaMismatch);
        }
        let mut last = 0u64;
        for a in &self.recent {
            if a.text.is_empty() {
                return Err(RouterError::EmptyText);
            }
            if a.ts_ms < last {
                return Err(RouterError::NonMonotonic {
                    prev: last,
                    new: a.ts_ms,
                });
            }
            last = a.ts_ms;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn severity_maps_polite() {
        assert_eq!(
            AriaLiveRouter::region_for(Severity::Info),
            LiveRegion::Polite
        );
        assert_eq!(
            AriaLiveRouter::region_for(Severity::Success),
            LiveRegion::Polite
        );
    }

    #[test]
    fn severity_maps_assertive() {
        assert_eq!(
            AriaLiveRouter::region_for(Severity::Warn),
            LiveRegion::Assertive
        );
        assert_eq!(
            AriaLiveRouter::region_for(Severity::Error),
            LiveRegion::Assertive
        );
    }

    #[test]
    fn announce_polite() {
        let mut r = AriaLiveRouter::new(2000);
        let v = r.announce(Severity::Info, "Saved.", 0).unwrap();
        assert_eq!(
            v,
            RouteResult::Announced {
                region: LiveRegion::Polite
            }
        );
    }

    #[test]
    fn duplicate_within_window_suppressed() {
        let mut r = AriaLiveRouter::new(2000);
        r.announce(Severity::Info, "Saved.", 0).unwrap();
        let v = r.announce(Severity::Info, "Saved.", 500).unwrap();
        assert!(matches!(
            v,
            RouteResult::Suppressed {
                region: LiveRegion::Polite,
                ..
            }
        ));
    }

    #[test]
    fn duplicate_after_window_announces() {
        let mut r = AriaLiveRouter::new(2000);
        r.announce(Severity::Info, "Saved.", 0).unwrap();
        let v = r.announce(Severity::Info, "Saved.", 2500).unwrap();
        assert_eq!(
            v,
            RouteResult::Announced {
                region: LiveRegion::Polite
            }
        );
    }

    #[test]
    fn cross_region_not_deduped() {
        let mut r = AriaLiveRouter::new(10_000);
        r.announce(Severity::Info, "Saved.", 0).unwrap();
        // Same text but warn → assertive region; should still announce.
        let v = r.announce(Severity::Warn, "Saved.", 500).unwrap();
        assert_eq!(
            v,
            RouteResult::Announced {
                region: LiveRegion::Assertive
            }
        );
    }

    #[test]
    fn empty_text_rejected() {
        let mut r = AriaLiveRouter::new(2000);
        assert!(matches!(
            r.announce(Severity::Info, "", 0).unwrap_err(),
            RouterError::EmptyText
        ));
    }

    #[test]
    fn nonmonotonic_rejected() {
        let mut r = AriaLiveRouter::new(2000);
        r.announce(Severity::Info, "x", 100).unwrap();
        assert!(matches!(
            r.announce(Severity::Info, "y", 50).unwrap_err(),
            RouterError::NonMonotonic { .. }
        ));
    }

    #[test]
    fn rotate_drops_old() {
        let mut r = AriaLiveRouter::new(2000);
        r.announce(Severity::Info, "x", 0).unwrap();
        r.rotate(10_000);
        assert!(r.recent.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = AriaLiveRouter::new(2000);
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RouterError::SchemaMismatch
        ));
    }

    #[test]
    fn router_serde_roundtrip() {
        let mut r = AriaLiveRouter::new(2000);
        r.announce(Severity::Warn, "Boom!", 0).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: AriaLiveRouter = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
