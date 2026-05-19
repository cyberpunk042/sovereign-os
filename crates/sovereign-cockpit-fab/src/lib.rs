//! `sovereign-cockpit-fab` — floating-action-button state.
//!
//! Primary action + optional speed-dial of secondary actions.
//! 4 corner positions, auto-hide on scroll-down, expanded toggle.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Corner position.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Corner {
    /// Top-left.
    TopLeft,
    /// Top-right.
    TopRight,
    /// Bottom-left.
    BottomLeft,
    /// Bottom-right.
    BottomRight,
}

/// One action.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FabAction {
    /// Stable id.
    pub id: String,
    /// Display label (tooltip).
    pub label: String,
    /// Icon hint.
    pub icon: String,
    /// Danger styling?
    pub danger: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Fab {
    /// Schema version.
    pub schema_version: String,
    /// Primary action.
    pub primary: FabAction,
    /// Speed-dial secondary actions.
    pub secondaries: Vec<FabAction>,
    /// Corner.
    pub corner: Corner,
    /// Speed-dial expanded?
    pub expanded: bool,
    /// Visible (false when auto-hidden by scroll-down)?
    pub visible: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FabError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty action id.
    #[error("action id empty")]
    EmptyId,
    /// Empty action label.
    #[error("action {0} label empty")]
    EmptyLabel(String),
    /// Empty action icon.
    #[error("action {0} icon empty")]
    EmptyIcon(String),
    /// Duplicate action id across primary + secondaries.
    #[error("duplicate action id: {0}")]
    DuplicateId(String),
}

impl Fab {
    /// New (visible, not expanded).
    pub fn new(primary: FabAction, corner: Corner) -> Result<Self, FabError> {
        check_action(&primary)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            primary,
            secondaries: Vec::new(),
            corner,
            expanded: false,
            visible: true,
        })
    }

    /// Add a secondary action.
    pub fn add_secondary(&mut self, a: FabAction) -> Result<(), FabError> {
        check_action(&a)?;
        if self.primary.id == a.id || self.secondaries.iter().any(|x| x.id == a.id) {
            return Err(FabError::DuplicateId(a.id));
        }
        self.secondaries.push(a);
        Ok(())
    }

    /// Toggle expanded.
    pub fn toggle_expanded(&mut self) {
        self.expanded = !self.expanded;
    }

    /// Mark hidden by scroll.
    pub fn scroll_down(&mut self) {
        self.visible = false;
        // Collapse when hidden.
        self.expanded = false;
    }

    /// Mark visible by scroll-up.
    pub fn scroll_up(&mut self) {
        self.visible = true;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FabError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FabError::SchemaMismatch);
        }
        check_action(&self.primary)?;
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        seen.insert(self.primary.id.as_str());
        for a in &self.secondaries {
            check_action(a)?;
            if !seen.insert(a.id.as_str()) {
                return Err(FabError::DuplicateId(a.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_action(a: &FabAction) -> Result<(), FabError> {
    if a.id.is_empty() { return Err(FabError::EmptyId); }
    if a.label.is_empty() { return Err(FabError::EmptyLabel(a.id.clone())); }
    if a.icon.is_empty() { return Err(FabError::EmptyIcon(a.id.clone())); }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn act(id: &str, danger: bool) -> FabAction {
        FabAction {
            id: id.into(),
            label: format!("L-{id}"),
            icon: format!("icon-{id}"),
            danger,
        }
    }

    #[test]
    fn new_primary() {
        let f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        assert!(f.visible);
        assert!(!f.expanded);
    }

    #[test]
    fn add_secondary() {
        let mut f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        f.add_secondary(act("import", false)).unwrap();
        assert_eq!(f.secondaries.len(), 1);
    }

    #[test]
    fn duplicate_id_rejected_in_secondaries() {
        let mut f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        f.add_secondary(act("a", false)).unwrap();
        assert!(matches!(f.add_secondary(act("a", false)).unwrap_err(), FabError::DuplicateId(_)));
    }

    #[test]
    fn duplicate_with_primary_rejected() {
        let mut f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        assert!(matches!(f.add_secondary(act("create", false)).unwrap_err(), FabError::DuplicateId(_)));
    }

    #[test]
    fn toggle_expanded() {
        let mut f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        f.toggle_expanded();
        assert!(f.expanded);
        f.toggle_expanded();
        assert!(!f.expanded);
    }

    #[test]
    fn scroll_down_hides_and_collapses() {
        let mut f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        f.toggle_expanded();
        f.scroll_down();
        assert!(!f.visible);
        assert!(!f.expanded);
    }

    #[test]
    fn scroll_up_restores_visibility() {
        let mut f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        f.scroll_down();
        f.scroll_up();
        assert!(f.visible);
    }

    #[test]
    fn empty_id_rejected() {
        let mut a = act("a", false);
        a.id = String::new();
        assert!(matches!(Fab::new(a, Corner::TopLeft).unwrap_err(), FabError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut a = act("a", false);
        a.label = String::new();
        assert!(matches!(Fab::new(a, Corner::TopLeft).unwrap_err(), FabError::EmptyLabel(_)));
    }

    #[test]
    fn empty_icon_rejected() {
        let mut a = act("a", false);
        a.icon = String::new();
        assert!(matches!(Fab::new(a, Corner::TopLeft).unwrap_err(), FabError::EmptyIcon(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FabError::SchemaMismatch));
    }

    #[test]
    fn corner_serde_kebab() {
        assert_eq!(serde_json::to_string(&Corner::BottomRight).unwrap(), "\"bottom-right\"");
    }

    #[test]
    fn fab_serde_roundtrip() {
        let mut f = Fab::new(act("create", false), Corner::BottomRight).unwrap();
        f.add_secondary(act("import", false)).unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: Fab = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
