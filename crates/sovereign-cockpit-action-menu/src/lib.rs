//! `sovereign-cockpit-action-menu` — hierarchical action menu state.
//!
//! Tree of MenuNode: Item, SubMenu(children), or Separator. Each
//! Item carries action_id, label, enabled, visible. SubMenu carries
//! children. visible() returns the rendered tree pruned of invisible
//! nodes and collapsed empty submenus.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One menu node.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum MenuNode {
    /// Action item.
    Item {
        /// action id.
        action_id: String,
        /// label.
        label: String,
        /// enabled flag.
        enabled: bool,
        /// visible flag.
        visible: bool,
    },
    /// Sub-menu.
    SubMenu {
        /// label.
        label: String,
        /// visible flag.
        visible: bool,
        /// children.
        children: Vec<MenuNode>,
    },
    /// Visual separator.
    Separator,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionMenu {
    /// Schema version.
    pub schema_version: String,
    /// Root nodes.
    pub nodes: Vec<MenuNode>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MenuError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty action_id.
    #[error("item action_id empty")]
    EmptyActionId,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate action_id across tree.
    #[error("duplicate action_id: {0}")]
    DuplicateActionId(String),
}

impl ActionMenu {
    /// New.
    pub fn new(nodes: Vec<MenuNode>) -> Result<Self, MenuError> {
        check_nodes(&nodes)?;
        let mut seen = std::collections::HashSet::new();
        for n in &nodes {
            check_dup(n, &mut seen)?;
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            nodes,
        })
    }

    /// Compute the visible (renderable) tree: prune invisible items
    /// and submenus, drop empty submenus, collapse leading/trailing/
    /// duplicate separators.
    pub fn visible(&self) -> Vec<MenuNode> {
        let mut out: Vec<MenuNode> = self.nodes.iter().filter_map(filter_visible).collect();
        collapse_separators(&mut out);
        out
    }

    /// Total visible-leaf count (action items).
    pub fn count_visible_items(&self) -> usize {
        fn walk(nodes: &[MenuNode], acc: &mut usize) {
            for n in nodes {
                match n {
                    MenuNode::Item { visible: true, .. } => *acc += 1,
                    MenuNode::SubMenu {
                        visible: true,
                        children,
                        ..
                    } => walk(children, acc),
                    _ => {}
                }
            }
        }
        let mut c = 0;
        walk(&self.nodes, &mut c);
        c
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MenuError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MenuError::SchemaMismatch);
        }
        check_nodes(&self.nodes)?;
        let mut seen = std::collections::HashSet::new();
        for n in &self.nodes {
            check_dup(n, &mut seen)?;
        }
        Ok(())
    }
}

fn check_nodes(nodes: &[MenuNode]) -> Result<(), MenuError> {
    for n in nodes {
        match n {
            MenuNode::Item {
                action_id, label, ..
            } => {
                if action_id.is_empty() {
                    return Err(MenuError::EmptyActionId);
                }
                if label.is_empty() {
                    return Err(MenuError::EmptyLabel);
                }
            }
            MenuNode::SubMenu {
                label, children, ..
            } => {
                if label.is_empty() {
                    return Err(MenuError::EmptyLabel);
                }
                check_nodes(children)?;
            }
            MenuNode::Separator => {}
        }
    }
    Ok(())
}

fn check_dup(n: &MenuNode, seen: &mut std::collections::HashSet<String>) -> Result<(), MenuError> {
    match n {
        MenuNode::Item { action_id, .. } => {
            if !seen.insert(action_id.clone()) {
                return Err(MenuError::DuplicateActionId(action_id.clone()));
            }
        }
        MenuNode::SubMenu { children, .. } => {
            for c in children {
                check_dup(c, seen)?;
            }
        }
        _ => {}
    }
    Ok(())
}

fn filter_visible(n: &MenuNode) -> Option<MenuNode> {
    match n {
        MenuNode::Item {
            visible: true,
            action_id,
            label,
            enabled,
            ..
        } => Some(MenuNode::Item {
            action_id: action_id.clone(),
            label: label.clone(),
            enabled: *enabled,
            visible: true,
        }),
        MenuNode::Item { visible: false, .. } => None,
        MenuNode::SubMenu {
            visible: true,
            label,
            children,
            ..
        } => {
            let kids: Vec<MenuNode> = children.iter().filter_map(filter_visible).collect();
            if kids.is_empty() {
                None
            } else {
                let mut k = kids;
                collapse_separators(&mut k);
                Some(MenuNode::SubMenu {
                    label: label.clone(),
                    visible: true,
                    children: k,
                })
            }
        }
        MenuNode::SubMenu { visible: false, .. } => None,
        MenuNode::Separator => Some(MenuNode::Separator),
    }
}

