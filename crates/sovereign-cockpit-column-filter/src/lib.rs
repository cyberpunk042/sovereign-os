//! `sovereign-cockpit-column-filter` — per-column filter rules.
//!
//! Rule per column: Contains(substring) | Equals(value) |
//! Range(lo, hi inclusive integers). set/clear per column.
//! matches(row[col_id → value]) returns true iff all rules
//! pass.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Rule.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Rule {
    /// Substring match.
    Contains {
        /// Substring.
        value: String,
    },
    /// Exact match.
    Equals {
        /// Value.
        value: String,
    },
    /// Inclusive integer range (parsed from value string).
    Range {
        /// Lo.
        lo: i64,
        /// Hi.
        hi: i64,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColumnFilter {
    /// Schema version.
    pub schema_version: String,
    /// column → rule.
    pub rules: BTreeMap<String, Rule>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FilterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("column empty")]
    EmptyColumn,
    /// Empty.
    #[error("value empty")]
    EmptyValue,
    /// Bad range.
    #[error("range lo must be <= hi")]
    BadRange,
}

impl ColumnFilter {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            rules: BTreeMap::new(),
        }
    }

    /// Set rule on a column.
    pub fn set(&mut self, column: &str, rule: Rule) -> Result<(), FilterError> {
        if column.is_empty() {
            return Err(FilterError::EmptyColumn);
        }
        match &rule {
            Rule::Contains { value } | Rule::Equals { value } => {
                if value.is_empty() {
                    return Err(FilterError::EmptyValue);
                }
            }
            Rule::Range { lo, hi } => {
                if lo > hi {
                    return Err(FilterError::BadRange);
                }
            }
        }
        self.rules.insert(column.into(), rule);
        Ok(())
    }

    /// Clear column.
    pub fn clear(&mut self, column: &str) -> bool {
        self.rules.remove(column).is_some()
    }

    /// Clear all.
    pub fn clear_all(&mut self) {
        self.rules.clear();
    }

    /// Match a row (column → value).
    pub fn matches(&self, row: &BTreeMap<String, String>) -> bool {
        for (col, rule) in &self.rules {
            let v = match row.get(col) {
                Some(v) => v,
                None => return false,
            };
            match rule {
                Rule::Contains { value } => {
                    if !v.contains(value.as_str()) {
                        return false;
                    }
                }
                Rule::Equals { value } => {
                    if v != value {
                        return false;
                    }
                }
                Rule::Range { lo, hi } => {
                    let n: i64 = match v.parse() {
                        Ok(n) => n,
                        Err(_) => return false,
                    };
                    if n < *lo || n > *hi {
                        return false;
                    }
                }
            }
        }
        true
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FilterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FilterError::SchemaMismatch);
        }
        for (k, rule) in &self.rules {
            if k.is_empty() {
                return Err(FilterError::EmptyColumn);
            }
            match rule {
                Rule::Contains { value } | Rule::Equals { value } => {
                    if value.is_empty() {
                        return Err(FilterError::EmptyValue);
                    }
                }
                Rule::Range { lo, hi } => {
                    if lo > hi {
                        return Err(FilterError::BadRange);
                    }
                }
            }
        }
        Ok(())
    }
}

impl Default for ColumnFilter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(items: &[(&str, &str)]) -> BTreeMap<String, String> {
        items
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect()
    }

    #[test]
    fn no_rules_matches() {
        let f = ColumnFilter::new();
        assert!(f.matches(&row(&[])));
    }

    #[test]
    fn contains_matches() {
        let mut f = ColumnFilter::new();
        f.set(
            "name",
            Rule::Contains {
                value: "ali".into(),
            },
        )
        .unwrap();
        assert!(f.matches(&row(&[("name", "alice")])));
        assert!(!f.matches(&row(&[("name", "bob")])));
    }

    #[test]
    fn equals_matches() {
        let mut f = ColumnFilter::new();
        f.set(
            "role",
            Rule::Equals {
                value: "admin".into(),
            },
        )
        .unwrap();
        assert!(f.matches(&row(&[("role", "admin")])));
        assert!(!f.matches(&row(&[("role", "user")])));
    }

    #[test]
    fn range_matches() {
        let mut f = ColumnFilter::new();
        f.set("age", Rule::Range { lo: 18, hi: 65 }).unwrap();
        assert!(f.matches(&row(&[("age", "30")])));
        assert!(!f.matches(&row(&[("age", "17")])));
        assert!(!f.matches(&row(&[("age", "abc")])));
    }

    #[test]
    fn multiple_rules_all_must_pass() {
        let mut f = ColumnFilter::new();
        f.set(
            "role",
            Rule::Equals {
                value: "admin".into(),
            },
        )
        .unwrap();
        f.set("age", Rule::Range { lo: 18, hi: 65 }).unwrap();
        assert!(f.matches(&row(&[("role", "admin"), ("age", "30")])));
        assert!(!f.matches(&row(&[("role", "admin"), ("age", "70")])));
    }

    #[test]
    fn missing_column_fails() {
        let mut f = ColumnFilter::new();
        f.set(
            "role",
            Rule::Equals {
                value: "admin".into(),
            },
        )
        .unwrap();
        assert!(!f.matches(&row(&[])));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut f = ColumnFilter::new();
        assert!(matches!(
            f.set("", Rule::Contains { value: "x".into() }).unwrap_err(),
            FilterError::EmptyColumn
        ));
        assert!(matches!(
            f.set("c", Rule::Contains { value: "".into() }).unwrap_err(),
            FilterError::EmptyValue
        ));
        assert!(matches!(
            f.set("c", Rule::Range { lo: 5, hi: 1 }).unwrap_err(),
            FilterError::BadRange
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = ColumnFilter::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FilterError::SchemaMismatch
        ));
    }

    #[test]
    fn filter_serde_roundtrip() {
        let mut f = ColumnFilter::new();
        f.set("c", Rule::Contains { value: "x".into() }).unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: ColumnFilter = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
