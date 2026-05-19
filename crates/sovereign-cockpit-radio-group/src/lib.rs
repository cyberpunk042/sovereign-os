//! `sovereign-cockpit-radio-group` — radio-group widget state.
//!
//! Mutually-exclusive selection from an ordered options list. Arrow
//! keys move through enabled options and wrap. `required = true`
//! makes an empty selection invalid for form-submit checks. Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Arrow direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Arrow {
    /// Next (Down/Right).
    Next,
    /// Previous (Up/Left).
    Prev,
}

/// One radio option.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RadioOption {
    /// Stable id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Enabled?
    pub enabled: bool,
}

/// Radio-group state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RadioGroup {
    /// Schema version.
    pub schema_version: String,
    /// Options.
    pub options: Vec<RadioOption>,
    /// Selected id (None = no selection).
    pub selected: Option<String>,
    /// Required for valid?
    pub required: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RadioError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("option id empty")]
    EmptyId,
    /// Empty label.
    #[error("option {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate option id: {0}")]
    DuplicateId(String),
    /// Unknown id.
    #[error("unknown option id: {0}")]
    Unknown(String),
    /// Selected option disabled.
    #[error("selected option {0} is disabled")]
    SelectedDisabled(String),
}

impl RadioGroup {
    /// New group.
    pub fn new(options: Vec<RadioOption>, required: bool) -> Result<Self, RadioError> {
        check_options(&options)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            options,
            selected: None,
            required,
        })
    }

    /// Select an option (must be enabled).
    pub fn select(&mut self, id: &str) -> Result<(), RadioError> {
        let opt = self.options.iter().find(|o| o.id == id)
            .ok_or_else(|| RadioError::Unknown(id.into()))?;
        if !opt.enabled {
            return Err(RadioError::SelectedDisabled(id.into()));
        }
        self.selected = Some(id.into());
        Ok(())
    }

    /// Clear selection.
    pub fn clear(&mut self) {
        self.selected = None;
    }

    /// Arrow-key navigation through enabled options (wraps).
    pub fn arrow(&mut self, dir: Arrow) -> Option<&str> {
        let enabled_indices: Vec<usize> = self.options.iter()
            .enumerate()
            .filter_map(|(i, o)| if o.enabled { Some(i) } else { None })
            .collect();
        if enabled_indices.is_empty() {
            return None;
        }
        let pos_in_enabled = self.selected.as_ref().and_then(|sel|
            enabled_indices.iter().position(|&i| &self.options[i].id == sel)
        );
        let next = match (pos_in_enabled, dir) {
            (None, Arrow::Next) => enabled_indices[0],
            (None, Arrow::Prev) => *enabled_indices.last().unwrap(),
            (Some(p), Arrow::Next) => enabled_indices[(p + 1) % enabled_indices.len()],
            (Some(p), Arrow::Prev) => enabled_indices[(p + enabled_indices.len() - 1) % enabled_indices.len()],
        };
        self.selected = Some(self.options[next].id.clone());
        self.selected.as_deref()
    }

    /// Form-valid check.
    pub fn is_valid(&self) -> bool {
        if self.required && self.selected.is_none() {
            return false;
        }
        true
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RadioError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RadioError::SchemaMismatch);
        }
        check_options(&self.options)?;
        if let Some(s) = &self.selected {
            let opt = self.options.iter().find(|o| &o.id == s)
                .ok_or_else(|| RadioError::Unknown(s.clone()))?;
            if !opt.enabled {
                return Err(RadioError::SelectedDisabled(s.clone()));
            }
        }
        Ok(())
    }
}

fn check_options(opts: &[RadioOption]) -> Result<(), RadioError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for o in opts {
        if o.id.is_empty() { return Err(RadioError::EmptyId); }
        if o.label.is_empty() { return Err(RadioError::EmptyLabel(o.id.clone())); }
        if !seen.insert(o.id.as_str()) {
            return Err(RadioError::DuplicateId(o.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn opt(id: &str, enabled: bool) -> RadioOption {
        RadioOption { id: id.into(), label: format!("L-{id}"), enabled }
    }

    #[test]
    fn select_works() {
        let mut g = RadioGroup::new(vec![opt("a", true), opt("b", true)], false).unwrap();
        g.select("a").unwrap();
        assert_eq!(g.selected.as_deref(), Some("a"));
    }

    #[test]
    fn select_disabled_rejected() {
        let mut g = RadioGroup::new(vec![opt("a", false), opt("b", true)], false).unwrap();
        assert!(matches!(g.select("a").unwrap_err(), RadioError::SelectedDisabled(_)));
    }

    #[test]
    fn select_unknown_rejected() {
        let mut g = RadioGroup::new(vec![opt("a", true)], false).unwrap();
        assert!(matches!(g.select("z").unwrap_err(), RadioError::Unknown(_)));
    }

    #[test]
    fn arrow_next_from_none_selects_first() {
        let mut g = RadioGroup::new(vec![opt("a", true), opt("b", true)], false).unwrap();
        assert_eq!(g.arrow(Arrow::Next), Some("a"));
    }

    #[test]
    fn arrow_prev_from_none_selects_last() {
        let mut g = RadioGroup::new(vec![opt("a", true), opt("b", true)], false).unwrap();
        assert_eq!(g.arrow(Arrow::Prev), Some("b"));
    }

    #[test]
    fn arrow_wraps() {
        let mut g = RadioGroup::new(vec![opt("a", true), opt("b", true), opt("c", true)], false).unwrap();
        g.select("c").unwrap();
        assert_eq!(g.arrow(Arrow::Next), Some("a"));
    }

    #[test]
    fn arrow_skips_disabled() {
        let mut g = RadioGroup::new(vec![opt("a", true), opt("b", false), opt("c", true)], false).unwrap();
        g.select("a").unwrap();
        assert_eq!(g.arrow(Arrow::Next), Some("c"));
    }

    #[test]
    fn arrow_all_disabled_returns_none() {
        let mut g = RadioGroup::new(vec![opt("a", false), opt("b", false)], false).unwrap();
        assert_eq!(g.arrow(Arrow::Next), None);
    }

    #[test]
    fn required_invalid_when_unselected() {
        let g = RadioGroup::new(vec![opt("a", true)], true).unwrap();
        assert!(!g.is_valid());
    }

    #[test]
    fn required_valid_when_selected() {
        let mut g = RadioGroup::new(vec![opt("a", true)], true).unwrap();
        g.select("a").unwrap();
        assert!(g.is_valid());
    }

    #[test]
    fn not_required_always_valid() {
        let g = RadioGroup::new(vec![opt("a", true)], false).unwrap();
        assert!(g.is_valid());
    }

    #[test]
    fn duplicate_rejected() {
        assert!(matches!(
            RadioGroup::new(vec![opt("a", true), opt("a", true)], false).unwrap_err(),
            RadioError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut o = opt("a", true);
        o.id = String::new();
        assert!(matches!(RadioGroup::new(vec![o], false).unwrap_err(), RadioError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut o = opt("a", true);
        o.label = String::new();
        assert!(matches!(RadioGroup::new(vec![o], false).unwrap_err(), RadioError::EmptyLabel(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = RadioGroup::new(vec![opt("a", true)], false).unwrap();
        g.schema_version = "9.9.9".into();
        assert!(matches!(g.validate().unwrap_err(), RadioError::SchemaMismatch));
    }

    #[test]
    fn group_serde_roundtrip() {
        let mut g = RadioGroup::new(vec![opt("a", true), opt("b", true)], true).unwrap();
        g.select("b").unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: RadioGroup = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
