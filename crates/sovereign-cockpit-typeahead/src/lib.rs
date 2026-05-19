//! `sovereign-cockpit-typeahead` — autocomplete UI state.
//!
//! Holds the operator's query, ranked candidates, the active-index
//! (highlighted suggestion), and event responses (arrow up / down /
//! enter / escape). Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Keyboard event types the typeahead reacts to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TypeaheadKey {
    /// Move highlight down (wraps).
    Down,
    /// Move highlight up (wraps).
    Up,
    /// Commit highlighted suggestion.
    Enter,
    /// Cancel (close panel, clear active).
    Escape,
}

/// Outcome of an Enter commit.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum CommitOutcome {
    /// A candidate was committed.
    Committed {
        /// Id.
        id: String,
        /// Label.
        label: String,
    },
    /// No candidates; Enter is a no-op.
    Empty,
}

/// One candidate.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Candidate {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Score (higher = better). Sorting is caller's responsibility;
    /// the panel rendering keeps insertion order.
    pub score: f32,
}

/// Typeahead state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Typeahead {
    /// Schema version.
    pub schema_version: String,
    /// Operator's current query string.
    pub query: String,
    /// Candidates in render order (already ranked).
    pub candidates: Vec<Candidate>,
    /// Highlighted index (None = nothing highlighted).
    pub active: Option<usize>,
    /// Is the suggestion panel open?
    pub open: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TypeaheadError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("candidate id empty")]
    EmptyId,
    /// Empty label.
    #[error("candidate {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate candidate id: {0}")]
    DuplicateId(String),
    /// Active out of range.
    #[error("active {active} out of range (len {len})")]
    ActiveOutOfRange {
        /// active.
        active: usize,
        /// len.
        len: usize,
    },
    /// NaN score.
    #[error("candidate {0} score NaN")]
    NanScore(String),
}

impl Typeahead {
    /// New closed typeahead with empty state.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            query: String::new(),
            candidates: Vec::new(),
            active: None,
            open: false,
        }
    }

    /// Update query + candidates from upstream search. Highlight resets
    /// to first candidate when non-empty, else None. Panel opens iff
    /// there is at least one candidate.
    pub fn update(&mut self, query: &str, candidates: Vec<Candidate>) -> Result<(), TypeaheadError> {
        check_candidates(&candidates)?;
        self.query = query.into();
        self.candidates = candidates;
        self.active = if self.candidates.is_empty() { None } else { Some(0) };
        self.open = !self.candidates.is_empty();
        Ok(())
    }

    /// Handle a key event. Returns CommitOutcome only for Enter.
    pub fn key(&mut self, k: TypeaheadKey) -> Option<CommitOutcome> {
        let n = self.candidates.len();
        match k {
            TypeaheadKey::Down => {
                if n == 0 {
                    self.active = None;
                } else {
                    self.active = Some(match self.active {
                        Some(i) => (i + 1) % n,
                        None => 0,
                    });
                }
                None
            }
            TypeaheadKey::Up => {
                if n == 0 {
                    self.active = None;
                } else {
                    self.active = Some(match self.active {
                        Some(i) => (i + n - 1) % n,
                        None => n - 1,
                    });
                }
                None
            }
            TypeaheadKey::Enter => {
                if let Some(i) = self.active {
                    let c = &self.candidates[i];
                    let out = CommitOutcome::Committed {
                        id: c.id.clone(),
                        label: c.label.clone(),
                    };
                    self.open = false;
                    Some(out)
                } else {
                    Some(CommitOutcome::Empty)
                }
            }
            TypeaheadKey::Escape => {
                self.open = false;
                self.active = None;
                None
            }
        }
    }

    /// Highlighted candidate (if any).
    pub fn highlighted(&self) -> Option<&Candidate> {
        self.active.map(|i| &self.candidates[i])
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TypeaheadError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TypeaheadError::SchemaMismatch);
        }
        check_candidates(&self.candidates)?;
        if let Some(a) = self.active {
            if a >= self.candidates.len() {
                return Err(TypeaheadError::ActiveOutOfRange {
                    active: a,
                    len: self.candidates.len(),
                });
            }
        }
        Ok(())
    }
}

fn check_candidates(cs: &[Candidate]) -> Result<(), TypeaheadError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for c in cs {
        if c.id.is_empty() {
            return Err(TypeaheadError::EmptyId);
        }
        if c.label.is_empty() {
            return Err(TypeaheadError::EmptyLabel(c.id.clone()));
        }
        if c.score.is_nan() {
            return Err(TypeaheadError::NanScore(c.id.clone()));
        }
        if !seen.insert(c.id.as_str()) {
            return Err(TypeaheadError::DuplicateId(c.id.clone()));
        }
    }
    Ok(())
}

