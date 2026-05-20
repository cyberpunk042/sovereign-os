//! `sovereign-cockpit-input-validator-set` — composable input rules.
//!
//! Each rule is one of:
//!   * `Required` — value must be non-empty.
//!   * `MinLength { n }` / `MaxLength { n }`.
//!   * `StartsWith { prefix }` / `EndsWith { suffix }` / `Contains { needle }`.
//!   * `OnlyAscii` — bytes in 0..=127.
//!
//! A `Field` is `{ id, rules }`. `validate(field_id, value)` runs
//! rules in order and returns the first failure as `Err(Failure {
//! rule_index, message })`, or `Ok(())`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One validation rule.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Rule {
    /// Required.
    Required,
    /// Min length.
    MinLength {
        /// n.
        n: u32,
    },
    /// Max length.
    MaxLength {
        /// n.
        n: u32,
    },
    /// Starts with.
    StartsWith {
        /// prefix.
        prefix: String,
    },
    /// Ends with.
    EndsWith {
        /// suffix.
        suffix: String,
    },
    /// Substring contains.
    Contains {
        /// needle.
        needle: String,
    },
    /// ASCII only.
    OnlyAscii,
}

/// Field.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Field {
    /// Rules in order.
    pub rules: Vec<Rule>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InputValidatorSet {
    /// Schema version.
    pub schema_version: String,
    /// id → field.
    pub fields: BTreeMap<String, Field>,
}

/// Validation failure.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Failure {
    /// Index of failing rule.
    pub rule_index: u32,
    /// Human message.
    pub message: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ValidatorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Unknown field.
    #[error("unknown field: {0}")]
    UnknownField(String),
}

impl InputValidatorSet {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            fields: BTreeMap::new(),
        }
    }

    /// Register field (replaces).
    pub fn register(&mut self, field_id: &str, rules: Vec<Rule>) -> Result<(), ValidatorError> {
        if field_id.is_empty() { return Err(ValidatorError::EmptyId); }
        self.fields.insert(field_id.into(), Field { rules });
        Ok(())
    }

    /// Validate.
    pub fn validate_value(&self, field_id: &str, value: &str) -> Result<Result<(), Failure>, ValidatorError> {
        let f = self.fields.get(field_id).ok_or_else(|| ValidatorError::UnknownField(field_id.into()))?;
        for (i, r) in f.rules.iter().enumerate() {
            if let Err(msg) = check_rule(r, value) {
                return Ok(Err(Failure { rule_index: i as u32, message: msg }));
            }
        }
        Ok(Ok(()))
    }

    /// Validate (state object).
    pub fn validate(&self) -> Result<(), ValidatorError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ValidatorError::SchemaMismatch); }
        for k in self.fields.keys() {
            if k.is_empty() { return Err(ValidatorError::EmptyId); }
        }
        Ok(())
    }
}

fn check_rule(r: &Rule, value: &str) -> Result<(), String> {
    match r {
        Rule::Required => {
            if value.is_empty() { return Err("required".into()); }
        }
        Rule::MinLength { n } => {
            if (value.chars().count() as u32) < *n {
                return Err(format!("min length {n}"));
            }
        }
        Rule::MaxLength { n } => {
            if (value.chars().count() as u32) > *n {
                return Err(format!("max length {n}"));
            }
        }
        Rule::StartsWith { prefix } => {
            if !value.starts_with(prefix.as_str()) {
                return Err(format!("must start with \"{prefix}\""));
            }
        }
        Rule::EndsWith { suffix } => {
            if !value.ends_with(suffix.as_str()) {
                return Err(format!("must end with \"{suffix}\""));
            }
        }
        Rule::Contains { needle } => {
            if !value.contains(needle.as_str()) {
                return Err(format!("must contain \"{needle}\""));
            }
        }
        Rule::OnlyAscii => {
            if !value.is_ascii() {
                return Err("ASCII only".into());
            }
        }
    }
    Ok(())
}

impl Default for InputValidatorSet {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn required_rule() {
        let mut s = InputValidatorSet::new();
        s.register("name", vec![Rule::Required]).unwrap();
        assert!(s.validate_value("name", "").unwrap().is_err());
        assert!(s.validate_value("name", "x").unwrap().is_ok());
    }

    #[test]
    fn min_max_length() {
        let mut s = InputValidatorSet::new();
        s.register("title", vec![Rule::MinLength { n: 3 }, Rule::MaxLength { n: 5 }]).unwrap();
        assert!(s.validate_value("title", "ab").unwrap().is_err());
        assert!(s.validate_value("title", "abc").unwrap().is_ok());
        assert!(s.validate_value("title", "abcdef").unwrap().is_err());
    }

    #[test]
    fn starts_with() {
        let mut s = InputValidatorSet::new();
        s.register("url", vec![Rule::StartsWith { prefix: "https://".into() }]).unwrap();
        assert!(s.validate_value("url", "https://example.com").unwrap().is_ok());
        assert!(s.validate_value("url", "http://x").unwrap().is_err());
    }

    #[test]
    fn ends_with() {
        let mut s = InputValidatorSet::new();
        s.register("file", vec![Rule::EndsWith { suffix: ".txt".into() }]).unwrap();
        assert!(s.validate_value("file", "a.txt").unwrap().is_ok());
        assert!(s.validate_value("file", "a.png").unwrap().is_err());
    }

    #[test]
    fn contains_rule() {
        let mut s = InputValidatorSet::new();
        s.register("e", vec![Rule::Contains { needle: "@".into() }]).unwrap();
        assert!(s.validate_value("e", "a@b").unwrap().is_ok());
        assert!(s.validate_value("e", "no").unwrap().is_err());
    }

    #[test]
    fn only_ascii() {
        let mut s = InputValidatorSet::new();
        s.register("ascii", vec![Rule::OnlyAscii]).unwrap();
        assert!(s.validate_value("ascii", "abc").unwrap().is_ok());
        assert!(s.validate_value("ascii", "héllo").unwrap().is_err());
    }

    #[test]
    fn first_failing_rule_wins() {
        let mut s = InputValidatorSet::new();
        s.register("f", vec![Rule::Required, Rule::MinLength { n: 5 }]).unwrap();
        // Empty string fails Required (idx 0), not MinLength.
        match s.validate_value("f", "").unwrap() {
            Err(Failure { rule_index, .. }) => assert_eq!(rule_index, 0),
            _ => panic!(),
        }
    }

    #[test]
    fn unicode_length() {
        let mut s = InputValidatorSet::new();
        // 3-char "héy" — count by Unicode chars (3), not bytes (4).
        s.register("u", vec![Rule::MinLength { n: 3 }, Rule::MaxLength { n: 3 }]).unwrap();
        assert!(s.validate_value("u", "héy").unwrap().is_ok());
    }

    #[test]
    fn unknown_field_rejected() {
        let s = InputValidatorSet::new();
        assert!(matches!(s.validate_value("nope", "x").unwrap_err(), ValidatorError::UnknownField(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = InputValidatorSet::new();
        assert!(matches!(s.register("", vec![]).unwrap_err(), ValidatorError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = InputValidatorSet::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), ValidatorError::SchemaMismatch));
    }

    #[test]
    fn validator_serde_roundtrip() {
        let mut s = InputValidatorSet::new();
        s.register("x", vec![Rule::Required, Rule::MaxLength { n: 10 }]).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: InputValidatorSet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
