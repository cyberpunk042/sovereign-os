//! `sovereign-cockpit-tri-state-checkbox` — tri-state state.
//!
//! State{Unchecked/Checked/Indeterminate}. cycle on click:
//! Unchecked→Checked→Unchecked (Indeterminate→Checked).
//! rollup(children) computes parent: all Checked → Checked;
//! all Unchecked → Unchecked; otherwise Indeterminate.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// Unchecked.
    Unchecked,
    /// Checked.
    Checked,
    /// Indeterminate.
    Indeterminate,
}

/// Versioned state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TriStateCheckbox {
    /// Schema version.
    pub schema_version: String,
    /// State.
    pub state: State,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CheckboxError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// Roll up children into parent state.
pub fn rollup(children: &[State]) -> State {
    if children.is_empty() {
        return State::Unchecked;
    }
    let all_checked = children.iter().all(|s| *s == State::Checked);
    let all_unchecked = children.iter().all(|s| *s == State::Unchecked);
    if all_checked {
        State::Checked
    } else if all_unchecked {
        State::Unchecked
    } else {
        State::Indeterminate
    }
}

impl TriStateCheckbox {
    /// New (Unchecked).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            state: State::Unchecked,
        }
    }

    /// Set.
    pub fn set(&mut self, s: State) {
        self.state = s;
    }

    /// Toggle via click semantics:
    /// Unchecked → Checked; Checked → Unchecked; Indeterminate → Checked.
    pub fn click(&mut self) -> State {
        self.state = match self.state {
            State::Unchecked => State::Checked,
            State::Checked => State::Unchecked,
            State::Indeterminate => State::Checked,
        };
        self.state
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CheckboxError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CheckboxError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for TriStateCheckbox {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn click_unchecked_to_checked() {
        let mut c = TriStateCheckbox::new();
        assert_eq!(c.click(), State::Checked);
    }

    #[test]
    fn click_checked_to_unchecked() {
        let mut c = TriStateCheckbox::new();
        c.set(State::Checked);
        assert_eq!(c.click(), State::Unchecked);
    }

    #[test]
    fn click_indeterminate_to_checked() {
        let mut c = TriStateCheckbox::new();
        c.set(State::Indeterminate);
        assert_eq!(c.click(), State::Checked);
    }

    #[test]
    fn rollup_all_checked() {
        let s = rollup(&[State::Checked, State::Checked, State::Checked]);
        assert_eq!(s, State::Checked);
    }

    #[test]
    fn rollup_all_unchecked() {
        let s = rollup(&[State::Unchecked, State::Unchecked]);
        assert_eq!(s, State::Unchecked);
    }

    #[test]
    fn rollup_mixed_is_indeterminate() {
        let s = rollup(&[State::Checked, State::Unchecked]);
        assert_eq!(s, State::Indeterminate);
    }

    #[test]
    fn rollup_with_indeterminate_child_is_indeterminate() {
        let s = rollup(&[State::Checked, State::Indeterminate]);
        assert_eq!(s, State::Indeterminate);
    }

    #[test]
    fn rollup_empty_is_unchecked() {
        let s = rollup(&[]);
        assert_eq!(s, State::Unchecked);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = TriStateCheckbox::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            CheckboxError::SchemaMismatch
        ));
    }

    #[test]
    fn checkbox_serde_roundtrip() {
        let mut c = TriStateCheckbox::new();
        c.set(State::Indeterminate);
        let j = serde_json::to_string(&c).unwrap();
        let back: TriStateCheckbox = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
