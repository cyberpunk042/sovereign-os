//! `sovereign-cockpit-keymap-editor` — operator keybind editor.
//!
//! action_id → chord BTreeMap. start_capture(action_id) puts editor
//! in capture mode; finalize_capture(chord) detects conflicts before
//! committing.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Phase {
    /// Idle (no active capture).
    Idle,
    /// Capturing the chord for an action.
    Capturing,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeymapEditor {
    /// Schema version.
    pub schema_version: String,
    /// action_id → chord.
    pub bindings: BTreeMap<String, String>,
    /// Active phase.
    pub phase: Phase,
    /// Active action being captured.
    pub capture_action: String,
}

/// Outcome of finalize_capture.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum CaptureOutcome {
    /// Committed.
    Committed {
        /// action.
        action_id: String,
        /// chord.
        chord: String,
    },
    /// Conflict with existing binding.
    Conflict {
        /// chord.
        chord: String,
        /// existing action.
        existing_action: String,
    },
    /// Capture not active.
    NotCapturing,
}

/// Errors.
#[derive(Debug, Error)]
pub enum EditorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty action id.
    #[error("action_id empty")]
    EmptyActionId,
    /// Empty chord.
    #[error("chord empty")]
    EmptyChord,
}

impl KeymapEditor {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            bindings: BTreeMap::new(),
            phase: Phase::Idle,
            capture_action: String::new(),
        }
    }

    /// Begin capture.
    pub fn start_capture(&mut self, action_id: &str) -> Result<(), EditorError> {
        if action_id.is_empty() {
            return Err(EditorError::EmptyActionId);
        }
        self.phase = Phase::Capturing;
        self.capture_action = action_id.into();
        Ok(())
    }

    /// Cancel capture.
    pub fn cancel_capture(&mut self) {
        self.phase = Phase::Idle;
        self.capture_action.clear();
    }

    /// Finalize capture.
    pub fn finalize_capture(&mut self, chord: &str) -> Result<CaptureOutcome, EditorError> {
        if chord.is_empty() {
            return Err(EditorError::EmptyChord);
        }
        if self.phase != Phase::Capturing {
            return Ok(CaptureOutcome::NotCapturing);
        }
        // Conflict check: any other action already bound to this chord?
        for (other_action, other_chord) in &self.bindings {
            if other_chord == chord && other_action != &self.capture_action {
                return Ok(CaptureOutcome::Conflict {
                    chord: chord.into(),
                    existing_action: other_action.clone(),
                });
            }
        }
        let action_id = std::mem::take(&mut self.capture_action);
        self.bindings.insert(action_id.clone(), chord.into());
        self.phase = Phase::Idle;
        Ok(CaptureOutcome::Committed {
            action_id,
            chord: chord.into(),
        })
    }

    /// Unbind.
    pub fn unbind(&mut self, action_id: &str) -> bool {
        self.bindings.remove(action_id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), EditorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(EditorError::SchemaMismatch);
        }
        for (action_id, chord) in &self.bindings {
            if action_id.is_empty() {
                return Err(EditorError::EmptyActionId);
            }
            if chord.is_empty() {
                return Err(EditorError::EmptyChord);
            }
        }
        Ok(())
    }
}

impl Default for KeymapEditor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_capture() {
        let mut e = KeymapEditor::new();
        e.start_capture("save").unwrap();
        assert_eq!(e.phase, Phase::Capturing);
    }

    #[test]
    fn empty_action_rejected() {
        let mut e = KeymapEditor::new();
        assert!(matches!(
            e.start_capture("").unwrap_err(),
            EditorError::EmptyActionId
        ));
    }

    #[test]
    fn cancel_resets() {
        let mut e = KeymapEditor::new();
        e.start_capture("save").unwrap();
        e.cancel_capture();
        assert_eq!(e.phase, Phase::Idle);
    }

    #[test]
    fn finalize_commits() {
        let mut e = KeymapEditor::new();
        e.start_capture("save").unwrap();
        let outcome = e.finalize_capture("ctrl+s").unwrap();
        match outcome {
            CaptureOutcome::Committed { action_id, chord } => {
                assert_eq!(action_id, "save");
                assert_eq!(chord, "ctrl+s");
            }
            _ => panic!(),
        }
        assert_eq!(e.bindings.get("save").unwrap(), "ctrl+s");
    }

    #[test]
    fn finalize_conflict_detected() {
        let mut e = KeymapEditor::new();
        e.start_capture("save").unwrap();
        e.finalize_capture("ctrl+s").unwrap();
        e.start_capture("snapshot").unwrap();
        let outcome = e.finalize_capture("ctrl+s").unwrap();
        match outcome {
            CaptureOutcome::Conflict {
                existing_action, ..
            } => {
                assert_eq!(existing_action, "save");
            }
            _ => panic!(),
        }
    }

    #[test]
    fn rebinding_same_action_ok() {
        let mut e = KeymapEditor::new();
        e.start_capture("save").unwrap();
        e.finalize_capture("ctrl+s").unwrap();
        e.start_capture("save").unwrap();
        let outcome = e.finalize_capture("ctrl+s").unwrap();
        assert!(matches!(outcome, CaptureOutcome::Committed { .. }));
    }

    #[test]
    fn finalize_without_capture_returns_not_capturing() {
        let mut e = KeymapEditor::new();
        let outcome = e.finalize_capture("ctrl+s").unwrap();
        assert!(matches!(outcome, CaptureOutcome::NotCapturing));
    }

    #[test]
    fn empty_chord_rejected() {
        let mut e = KeymapEditor::new();
        e.start_capture("save").unwrap();
        assert!(matches!(
            e.finalize_capture("").unwrap_err(),
            EditorError::EmptyChord
        ));
    }

    #[test]
    fn unbind_removes() {
        let mut e = KeymapEditor::new();
        e.start_capture("save").unwrap();
        e.finalize_capture("ctrl+s").unwrap();
        assert!(e.unbind("save"));
        assert!(!e.unbind("save"));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut e = KeymapEditor::new();
        e.schema_version = "9.9.9".into();
        assert!(matches!(
            e.validate().unwrap_err(),
            EditorError::SchemaMismatch
        ));
    }

    #[test]
    fn editor_serde_roundtrip() {
        let mut e = KeymapEditor::new();
        e.start_capture("save").unwrap();
        e.finalize_capture("ctrl+s").unwrap();
        let j = serde_json::to_string(&e).unwrap();
        let back: KeymapEditor = serde_json::from_str(&j).unwrap();
        assert_eq!(e, back);
    }
}
