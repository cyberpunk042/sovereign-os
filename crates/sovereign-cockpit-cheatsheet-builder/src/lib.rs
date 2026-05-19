//! `sovereign-cockpit-cheatsheet-builder` — cheatsheet projection.
//!
//! Group registered (action, chord, group) entries into a
//! category-grouped, stable-ordered structure ready for the help
//! overlay.
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
    /// Action id (stable).
    pub action_id: String,
    /// Display label.
    pub label: String,
    /// Chord text.
    pub chord: String,
    /// Group / category.
    pub group: String,
}

/// One projected row (stable for render).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Row {
    /// Label.
    pub label: String,
    /// Chord.
    pub chord: String,
}

/// One group section.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Section {
    /// Group name.
    pub group: String,
    /// Rows.
    pub rows: Vec<Row>,
}

/// Projection.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Cheatsheet {
    /// Schema version.
    pub schema_version: String,
    /// Sections sorted by group name, rows sorted by label.
    pub sections: Vec<Section>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CheatsheetError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty action id.
    #[error("action_id empty")]
    EmptyActionId,
    /// Empty label.
    #[error("entry {0} label empty")]
    EmptyLabel(String),
    /// Empty chord.
    #[error("entry {0} chord empty")]
    EmptyChord(String),
    /// Empty group.
    #[error("entry {0} group empty")]
    EmptyGroup(String),
    /// Duplicate action.
    #[error("duplicate action_id: {0}")]
    DuplicateActionId(String),
}

/// Builder (stateless).
#[derive(Debug, Clone, Default)]
pub struct CheatsheetBuilder;

impl CheatsheetBuilder {
    /// Build.
    pub fn build(entries: &[Entry]) -> Result<Cheatsheet, CheatsheetError> {
        check_entries(entries)?;
        use std::collections::BTreeMap;
        let mut by_group: BTreeMap<String, Vec<Row>> = BTreeMap::new();
        for e in entries {
            by_group.entry(e.group.clone()).or_default().push(Row {
                label: e.label.clone(),
                chord: e.chord.clone(),
            });
        }
        let mut sections: Vec<Section> = Vec::with_capacity(by_group.len());
        for (group, mut rows) in by_group {
            rows.sort_by(|a, b| a.label.cmp(&b.label));
            sections.push(Section { group, rows });
        }
        Ok(Cheatsheet {
            schema_version: SCHEMA_VERSION.into(),
            sections,
        })
    }
}

fn check_entries(entries: &[Entry]) -> Result<(), CheatsheetError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for e in entries {
        if e.action_id.is_empty() { return Err(CheatsheetError::EmptyActionId); }
        if e.label.is_empty() { return Err(CheatsheetError::EmptyLabel(e.action_id.clone())); }
        if e.chord.is_empty() { return Err(CheatsheetError::EmptyChord(e.action_id.clone())); }
        if e.group.is_empty() { return Err(CheatsheetError::EmptyGroup(e.action_id.clone())); }
        if !seen.insert(e.action_id.as_str()) {
            return Err(CheatsheetError::DuplicateActionId(e.action_id.clone()));
        }
    }
    Ok(())
}

impl Cheatsheet {
    /// Validate.
    pub fn validate(&self) -> Result<(), CheatsheetError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CheatsheetError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(id: &str, label: &str, chord: &str, group: &str) -> Entry {
        Entry {
            action_id: id.into(),
            label: label.into(),
            chord: chord.into(),
            group: group.into(),
        }
    }

    #[test]
    fn empty_builds_empty() {
        let c = CheatsheetBuilder::build(&[]).unwrap();
        assert!(c.sections.is_empty());
    }

    #[test]
    fn grouped_by_group_name_sorted() {
        let entries = vec![
            e("save", "Save", "ctrl+s", "File"),
            e("copy", "Copy", "ctrl+c", "Edit"),
            e("paste", "Paste", "ctrl+v", "Edit"),
        ];
        let c = CheatsheetBuilder::build(&entries).unwrap();
        assert_eq!(c.sections.len(), 2);
        // BTreeMap sorts alphabetically: Edit, File
        assert_eq!(c.sections[0].group, "Edit");
        assert_eq!(c.sections[1].group, "File");
    }

    #[test]
    fn rows_sorted_by_label() {
        let entries = vec![
            e("z", "Zebra", "z", "Animals"),
            e("a", "Aardvark", "a", "Animals"),
        ];
        let c = CheatsheetBuilder::build(&entries).unwrap();
        assert_eq!(c.sections[0].rows[0].label, "Aardvark");
        assert_eq!(c.sections[0].rows[1].label, "Zebra");
    }

    #[test]
    fn duplicate_action_id_rejected() {
        let entries = vec![
            e("a", "L1", "c1", "g"),
            e("a", "L2", "c2", "g"),
        ];
        assert!(matches!(CheatsheetBuilder::build(&entries).unwrap_err(), CheatsheetError::DuplicateActionId(_)));
    }

    #[test]
    fn empty_id_rejected() {
        assert!(matches!(
            CheatsheetBuilder::build(&[e("", "L", "c", "g")]).unwrap_err(),
            CheatsheetError::EmptyActionId
        ));
    }

    #[test]
    fn empty_label_rejected() {
        assert!(matches!(
            CheatsheetBuilder::build(&[e("a", "", "c", "g")]).unwrap_err(),
            CheatsheetError::EmptyLabel(_)
        ));
    }

    #[test]
    fn empty_chord_rejected() {
        assert!(matches!(
            CheatsheetBuilder::build(&[e("a", "L", "", "g")]).unwrap_err(),
            CheatsheetError::EmptyChord(_)
        ));
    }

    #[test]
    fn empty_group_rejected() {
        assert!(matches!(
            CheatsheetBuilder::build(&[e("a", "L", "c", "")]).unwrap_err(),
            CheatsheetError::EmptyGroup(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = CheatsheetBuilder::build(&[]).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), CheatsheetError::SchemaMismatch));
    }

    #[test]
    fn cheatsheet_serde_roundtrip() {
        let entries = vec![e("a", "Aardvark", "a", "G1"), e("b", "Bear", "b", "G2")];
        let c = CheatsheetBuilder::build(&entries).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: Cheatsheet = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
