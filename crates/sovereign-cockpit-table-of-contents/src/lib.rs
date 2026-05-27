//! `sovereign-cockpit-table-of-contents` — hierarchical TOC.
//!
//! Heading{id, label, level, offset}. add appends in document
//! order (level 1..=6). update_scroll(offset) picks the latest
//! heading whose offset <= scroll_offset as active; if none,
//! the first heading is active. nested() builds parent→children
//! depths via level descents.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Heading.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Heading {
    /// Anchor id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Level 1..=6.
    pub level: u8,
    /// Scroll offset in px.
    pub offset: u32,
}

/// Active heading info.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Active {
    /// Active heading id.
    pub id: String,
    /// Index in the headings vec.
    pub index: usize,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TableOfContents {
    /// Schema version.
    pub schema_version: String,
    /// Headings in document order.
    pub headings: Vec<Heading>,
    /// Current scroll offset.
    pub scroll_offset: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TocError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Bad level.
    #[error("level must be 1..=6")]
    BadLevel,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl TableOfContents {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            headings: Vec::new(),
            scroll_offset: 0,
        }
    }

    /// Add heading.
    pub fn add(&mut self, id: &str, label: &str, level: u8, offset: u32) -> Result<(), TocError> {
        if id.is_empty() {
            return Err(TocError::EmptyId);
        }
        if label.is_empty() {
            return Err(TocError::EmptyLabel);
        }
        if level == 0 || level > 6 {
            return Err(TocError::BadLevel);
        }
        if self.headings.iter().any(|h| h.id == id) {
            return Err(TocError::DuplicateId(id.into()));
        }
        self.headings.push(Heading {
            id: id.into(),
            label: label.into(),
            level,
            offset,
        });
        Ok(())
    }

    /// Update scroll offset.
    pub fn update_scroll(&mut self, scroll_offset: u32) {
        self.scroll_offset = scroll_offset;
    }

    /// Active heading at current scroll_offset.
    pub fn active(&self) -> Option<Active> {
        if self.headings.is_empty() {
            return None;
        }
        let mut best: Option<(usize, &Heading)> = None;
        for (i, h) in self.headings.iter().enumerate() {
            if h.offset <= self.scroll_offset {
                best = Some((i, h));
            } else {
                break;
            }
        }
        let (index, h) = best.unwrap_or((0, &self.headings[0]));
        Some(Active {
            id: h.id.clone(),
            index,
        })
    }

    /// Children of heading at index (next siblings until a level <= that level).
    pub fn children_of(&self, parent_index: usize) -> Vec<usize> {
        let Some(parent) = self.headings.get(parent_index) else {
            return Vec::new();
        };
        let mut out = Vec::new();
        for (i, h) in self.headings.iter().enumerate().skip(parent_index + 1) {
            if h.level <= parent.level {
                break;
            }
            if h.level == parent.level + 1 {
                out.push(i);
            }
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TocError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TocError::SchemaMismatch);
        }
        for h in &self.headings {
            if h.id.is_empty() {
                return Err(TocError::EmptyId);
            }
            if h.label.is_empty() {
                return Err(TocError::EmptyLabel);
            }
            if h.level == 0 || h.level > 6 {
                return Err(TocError::BadLevel);
            }
        }
        Ok(())
    }
}

impl Default for TableOfContents {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_has_no_active() {
        let t = TableOfContents::new();
        assert_eq!(t.active(), None);
    }

    #[test]
    fn first_active_when_before_all() {
        let mut t = TableOfContents::new();
        t.add("a", "A", 1, 100).unwrap();
        t.add("b", "B", 1, 500).unwrap();
        t.update_scroll(0);
        assert_eq!(t.active().unwrap().id, "a");
    }

    #[test]
    fn picks_latest_heading_at_or_before_scroll() {
        let mut t = TableOfContents::new();
        t.add("a", "A", 1, 100).unwrap();
        t.add("b", "B", 1, 500).unwrap();
        t.add("c", "C", 1, 1000).unwrap();
        t.update_scroll(750);
        assert_eq!(t.active().unwrap().id, "b");
    }

    #[test]
    fn last_active_when_scrolled_past_end() {
        let mut t = TableOfContents::new();
        t.add("a", "A", 1, 100).unwrap();
        t.add("b", "B", 1, 500).unwrap();
        t.update_scroll(9999);
        assert_eq!(t.active().unwrap().id, "b");
    }

    #[test]
    fn children_of_parent() {
        let mut t = TableOfContents::new();
        t.add("h1", "Intro", 1, 0).unwrap();
        t.add("h2a", "Setup", 2, 100).unwrap();
        t.add("h2b", "Run", 2, 200).unwrap();
        t.add("h1b", "Outro", 1, 300).unwrap();
        let kids = t.children_of(0);
        assert_eq!(kids, vec![1, 2]);
    }

    #[test]
    fn children_skips_grandchildren() {
        let mut t = TableOfContents::new();
        t.add("h1", "Top", 1, 0).unwrap();
        t.add("h2", "Mid", 2, 100).unwrap();
        t.add("h3", "Deep", 3, 200).unwrap();
        t.add("h2b", "Mid2", 2, 300).unwrap();
        let kids = t.children_of(0);
        assert_eq!(kids, vec![1, 3]);
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut t = TableOfContents::new();
        t.add("a", "A", 1, 0).unwrap();
        assert!(matches!(
            t.add("a", "A2", 1, 100).unwrap_err(),
            TocError::DuplicateId(_)
        ));
    }

    #[test]
    fn bad_inputs_rejected() {
        let mut t = TableOfContents::new();
        assert!(matches!(
            t.add("", "A", 1, 0).unwrap_err(),
            TocError::EmptyId
        ));
        assert!(matches!(
            t.add("a", "", 1, 0).unwrap_err(),
            TocError::EmptyLabel
        ));
        assert!(matches!(
            t.add("a", "A", 0, 0).unwrap_err(),
            TocError::BadLevel
        ));
        assert!(matches!(
            t.add("a", "A", 7, 0).unwrap_err(),
            TocError::BadLevel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TableOfContents::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            TocError::SchemaMismatch
        ));
    }

    #[test]
    fn toc_serde_roundtrip() {
        let mut t = TableOfContents::new();
        t.add("a", "A", 1, 0).unwrap();
        t.update_scroll(50);
        let j = serde_json::to_string(&t).unwrap();
        let back: TableOfContents = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
