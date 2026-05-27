//! `sovereign-cockpit-error-banner` — persistent top-of-page banners.
//!
//! Stack of `ErrorBanner` items, each with (id, severity, title, body,
//! dismissible, primary_action). Capacity 5; oldest non-dismissible
//! retained over newer dismissibles.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_cockpit_banner_state::BannerSeverity;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max simultaneous banners.
pub const MAX_BANNERS: usize = 5;

/// One banner.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ErrorBanner {
    /// Id.
    pub id: String,
    /// Severity.
    pub severity: BannerSeverity,
    /// Title (≤ 80 chars).
    pub title: String,
    /// Body (≤ 400 chars).
    pub body: String,
    /// Whether operator can dismiss.
    pub dismissible: bool,
    /// Optional primary action label (e.g. "Retry").
    pub primary_action_label: String,
    /// Optional primary action command id.
    pub primary_action_command: String,
}

/// Stack envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ErrorBannerStack {
    /// Schema version.
    pub schema_version: String,
    /// Banners.
    pub banners: Vec<ErrorBanner>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BannerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("banner id empty")]
    EmptyId,
    /// Empty title.
    #[error("banner {0} title empty")]
    EmptyTitle(String),
    /// Title too long.
    #[error("banner {id} title length {len} > 80")]
    TitleTooLong {
        /// id.
        id: String,
        /// len.
        len: usize,
    },
    /// Body too long.
    #[error("banner {id} body length {len} > 400")]
    BodyTooLong {
        /// id.
        id: String,
        /// len.
        len: usize,
    },
    /// Duplicate.
    #[error("duplicate banner id: {0}")]
    Duplicate(String),
    /// Unknown.
    #[error("unknown banner id: {0}")]
    Unknown(String),
    /// Cannot dismiss non-dismissible.
    #[error("banner {0} is non-dismissible")]
    NotDismissible(String),
}

impl ErrorBannerStack {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            banners: Vec::new(),
        }
    }

    /// Push a banner. Overflow: drop oldest dismissible first.
    pub fn push(&mut self, b: ErrorBanner) -> Result<(), BannerError> {
        check_shape(&b)?;
        if self.banners.iter().any(|x| x.id == b.id) {
            return Err(BannerError::Duplicate(b.id));
        }
        self.banners.push(b);
        while self.banners.len() > MAX_BANNERS {
            if let Some(pos) = self.banners.iter().position(|x| x.dismissible) {
                self.banners.remove(pos);
            } else {
                // All non-dismissible — drop oldest anyway to enforce cap.
                self.banners.remove(0);
            }
        }
        Ok(())
    }

    /// Dismiss by id.
    pub fn dismiss(&mut self, id: &str) -> Result<(), BannerError> {
        let pos = self
            .banners
            .iter()
            .position(|b| b.id == id)
            .ok_or_else(|| BannerError::Unknown(id.into()))?;
        if !self.banners[pos].dismissible {
            return Err(BannerError::NotDismissible(id.into()));
        }
        self.banners.remove(pos);
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, id: &str) -> Option<&ErrorBanner> {
        self.banners.iter().find(|b| b.id == id)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BannerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BannerError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for b in &self.banners {
            check_shape(b)?;
            if !seen.insert(b.id.as_str()) {
                return Err(BannerError::Duplicate(b.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_shape(b: &ErrorBanner) -> Result<(), BannerError> {
    if b.id.is_empty() {
        return Err(BannerError::EmptyId);
    }
    if b.title.is_empty() {
        return Err(BannerError::EmptyTitle(b.id.clone()));
    }
    let n = b.title.chars().count();
    if n > 80 {
        return Err(BannerError::TitleTooLong {
            id: b.id.clone(),
            len: n,
        });
    }
    let n = b.body.chars().count();
    if n > 400 {
        return Err(BannerError::BodyTooLong {
            id: b.id.clone(),
            len: n,
        });
    }
    Ok(())
}

impl Default for ErrorBannerStack {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b(id: &str, sev: BannerSeverity, dismissible: bool) -> ErrorBanner {
        ErrorBanner {
            id: id.into(),
            severity: sev,
            title: format!("Title {id}"),
            body: String::new(),
            dismissible,
            primary_action_label: String::new(),
            primary_action_command: String::new(),
        }
    }

    #[test]
    fn empty_stack_validates() {
        ErrorBannerStack::new().validate().unwrap();
    }

    #[test]
    fn push_and_dismiss() {
        let mut s = ErrorBannerStack::new();
        s.push(b("a", BannerSeverity::Warn, true)).unwrap();
        s.dismiss("a").unwrap();
        assert!(s.banners.is_empty());
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = ErrorBannerStack::new();
        s.push(b("a", BannerSeverity::Warn, true)).unwrap();
        assert!(matches!(
            s.push(b("a", BannerSeverity::Critical, true)).unwrap_err(),
            BannerError::Duplicate(_)
        ));
    }

    #[test]
    fn non_dismissible_cannot_dismiss() {
        let mut s = ErrorBannerStack::new();
        s.push(b("a", BannerSeverity::Critical, false)).unwrap();
        assert!(matches!(
            s.dismiss("a").unwrap_err(),
            BannerError::NotDismissible(_)
        ));
    }

    #[test]
    fn overflow_drops_dismissible_first() {
        let mut s = ErrorBannerStack::new();
        // Non-dismissible at the bottom.
        s.push(b("crit", BannerSeverity::Critical, false)).unwrap();
        // Fill with dismissibles.
        for i in 0..MAX_BANNERS {
            s.push(b(&format!("d{i}"), BannerSeverity::Notice, true))
                .unwrap();
        }
        // The non-dismissible "crit" should still be in the stack.
        assert!(s.get("crit").is_some());
    }

    #[test]
    fn empty_title_rejected() {
        let mut s = ErrorBannerStack::new();
        let mut bad = b("a", BannerSeverity::Notice, true);
        bad.title = String::new();
        assert!(matches!(
            s.push(bad).unwrap_err(),
            BannerError::EmptyTitle(_)
        ));
    }

    #[test]
    fn title_too_long_rejected() {
        let mut s = ErrorBannerStack::new();
        let mut bad = b("a", BannerSeverity::Notice, true);
        bad.title = "x".repeat(81);
        assert!(matches!(
            s.push(bad).unwrap_err(),
            BannerError::TitleTooLong { .. }
        ));
    }

    #[test]
    fn body_too_long_rejected() {
        let mut s = ErrorBannerStack::new();
        let mut bad = b("a", BannerSeverity::Notice, true);
        bad.body = "x".repeat(401);
        assert!(matches!(
            s.push(bad).unwrap_err(),
            BannerError::BodyTooLong { .. }
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ErrorBannerStack::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            BannerError::SchemaMismatch
        ));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = ErrorBannerStack::new();
        s.push(b("a", BannerSeverity::Warn, true)).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ErrorBannerStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
