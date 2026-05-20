//! `sovereign-cockpit-rollout-banner` — feature rollout banner.
//!
//! Label{Alpha/Beta/EarlyAccess/Generally Available}. Banner
//! per feature_id with label, cohort_name, dismissed flag.
//! should_show(feature_id) iff registered + not dismissed +
//! label != GenerallyAvailable.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Label.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Label {
    /// Alpha.
    Alpha,
    /// Beta.
    Beta,
    /// Early-access.
    EarlyAccess,
    /// Generally available.
    GenerallyAvailable,
}

/// Banner.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Banner {
    /// Label.
    pub label: Label,
    /// Cohort name.
    pub cohort: String,
    /// Dismissed.
    pub dismissed: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RolloutBanner {
    /// Schema version.
    pub schema_version: String,
    /// feature_id → banner.
    pub banners: BTreeMap<String, Banner>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BannerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("feature id empty")]
    EmptyFeature,
    /// Empty.
    #[error("cohort empty")]
    EmptyCohort,
    /// Unknown.
    #[error("unknown feature: {0}")]
    UnknownFeature(String),
}

impl RolloutBanner {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            banners: BTreeMap::new(),
        }
    }

    /// Register / replace banner.
    pub fn register(&mut self, feature_id: &str, label: Label, cohort: &str) -> Result<(), BannerError> {
        if feature_id.is_empty() { return Err(BannerError::EmptyFeature); }
        if cohort.is_empty() { return Err(BannerError::EmptyCohort); }
        self.banners.insert(feature_id.into(), Banner {
            label,
            cohort: cohort.into(),
            dismissed: false,
        });
        Ok(())
    }

    /// Dismiss banner.
    pub fn dismiss(&mut self, feature_id: &str) -> Result<(), BannerError> {
        let b = self.banners.get_mut(feature_id).ok_or_else(|| BannerError::UnknownFeature(feature_id.into()))?;
        b.dismissed = true;
        Ok(())
    }

    /// Should show banner?
    pub fn should_show(&self, feature_id: &str) -> bool {
        match self.banners.get(feature_id) {
            None => false,
            Some(b) => !b.dismissed && b.label != Label::GenerallyAvailable,
        }
    }

    /// Active banners (should-show).
    pub fn active(&self) -> Vec<&str> {
        self.banners.iter()
            .filter(|(id, _)| self.should_show(id))
            .map(|(k, _)| k.as_str())
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BannerError> {
        if self.schema_version != SCHEMA_VERSION { return Err(BannerError::SchemaMismatch); }
        for (k, b) in &self.banners {
            if k.is_empty() { return Err(BannerError::EmptyFeature); }
            if b.cohort.is_empty() { return Err(BannerError::EmptyCohort); }
        }
        Ok(())
    }
}

impl Default for RolloutBanner {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_and_show() {
        let mut r = RolloutBanner::new();
        r.register("dark-mode", Label::Beta, "early-adopters").unwrap();
        assert!(r.should_show("dark-mode"));
    }

    #[test]
    fn dismiss_hides() {
        let mut r = RolloutBanner::new();
        r.register("a", Label::Alpha, "internal").unwrap();
        r.dismiss("a").unwrap();
        assert!(!r.should_show("a"));
    }

    #[test]
    fn ga_label_no_show() {
        let mut r = RolloutBanner::new();
        r.register("a", Label::GenerallyAvailable, "all").unwrap();
        assert!(!r.should_show("a"));
    }

    #[test]
    fn active_lists_visible() {
        let mut r = RolloutBanner::new();
        r.register("a", Label::Beta, "x").unwrap();
        r.register("b", Label::GenerallyAvailable, "x").unwrap();
        r.register("c", Label::Alpha, "x").unwrap();
        r.dismiss("c").unwrap();
        let act = r.active();
        assert_eq!(act, vec!["a"]);
    }

    #[test]
    fn unknown_dismiss_rejected() {
        let mut r = RolloutBanner::new();
        assert!(matches!(r.dismiss("nope").unwrap_err(), BannerError::UnknownFeature(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut r = RolloutBanner::new();
        assert!(matches!(r.register("", Label::Beta, "c").unwrap_err(), BannerError::EmptyFeature));
        assert!(matches!(r.register("a", Label::Beta, "").unwrap_err(), BannerError::EmptyCohort));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = RolloutBanner::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), BannerError::SchemaMismatch));
    }

    #[test]
    fn banner_serde_roundtrip() {
        let mut r = RolloutBanner::new();
        r.register("a", Label::Beta, "x").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: RolloutBanner = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
