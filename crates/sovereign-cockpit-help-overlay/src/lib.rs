//! `sovereign-cockpit-help-overlay` — shortcut help overlay.
//!
//! Sectioned entries (e.g. "Navigation": `?`, "Cmd+P"). Each entry
//! has a `keys` and `description`. Sections are ordered. `search(q)`
//! returns matching entries case-insensitively across description
//! AND keys.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Keys display.
    pub keys: String,
    /// Description.
    pub description: String,
}

/// One section.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Section {
    /// Title.
    pub title: String,
    /// Entries.
    pub entries: Vec<Entry>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HelpOverlay {
    /// Schema version.
    pub schema_version: String,
    /// Sections in order.
    pub sections: Vec<Section>,
}

/// Search result row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SearchHit {
    /// Section title.
    pub section: String,
    /// Entry.
    pub entry: Entry,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HelpError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Empty.
    #[error("keys empty")]
    EmptyKeys,
    /// Empty.
    #[error("description empty")]
    EmptyDescription,
    /// Duplicate.
    #[error("duplicate section: {0}")]
    DuplicateSection(String),
    /// Unknown.
    #[error("unknown section: {0}")]
    UnknownSection(String),
}

impl HelpOverlay {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            sections: Vec::new(),
        }
    }

    /// Add a section (append).
    pub fn add_section(&mut self, title: &str) -> Result<(), HelpError> {
        if title.is_empty() {
            return Err(HelpError::EmptyTitle);
        }
        if self.sections.iter().any(|s| s.title == title) {
            return Err(HelpError::DuplicateSection(title.into()));
        }
        self.sections.push(Section {
            title: title.into(),
            entries: Vec::new(),
        });
        Ok(())
    }

    /// Add entry to existing section.
    pub fn add_entry(
        &mut self,
        section: &str,
        keys: &str,
        description: &str,
    ) -> Result<(), HelpError> {
        if keys.is_empty() {
            return Err(HelpError::EmptyKeys);
        }
        if description.is_empty() {
            return Err(HelpError::EmptyDescription);
        }
        let s = self
            .sections
            .iter_mut()
            .find(|s| s.title == section)
            .ok_or_else(|| HelpError::UnknownSection(section.into()))?;
        s.entries.push(Entry {
            keys: keys.into(),
            description: description.into(),
        });
        Ok(())
    }

    /// Search across entries.
    pub fn search(&self, q: &str) -> Vec<SearchHit> {
        if q.is_empty() {
            return self
                .sections
                .iter()
                .flat_map(|s| {
                    s.entries.iter().map(move |e| SearchHit {
                        section: s.title.clone(),
                        entry: e.clone(),
                    })
                })
                .collect();
        }
        let needle = q.to_lowercase();
        let mut out = Vec::new();
        for s in &self.sections {
            for e in &s.entries {
                if e.description.to_lowercase().contains(&needle)
                    || e.keys.to_lowercase().contains(&needle)
                {
                    out.push(SearchHit {
                        section: s.title.clone(),
                        entry: e.clone(),
                    });
                }
            }
        }
        out
    }

    /// Total entries.
    pub fn total_entries(&self) -> usize {
        self.sections.iter().map(|s| s.entries.len()).sum()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HelpError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HelpError::SchemaMismatch);
        }
        for s in &self.sections {
            if s.title.is_empty() {
                return Err(HelpError::EmptyTitle);
            }
            for e in &s.entries {
                if e.keys.is_empty() {
                    return Err(HelpError::EmptyKeys);
                }
                if e.description.is_empty() {
                    return Err(HelpError::EmptyDescription);
                }
            }
        }
        Ok(())
    }
}

impl Default for HelpOverlay {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn loaded() -> HelpOverlay {
        let mut h = HelpOverlay::new();
        h.add_section("Navigation").unwrap();
        h.add_entry("Navigation", "Cmd+P", "Quick open").unwrap();
        h.add_entry("Navigation", "Cmd+K", "Command palette")
            .unwrap();
        h.add_section("Editing").unwrap();
        h.add_entry("Editing", "Cmd+Z", "Undo").unwrap();
        h
    }

    #[test]
    fn add_and_total() {
        let h = loaded();
        assert_eq!(h.total_entries(), 3);
    }

    #[test]
    fn search_finds_by_keys() {
        let h = loaded();
        let r = h.search("cmd+p");
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].entry.description, "Quick open");
    }

    #[test]
    fn search_finds_by_description() {
        let h = loaded();
        let r = h.search("undo");
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].section, "Editing");
    }

    #[test]
    fn empty_search_returns_all() {
        let h = loaded();
        assert_eq!(h.search("").len(), 3);
    }

    #[test]
    fn case_insensitive() {
        let h = loaded();
        assert_eq!(h.search("UNDO").len(), 1);
    }

    #[test]
    fn duplicate_section_rejected() {
        let mut h = HelpOverlay::new();
        h.add_section("X").unwrap();
        assert!(matches!(
            h.add_section("X").unwrap_err(),
            HelpError::DuplicateSection(_)
        ));
    }

    #[test]
    fn unknown_section_rejected() {
        let mut h = HelpOverlay::new();
        assert!(matches!(
            h.add_entry("nope", "k", "d").unwrap_err(),
            HelpError::UnknownSection(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut h = HelpOverlay::new();
        assert!(matches!(
            h.add_section("").unwrap_err(),
            HelpError::EmptyTitle
        ));
        h.add_section("X").unwrap();
        assert!(matches!(
            h.add_entry("X", "", "d").unwrap_err(),
            HelpError::EmptyKeys
        ));
        assert!(matches!(
            h.add_entry("X", "k", "").unwrap_err(),
            HelpError::EmptyDescription
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = HelpOverlay::new();
        h.schema_version = "9.9.9".into();
        assert!(matches!(
            h.validate().unwrap_err(),
            HelpError::SchemaMismatch
        ));
    }

    #[test]
    fn help_serde_roundtrip() {
        let h = loaded();
        let j = serde_json::to_string(&h).unwrap();
        let back: HelpOverlay = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
