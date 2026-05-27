//! `sovereign-cockpit-saved-search-set` — named saved searches.
//!
//! Each saved search has a stable id, a display name, a query
//! string, optional scope, run count, and last-run timestamp.
//! `recents(n)` returns the most-recently-used. `frequents(n)`
//! returns the most-used. `recent_and_frequent(n)` blends both via
//! a simple normalized score.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One saved search.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SavedSearch {
    /// Stable id.
    pub id: String,
    /// Display name.
    pub name: String,
    /// Query string.
    pub query: String,
    /// Optional scope label.
    pub scope: Option<String>,
    /// Run count.
    pub run_count: u64,
    /// Last-run ts (0 if never).
    pub last_run_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SavedSearchSet {
    /// Schema version.
    pub schema_version: String,
    /// id → saved search.
    pub searches: BTreeMap<String, SavedSearch>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SavedSearchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty name.
    #[error("name empty")]
    EmptyName,
    /// Empty query.
    #[error("query empty")]
    EmptyQuery,
    /// Duplicate.
    #[error("duplicate saved-search id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown saved search: {0}")]
    UnknownSearch(String),
}

impl SavedSearchSet {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            searches: BTreeMap::new(),
        }
    }

    /// Add.
    pub fn add(
        &mut self,
        id: &str,
        name: &str,
        query: &str,
        scope: Option<&str>,
    ) -> Result<(), SavedSearchError> {
        if id.is_empty() {
            return Err(SavedSearchError::EmptyId);
        }
        if name.is_empty() {
            return Err(SavedSearchError::EmptyName);
        }
        if query.is_empty() {
            return Err(SavedSearchError::EmptyQuery);
        }
        if self.searches.contains_key(id) {
            return Err(SavedSearchError::DuplicateId(id.into()));
        }
        self.searches.insert(
            id.into(),
            SavedSearch {
                id: id.into(),
                name: name.into(),
                query: query.into(),
                scope: scope.map(|s| s.into()),
                run_count: 0,
                last_run_ms: 0,
            },
        );
        Ok(())
    }

    /// Update name/query/scope of an existing entry.
    pub fn edit(
        &mut self,
        id: &str,
        name: &str,
        query: &str,
        scope: Option<&str>,
    ) -> Result<(), SavedSearchError> {
        if name.is_empty() {
            return Err(SavedSearchError::EmptyName);
        }
        if query.is_empty() {
            return Err(SavedSearchError::EmptyQuery);
        }
        let s = self
            .searches
            .get_mut(id)
            .ok_or_else(|| SavedSearchError::UnknownSearch(id.into()))?;
        s.name = name.into();
        s.query = query.into();
        s.scope = scope.map(|s| s.into());
        Ok(())
    }

    /// Record a run.
    pub fn record_run(&mut self, id: &str, ts_ms: u64) -> Result<(), SavedSearchError> {
        let s = self
            .searches
            .get_mut(id)
            .ok_or_else(|| SavedSearchError::UnknownSearch(id.into()))?;
        s.run_count = s.run_count.saturating_add(1);
        s.last_run_ms = ts_ms;
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.searches.remove(id).is_some()
    }

    /// Get.
    pub fn get(&self, id: &str) -> Option<&SavedSearch> {
        self.searches.get(id)
    }

    /// Most-recently-used (top n).
    pub fn recents(&self, n: usize) -> Vec<SavedSearch> {
        let mut v: Vec<SavedSearch> = self.searches.values().cloned().collect();
        v.sort_by(|a, b| b.last_run_ms.cmp(&a.last_run_ms).then(a.name.cmp(&b.name)));
        v.truncate(n);
        v
    }

    /// Most-frequently-used (top n).
    pub fn frequents(&self, n: usize) -> Vec<SavedSearch> {
        let mut v: Vec<SavedSearch> = self.searches.values().cloned().collect();
        v.sort_by(|a, b| b.run_count.cmp(&a.run_count).then(a.name.cmp(&b.name)));
        v.truncate(n);
        v
    }

    /// Recent-and-frequent blend (normalized 0..1 each, summed; n items).
    pub fn recent_and_frequent(&self, now_ms: u64, n: usize) -> Vec<SavedSearch> {
        if self.searches.is_empty() {
            return Vec::new();
        }
        let max_count = self
            .searches
            .values()
            .map(|s| s.run_count)
            .max()
            .unwrap_or(1)
            .max(1);
        let mut scored: Vec<(u64, SavedSearch)> = self
            .searches
            .values()
            .map(|s| {
                let recency_score = if s.last_run_ms == 0 {
                    0
                } else {
                    // Normalize to 0..1000 — newer is higher.
                    let age = now_ms.saturating_sub(s.last_run_ms);
                    1000u64.saturating_sub(age.min(1000))
                };
                let freq_score = (s.run_count.saturating_mul(1000)) / max_count;
                (recency_score.saturating_add(freq_score), s.clone())
            })
            .collect();
        scored.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.name.cmp(&b.1.name)));
        scored.into_iter().take(n).map(|(_, s)| s).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SavedSearchError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SavedSearchError::SchemaMismatch);
        }
        for (id, s) in &self.searches {
            if id.is_empty() {
                return Err(SavedSearchError::EmptyId);
            }
            if s.name.is_empty() {
                return Err(SavedSearchError::EmptyName);
            }
            if s.query.is_empty() {
                return Err(SavedSearchError::EmptyQuery);
            }
        }
        Ok(())
    }
}

