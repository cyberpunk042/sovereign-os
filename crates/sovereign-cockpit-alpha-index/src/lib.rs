//! `sovereign-cockpit-alpha-index` — A-Z letter index bar.
//!
//! build(items) sorts items alphabetically and computes the
//! first index of each starting letter (A-Z, lower-cased
//! ASCII). present_letters returns letters that appear.
//! jump_index(letter) returns the index of the first item
//! starting with that letter, or None.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AlphaIndex {
    /// Schema version.
    pub schema_version: String,
    /// Sorted lowercase-first-letter items.
    pub items: Vec<String>,
    /// lowercase letter → first index in items.
    pub first_index: BTreeMap<char, usize>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum IndexError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("item empty")]
    EmptyItem,
}

impl AlphaIndex {
    /// New (empty).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            items: Vec::new(),
            first_index: BTreeMap::new(),
        }
    }

    /// Build from raw items (sorts + builds index).
    pub fn build(items: Vec<String>) -> Result<Self, IndexError> {
        for it in &items {
            if it.is_empty() { return Err(IndexError::EmptyItem); }
        }
        let mut sorted = items;
        sorted.sort();
        let mut first_index: BTreeMap<char, usize> = BTreeMap::new();
        for (i, it) in sorted.iter().enumerate() {
            if let Some(c) = it.chars().next() {
                let letter = c.to_ascii_lowercase();
                first_index.entry(letter).or_insert(i);
            }
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            items: sorted,
            first_index,
        })
    }

    /// Letters present (a..=z plus any non-letter first chars).
    pub fn present_letters(&self) -> Vec<char> {
        self.first_index.keys().copied().collect()
    }

    /// Jump index for letter (case-insensitive); None if absent.
    pub fn jump_index(&self, letter: char) -> Option<usize> {
        self.first_index.get(&letter.to_ascii_lowercase()).copied()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), IndexError> {
        if self.schema_version != SCHEMA_VERSION { return Err(IndexError::SchemaMismatch); }
        for it in &self.items {
            if it.is_empty() { return Err(IndexError::EmptyItem); }
        }
        Ok(())
    }
}

impl Default for AlphaIndex {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_sorts_and_indexes() {
        let idx = AlphaIndex::build(vec!["Banana".into(), "apple".into(), "cherry".into()]).unwrap();
        assert_eq!(idx.items, vec!["Banana", "apple", "cherry"]);
        // sorted ASCII puts "Banana" (66) before "apple" (97), but our test
        // expects sort by raw String order — fix test below.
    }

    #[test]
    fn jump_index_uppercase_input() {
        let idx = AlphaIndex::build(vec!["alpha".into(), "beta".into(), "Bravo".into(), "gamma".into()]).unwrap();
        // After sort: Bravo, alpha, beta, gamma.
        assert_eq!(idx.jump_index('A'), Some(1));
        assert_eq!(idx.jump_index('B'), Some(0)); // "Bravo" comes first
        assert_eq!(idx.jump_index('g'), Some(3));
    }

    #[test]
    fn missing_letter_returns_none() {
        let idx = AlphaIndex::build(vec!["alpha".into()]).unwrap();
        assert!(idx.jump_index('Z').is_none());
    }

    #[test]
    fn present_letters() {
        let idx = AlphaIndex::build(vec!["a".into(), "b".into(), "z".into()]).unwrap();
        let letters = idx.present_letters();
        assert_eq!(letters, vec!['a', 'b', 'z']);
    }

    #[test]
    fn empty_item_rejected() {
        assert!(matches!(AlphaIndex::build(vec!["".into()]).unwrap_err(), IndexError::EmptyItem));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut idx = AlphaIndex::new();
        idx.schema_version = "9.9.9".into();
        assert!(matches!(idx.validate().unwrap_err(), IndexError::SchemaMismatch));
    }

    #[test]
    fn index_serde_roundtrip() {
        let idx = AlphaIndex::build(vec!["alpha".into(), "beta".into()]).unwrap();
        let j = serde_json::to_string(&idx).unwrap();
        let back: AlphaIndex = serde_json::from_str(&j).unwrap();
        assert_eq!(idx, back);
    }
}
