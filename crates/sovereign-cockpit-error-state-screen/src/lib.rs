//! `sovereign-cockpit-error-state-screen` — large-format error UI.
//!
//! When a major view fails to load, the cockpit shows a full-screen
//! state with a category (Network/Permission/NotFound/Server/Unknown),
//! a headline, a body, an optional `retry_handler_id`, and a retry
//! counter. `attempt_retry()` increments counter; the caller is
//! responsible for actually re-triggering the handler.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Error category.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Category {
    /// Network.
    Network,
    /// Permission denied.
    Permission,
    /// 404 / not found.
    NotFound,
    /// 5xx server error.
    Server,
    /// Anything else.
    Unknown,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ErrorStateScreen {
    /// Schema version.
    pub schema_version: String,
    /// Category.
    pub category: Category,
    /// Headline.
    pub headline: String,
    /// Body / details.
    pub body: String,
    /// Retry handler (None = no retry button).
    pub retry_handler_id: Option<String>,
    /// Retry attempts.
    pub retry_attempts: u32,
    /// Last attempt ts.
    pub last_attempt_ms: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ScreenError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty headline.
    #[error("headline empty")]
    EmptyHeadline,
    /// Empty body.
    #[error("body empty")]
    EmptyBody,
    /// Empty handler id.
    #[error("handler id empty")]
    EmptyHandler,
    /// No retry handler set.
    #[error("no retry handler set")]
    NoRetry,
}

impl ErrorStateScreen {
    /// New.
    pub fn new(category: Category, headline: &str, body: &str) -> Result<Self, ScreenError> {
        if headline.is_empty() {
            return Err(ScreenError::EmptyHeadline);
        }
        if body.is_empty() {
            return Err(ScreenError::EmptyBody);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            category,
            headline: headline.into(),
            body: body.into(),
            retry_handler_id: None,
            retry_attempts: 0,
            last_attempt_ms: 0,
        })
    }

    /// Wire up retry.
    pub fn with_retry(mut self, handler_id: &str) -> Result<Self, ScreenError> {
        if handler_id.is_empty() {
            return Err(ScreenError::EmptyHandler);
        }
        self.retry_handler_id = Some(handler_id.into());
        Ok(self)
    }

    /// Attempt retry (increments counter; caller invokes handler).
    pub fn attempt_retry(&mut self, ts_ms: u64) -> Result<u32, ScreenError> {
        if self.retry_handler_id.is_none() {
            return Err(ScreenError::NoRetry);
        }
        self.retry_attempts = self.retry_attempts.saturating_add(1);
        self.last_attempt_ms = ts_ms;
        Ok(self.retry_attempts)
    }

    /// Is retry offered?
    pub fn can_retry(&self) -> bool {
        self.retry_handler_id.is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ScreenError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ScreenError::SchemaMismatch);
        }
        if self.headline.is_empty() {
            return Err(ScreenError::EmptyHeadline);
        }
        if self.body.is_empty() {
            return Err(ScreenError::EmptyBody);
        }
        if let Some(h) = &self.retry_handler_id {
            if h.is_empty() {
                return Err(ScreenError::EmptyHandler);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_basic() {
        let s = ErrorStateScreen::new(Category::Network, "Offline", "You are offline").unwrap();
        assert_eq!(s.category, Category::Network);
        assert!(!s.can_retry());
    }

    #[test]
    fn with_retry_makes_retryable() {
        let s = ErrorStateScreen::new(Category::Server, "Oops", "Server error")
            .unwrap()
            .with_retry("reload-view")
            .unwrap();
        assert!(s.can_retry());
    }

    #[test]
    fn attempt_retry_increments() {
        let mut s = ErrorStateScreen::new(Category::Network, "Offline", "x")
            .unwrap()
            .with_retry("h")
            .unwrap();
        assert_eq!(s.attempt_retry(100).unwrap(), 1);
        assert_eq!(s.attempt_retry(200).unwrap(), 2);
        assert_eq!(s.last_attempt_ms, 200);
    }

    #[test]
    fn retry_without_handler_rejected() {
        let mut s = ErrorStateScreen::new(Category::Network, "Offline", "x").unwrap();
        assert!(matches!(
            s.attempt_retry(0).unwrap_err(),
            ScreenError::NoRetry
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        assert!(matches!(
            ErrorStateScreen::new(Category::Network, "", "x").unwrap_err(),
            ScreenError::EmptyHeadline
        ));
        assert!(matches!(
            ErrorStateScreen::new(Category::Network, "h", "").unwrap_err(),
            ScreenError::EmptyBody
        ));
        let s = ErrorStateScreen::new(Category::Network, "h", "b").unwrap();
        assert!(matches!(
            s.with_retry("").unwrap_err(),
            ScreenError::EmptyHandler
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ErrorStateScreen::new(Category::Network, "h", "b").unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            ScreenError::SchemaMismatch
        ));
    }

    #[test]
    fn categories_distinct() {
        let n = ErrorStateScreen::new(Category::Network, "h", "b").unwrap();
        let p = ErrorStateScreen::new(Category::Permission, "h", "b").unwrap();
        let nf = ErrorStateScreen::new(Category::NotFound, "h", "b").unwrap();
        let s = ErrorStateScreen::new(Category::Server, "h", "b").unwrap();
        let u = ErrorStateScreen::new(Category::Unknown, "h", "b").unwrap();
        assert!(
            n.category != p.category
                && p.category != nf.category
                && nf.category != s.category
                && s.category != u.category
        );
    }

    #[test]
    fn screen_serde_roundtrip() {
        let mut s = ErrorStateScreen::new(Category::Server, "Oops", "Server error")
            .unwrap()
            .with_retry("h")
            .unwrap();
        s.attempt_retry(100).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ErrorStateScreen = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
