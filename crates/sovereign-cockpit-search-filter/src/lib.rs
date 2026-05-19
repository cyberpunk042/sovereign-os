//! `sovereign-cockpit-search-filter` — composite filter snapshot.
//!
//! Bundles (query_text, facets BTreeMap, sort_key, sort_direction)
//! into one immutable-feeling snapshot. The data layer treats the
//! whole snapshot as a key for memoizing results.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Sort direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SortDirection {
    /// Ascending.
    Asc,
    /// Descending.
    Desc,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SearchFilter {
    /// Schema version.
    pub schema_version: String,
    /// Free-text query.
    pub query_text: String,
    /// facet_name → selected value(s).
    pub facets: BTreeMap<String, Vec<String>>,
    /// Sort field (empty = no sort).
    pub sort_key: String,
    /// Sort direction (ignored when sort_key empty).
    pub sort_direction: SortDirection,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FilterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty facet name.
    #[error("facet name empty")]
    EmptyFacetName,
    /// Empty facet value.
    #[error("facet {0} has empty value")]
    EmptyFacetValue(String),
}

impl SearchFilter {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            query_text: String::new(),
            facets: BTreeMap::new(),
            sort_key: String::new(),
            sort_direction: SortDirection::Asc,
        }
    }

    /// Set query.
    pub fn set_query(&mut self, q: &str) {
        self.query_text = q.into();
    }

    /// Apply a facet value (additive in the value list; dedup'd).
    pub fn apply_facet(&mut self, name: &str, value: &str) -> Result<(), FilterError> {
        if name.is_empty() { return Err(FilterError::EmptyFacetName); }
        if value.is_empty() { return Err(FilterError::EmptyFacetValue(name.into())); }
        let entry = self.facets.entry(name.into()).or_default();
        if !entry.iter().any(|v| v == value) {
            entry.push(value.into());
            entry.sort();
        }
        Ok(())
    }

    /// Drop a facet value.
    pub fn drop_facet(&mut self, name: &str, value: &str) {
        if let Some(values) = self.facets.get_mut(name) {
            values.retain(|v| v != value);
            if values.is_empty() {
                self.facets.remove(name);
            }
        }
    }

    /// Clear all facets.
    pub fn clear_facets(&mut self) {
        self.facets.clear();
    }

    /// Set sort.
    pub fn set_sort(&mut self, key: &str, direction: SortDirection) {
        self.sort_key = key.into();
        self.sort_direction = direction;
    }

    /// Clear sort.
    pub fn clear_sort(&mut self) {
        self.sort_key.clear();
        self.sort_direction = SortDirection::Asc;
    }

    /// Has any active filter?
    pub fn is_active(&self) -> bool {
        !self.query_text.is_empty() || !self.facets.is_empty()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FilterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FilterError::SchemaMismatch);
        }
        for (name, values) in &self.facets {
            if name.is_empty() { return Err(FilterError::EmptyFacetName); }
            for v in values {
                if v.is_empty() { return Err(FilterError::EmptyFacetValue(name.clone())); }
            }
        }
        Ok(())
    }
}

impl Default for SearchFilter {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_inactive() {
        let f = SearchFilter::new();
        assert!(!f.is_active());
    }

    #[test]
    fn query_active() {
        let mut f = SearchFilter::new();
        f.set_query("hello");
        assert!(f.is_active());
    }

    #[test]
    fn facet_active() {
        let mut f = SearchFilter::new();
        f.apply_facet("status", "active").unwrap();
        assert!(f.is_active());
    }

    #[test]
    fn apply_facet_dedup() {
        let mut f = SearchFilter::new();
        f.apply_facet("status", "active").unwrap();
        f.apply_facet("status", "active").unwrap();
        assert_eq!(f.facets["status"].len(), 1);
    }

    #[test]
    fn multiple_values_sorted() {
        let mut f = SearchFilter::new();
        f.apply_facet("status", "z").unwrap();
        f.apply_facet("status", "a").unwrap();
        assert_eq!(f.facets["status"], vec!["a".to_string(), "z".to_string()]);
    }

    #[test]
    fn drop_facet_removes_value() {
        let mut f = SearchFilter::new();
        f.apply_facet("status", "active").unwrap();
        f.apply_facet("status", "draft").unwrap();
        f.drop_facet("status", "active");
        assert_eq!(f.facets["status"], vec!["draft".to_string()]);
    }

    #[test]
    fn drop_last_value_removes_facet() {
        let mut f = SearchFilter::new();
        f.apply_facet("status", "active").unwrap();
        f.drop_facet("status", "active");
        assert!(f.facets.is_empty());
    }

    #[test]
    fn clear_facets() {
        let mut f = SearchFilter::new();
        f.apply_facet("status", "active").unwrap();
        f.apply_facet("type", "doc").unwrap();
        f.clear_facets();
        assert!(f.facets.is_empty());
    }

    #[test]
    fn set_sort_then_clear() {
        let mut f = SearchFilter::new();
        f.set_sort("title", SortDirection::Desc);
        assert_eq!(f.sort_key, "title");
        f.clear_sort();
        assert!(f.sort_key.is_empty());
    }

    #[test]
    fn empty_facet_name_rejected() {
        let mut f = SearchFilter::new();
        assert!(matches!(f.apply_facet("", "x").unwrap_err(), FilterError::EmptyFacetName));
    }

    #[test]
    fn empty_facet_value_rejected() {
        let mut f = SearchFilter::new();
        assert!(matches!(f.apply_facet("a", "").unwrap_err(), FilterError::EmptyFacetValue(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = SearchFilter::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FilterError::SchemaMismatch));
    }

    #[test]
    fn filter_serde_roundtrip() {
        let mut f = SearchFilter::new();
        f.set_query("hi");
        f.apply_facet("status", "active").unwrap();
        f.set_sort("title", SortDirection::Asc);
        let j = serde_json::to_string(&f).unwrap();
        let back: SearchFilter = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
