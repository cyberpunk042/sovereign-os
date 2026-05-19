//! `sovereign-cockpit-grouped-list` — section-list state.
//!
//! Items carry group_key. Per-group `collapsed` flag. flat_render
//! emits a flat Vec<Row> alternating GroupHeader and Item, skipping
//! items of collapsed groups.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Item {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Group key.
    pub group_key: String,
}

/// One group.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Group {
    /// Stable key.
    pub key: String,
    /// Header label.
    pub header: String,
    /// Collapsed?
    pub collapsed: bool,
}

/// Rendered row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Row {
    /// Header.
    GroupHeader {
        /// key.
        key: String,
        /// label.
        label: String,
        /// collapsed.
        collapsed: bool,
        /// item count inside.
        item_count: u32,
    },
    /// Item.
    Item {
        /// id.
        id: String,
        /// label.
        label: String,
        /// group_key.
        group_key: String,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GroupedList {
    /// Schema version.
    pub schema_version: String,
    /// Groups in render order.
    pub groups: Vec<Group>,
    /// Items in render order.
    pub items: Vec<Item>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GroupedListError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty key.
    #[error("group key empty")]
    EmptyKey,
    /// Empty id.
    #[error("item id empty")]
    EmptyId,
    /// Empty header.
    #[error("group {0} header empty")]
    EmptyHeader(String),
    /// Empty item label.
    #[error("item {0} label empty")]
    EmptyLabel(String),
    /// Duplicate group key.
    #[error("duplicate group key: {0}")]
    DuplicateGroupKey(String),
    /// Duplicate item id.
    #[error("duplicate item id: {0}")]
    DuplicateItemId(String),
    /// Item references unknown group.
    #[error("item {item} references unknown group: {group}")]
    UnknownGroup {
        /// item.
        item: String,
        /// group.
        group: String,
    },
    /// Unknown id (op).
    #[error("unknown group key: {0}")]
    Unknown(String),
}

impl GroupedList {
    /// New.
    pub fn new(groups: Vec<Group>, items: Vec<Item>) -> Result<Self, GroupedListError> {
        check_groups_items(&groups, &items)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            groups,
            items,
        })
    }

    /// Toggle a group's collapsed flag.
    pub fn toggle_group(&mut self, key: &str) -> Result<(), GroupedListError> {
        let g = self.groups.iter_mut().find(|g| g.key == key)
            .ok_or_else(|| GroupedListError::Unknown(key.into()))?;
        g.collapsed = !g.collapsed;
        Ok(())
    }

    /// Flat render.
    pub fn flat_render(&self) -> Vec<Row> {
        let mut out: Vec<Row> = Vec::new();
        for g in &self.groups {
            let item_count = self.items.iter().filter(|i| i.group_key == g.key).count() as u32;
            out.push(Row::GroupHeader {
                key: g.key.clone(),
                label: g.header.clone(),
                collapsed: g.collapsed,
                item_count,
            });
            if g.collapsed { continue; }
            for it in self.items.iter().filter(|i| i.group_key == g.key) {
                out.push(Row::Item {
                    id: it.id.clone(),
                    label: it.label.clone(),
                    group_key: it.group_key.clone(),
                });
            }
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GroupedListError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GroupedListError::SchemaMismatch);
        }
        check_groups_items(&self.groups, &self.items)
    }
}

