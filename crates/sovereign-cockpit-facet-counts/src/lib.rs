//! `sovereign-cockpit-facet-counts` — search-result facet sidebar.
//!
//! Per facet (e.g. "kind", "owner"), the cockpit tracks bucket counts
//! and selection state. `set_count(facet, bucket, n)` records a count;
//! `toggle(facet, bucket)` flips selection; `selected(facet)` lists
//! currently-selected buckets; `top(facet, n)` returns the n highest-
//! count buckets in descending order, ties broken alphabetically.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One facet (e.g. "kind").
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Facet {
    /// bucket → count.
    pub counts: BTreeMap<String, u64>,
    /// Currently-selected buckets.
    pub selected: BTreeSet<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FacetCounts {
    /// Schema version.
    pub schema_version: String,
    /// facet name → facet.
    pub facets: BTreeMap<String, Facet>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FacetError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty facet.
    #[error("facet empty")]
    EmptyFacet,
    /// Empty bucket.
    #[error("bucket empty")]
    EmptyBucket,
}

impl FacetCounts {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            facets: BTreeMap::new(),
        }
    }

    /// Set a bucket count (creates facet if absent).
    pub fn set_count(&mut self, facet: &str, bucket: &str, n: u64) -> Result<(), FacetError> {
        if facet.is_empty() {
            return Err(FacetError::EmptyFacet);
        }
        if bucket.is_empty() {
            return Err(FacetError::EmptyBucket);
        }
        self.facets
            .entry(facet.into())
            .or_default()
            .counts
            .insert(bucket.into(), n);
        Ok(())
    }

    /// Increment a bucket by 1.
    pub fn increment(&mut self, facet: &str, bucket: &str) -> Result<u64, FacetError> {
        if facet.is_empty() {
            return Err(FacetError::EmptyFacet);
        }
        if bucket.is_empty() {
            return Err(FacetError::EmptyBucket);
        }
        let entry = self
            .facets
            .entry(facet.into())
            .or_default()
            .counts
            .entry(bucket.into())
            .or_insert(0);
        *entry = entry.saturating_add(1);
        Ok(*entry)
    }

    /// Toggle a selection. Returns the new state (true=selected).
    pub fn toggle(&mut self, facet: &str, bucket: &str) -> Result<bool, FacetError> {
        if facet.is_empty() {
            return Err(FacetError::EmptyFacet);
        }
        if bucket.is_empty() {
            return Err(FacetError::EmptyBucket);
        }
        let f = self.facets.entry(facet.into()).or_default();
        if f.selected.contains(bucket) {
            f.selected.remove(bucket);
            Ok(false)
        } else {
            f.selected.insert(bucket.into());
            Ok(true)
        }
    }

    /// Selected buckets in this facet.
    pub fn selected(&self, facet: &str) -> Vec<String> {
        self.facets
            .get(facet)
            .map(|f| f.selected.iter().cloned().collect())
            .unwrap_or_default()
    }

    /// Top n buckets by count, descending; ties broken alphabetically.
    pub fn top(&self, facet: &str, n: usize) -> Vec<(String, u64)> {
        let Some(f) = self.facets.get(facet) else {
            return Vec::new();
        };
        let mut v: Vec<(String, u64)> = f.counts.iter().map(|(k, v)| (k.clone(), *v)).collect();
        v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
        v.truncate(n);
        v
    }

    /// Clear all selections in a facet.
    pub fn clear_selections(&mut self, facet: &str) -> bool {
        if let Some(f) = self.facets.get_mut(facet) {
            let had = !f.selected.is_empty();
            f.selected.clear();
            had
        } else {
            false
        }
    }

    /// Drop a whole facet.
    pub fn drop_facet(&mut self, facet: &str) -> bool {
        self.facets.remove(facet).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FacetError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FacetError::SchemaMismatch);
        }
        for (name, f) in &self.facets {
            if name.is_empty() {
                return Err(FacetError::EmptyFacet);
            }
            for b in f.counts.keys() {
                if b.is_empty() {
                    return Err(FacetError::EmptyBucket);
                }
            }
            for b in &f.selected {
                if b.is_empty() {
                    return Err(FacetError::EmptyBucket);
                }
            }
        }
        Ok(())
    }
}

impl Default for FacetCounts {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn set_and_top() {
        let mut f = FacetCounts::new();
        f.set_count("kind", "audit", 5).unwrap();
        f.set_count("kind", "decision", 12).unwrap();
        f.set_count("kind", "tool-call", 1).unwrap();
        let t = f.top("kind", 2);
        assert_eq!(t[0].0, "decision");
        assert_eq!(t[0].1, 12);
        assert_eq!(t[1].0, "audit");
    }

    #[test]
    fn increment_creates_and_grows() {
        let mut f = FacetCounts::new();
        f.increment("kind", "audit").unwrap();
        f.increment("kind", "audit").unwrap();
        assert_eq!(f.facets["kind"].counts["audit"], 2);
    }

    #[test]
    fn toggle_round_trip() {
        let mut f = FacetCounts::new();
        f.set_count("kind", "a", 1).unwrap();
        assert!(f.toggle("kind", "a").unwrap());
        assert_eq!(f.selected("kind"), vec!["a"]);
        assert!(!f.toggle("kind", "a").unwrap());
        assert!(f.selected("kind").is_empty());
    }

    #[test]
    fn ties_broken_alphabetically() {
        let mut f = FacetCounts::new();
        f.set_count("kind", "b", 5).unwrap();
        f.set_count("kind", "a", 5).unwrap();
        let t = f.top("kind", 10);
        assert_eq!(t[0].0, "a");
        assert_eq!(t[1].0, "b");
    }

    #[test]
    fn clear_selections() {
        let mut f = FacetCounts::new();
        f.toggle("kind", "a").unwrap();
        f.toggle("kind", "b").unwrap();
        assert!(f.clear_selections("kind"));
        assert!(f.selected("kind").is_empty());
    }

    #[test]
    fn drop_facet() {
        let mut f = FacetCounts::new();
        f.set_count("kind", "a", 1).unwrap();
        assert!(f.drop_facet("kind"));
        assert!(f.top("kind", 10).is_empty());
    }

    #[test]
    fn unknown_facet_empty() {
        let f = FacetCounts::new();
        assert!(f.top("nope", 10).is_empty());
        assert!(f.selected("nope").is_empty());
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut f = FacetCounts::new();
        assert!(matches!(
            f.set_count("", "a", 1).unwrap_err(),
            FacetError::EmptyFacet
        ));
        assert!(matches!(
            f.set_count("kind", "", 1).unwrap_err(),
            FacetError::EmptyBucket
        ));
        assert!(matches!(
            f.toggle("", "a").unwrap_err(),
            FacetError::EmptyFacet
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = FacetCounts::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FacetError::SchemaMismatch
        ));
    }

    #[test]
    fn facet_serde_roundtrip() {
        let mut f = FacetCounts::new();
        f.set_count("kind", "a", 1).unwrap();
        f.toggle("kind", "a").unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: FacetCounts = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
