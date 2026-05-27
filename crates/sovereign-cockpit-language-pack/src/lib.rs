//! `sovereign-cockpit-language-pack` — operator-provided i18n strings.
//!
//! `LanguagePack` = `(locale_tag, default_locale, table[key → text])`.
//! Lookup falls back to default_locale entry if key missing in active.
//! Operator-curated; cockpit reads.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One locale table.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LocaleTable {
    /// Locale tag (BCP-47).
    pub locale_tag: String,
    /// key → translated text.
    pub strings: BTreeMap<String, String>,
}

/// Language pack envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LanguagePack {
    /// Schema version.
    pub schema_version: String,
    /// Active locale tag.
    pub active: String,
    /// Default locale tag (fallback).
    pub default_locale: String,
    /// All locale tables registered.
    pub tables: Vec<LocaleTable>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LanguageError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Active locale not in tables.
    #[error("active locale {0} not registered")]
    ActiveUnregistered(String),
    /// Default locale not in tables.
    #[error("default locale {0} not registered")]
    DefaultUnregistered(String),
    /// Duplicate locale tag.
    #[error("duplicate locale tag: {0}")]
    DuplicateLocale(String),
    /// Empty locale_tag.
    #[error("locale_tag empty")]
    EmptyLocaleTag,
    /// Empty key in table.
    #[error("locale {0} has empty string key")]
    EmptyKey(String),
}

impl LanguagePack {
    /// New with default-only.
    pub fn new(default_locale: &str) -> Result<Self, LanguageError> {
        if default_locale.is_empty() {
            return Err(LanguageError::EmptyLocaleTag);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            active: default_locale.into(),
            default_locale: default_locale.into(),
            tables: vec![LocaleTable {
                locale_tag: default_locale.into(),
                strings: BTreeMap::new(),
            }],
        })
    }

    /// Add a locale table.
    pub fn add_locale(&mut self, locale_tag: &str) -> Result<(), LanguageError> {
        if locale_tag.is_empty() {
            return Err(LanguageError::EmptyLocaleTag);
        }
        if self.tables.iter().any(|t| t.locale_tag == locale_tag) {
            return Err(LanguageError::DuplicateLocale(locale_tag.into()));
        }
        self.tables.push(LocaleTable {
            locale_tag: locale_tag.into(),
            strings: BTreeMap::new(),
        });
        Ok(())
    }

    /// Set a translation.
    pub fn set(&mut self, locale_tag: &str, key: &str, text: &str) -> Result<(), LanguageError> {
        if key.is_empty() {
            return Err(LanguageError::EmptyKey(locale_tag.into()));
        }
        let t = self
            .tables
            .iter_mut()
            .find(|t| t.locale_tag == locale_tag)
            .ok_or_else(|| LanguageError::ActiveUnregistered(locale_tag.into()))?;
        t.strings.insert(key.into(), text.into());
        Ok(())
    }

    /// Activate a locale.
    pub fn activate(&mut self, locale_tag: &str) -> Result<(), LanguageError> {
        if !self.tables.iter().any(|t| t.locale_tag == locale_tag) {
            return Err(LanguageError::ActiveUnregistered(locale_tag.into()));
        }
        self.active = locale_tag.into();
        Ok(())
    }

    /// Translate a key. Falls back to default_locale then to key.
    pub fn translate<'a>(&'a self, key: &'a str) -> &'a str {
        if let Some(t) = self.tables.iter().find(|t| t.locale_tag == self.active)
            && let Some(s) = t.strings.get(key)
        {
            return s.as_str();
        }
        if let Some(t) = self
            .tables
            .iter()
            .find(|t| t.locale_tag == self.default_locale)
            && let Some(s) = t.strings.get(key)
        {
            return s.as_str();
        }
        key
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LanguageError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LanguageError::SchemaMismatch);
        }
        if !self.tables.iter().any(|t| t.locale_tag == self.active) {
            return Err(LanguageError::ActiveUnregistered(self.active.clone()));
        }
        if !self
            .tables
            .iter()
            .any(|t| t.locale_tag == self.default_locale)
        {
            return Err(LanguageError::DefaultUnregistered(
                self.default_locale.clone(),
            ));
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.tables {
            if t.locale_tag.is_empty() {
                return Err(LanguageError::EmptyLocaleTag);
            }
            if !seen.insert(t.locale_tag.as_str()) {
                return Err(LanguageError::DuplicateLocale(t.locale_tag.clone()));
            }
            for k in t.strings.keys() {
                if k.is_empty() {
                    return Err(LanguageError::EmptyKey(t.locale_tag.clone()));
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_validates() {
        LanguagePack::new("en-US").unwrap().validate().unwrap();
    }

    #[test]
    fn empty_default_rejected() {
        assert!(matches!(
            LanguagePack::new("").unwrap_err(),
            LanguageError::EmptyLocaleTag
        ));
    }

    #[test]
    fn set_and_translate() {
        let mut p = LanguagePack::new("en-US").unwrap();
        p.set("en-US", "hello", "Hello").unwrap();
        assert_eq!(p.translate("hello"), "Hello");
    }

    #[test]
    fn fallback_to_default() {
        let mut p = LanguagePack::new("en-US").unwrap();
        p.set("en-US", "hello", "Hello").unwrap();
        p.add_locale("fr-FR").unwrap();
        p.activate("fr-FR").unwrap();
        assert_eq!(p.translate("hello"), "Hello");
    }

    #[test]
    fn key_as_last_resort() {
        let p = LanguagePack::new("en-US").unwrap();
        assert_eq!(p.translate("nokey"), "nokey");
    }

    #[test]
    fn duplicate_locale_rejected() {
        let mut p = LanguagePack::new("en-US").unwrap();
        assert!(matches!(
            p.add_locale("en-US").unwrap_err(),
            LanguageError::DuplicateLocale(_)
        ));
    }

    #[test]
    fn activate_unregistered_rejected() {
        let mut p = LanguagePack::new("en-US").unwrap();
        assert!(matches!(
            p.activate("ja-JP").unwrap_err(),
            LanguageError::ActiveUnregistered(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = LanguagePack::new("en-US").unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            LanguageError::SchemaMismatch
        ));
    }

    #[test]
    fn pack_serde_roundtrip() {
        let mut p = LanguagePack::new("en-US").unwrap();
        p.set("en-US", "hello", "Hello").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: LanguagePack = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
