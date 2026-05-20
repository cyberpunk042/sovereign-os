//! `sovereign-cockpit-snippet-library` — operator-curated text snippets.
//!
//! Each Snippet has a stable id, a display name, a body, an optional
//! one-token trigger (typed in the input as `;<trigger>;` to expand),
//! and an arbitrary set of tags.
//!
//! `search(query, tag_filter)` returns matches ranked:
//!   1. exact-name match
//!   2. trigger == query
//!   3. name starts-with(query)
//!   4. body contains(query)
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One snippet.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Snippet {
    /// Stable id.
    pub id: String,
    /// Display name.
    pub name: String,
    /// Body text.
    pub body: String,
    /// Optional trigger token.
    pub trigger: Option<String>,
    /// Tags.
    pub tags: BTreeSet<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SnippetLibrary {
    /// Schema version.
    pub schema_version: String,
    /// id → snippet.
    pub snippets: BTreeMap<String, Snippet>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SnippetError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("snippet id empty")]
    EmptyId,
    /// Empty name.
    #[error("snippet name empty")]
    EmptyName,
    /// Empty body.
    #[error("snippet body empty")]
    EmptyBody,
    /// Duplicate.
    #[error("duplicate snippet id: {0}")]
    DuplicateId(String),
}

impl SnippetLibrary {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            snippets: BTreeMap::new(),
        }
    }

    /// Add.
    pub fn add(&mut self, snippet: Snippet) -> Result<(), SnippetError> {
        if snippet.id.is_empty() { return Err(SnippetError::EmptyId); }
        if snippet.name.is_empty() { return Err(SnippetError::EmptyName); }
        if snippet.body.is_empty() { return Err(SnippetError::EmptyBody); }
        if self.snippets.contains_key(&snippet.id) {
            return Err(SnippetError::DuplicateId(snippet.id));
        }
        self.snippets.insert(snippet.id.clone(), snippet);
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.snippets.remove(id).is_some()
    }

    /// Get.
    pub fn get(&self, id: &str) -> Option<&Snippet> {
        self.snippets.get(id)
    }

    /// Search.
    pub fn search(&self, query: &str, tag_filter: &[&str]) -> Vec<Snippet> {
        let q = query.to_lowercase();
        let mut scored: Vec<(u8, &Snippet)> = self.snippets.values()
            .filter(|s| {
                if tag_filter.is_empty() { return true; }
                tag_filter.iter().all(|t| s.tags.contains(*t))
            })
            .filter_map(|s| {
                let n = s.name.to_lowercase();
                let b = s.body.to_lowercase();
                let trig = s.trigger.as_ref().map(|t| t.to_lowercase());
                if n == q { Some((4, s)) }
                else if trig.as_deref() == Some(q.as_str()) { Some((3, s)) }
                else if n.starts_with(&q) { Some((2, s)) }
                else if b.contains(&q) { Some((1, s)) }
                else { None }
            })
            .collect();
        scored.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.name.cmp(&b.1.name)));
        scored.into_iter().map(|(_, s)| s.clone()).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SnippetError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SnippetError::SchemaMismatch); }
        for (id, s) in &self.snippets {
            if id.is_empty() { return Err(SnippetError::EmptyId); }
            if s.name.is_empty() { return Err(SnippetError::EmptyName); }
            if s.body.is_empty() { return Err(SnippetError::EmptyBody); }
        }
        Ok(())
    }
}

impl Default for SnippetLibrary {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snip(id: &str, name: &str, body: &str, trigger: Option<&str>, tags: &[&str]) -> Snippet {
        Snippet {
            id: id.into(),
            name: name.into(),
            body: body.into(),
            trigger: trigger.map(|s| s.into()),
            tags: tags.iter().map(|t| (*t).into()).collect(),
        }
    }

    #[test]
    fn add_and_get() {
        let mut l = SnippetLibrary::new();
        l.add(snip("s1", "Greeting", "Hello!", Some("hi"), &["common"])).unwrap();
        assert!(l.get("s1").is_some());
    }

    #[test]
    fn duplicate_rejected() {
        let mut l = SnippetLibrary::new();
        l.add(snip("s1", "X", "Y", None, &[])).unwrap();
        assert!(matches!(l.add(snip("s1", "X", "Y", None, &[])).unwrap_err(), SnippetError::DuplicateId(_)));
    }

    #[test]
    fn search_ranks_exact_first() {
        let mut l = SnippetLibrary::new();
        l.add(snip("s1", "Hello world", "Hi there", None, &[])).unwrap();
        l.add(snip("s2", "Hello", "Different", None, &[])).unwrap();
        let r = l.search("hello", &[]);
        assert_eq!(r[0].id, "s2"); // exact match first.
    }

    #[test]
    fn search_by_trigger() {
        let mut l = SnippetLibrary::new();
        l.add(snip("s1", "Long Name", "body", Some("ln"), &[])).unwrap();
        let r = l.search("ln", &[]);
        assert!(r.iter().any(|s| s.id == "s1"));
    }

    #[test]
    fn search_filters_by_tag() {
        let mut l = SnippetLibrary::new();
        l.add(snip("s1", "Hello", "x", None, &["common"])).unwrap();
        l.add(snip("s2", "Hello", "y", None, &["rare"])).unwrap();
        let r = l.search("hello", &["common"]);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].id, "s1");
    }

    #[test]
    fn remove_returns_bool() {
        let mut l = SnippetLibrary::new();
        l.add(snip("s1", "X", "Y", None, &[])).unwrap();
        assert!(l.remove("s1"));
        assert!(!l.remove("s1"));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut l = SnippetLibrary::new();
        assert!(matches!(l.add(snip("", "X", "Y", None, &[])).unwrap_err(), SnippetError::EmptyId));
        assert!(matches!(l.add(snip("s", "", "Y", None, &[])).unwrap_err(), SnippetError::EmptyName));
        assert!(matches!(l.add(snip("s", "X", "", None, &[])).unwrap_err(), SnippetError::EmptyBody));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = SnippetLibrary::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), SnippetError::SchemaMismatch));
    }

    #[test]
    fn library_serde_roundtrip() {
        let mut l = SnippetLibrary::new();
        l.add(snip("s1", "X", "Y", Some("t"), &["a", "b"])).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: SnippetLibrary = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
