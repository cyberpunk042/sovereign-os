//! `sovereign-cockpit-rate-limit-banner` — throttle banner.
//!
//! Reads (Throttled until_ms / Allowed). render(now_ms) returns
//! Hidden when allowed; CountdownBanner{message, remaining_seconds}
//! when throttled.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RateLimitBanner {
    /// Schema version.
    pub schema_version: String,
    /// Throttled until wall-clock ms (0 = not throttled).
    pub throttled_until_ms: u64,
    /// Reason text shown when throttled.
    pub reason: String,
}

/// Render.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum BannerRender {
    /// Hidden (not throttled).
    Hidden,
    /// Countdown banner.
    Countdown {
        /// message.
        message: String,
        /// remaining seconds.
        remaining_seconds: u32,
    },
}

/// Errors.
#[derive(Debug, Error)]
pub enum BannerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty reason when throttled.
    #[error("reason empty when throttled")]
    EmptyReason,
}

impl RateLimitBanner {
    /// New (not throttled).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            throttled_until_ms: 0,
            reason: String::new(),
        }
    }

    /// Apply throttle.
    pub fn throttle_until(&mut self, until_ms: u64, reason: &str) -> Result<(), BannerError> {
        if reason.is_empty() {
            return Err(BannerError::EmptyReason);
        }
        self.throttled_until_ms = until_ms;
        self.reason = reason.into();
        Ok(())
    }

    /// Clear throttle.
    pub fn clear(&mut self) {
        self.throttled_until_ms = 0;
        self.reason.clear();
    }

    /// Render at now.
    pub fn render(&self, now_ms: u64) -> BannerRender {
        if self.throttled_until_ms == 0 || now_ms >= self.throttled_until_ms {
            return BannerRender::Hidden;
        }
        let remaining_ms = self.throttled_until_ms - now_ms;
        let remaining_seconds = ((remaining_ms + 999) / 1000) as u32; // ceil
        BannerRender::Countdown {
            message: format!("{} — try again in {}s", self.reason, remaining_seconds),
            remaining_seconds,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BannerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BannerError::SchemaMismatch);
        }
        if self.throttled_until_ms > 0 && self.reason.is_empty() {
            return Err(BannerError::EmptyReason);
        }
        Ok(())
    }
}

impl Default for RateLimitBanner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_hidden() {
        let b = RateLimitBanner::new();
        assert!(matches!(b.render(0), BannerRender::Hidden));
    }

    #[test]
    fn throttle_renders_countdown() {
        let mut b = RateLimitBanner::new();
        b.throttle_until(10_000, "too many requests").unwrap();
        match b.render(5_000) {
            BannerRender::Countdown {
                remaining_seconds,
                message,
            } => {
                assert_eq!(remaining_seconds, 5);
                assert!(message.contains("too many requests"));
                assert!(message.contains("5s"));
            }
            _ => panic!(),
        }
    }

    #[test]
    fn expired_throttle_hidden() {
        let mut b = RateLimitBanner::new();
        b.throttle_until(5_000, "throttled").unwrap();
        assert!(matches!(b.render(6_000), BannerRender::Hidden));
    }

    #[test]
    fn at_expiry_hidden() {
        let mut b = RateLimitBanner::new();
        b.throttle_until(5_000, "throttled").unwrap();
        assert!(matches!(b.render(5_000), BannerRender::Hidden));
    }

    #[test]
    fn clear_resets() {
        let mut b = RateLimitBanner::new();
        b.throttle_until(5_000, "x").unwrap();
        b.clear();
        assert!(matches!(b.render(0), BannerRender::Hidden));
    }

    #[test]
    fn empty_reason_rejected() {
        let mut b = RateLimitBanner::new();
        assert!(matches!(
            b.throttle_until(1000, "").unwrap_err(),
            BannerError::EmptyReason
        ));
    }

    #[test]
    fn validate_throttled_no_reason_rejected() {
        let mut b = RateLimitBanner::new();
        b.throttled_until_ms = 1000;
        assert!(matches!(
            b.validate().unwrap_err(),
            BannerError::EmptyReason
        ));
    }

    #[test]
    fn ceil_remaining_seconds() {
        let mut b = RateLimitBanner::new();
        b.throttle_until(1500, "x").unwrap();
        match b.render(0) {
            BannerRender::Countdown {
                remaining_seconds, ..
            } => assert_eq!(remaining_seconds, 2),
            _ => panic!(),
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = RateLimitBanner::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            BannerError::SchemaMismatch
        ));
    }

    #[test]
    fn render_serde_kebab() {
        let r = BannerRender::Hidden;
        assert!(
            serde_json::to_string(&r)
                .unwrap()
                .contains("\"kind\":\"hidden\"")
        );
    }

    #[test]
    fn banner_serde_roundtrip() {
        let mut b = RateLimitBanner::new();
        b.throttle_until(5000, "limited").unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: RateLimitBanner = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
