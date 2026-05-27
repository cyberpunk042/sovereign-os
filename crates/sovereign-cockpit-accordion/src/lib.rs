//! `sovereign-cockpit-accordion` — collapsible-panel group state.
//!
//! Ordered sections with title + expanded flag. An optional
//! `single_open` invariant collapses other sections when one opens.
//! Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One section.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Section {
    /// Stable id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Is it currently expanded?
    pub expanded: bool,
}

/// Accordion state envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Accordion {
    /// Schema version.
    pub schema_version: String,
    /// Sections in render order.
    pub sections: Vec<Section>,
    /// If true, opening one section collapses all others.
    pub single_open: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AccordionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("section id empty")]
    EmptyId,
    /// Empty title.
    #[error("section {0} title empty")]
    EmptyTitle(String),
    /// Duplicate id.
    #[error("duplicate section id: {0}")]
    DuplicateId(String),
    /// Multiple expanded under single_open.
    #[error("single_open violated: {0} sections expanded")]
    SingleOpenViolated(usize),
    /// Unknown id.
    #[error("unknown section id: {0}")]
    Unknown(String),
}

impl Accordion {
    /// New accordion.
    pub fn new(sections: Vec<Section>, single_open: bool) -> Result<Self, AccordionError> {
        check_sections(&sections)?;
        if single_open {
            let n = sections.iter().filter(|s| s.expanded).count();
            if n > 1 {
                return Err(AccordionError::SingleOpenViolated(n));
            }
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            sections,
            single_open,
        })
    }

    /// Expand a section. Under single_open, collapses all others.
    pub fn expand(&mut self, id: &str) -> Result<(), AccordionError> {
        let pos = self
            .sections
            .iter()
            .position(|s| s.id == id)
            .ok_or_else(|| AccordionError::Unknown(id.into()))?;
        if self.single_open {
            for (i, s) in self.sections.iter_mut().enumerate() {
                s.expanded = i == pos;
            }
        } else {
            self.sections[pos].expanded = true;
        }
        Ok(())
    }

    /// Collapse a section.
    pub fn collapse(&mut self, id: &str) -> Result<(), AccordionError> {
        let s = self
            .sections
            .iter_mut()
            .find(|s| s.id == id)
            .ok_or_else(|| AccordionError::Unknown(id.into()))?;
        s.expanded = false;
        Ok(())
    }

    /// Toggle (expand if collapsed, collapse if expanded).
    pub fn toggle(&mut self, id: &str) -> Result<(), AccordionError> {
        let pos = self
            .sections
            .iter()
            .position(|s| s.id == id)
            .ok_or_else(|| AccordionError::Unknown(id.into()))?;
        if self.sections[pos].expanded {
            self.sections[pos].expanded = false;
        } else if self.single_open {
            for (i, s) in self.sections.iter_mut().enumerate() {
                s.expanded = i == pos;
            }
        } else {
            self.sections[pos].expanded = true;
        }
        Ok(())
    }

    /// Currently-expanded section ids.
    pub fn expanded(&self) -> Vec<&str> {
        self.sections
            .iter()
            .filter(|s| s.expanded)
            .map(|s| s.id.as_str())
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AccordionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(AccordionError::SchemaMismatch);
        }
        check_sections(&self.sections)?;
        if self.single_open {
            let n = self.sections.iter().filter(|s| s.expanded).count();
            if n > 1 {
                return Err(AccordionError::SingleOpenViolated(n));
            }
        }
        Ok(())
    }
}

fn check_sections(sections: &[Section]) -> Result<(), AccordionError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for s in sections {
        if s.id.is_empty() {
            return Err(AccordionError::EmptyId);
        }
        if s.title.is_empty() {
            return Err(AccordionError::EmptyTitle(s.id.clone()));
        }
        if !seen.insert(s.id.as_str()) {
            return Err(AccordionError::DuplicateId(s.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sec(id: &str, expanded: bool) -> Section {
        Section {
            id: id.into(),
            title: format!("T-{id}"),
            expanded,
        }
    }

    #[test]
    fn empty_validates() {
        Accordion::new(vec![], false).unwrap().validate().unwrap();
    }

    #[test]
    fn expand_section() {
        let mut a = Accordion::new(vec![sec("a", false), sec("b", false)], false).unwrap();
        a.expand("a").unwrap();
        assert_eq!(a.expanded(), vec!["a"]);
    }

    #[test]
    fn single_open_collapses_others() {
        let mut a =
            Accordion::new(vec![sec("a", true), sec("b", false), sec("c", false)], true).unwrap();
        a.expand("b").unwrap();
        assert_eq!(a.expanded(), vec!["b"]);
    }

    #[test]
    fn multi_open_keeps_others() {
        let mut a = Accordion::new(
            vec![sec("a", true), sec("b", false), sec("c", false)],
            false,
        )
        .unwrap();
        a.expand("b").unwrap();
        let e = a.expanded();
        assert!(e.contains(&"a"));
        assert!(e.contains(&"b"));
    }

    #[test]
    fn collapse_section() {
        let mut a = Accordion::new(vec![sec("a", true)], false).unwrap();
        a.collapse("a").unwrap();
        assert!(a.expanded().is_empty());
    }

    #[test]
    fn toggle_flips_state() {
        let mut a = Accordion::new(vec![sec("a", false)], false).unwrap();
        a.toggle("a").unwrap();
        assert_eq!(a.expanded(), vec!["a"]);
        a.toggle("a").unwrap();
        assert!(a.expanded().is_empty());
    }

    #[test]
    fn toggle_single_open_collapses_others() {
        let mut a = Accordion::new(vec![sec("a", true), sec("b", false)], true).unwrap();
        a.toggle("b").unwrap();
        assert_eq!(a.expanded(), vec!["b"]);
    }

    #[test]
    fn unknown_id_rejected() {
        let mut a = Accordion::new(vec![sec("a", false)], false).unwrap();
        assert!(matches!(
            a.expand("z").unwrap_err(),
            AccordionError::Unknown(_)
        ));
        assert!(matches!(
            a.collapse("z").unwrap_err(),
            AccordionError::Unknown(_)
        ));
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            Accordion::new(vec![sec("a", false), sec("a", false)], false).unwrap_err(),
            AccordionError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = sec("a", false);
        s.id = String::new();
        assert!(matches!(
            Accordion::new(vec![s], false).unwrap_err(),
            AccordionError::EmptyId
        ));
    }

    #[test]
    fn empty_title_rejected() {
        let mut s = sec("a", false);
        s.title = String::new();
        assert!(matches!(
            Accordion::new(vec![s], false).unwrap_err(),
            AccordionError::EmptyTitle(_)
        ));
    }

    #[test]
    fn single_open_invariant_rejected_on_new() {
        assert!(matches!(
            Accordion::new(vec![sec("a", true), sec("b", true)], true).unwrap_err(),
            AccordionError::SingleOpenViolated(2)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut a = Accordion::new(vec![sec("a", false)], false).unwrap();
        a.schema_version = "9.9.9".into();
        assert!(matches!(
            a.validate().unwrap_err(),
            AccordionError::SchemaMismatch
        ));
    }

    #[test]
    fn accordion_serde_roundtrip() {
        let a = Accordion::new(vec![sec("a", true), sec("b", false)], false).unwrap();
        let j = serde_json::to_string(&a).unwrap();
        let back: Accordion = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