fn check_groups_items(groups: &[Group], items: &[Item]) -> Result<(), GroupedListError> {
    use std::collections::HashSet;
    let mut gkeys: HashSet<&str> = HashSet::new();
    for g in groups {
        if g.key.is_empty() { return Err(GroupedListError::EmptyKey); }
        if g.header.is_empty() { return Err(GroupedListError::EmptyHeader(g.key.clone())); }
        if !gkeys.insert(g.key.as_str()) {
            return Err(GroupedListError::DuplicateGroupKey(g.key.clone()));
        }
    }
    let mut iids: HashSet<&str> = HashSet::new();
    for it in items {
        if it.id.is_empty() { return Err(GroupedListError::EmptyId); }
        if it.label.is_empty() { return Err(GroupedListError::EmptyLabel(it.id.clone())); }
        if !iids.insert(it.id.as_str()) {
            return Err(GroupedListError::DuplicateItemId(it.id.clone()));
        }
        if !gkeys.contains(it.group_key.as_str()) {
            return Err(GroupedListError::UnknownGroup {
                item: it.id.clone(),
                group: it.group_key.clone(),
            });
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn g(key: &str, collapsed: bool) -> Group {
        Group { key: key.into(), header: format!("H-{key}"), collapsed }
    }

    fn it(id: &str, group: &str) -> Item {
        Item { id: id.into(), label: format!("L-{id}"), group_key: group.into() }
    }

    #[test]
    fn empty_validates() {
        GroupedList::new(vec![], vec![]).unwrap().validate().unwrap();
    }

    #[test]
    fn flat_render_includes_headers_and_items() {
        let gl = GroupedList::new(
            vec![g("g1", false), g("g2", false)],
            vec![it("a", "g1"), it("b", "g1"), it("c", "g2")],
        ).unwrap();
        let rows = gl.flat_render();
        assert_eq!(rows.len(), 5); // 2 headers + 3 items
    }

    #[test]
    fn collapsed_group_hides_items() {
        let gl = GroupedList::new(
            vec![g("g1", true), g("g2", false)],
            vec![it("a", "g1"), it("b", "g1"), it("c", "g2")],
        ).unwrap();
        let rows = gl.flat_render();
        // 2 headers + 1 item (g2 only).
        assert_eq!(rows.len(), 3);
    }

    #[test]
    fn item_count_reported() {
        let gl = GroupedList::new(
            vec![g("g1", false)],
            vec![it("a", "g1"), it("b", "g1")],
        ).unwrap();
        let rows = gl.flat_render();
        match &rows[0] {
            Row::GroupHeader { item_count, .. } => assert_eq!(*item_count, 2),
            _ => panic!(),
        }
    }

    #[test]
    fn toggle_group_flips() {
        let mut gl = GroupedList::new(
            vec![g("g1", false)],
            vec![it("a", "g1")],
        ).unwrap();
        gl.toggle_group("g1").unwrap();
        assert!(gl.groups[0].collapsed);
        gl.toggle_group("g1").unwrap();
        assert!(!gl.groups[0].collapsed);
    }

    #[test]
    fn unknown_group_in_items_rejected() {
        assert!(matches!(
            GroupedList::new(vec![g("g1", false)], vec![it("a", "ghost")]).unwrap_err(),
            GroupedListError::UnknownGroup { .. }
        ));
    }

    #[test]
    fn duplicate_group_key_rejected() {
        assert!(matches!(
            GroupedList::new(vec![g("g1", false), g("g1", false)], vec![]).unwrap_err(),
            GroupedListError::DuplicateGroupKey(_)
        ));
    }

    #[test]
    fn duplicate_item_id_rejected() {
        assert!(matches!(
            GroupedList::new(vec![g("g1", false)], vec![it("a", "g1"), it("a", "g1")]).unwrap_err(),
            GroupedListError::DuplicateItemId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = it("a", "g1");
        x.id = String::new();
        assert!(matches!(
            GroupedList::new(vec![g("g1", false)], vec![x]).unwrap_err(),
            GroupedListError::EmptyId
        ));
    }

    #[test]
    fn empty_header_rejected() {
        let mut x = g("g1", false);
        x.header = String::new();
        assert!(matches!(GroupedList::new(vec![x], vec![]).unwrap_err(), GroupedListError::EmptyHeader(_)));
    }

    #[test]
    fn toggle_unknown_rejected() {
        let mut gl = GroupedList::new(vec![g("g1", false)], vec![]).unwrap();
        assert!(matches!(gl.toggle_group("ghost").unwrap_err(), GroupedListError::Unknown(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut gl = GroupedList::new(vec![g("g1", false)], vec![]).unwrap();
        gl.schema_version = "9.9.9".into();
        assert!(matches!(gl.validate().unwrap_err(), GroupedListError::SchemaMismatch));
    }

    #[test]
    fn row_serde_kebab() {
        let r = Row::GroupHeader { key: "k".into(), label: "L".into(), collapsed: false, item_count: 0 };
        assert!(serde_json::to_string(&r).unwrap().contains("\"kind\":\"group-header\""));
    }

    #[test]
    fn list_serde_roundtrip() {
        let gl = GroupedList::new(
            vec![g("g1", false)],
            vec![it("a", "g1")],
        ).unwrap();
        let j = serde_json::to_string(&gl).unwrap();
        let back: GroupedList = serde_json::from_str(&j).unwrap();
        assert_eq!(gl, back);
    }
}
