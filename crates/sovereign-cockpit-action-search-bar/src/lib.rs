//! `sovereign-cockpit-action-search-bar` — searchable action list.
//!
//! Each Action{id, name, category, keywords}. search(q) returns
//! scored matches: 4=exact name, 3=name starts-with, 2=category
//! contains, 1=keyword contains, 0=name contains; ties by name.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One action.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Action {
    /// Id.
    pub id: String,
    /// Name.
    pub name: String,
    /// Category.
    pub category: String,
    /// Keywords.
    pub keywords: BTreeSet<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionSearchBar {
    /// Schema version.
    pub schema_version: String,
    /// id → action.
    pub actions: BTreeMap<String, Action>,
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
    #[error("name empty")]
    EmptyName,
    /// Empty.
    #[error("category empty")]
    EmptyCategory,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl ActionSearchBar {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            actions: BTreeMap::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, id: &str, name: &str, category: &str, keywords: &[&str]) -> Result<(), SearchError> {
        if id.is_empty() { return Err(SearchError::EmptyId); }
        if name.is_empty() { return Err(SearchError::EmptyName); }
        if category.is_empty() { return Err(SearchError::EmptyCategory); }
        if self.actions.contains_key(id) { return Err(SearchError::DuplicateId(id.into())); }
        self.actions.insert(id.into(), Action {
            id: id.into(),
            name: name.into(),
            category: category.into(),
            keywords: keywords.iter().map(|k| (*k).into()).collect(),
        });
        Ok(())
    }

    /// Search.
    pub fn search(&self, q: &str) -> Vec<Action> {
        if q.is_empty() {
            let mut v: Vec<Action> = self.actions.values().cloned().collect();
            v.sort_by(|a, b| a.name.cmp(&b.name));
            return v;
        }
        let needle = q.to_lowercase();
        let mut scored: Vec<(u8, Action)> = self.actions.values()
            .filter_map(|a| {
                let name_l = a.name.to_lowercase();
                if name_l == needle { Some((4, a.clone())) }
                else if name_l.starts_with(&needle) { Some((3, a.clone())) }
                else if a.category.to_lowercase().contains(&needle) { Some((2, a.clone())) }
                else if a.keywords.iter().any(|k| k.to_lowercase().contains(&needle)) { Some((1, a.clone())) }
                else if name_l.contains(&needle) { Some((0, a.clone())) }
                else { None }
            })
            .collect();
        scored.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.name.cmp(&b.1.name)));
        scored.into_iter().map(|(_, a)| a).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SearchError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SearchError::SchemaMismatch); }
        for (id, a) in &self.actions {
            if id.is_empty() { return Err(SearchError::EmptyId); }
            if a.name.is_empty() { return Err(SearchError::EmptyName); }
            if a.category.is_empty() { return Err(SearchError::EmptyCategory); }
        }
        Ok(())
    }
}

impl Default for ActionSearchBar {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn loaded() -> ActionSearchBar {
        let mut s = ActionSearchBar::new();
        s.register("s1", "Save All", "file", &["save", "all"]).unwrap();
        s.register("s2", "Save As", "file", &["save", "as"]).unwrap();
        s.register("o1", "Open File", "file", &["open"]).unwrap();
        s.register("p1", "Print", "print", &["print", "paper"]).unwrap();
        s
    }

    #[test]
    fn exact_name_wins() {
        let s = loaded();
        let r = s.search("Print");
        assert_eq!(r[0].id, "p1");
    }

    #[test]
    fn starts_with_ranks_high() {
        let s = loaded();
        let r = s.search("save");
        // Two matches start with "save"; alpha-ordered "Save All" before "Save As".
        assert_eq!(r[0].id, "s1");
        assert_eq!(r[1].id, "s2");
    }

    #[test]
    fn category_match() {
        let s = loaded();
        let r = s.search("file");
        // All three file-category items match.
        assert!(r.len() >= 3);
    }

    #[test]
    fn keyword_match() {
        let s = loaded();
        let r = s.search("paper");
        assert_eq!(r[0].id, "p1");
    }

    #[test]
    fn empty_query_returns_all_sorted() {
        let s = loaded();
        let r = s.search("");
        assert_eq!(r.len(), 4);
        assert_eq!(r[0].name, "Open File");
    }

    #[test]
    fn case_insensitive() {
        let s = loaded();
        assert_eq!(s.search("SAVE")[0].id, "s1");
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = ActionSearchBar::new();
        s.register("a", "A", "c", &[]).unwrap();
        assert!(matches!(s.register("a", "A", "c", &[]).unwrap_err(), SearchError::DuplicateId(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = ActionSearchBar::new();
        assert!(matches!(s.register("", "A", "c", &[]).unwrap_err(), SearchError::EmptyId));
        assert!(matches!(s.register("a", "", "c", &[]).unwrap_err(), SearchError::EmptyName));
        assert!(matches!(s.register("a", "A", "", &[]).unwrap_err(), SearchError::EmptyCategory));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ActionSearchBar::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SearchError::SchemaMismatch));
    }

    #[test]
    fn search_serde_roundtrip() {
        let s = loaded();
        let j = serde_json::to_string(&s).unwrap();
        let back: ActionSearchBar = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
