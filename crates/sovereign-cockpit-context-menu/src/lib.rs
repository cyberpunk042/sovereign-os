//! `sovereign-cockpit-context-menu` — right-click menu definitions.
//!
//! Per-target-kind menu structure (items + separators + submenus).
//! Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Target kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TargetKind {
    /// Conversation turn.
    Turn,
    /// Dashboard widget.
    DashboardWidget,
    /// Replay step.
    ReplayStep,
    /// Pin card.
    PinCard,
    /// Notification.
    Notification,
    /// Tab.
    Tab,
}

/// One menu item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum MenuItem {
    /// Action item (label, command_id, enabled).
    Action {
        /// Label.
        label: String,
        /// Command id fired on click.
        command_id: String,
        /// Currently enabled.
        enabled: bool,
    },
    /// Separator.
    Separator,
    /// Submenu (label, items).
    Submenu {
        /// Label.
        label: String,
        /// Submenu items.
        items: Vec<MenuItem>,
    },
}

/// Menu for a target kind.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContextMenu {
    /// Target kind this menu serves.
    pub target: TargetKind,
    /// Items in order.
    pub items: Vec<MenuItem>,
}

/// Menu registry envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContextMenuRegistry {
    /// Schema version.
    pub schema_version: String,
    /// One menu per target kind.
    pub menus: Vec<ContextMenu>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ContextMenuError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty action label.
    #[error("action label empty")]
    EmptyLabel,
    /// Empty command_id.
    #[error("action {0} command_id empty")]
    EmptyCommandId(String),
    /// Empty submenu label.
    #[error("submenu label empty")]
    EmptySubmenuLabel,
    /// Empty submenu (no items).
    #[error("submenu {0} has no items")]
    EmptySubmenu(String),
    /// Duplicate target.
    #[error("duplicate target: {0:?}")]
    DuplicateTarget(TargetKind),
}

impl ContextMenuRegistry {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            menus: Vec::new(),
        }
    }

    /// Register a menu.
    pub fn register(&mut self, menu: ContextMenu) -> Result<(), ContextMenuError> {
        validate_items(&menu.items)?;
        if self.menus.iter().any(|m| m.target == menu.target) {
            return Err(ContextMenuError::DuplicateTarget(menu.target));
        }
        self.menus.push(menu);
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, target: TargetKind) -> Option<&ContextMenu> {
        self.menus.iter().find(|m| m.target == target)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ContextMenuError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ContextMenuError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<TargetKind> = HashSet::new();
        for m in &self.menus {
            if !seen.insert(m.target) {
                return Err(ContextMenuError::DuplicateTarget(m.target));
            }
            validate_items(&m.items)?;
        }
        Ok(())
    }
}

fn validate_items(items: &[MenuItem]) -> Result<(), ContextMenuError> {
    for it in items {
        match it {
            MenuItem::Action {
                label, command_id, ..
            } => {
                if label.is_empty() {
                    return Err(ContextMenuError::EmptyLabel);
                }
                if command_id.is_empty() {
                    return Err(ContextMenuError::EmptyCommandId(label.clone()));
                }
            }
            MenuItem::Separator => {}
            MenuItem::Submenu { label, items } => {
                if label.is_empty() {
                    return Err(ContextMenuError::EmptySubmenuLabel);
                }
                if items.is_empty() {
                    return Err(ContextMenuError::EmptySubmenu(label.clone()));
                }
                validate_items(items)?;
            }
        }
    }
    Ok(())
}

impl Default for ContextMenuRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn action(label: &str, cmd: &str) -> MenuItem {
        MenuItem::Action {
            label: label.into(),
            command_id: cmd.into(),
            enabled: true,
        }
    }

    #[test]
    fn empty_registry_validates() {
        ContextMenuRegistry::new().validate().unwrap();
    }

    #[test]
    fn register_simple_menu() {
        let mut r = ContextMenuRegistry::new();
        r.register(ContextMenu {
            target: TargetKind::Turn,
            items: vec![
                action("Copy", "turn.copy"),
                MenuItem::Separator,
                action("Bookmark", "turn.bookmark"),
            ],
        })
        .unwrap();
        assert!(r.get(TargetKind::Turn).is_some());
    }

    #[test]
    fn register_with_submenu() {
        let mut r = ContextMenuRegistry::new();
        r.register(ContextMenu {
            target: TargetKind::Tab,
            items: vec![MenuItem::Submenu {
                label: "Move to".into(),
                items: vec![
                    action("New window", "tab.move-new"),
                    action("Other window", "tab.move-other"),
                ],
            }],
        })
        .unwrap();
    }

    #[test]
    fn duplicate_target_rejected() {
        let mut r = ContextMenuRegistry::new();
        r.register(ContextMenu {
            target: TargetKind::Turn,
            items: vec![action("Copy", "x")],
        })
        .unwrap();
        let err = r
            .register(ContextMenu {
                target: TargetKind::Turn,
                items: vec![action("Paste", "y")],
            })
            .unwrap_err();
        assert!(matches!(
            err,
            ContextMenuError::DuplicateTarget(TargetKind::Turn)
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut r = ContextMenuRegistry::new();
        let err = r
            .register(ContextMenu {
                target: TargetKind::Turn,
                items: vec![action("", "x")],
            })
            .unwrap_err();
        assert!(matches!(err, ContextMenuError::EmptyLabel));
    }

    #[test]
    fn empty_command_rejected() {
        let mut r = ContextMenuRegistry::new();
        let err = r
            .register(ContextMenu {
                target: TargetKind::Turn,
                items: vec![action("x", "")],
            })
            .unwrap_err();
        assert!(matches!(err, ContextMenuError::EmptyCommandId(_)));
    }

    #[test]
    fn empty_submenu_rejected() {
        let mut r = ContextMenuRegistry::new();
        let err = r
            .register(ContextMenu {
                target: TargetKind::Tab,
                items: vec![MenuItem::Submenu {
                    label: "Move".into(),
                    items: vec![],
                }],
            })
            .unwrap_err();
        assert!(matches!(err, ContextMenuError::EmptySubmenu(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = ContextMenuRegistry::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            ContextMenuError::SchemaMismatch
        ));
    }

    #[test]
    fn registry_serde_roundtrip() {
        let mut r = ContextMenuRegistry::new();
        r.register(ContextMenu {
            target: TargetKind::Turn,
            items: vec![action("Copy", "turn.copy")],
        })
        .unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: ContextMenuRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