impl Default for Typeahead {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cand(id: &str, score: f32) -> Candidate {
        Candidate { id: id.into(), label: format!("L-{id}"), score }
    }

    #[test]
    fn new_is_closed_empty() {
        let t = Typeahead::new();
        assert!(!t.open);
        assert!(t.active.is_none());
    }

    #[test]
    fn update_opens_panel_when_candidates() {
        let mut t = Typeahead::new();
        t.update("ab", vec![cand("a", 1.0), cand("b", 0.5)]).unwrap();
        assert!(t.open);
        assert_eq!(t.active, Some(0));
    }

    #[test]
    fn update_closes_panel_when_empty() {
        let mut t = Typeahead::new();
        t.update("xyz", vec![]).unwrap();
        assert!(!t.open);
        assert!(t.active.is_none());
    }

    #[test]
    fn down_wraps() {
        let mut t = Typeahead::new();
        t.update("x", vec![cand("a", 1.0), cand("b", 0.5), cand("c", 0.1)]).unwrap();
        t.key(TypeaheadKey::Down);
        assert_eq!(t.active, Some(1));
        t.key(TypeaheadKey::Down);
        assert_eq!(t.active, Some(2));
        t.key(TypeaheadKey::Down);
        assert_eq!(t.active, Some(0));
    }

    #[test]
    fn up_wraps() {
        let mut t = Typeahead::new();
        t.update("x", vec![cand("a", 1.0), cand("b", 0.5)]).unwrap();
        t.key(TypeaheadKey::Up);
        assert_eq!(t.active, Some(1));
    }

    #[test]
    fn enter_commits_active() {
        let mut t = Typeahead::new();
        t.update("x", vec![cand("a", 1.0), cand("b", 0.5)]).unwrap();
        t.key(TypeaheadKey::Down);
        let out = t.key(TypeaheadKey::Enter).unwrap();
        match out {
            CommitOutcome::Committed { id, .. } => assert_eq!(id, "b"),
            _ => panic!(),
        }
        assert!(!t.open);
    }

    #[test]
    fn enter_empty_returns_empty() {
        let mut t = Typeahead::new();
        assert!(matches!(t.key(TypeaheadKey::Enter), Some(CommitOutcome::Empty)));
    }

    #[test]
    fn escape_closes_and_clears() {
        let mut t = Typeahead::new();
        t.update("x", vec![cand("a", 1.0)]).unwrap();
        t.key(TypeaheadKey::Escape);
        assert!(!t.open);
        assert!(t.active.is_none());
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut t = Typeahead::new();
        assert!(matches!(
            t.update("x", vec![cand("a", 1.0), cand("a", 0.5)]).unwrap_err(),
            TypeaheadError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut t = Typeahead::new();
        let mut c = cand("a", 1.0);
        c.id = String::new();
        assert!(matches!(t.update("x", vec![c]).unwrap_err(), TypeaheadError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut t = Typeahead::new();
        let mut c = cand("a", 1.0);
        c.label = String::new();
        assert!(matches!(t.update("x", vec![c]).unwrap_err(), TypeaheadError::EmptyLabel(_)));
    }

    #[test]
    fn nan_score_rejected() {
        let mut t = Typeahead::new();
        let c = cand("a", f32::NAN);
        assert!(matches!(t.update("x", vec![c]).unwrap_err(), TypeaheadError::NanScore(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = Typeahead::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TypeaheadError::SchemaMismatch));
    }

    #[test]
    fn key_serde_kebab() {
        assert_eq!(serde_json::to_string(&TypeaheadKey::Down).unwrap(), "\"down\"");
        assert_eq!(serde_json::to_string(&TypeaheadKey::Escape).unwrap(), "\"escape\"");
    }

    #[test]
    fn outcome_serde_kebab() {
        let c = CommitOutcome::Committed { id: "a".into(), label: "A".into() };
        let j = serde_json::to_string(&c).unwrap();
        assert!(j.contains("\"kind\":\"committed\""));
        let e = CommitOutcome::Empty;
        assert!(serde_json::to_string(&e).unwrap().contains("\"empty\""));
    }

    #[test]
    fn typeahead_serde_roundtrip() {
        let mut t = Typeahead::new();
        t.update("ab", vec![cand("a", 1.0), cand("b", 0.5)]).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: Typeahead = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
