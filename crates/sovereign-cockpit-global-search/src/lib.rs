//! `sovereign-cockpit-global-search` — cross-source search.
//!
//! Sources contribute pre-scored Results. merge_results sorts
//! results by score desc, source-weight, then ts desc.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One source.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Source {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Weight (higher = preferred).
    pub weight: u32,
    /// Enabled.
    pub enabled: bool,
}

/// One result.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Result_ {
    /// Source id.
    pub source: String,
    /// Result id within source.
    pub id: String,
    /// Title.
    pub title: String,
    /// Snippet.
    pub snippet: String,
    /// Score (caller-provided).
    pub score: u32,
    /// Ts.
    pub ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GlobalSearch {
    /// Schema version.
    pub schema_version: String,
    /// source → source.
    pub sources: BTreeMap<String, Source>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SearchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate source: {0}")]
    DuplicateSource(String),
    /// Unknown source.
    #[error("unknown source: {0}")]
    UnknownSource(String),
}

impl GlobalSearch {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            sources: BTreeMap::new(),
        }
    }

    /// Register source.
    pub fn register_source(
        &mut self,
        id: &str,
        label: &str,
        weight: u32,
    ) -> Result<(), SearchError> {
        if id.is_empty() {
            return Err(SearchError::EmptyId);
        }
        if label.is_empty() {
            return Err(SearchError::EmptyLabel);
        }
        if self.sources.contains_key(id) {
            return Err(SearchError::DuplicateSource(id.into()));
        }
        self.sources.insert(
            id.into(),
            Source {
                id: id.into(),
                label: label.into(),
                weight,
                enabled: true,
            },
        );
        Ok(())
    }

    /// Enable / disable.
    pub fn set_enabled(&mut self, source: &str, enabled: bool) -> Result<(), SearchError> {
        let s = self
            .sources
            .get_mut(source)
            .ok_or_else(|| SearchError::UnknownSource(source.into()))?;
        s.enabled = enabled;
        Ok(())
    }

    /// Merge caller-provided per-source results into a unified ranking.
    /// Drops results from disabled sources.
    pub fn merge_results(&self, results: &[Result_], limit: usize) -> Vec<Result_> {
        let mut v: Vec<Result_> = results
            .iter()
            .filter(|r| {
                self.sources
                    .get(&r.source)
                    .map(|s| s.enabled)
                    .unwrap_or(false)
            })
            .cloned()
            .collect();
        // Composite score: result.score × source.weight.
        v.sort_by(|a, b| {
            let wa = self.sources.get(&a.source).map(|s| s.weight).unwrap_or(1);
            let wb = self.sources.get(&b.source).map(|s| s.weight).unwrap_or(1);
            let composite_a = (a.score as u64).saturating_mul(wa as u64);
            let composite_b = (b.score as u64).saturating_mul(wb as u64);
            composite_b
                .cmp(&composite_a)
                .then(b.ts_ms.cmp(&a.ts_ms))
                .then(a.title.cmp(&b.title))
        });
        v.truncate(limit);
        v
    }

    /// Enabled sources in label order.
    pub fn enabled_sources(&self) -> Vec<Source> {
        let mut v: Vec<Source> = self
            .sources
            .values()
            .filter(|s| s.enabled)
            .cloned()
            .collect();
        v.sort_by(|a, b| a.label.cmp(&b.label));
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SearchError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SearchError::SchemaMismatch);
        }
        for (id, s) in &self.sources {
            if id.is_empty() {
                return Err(SearchError::EmptyId);
            }
            if s.label.is_empty() {
                return Err(SearchError::EmptyLabel);
            }
        }
        Ok(())
    }
}

impl Default for GlobalSearch {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn r(source: &str, id: &str, score: u32, ts: u64) -> Result_ {
        Result_ {
            source: source.into(),
            id: id.into(),
            title: id.into(),
            snippet: format!("{id} snip"),
            score,
            ts_ms: ts,
        }
    }

    #[test]
    fn merge_orders_by_composite() {
        let mut g = GlobalSearch::new();
        g.register_source("a", "A", 10).unwrap();
        g.register_source("b", "B", 1).unwrap();
        let results = vec![
            r("a", "r1", 5, 0),   // composite 50
            r("b", "r2", 100, 0), // composite 100
        ];
        let merged = g.merge_results(&results, 10);
        assert_eq!(merged[0].id, "r2");
    }

    #[test]
    fn disabled_source_filtered() {
        let mut g = GlobalSearch::new();
        g.register_source("a", "A", 10).unwrap();
        g.set_enabled("a", false).unwrap();
        let merged = g.merge_results(&[r("a", "r1", 100, 0)], 10);
        assert!(merged.is_empty());
    }

    #[test]
    fn limit_truncates() {
        let mut g = GlobalSearch::new();
        g.register_source("a", "A", 1).unwrap();
        let results: Vec<_> = (0..10).map(|i| r("a", &format!("r{i}"), i, 0)).collect();
        let merged = g.merge_results(&results, 3);
        assert_eq!(merged.len(), 3);
    }

    #[test]
    fn duplicate_source_rejected() {
        let mut g = GlobalSearch::new();
        g.register_source("a", "A", 1).unwrap();
        assert!(matches!(
            g.register_source("a", "A", 1).unwrap_err(),
            SearchError::DuplicateSource(_)
        ));
    }

    #[test]
    fn unknown_source_set_enabled_rejected() {
        let mut g = GlobalSearch::new();
        assert!(matches!(
            g.set_enabled("nope", false).unwrap_err(),
            SearchError::UnknownSource(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut g = GlobalSearch::new();
        assert!(matches!(
            g.register_source("", "A", 1).unwrap_err(),
            SearchError::EmptyId
        ));
        assert!(matches!(
            g.register_source("a", "", 1).unwrap_err(),
            SearchError::EmptyLabel
        ));
    }

    #[test]
    fn enabled_sources_sorted() {
        let mut g = GlobalSearch::new();
        g.register_source("z", "Zeta", 1).unwrap();
        g.register_source("a", "Alpha", 1).unwrap();
        let v = g.enabled_sources();
        assert_eq!(v[0].label, "Alpha");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = GlobalSearch::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            SearchError::SchemaMismatch
        ));
    }

    #[test]
    fn search_serde_roundtrip() {
        let mut g = GlobalSearch::new();
        g.register_source("a", "A", 1).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: GlobalSearch = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
