//! `sovereign-cockpit-quick-filter` — multi-chip operator filter.
//!
//! Each `Chip` is `(facet, value)`. Combine via `AndAll` or `AndAnyOfPerFacet`
//! semantics. Evaluator takes a row (BTreeMap<String,String>) and returns
//! true if the row matches.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Filter combination mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CombineMode {
    /// Every chip must match (strict AND).
    AndAll,
    /// Group chips by facet; row must have ANY value within facet, AND across facets.
    AndAnyOfPerFacet,
}

/// One filter chip.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Chip {
    /// Facet name (e.g. "severity", "tag").
    pub facet: String,
    /// Required value.
    pub value: String,
}

/// Quick filter envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QuickFilter {
    /// Schema version.
    pub schema_version: String,
    /// Combine mode.
    pub mode: CombineMode,
    /// Active chips.
    pub chips: Vec<Chip>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FilterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty facet.
    #[error("chip facet empty")]
    EmptyFacet,
    /// Empty value.
    #[error("chip value empty")]
    EmptyValue,
}

impl QuickFilter {
    /// New empty filter with default AndAll.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: CombineMode::AndAll,
            chips: Vec::new(),
        }
    }

    /// Add a chip.
    pub fn add(&mut self, facet: &str, value: &str) -> Result<(), FilterError> {
        if facet.is_empty() {
            return Err(FilterError::EmptyFacet);
        }
        if value.is_empty() {
            return Err(FilterError::EmptyValue);
        }
        self.chips.push(Chip {
            facet: facet.into(),
            value: value.into(),
        });
        Ok(())
    }

    /// Remove all chips for a facet.
    pub fn remove_facet(&mut self, facet: &str) {
        self.chips.retain(|c| c.facet != facet);
    }

    /// Clear all chips.
    pub fn clear(&mut self) {
        self.chips.clear();
    }

    /// Set combine mode.
    pub fn set_mode(&mut self, mode: CombineMode) {
        self.mode = mode;
    }

    /// Evaluate against a row. Empty chips → always true.
    pub fn matches(&self, row: &BTreeMap<String, String>) -> bool {
        if self.chips.is_empty() {
            return true;
        }
        match self.mode {
            CombineMode::AndAll => self
                .chips
                .iter()
                .all(|c| row.get(&c.facet).map(|v| v == &c.value).unwrap_or(false)),
            CombineMode::AndAnyOfPerFacet => {
                // Group chips by facet.
                let mut by_facet: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
                for c in &self.chips {
                    by_facet
                        .entry(c.facet.as_str())
                        .or_default()
                        .push(c.value.as_str());
                }
                // Each facet must match ANY of its values.
                by_facet.iter().all(|(facet, values)| {
                    row.get(*facet)
                        .map(|v| values.iter().any(|x| *x == v))
                        .unwrap_or(false)
                })
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FilterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FilterError::SchemaMismatch);
        }
        for c in &self.chips {
            if c.facet.is_empty() {
                return Err(FilterError::EmptyFacet);
            }
            if c.value.is_empty() {
                return Err(FilterError::EmptyValue);
            }
        }
        Ok(())
    }
}

impl Default for QuickFilter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(pairs: &[(&str, &str)]) -> BTreeMap<String, String> {
        pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect()
    }

    #[test]
    fn empty_filter_matches_anything() {
        let f = QuickFilter::new();
        assert!(f.matches(&row(&[])));
        assert!(f.matches(&row(&[("a", "b")])));
    }

    #[test]
    fn and_all_strict() {
        let mut f = QuickFilter::new();
        f.add("severity", "critical").unwrap();
        f.add("source", "ips").unwrap();
        assert!(f.matches(&row(&[("severity", "critical"), ("source", "ips")])));
        assert!(!f.matches(&row(&[("severity", "warn"), ("source", "ips")])));
        assert!(!f.matches(&row(&[("severity", "critical"), ("source", "other")])));
    }

    #[test]
    fn and_any_of_per_facet_allows_or_within_facet() {
        let mut f = QuickFilter::new();
        f.set_mode(CombineMode::AndAnyOfPerFacet);
        f.add("severity", "critical").unwrap();
        f.add("severity", "warn").unwrap();
        f.add("source", "ips").unwrap();
        // Critical + ips → match.
        assert!(f.matches(&row(&[("severity", "critical"), ("source", "ips")])));
        // Warn + ips → match.
        assert!(f.matches(&row(&[("severity", "warn"), ("source", "ips")])));
        // Notice + ips → fail (notice not in severity facet).
        assert!(!f.matches(&row(&[("severity", "notice"), ("source", "ips")])));
        // Critical + other → fail.
        assert!(!f.matches(&row(&[("severity", "critical"), ("source", "other")])));
    }

    #[test]
    fn remove_facet() {
        let mut f = QuickFilter::new();
        f.add("a", "x").unwrap();
        f.add("a", "y").unwrap();
        f.add("b", "z").unwrap();
        f.remove_facet("a");
        assert_eq!(f.chips.len(), 1);
        assert_eq!(f.chips[0].facet, "b");
    }

    #[test]
    fn clear_drops_all() {
        let mut f = QuickFilter::new();
        f.add("a", "x").unwrap();
        f.clear();
        assert!(f.chips.is_empty());
    }

    #[test]
    fn empty_facet_rejected() {
        let mut f = QuickFilter::new();
        assert!(matches!(
            f.add("", "x").unwrap_err(),
            FilterError::EmptyFacet
        ));
    }

    #[test]
    fn empty_value_rejected() {
        let mut f = QuickFilter::new();
        assert!(matches!(
            f.add("a", "").unwrap_err(),
            FilterError::EmptyValue
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = QuickFilter::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FilterError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&CombineMode::AndAll).unwrap(),
            "\"and-all\""
        );
        assert_eq!(
            serde_json::to_string(&CombineMode::AndAnyOfPerFacet).unwrap(),
            "\"and-any-of-per-facet\""
        );
    }

    #[test]
    fn filter_serde_roundtrip() {
        let mut f = QuickFilter::new();
        f.add("a", "x").unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: QuickFilter = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
