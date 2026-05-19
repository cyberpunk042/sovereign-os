//! `sovereign-cockpit-empty-search-state` — no-results UX state.
//!
//! Given (query, has_filters, indexed) classify why there are no
//! results and pick the operator-facing message + suggested-action.
//! Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Empty-state cause.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EmptyCause {
    /// Operator hasn't typed anything.
    BlankQuery,
    /// Query is non-blank but matches nothing.
    NothingMatches,
    /// Matches exist but were removed by active filters.
    FilteredOut,
    /// Index not built yet.
    NotIndexedYet,
}

/// Suggested action (operator can invoke from the empty state).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SuggestedAction {
    /// Start typing.
    StartTyping,
    /// Broaden query (try synonyms / fewer terms).
    BroadenQuery,
    /// Clear all filters.
    ClearFilters,
    /// Trigger an index rebuild.
    RebuildIndex,
}

/// Input.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct EmptySearchInput {
    /// Is the query blank (or only whitespace)?
    pub blank_query: bool,
    /// Are any filters active?
    pub has_filters: bool,
    /// Has the index been built?
    pub indexed: bool,
}

/// Computed empty-state display.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EmptySearchState {
    /// Schema version.
    pub schema_version: String,
    /// Classified cause.
    pub cause: EmptyCause,
    /// Operator-facing headline.
    pub headline: String,
    /// Operator-facing detail.
    pub detail: String,
    /// Recommended action.
    pub suggested_action: SuggestedAction,
}

/// Errors.
#[derive(Debug, Error)]
pub enum EmptyStateError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// Pure classifier.
#[derive(Debug, Clone, Default)]
pub struct EmptySearchClassifier;

impl EmptySearchClassifier {
    /// Classify.
    pub fn classify(input: EmptySearchInput) -> EmptySearchState {
        if !input.indexed {
            return EmptySearchState {
                schema_version: SCHEMA_VERSION.into(),
                cause: EmptyCause::NotIndexedYet,
                headline: "Index not ready".into(),
                detail: "Search results will appear once the index has been built.".into(),
                suggested_action: SuggestedAction::RebuildIndex,
            };
        }
        if input.blank_query {
            return EmptySearchState {
                schema_version: SCHEMA_VERSION.into(),
                cause: EmptyCause::BlankQuery,
                headline: "Type to search".into(),
                detail: "Enter at least one search term to see results.".into(),
                suggested_action: SuggestedAction::StartTyping,
            };
        }
        if input.has_filters {
            return EmptySearchState {
                schema_version: SCHEMA_VERSION.into(),
                cause: EmptyCause::FilteredOut,
                headline: "No matches under current filters".into(),
                detail: "Active filters may be hiding matches; clearing them may surface results.".into(),
                suggested_action: SuggestedAction::ClearFilters,
            };
        }
        EmptySearchState {
            schema_version: SCHEMA_VERSION.into(),
            cause: EmptyCause::NothingMatches,
            headline: "No matches found".into(),
            detail: "Try fewer terms, synonyms, or a broader query.".into(),
            suggested_action: SuggestedAction::BroadenQuery,
        }
    }
}

impl EmptySearchState {
    /// Validate.
    pub fn validate(&self) -> Result<(), EmptyStateError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(EmptyStateError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn inp(blank: bool, filters: bool, idx: bool) -> EmptySearchInput {
        EmptySearchInput { blank_query: blank, has_filters: filters, indexed: idx }
    }

    #[test]
    fn not_indexed_wins() {
        let s = EmptySearchClassifier::classify(inp(false, true, false));
        assert_eq!(s.cause, EmptyCause::NotIndexedYet);
        assert_eq!(s.suggested_action, SuggestedAction::RebuildIndex);
    }

    #[test]
    fn blank_query_classified() {
        let s = EmptySearchClassifier::classify(inp(true, false, true));
        assert_eq!(s.cause, EmptyCause::BlankQuery);
        assert_eq!(s.suggested_action, SuggestedAction::StartTyping);
    }

    #[test]
    fn filters_active_classified() {
        let s = EmptySearchClassifier::classify(inp(false, true, true));
        assert_eq!(s.cause, EmptyCause::FilteredOut);
        assert_eq!(s.suggested_action, SuggestedAction::ClearFilters);
    }

    #[test]
    fn nothing_matches_classified() {
        let s = EmptySearchClassifier::classify(inp(false, false, true));
        assert_eq!(s.cause, EmptyCause::NothingMatches);
        assert_eq!(s.suggested_action, SuggestedAction::BroadenQuery);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = EmptySearchClassifier::classify(inp(true, false, true));
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), EmptyStateError::SchemaMismatch));
    }

    #[test]
    fn headlines_nonempty() {
        for blank in [true, false] {
            for filters in [true, false] {
                for idx in [true, false] {
                    let s = EmptySearchClassifier::classify(inp(blank, filters, idx));
                    assert!(!s.headline.is_empty());
                    assert!(!s.detail.is_empty());
                }
            }
        }
    }

    #[test]
    fn cause_serde_kebab() {
        assert_eq!(serde_json::to_string(&EmptyCause::NotIndexedYet).unwrap(), "\"not-indexed-yet\"");
        assert_eq!(serde_json::to_string(&EmptyCause::FilteredOut).unwrap(), "\"filtered-out\"");
    }

    #[test]
    fn action_serde_kebab() {
        assert_eq!(serde_json::to_string(&SuggestedAction::RebuildIndex).unwrap(), "\"rebuild-index\"");
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = EmptySearchClassifier::classify(inp(false, true, true));
        let j = serde_json::to_string(&s).unwrap();
        let back: EmptySearchState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