fn collapse_separators(nodes: &mut Vec<MenuNode>) {
    while matches!(nodes.first(), Some(MenuNode::Separator)) {
        nodes.remove(0);
    }
    while matches!(nodes.last(), Some(MenuNode::Separator)) {
        nodes.pop();
    }
    let mut i = 1;
    while i < nodes.len() {
        if matches!(nodes[i], MenuNode::Separator) && matches!(nodes[i - 1], MenuNode::Separator) {
            nodes.remove(i);
        } else {
            i += 1;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(id: &str, visible: bool, enabled: bool) -> MenuNode {
        MenuNode::Item {
            action_id: id.into(),
            label: format!("L-{id}"),
            enabled,
            visible,
        }
    }

    fn sub(label: &str, visible: bool, children: Vec<MenuNode>) -> MenuNode {
        MenuNode::SubMenu {
            label: label.into(),
            visible,
            children,
        }
    }

    #[test]
    fn visible_filters_invisible_items() {
        let m = ActionMenu::new(vec![
            item("a", true, true),
            item("b", false, true),
            item("c", true, false),
        ])
        .unwrap();
        let v = m.visible();
        assert_eq!(v.len(), 2);
    }

    #[test]
    fn submenu_with_no_visible_children_pruned() {
        let m =
            ActionMenu::new(vec![sub("Edit", true, vec![item("hidden", false, true)])]).unwrap();
        assert!(m.visible().is_empty());
    }

    #[test]
    fn nested_submenu_walks() {
        let m = ActionMenu::new(vec![
            sub(
                "Edit",
                true,
                vec![item("copy", true, true), item("paste", true, true)],
            ),
            item("save", true, true),
        ])
        .unwrap();
        assert_eq!(m.count_visible_items(), 3);
    }

    #[test]
    fn separators_collapse() {
        let m = ActionMenu::new(vec![
            MenuNode::Separator,
            item("a", true, true),
            MenuNode::Separator,
            MenuNode::Separator,
            item("b", true, true),
            MenuNode::Separator,
        ])
        .unwrap();
        let v = m.visible();
        // Leading & trailing dropped, double separator collapsed.
        // Expect: a, sep, b
        assert_eq!(v.len(), 3);
        assert!(matches!(v[1], MenuNode::Separator));
    }

    #[test]
    fn duplicate_action_id_rejected() {
        let err = ActionMenu::new(vec![item("a", true, true), item("a", true, true)]).unwrap_err();
        assert!(matches!(err, MenuError::DuplicateActionId(_)));
    }

    #[test]
    fn duplicate_across_submenus_rejected() {
        let err = ActionMenu::new(vec![
            item("a", true, true),
            sub("X", true, vec![item("a", true, true)]),
        ])
        .unwrap_err();
        assert!(matches!(err, MenuError::DuplicateActionId(_)));
    }

    #[test]
    fn empty_action_id_rejected() {
        let err = ActionMenu::new(vec![item("", true, true)]).unwrap_err();
        assert!(matches!(err, MenuError::EmptyActionId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut x = item("a", true, true);
        if let MenuNode::Item { label, .. } = &mut x {
            *label = String::new();
        }
        assert!(matches!(
            ActionMenu::new(vec![x]).unwrap_err(),
            MenuError::EmptyLabel
        ));
    }

    #[test]
    fn submenu_empty_label_rejected() {
        let s = sub("", true, vec![]);
        assert!(matches!(
            ActionMenu::new(vec![s]).unwrap_err(),
            MenuError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = ActionMenu::new(vec![item("a", true, true)]).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            MenuError::SchemaMismatch
        ));
    }

    #[test]
    fn node_serde_kebab() {
        let n = MenuNode::Separator;
        let j = serde_json::to_string(&n).unwrap();
        assert!(j.contains("\"kind\":\"separator\""));
    }

    #[test]
    fn menu_serde_roundtrip() {
        let m = ActionMenu::new(vec![
            item("a", true, true),
            sub("Edit", true, vec![item("b", true, true)]),
        ])
        .unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: ActionMenu = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
