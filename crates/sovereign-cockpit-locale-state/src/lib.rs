//! `sovereign-cockpit-locale-state` — operator locale preferences.
//!
//! 4 canonical date formats × 3 number formats × 7 first-day-of-week
//! choices. Locale tag is a free-form BCP-47 string (validated as
//! `lang[-REGION]`).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Date format.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DateFormat {
    /// YYYY-MM-DD (ISO-8601).
    Iso8601,
    /// MM/DD/YYYY (US).
    Us,
    /// DD/MM/YYYY (EU / UK).
    Eu,
    /// DD.MM.YYYY (DE).
    Dotted,
}

/// Number format.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum NumberFormat {
    /// 1,234.56 (US).
    UsDecimal,
    /// 1.234,56 (DE / FR).
    EuDecimal,
    /// 1 234,56 (FR with thin space).
    FrDecimal,
}

/// First day of week.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum FirstDayOfWeek {
    /// Monday.
    Monday,
    /// Tuesday.
    Tuesday,
    /// Wednesday.
    Wednesday,
    /// Thursday.
    Thursday,
    /// Friday.
    Friday,
    /// Saturday.
    Saturday,
    /// Sunday.
    Sunday,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LocaleState {
    /// Schema version.
    pub schema_version: String,
    /// BCP-47 tag (e.g. "en-US", "fr-FR", "ja-JP").
    pub locale_tag: String,
    /// Date format.
    pub date_format: DateFormat,
    /// Number format.
    pub number_format: NumberFormat,
    /// First day of week.
    pub first_day_of_week: FirstDayOfWeek,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LocaleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Locale tag malformed.
    #[error("invalid locale tag: {0}")]
    BadLocaleTag(String),
}

fn locale_tag_ok(tag: &str) -> bool {
    if tag.is_empty() {
        return false;
    }
    let parts: Vec<&str> = tag.split('-').collect();
    if parts.is_empty() || parts.len() > 3 {
        return false;
    }
    // First segment: lowercase ASCII letters.
    if !parts[0].chars().all(|c| c.is_ascii_lowercase()) {
        return false;
    }
    if parts[0].len() < 2 || parts[0].len() > 3 {
        return false;
    }
    // Remaining segments: uppercase ASCII letters/digits.
    for p in &parts[1..] {
        if p.is_empty() {
            return false;
        }
        if !p.chars().all(|c| c.is_ascii_alphanumeric()) {
            return false;
        }
    }
    true
}

impl LocaleState {
    /// Default — en-US, ISO-8601, US decimal, Sunday.
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            locale_tag: "en-US".into(),
            date_format: DateFormat::Iso8601,
            number_format: NumberFormat::UsDecimal,
            first_day_of_week: FirstDayOfWeek::Sunday,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LocaleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LocaleError::SchemaMismatch);
        }
        if !locale_tag_ok(&self.locale_tag) {
            return Err(LocaleError::BadLocaleTag(self.locale_tag.clone()));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        LocaleState::default_state().validate().unwrap();
    }

    #[test]
    fn locale_tag_lang_only_ok() {
        let mut s = LocaleState::default_state();
        s.locale_tag = "fr".into();
        s.validate().unwrap();
    }

    #[test]
    fn locale_tag_lang_region_ok() {
        let mut s = LocaleState::default_state();
        s.locale_tag = "ja-JP".into();
        s.validate().unwrap();
    }

    #[test]
    fn locale_tag_empty_rejected() {
        let mut s = LocaleState::default_state();
        s.locale_tag = String::new();
        assert!(matches!(
            s.validate().unwrap_err(),
            LocaleError::BadLocaleTag(_)
        ));
    }

    #[test]
    fn locale_tag_too_long_rejected() {
        let mut s = LocaleState::default_state();
        s.locale_tag = "abcdef".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            LocaleError::BadLocaleTag(_)
        ));
    }

    #[test]
    fn locale_tag_uppercase_lang_rejected() {
        let mut s = LocaleState::default_state();
        s.locale_tag = "EN-US".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            LocaleError::BadLocaleTag(_)
        ));
    }

    #[test]
    fn date_format_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&DateFormat::Iso8601).unwrap(),
            "\"iso8601\""
        );
        assert_eq!(serde_json::to_string(&DateFormat::Us).unwrap(), "\"us\"");
        assert_eq!(
            serde_json::to_string(&DateFormat::Dotted).unwrap(),
            "\"dotted\""
        );
    }

    #[test]
    fn first_day_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&FirstDayOfWeek::Monday).unwrap(),
            "\"monday\""
        );
        assert_eq!(
            serde_json::to_string(&FirstDayOfWeek::Sunday).unwrap(),
            "\"sunday\""
        );
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = LocaleState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            LocaleError::SchemaMismatch
        ));
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = LocaleState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: LocaleState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
