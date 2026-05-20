//! `sovereign-cockpit-inline-rename` — click-to-edit rename.
//!
//! Per target id, state {Idle/Editing{draft, original}}. enter
//! begins editing; edit updates draft; commit replaces canonical
//! with draft; cancel discards draft.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Rename state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum State {
    /// Idle.
    Idle {
        /// canonical name.
        name: String,
    },
    /// Editing.
    Editing {
        /// canonical name before edit.
        original: String,
        /// draft.
        draft: String,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InlineRename {
    /// Schema version.
    pub schema_version: String,
    /// target id → state.
    pub targets: BTreeMap<String, State>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RenameError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("name empty")]
    EmptyName,
    /// Unknown.
    #[error("unknown target: {0}")]
    UnknownTarget(String),
    /// Invalid transition.
    #[error("invalid transition for {0}")]
    InvalidTransition(String),
}

impl InlineRename {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            targets: BTreeMap::new(),
        }
    }

    /// Register target with initial name.
    pub fn register(&mut self, id: &str, name: &str) -> Result<(), RenameError> {
        if id.is_empty() { return Err(RenameError::EmptyId); }
        if name.is_empty() { return Err(RenameError::EmptyName); }
        self.targets.insert(id.into(), State::Idle { name: name.into() });
        Ok(())
    }

    /// Enter editing.
    pub fn enter(&mut self, id: &str) -> Result<(), RenameError> {
        let s = self.targets.get_mut(id).ok_or_else(|| RenameError::UnknownTarget(id.into()))?;
        let name = match s {
            State::Idle { name } => name.clone(),
            _ => return Err(RenameError::InvalidTransition(id.into())),
        };
        *s = State::Editing { original: name.clone(), draft: name };
        Ok(())
    }

    /// Update draft.
    pub fn edit(&mut self, id: &str, draft: &str) -> Result<(), RenameError> {
        let s = self.targets.get_mut(id).ok_or_else(|| RenameError::UnknownTarget(id.into()))?;
        match s {
            State::Editing { draft: d, .. } => { *d = draft.into(); Ok(()) }
            _ => Err(RenameError::InvalidTransition(id.into())),
        }
    }

    /// Commit — accepts draft as new name (rejects empty).
    pub fn commit(&mut self, id: &str) -> Result<String, RenameError> {
        let s = self.targets.get_mut(id).ok_or_else(|| RenameError::UnknownTarget(id.into()))?;
        let new_name = match s {
            State::Editing { draft, .. } => {
                if draft.is_empty() { return Err(RenameError::EmptyName); }
                draft.clone()
            }
            _ => return Err(RenameError::InvalidTransition(id.into())),
        };
        *s = State::Idle { name: new_name.clone() };
        Ok(new_name)
    }

    /// Cancel (discard draft, revert to original).
    pub fn cancel(&mut self, id: &str) -> Result<(), RenameError> {
        let s = self.targets.get_mut(id).ok_or_else(|| RenameError::UnknownTarget(id.into()))?;
        let orig = match s {
            State::Editing { original, .. } => original.clone(),
            _ => return Err(RenameError::InvalidTransition(id.into())),
        };
        *s = State::Idle { name: orig };
        Ok(())
    }

    /// Canonical name.
    pub fn name_of(&self, id: &str) -> Option<String> {
        match self.targets.get(id) {
            Some(State::Idle { name }) => Some(name.clone()),
            Some(State::Editing { original, .. }) => Some(original.clone()),
            None => None,
        }
    }

    /// Is editing.
    pub fn is_editing(&self, id: &str) -> bool {
        matches!(self.targets.get(id), Some(State::Editing { .. }))
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RenameError> {
        if self.schema_version != SCHEMA_VERSION { return Err(RenameError::SchemaMismatch); }
        for (id, s) in &self.targets {
            if id.is_empty() { return Err(RenameError::EmptyId); }
            match s {
                State::Idle { name } => {
                    if name.is_empty() { return Err(RenameError::EmptyName); }
                }
                State::Editing { original, .. } => {
                    if original.is_empty() { return Err(RenameError::EmptyName); }
                }
            }
        }
        Ok(())
    }
}

impl Default for InlineRename {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_rename() {
        let mut r = InlineRename::new();
        r.register("t", "old").unwrap();
        r.enter("t").unwrap();
        r.edit("t", "new").unwrap();
        let n = r.commit("t").unwrap();
        assert_eq!(n, "new");
        assert_eq!(r.name_of("t").as_deref(), Some("new"));
    }

    #[test]
    fn cancel_reverts() {
        let mut r = InlineRename::new();
        r.register("t", "old").unwrap();
        r.enter("t").unwrap();
        r.edit("t", "new").unwrap();
        r.cancel("t").unwrap();
        assert_eq!(r.name_of("t").as_deref(), Some("old"));
    }

    #[test]
    fn commit_empty_rejected() {
        let mut r = InlineRename::new();
        r.register("t", "old").unwrap();
        r.enter("t").unwrap();
        r.edit("t", "").unwrap();
        assert!(matches!(r.commit("t").unwrap_err(), RenameError::EmptyName));
    }

    #[test]
    fn edit_from_idle_rejected() {
        let mut r = InlineRename::new();
        r.register("t", "old").unwrap();
        assert!(matches!(r.edit("t", "x").unwrap_err(), RenameError::InvalidTransition(_)));
    }

    #[test]
    fn enter_when_already_editing_rejected() {
        let mut r = InlineRename::new();
        r.register("t", "old").unwrap();
        r.enter("t").unwrap();
        assert!(matches!(r.enter("t").unwrap_err(), RenameError::InvalidTransition(_)));
    }

    #[test]
    fn unknown_target_rejected() {
        let mut r = InlineRename::new();
        assert!(matches!(r.enter("nope").unwrap_err(), RenameError::UnknownTarget(_)));
    }

    #[test]
    fn is_editing_tracks_state() {
        let mut r = InlineRename::new();
        r.register("t", "old").unwrap();
        assert!(!r.is_editing("t"));
        r.enter("t").unwrap();
        assert!(r.is_editing("t"));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut r = InlineRename::new();
        assert!(matches!(r.register("", "x").unwrap_err(), RenameError::EmptyId));
        assert!(matches!(r.register("t", "").unwrap_err(), RenameError::EmptyName));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = InlineRename::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), RenameError::SchemaMismatch));
    }

    #[test]
    fn rename_serde_roundtrip() {
        let mut r = InlineRename::new();
        r.register("t", "old").unwrap();
        r.enter("t").unwrap();
        r.edit("t", "new").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: InlineRename = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