impl Default for SavedSearchSet {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_get() {
        let mut s = SavedSearchSet::new();
        s.add("s1", "Recent errors", "level:error", None).unwrap();
        assert!(s.get("s1").is_some());
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = SavedSearchSet::new();
        s.add("s1", "x", "y", None).unwrap();
        assert!(matches!(
            s.add("s1", "x", "y", None).unwrap_err(),
            SavedSearchError::DuplicateId(_)
        ));
    }

    #[test]
    fn edit_updates() {
        let mut s = SavedSearchSet::new();
        s.add("s1", "old", "q1", None).unwrap();
        s.edit("s1", "new", "q2", Some("scope")).unwrap();
        let r = s.get("s1").unwrap();
        assert_eq!(r.name, "new");
        assert_eq!(r.query, "q2");
        assert_eq!(r.scope.as_deref(), Some("scope"));
    }

    #[test]
    fn record_run_increments() {
        let mut s = SavedSearchSet::new();
        s.add("s1", "x", "y", None).unwrap();
        s.record_run("s1", 100).unwrap();
        s.record_run("s1", 200).unwrap();
        let r = s.get("s1").unwrap();
        assert_eq!(r.run_count, 2);
        assert_eq!(r.last_run_ms, 200);
    }

    #[test]
    fn recents_ordered_by_last_run() {
        let mut s = SavedSearchSet::new();
        s.add("s1", "a", "q", None).unwrap();
        s.add("s2", "b", "q", None).unwrap();
        s.record_run("s1", 100).unwrap();
        s.record_run("s2", 200).unwrap();
        let r = s.recents(10);
        assert_eq!(r[0].id, "s2");
        assert_eq!(r[1].id, "s1");
    }

    #[test]
    fn frequents_ordered_by_count() {
        let mut s = SavedSearchSet::new();
        s.add("s1", "a", "q", None).unwrap();
        s.add("s2", "b", "q", None).unwrap();
        s.record_run("s1", 100).unwrap();
        s.record_run("s1", 200).unwrap();
        s.record_run("s2", 300).unwrap();
        let r = s.frequents(10);
        assert_eq!(r[0].id, "s1");
    }

    #[test]
    fn recent_and_frequent_blends() {
        let mut s = SavedSearchSet::new();
        s.add("old_freq", "old freq", "q", None).unwrap();
        s.add("new_rare", "new rare", "q", None).unwrap();
        // old_freq: 10 runs but stale
        for i in 0..10 {
            s.record_run("old_freq", i).unwrap();
        }
        // new_rare: 1 run but recent
        s.record_run("new_rare", 1_000_000).unwrap();
        let r = s.recent_and_frequent(1_000_000, 2);
        assert_eq!(r.len(), 2);
        // new_rare wins on recency component.
        assert_eq!(r[0].id, "new_rare");
    }

    #[test]
    fn remove_works() {
        let mut s = SavedSearchSet::new();
        s.add("s1", "x", "y", None).unwrap();
        assert!(s.remove("s1"));
        assert!(s.get("s1").is_none());
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = SavedSearchSet::new();
        assert!(matches!(
            s.add("", "n", "q", None).unwrap_err(),
            SavedSearchError::EmptyId
        ));
        assert!(matches!(
            s.add("a", "", "q", None).unwrap_err(),
            SavedSearchError::EmptyName
        ));
        assert!(matches!(
            s.add("a", "n", "", None).unwrap_err(),
            SavedSearchError::EmptyQuery
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SavedSearchSet::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SavedSearchError::SchemaMismatch
        ));
    }

    #[test]
    fn search_serde_roundtrip() {
        let mut s = SavedSearchSet::new();
        s.add("s1", "x", "y", Some("scope")).unwrap();
        s.record_run("s1", 100).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SavedSearchSet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
