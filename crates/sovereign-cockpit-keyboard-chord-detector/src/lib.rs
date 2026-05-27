//! `sovereign-cockpit-keyboard-chord-detector` — multi-key chords.
//!
//! Chords like `Ctrl+K S` are detected by registering a sequence of
//! key tokens. `press(key, ts_ms)` feeds keys into the detector;
//! if a prefix of any registered chord is matched, the detector
//! enters a buffered state. If `timeout_ms` elapses without
//! advancing, the buffer is cleared. On a full match, the chord's
//! action id is returned.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One chord binding.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Chord {
    /// Key sequence (each element is a normalized key spec).
    pub keys: Vec<String>,
    /// Action id to fire.
    pub action_id: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeyboardChordDetector {
    /// Schema version.
    pub schema_version: String,
    /// Registered chords.
    pub chords: Vec<Chord>,
    /// Buffer (keys pressed since last reset).
    pub buffer: Vec<String>,
    /// Last press ts.
    pub last_press_ms: u64,
    /// Timeout to clear buffer.
    pub timeout_ms: u64,
}

/// Press verdict.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum PressVerdict {
    /// No chord active.
    NoMatch,
    /// Buffered (partial match exists).
    Buffered {
        /// Snapshot of current buffer.
        buffer: Vec<String>,
    },
    /// Fired.
    Fired {
        /// action.
        action_id: String,
    },
}

/// Errors.
#[derive(Debug, Error)]
pub enum ChordError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("chord must have ≥1 key")]
    EmptyChord,
    /// Empty key.
    #[error("key empty")]
    EmptyKey,
    /// Empty action.
    #[error("action id empty")]
    EmptyAction,
    /// Duplicate chord.
    #[error("chord already registered: {0:?}")]
    DuplicateChord(Vec<String>),
}

impl KeyboardChordDetector {
    /// New.
    pub fn new(timeout_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            chords: Vec::new(),
            buffer: Vec::new(),
            last_press_ms: 0,
            timeout_ms,
        }
    }

    /// Register a chord.
    pub fn register(&mut self, keys: &[&str], action_id: &str) -> Result<(), ChordError> {
        if keys.is_empty() {
            return Err(ChordError::EmptyChord);
        }
        for k in keys {
            if k.is_empty() {
                return Err(ChordError::EmptyKey);
            }
        }
        if action_id.is_empty() {
            return Err(ChordError::EmptyAction);
        }
        let key_vec: Vec<String> = keys.iter().map(|k| (*k).into()).collect();
        if self.chords.iter().any(|c| c.keys == key_vec) {
            return Err(ChordError::DuplicateChord(key_vec));
        }
        self.chords.push(Chord {
            keys: key_vec,
            action_id: action_id.into(),
        });
        Ok(())
    }

    /// Press.
    pub fn press(&mut self, key: &str, ts_ms: u64) -> PressVerdict {
        // Timeout — clear buffer if too long.
        if !self.buffer.is_empty() && ts_ms.saturating_sub(self.last_press_ms) > self.timeout_ms {
            self.buffer.clear();
        }
        self.buffer.push(key.into());
        self.last_press_ms = ts_ms;
        // Full match?
        for c in &self.chords {
            if c.keys == self.buffer {
                let action_id = c.action_id.clone();
                self.buffer.clear();
                return PressVerdict::Fired { action_id };
            }
        }
        // Prefix of any chord?
        let any_prefix = self
            .chords
            .iter()
            .any(|c| c.keys.len() > self.buffer.len() && c.keys.starts_with(&self.buffer));
        if any_prefix {
            PressVerdict::Buffered {
                buffer: self.buffer.clone(),
            }
        } else {
            self.buffer.clear();
            PressVerdict::NoMatch
        }
    }

    /// Reset buffer manually (e.g. user pressed Escape).
    pub fn reset(&mut self) {
        self.buffer.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ChordError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ChordError::SchemaMismatch);
        }
        for c in &self.chords {
            if c.keys.is_empty() {
                return Err(ChordError::EmptyChord);
            }
            for k in &c.keys {
                if k.is_empty() {
                    return Err(ChordError::EmptyKey);
                }
            }
            if c.action_id.is_empty() {
                return Err(ChordError::EmptyAction);
            }
        }
        Ok(())
    }
}

impl Default for KeyboardChordDetector {
    fn default() -> Self {
        Self::new(1000)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_key_chord_fires_immediately() {
        let mut d = KeyboardChordDetector::new(1000);
        d.register(&["Escape"], "menu-close").unwrap();
        match d.press("Escape", 0) {
            PressVerdict::Fired { action_id } => assert_eq!(action_id, "menu-close"),
            _ => panic!(),
        }
    }

    #[test]
    fn two_key_chord_fires_on_second() {
        let mut d = KeyboardChordDetector::new(1000);
        d.register(&["Ctrl+K", "S"], "save-all").unwrap();
        match d.press("Ctrl+K", 0) {
            PressVerdict::Buffered { buffer } => assert_eq!(buffer, vec!["Ctrl+K"]),
            _ => panic!(),
        }
        match d.press("S", 100) {
            PressVerdict::Fired { action_id } => assert_eq!(action_id, "save-all"),
            _ => panic!(),
        }
    }

    #[test]
    fn timeout_clears_buffer() {
        let mut d = KeyboardChordDetector::new(500);
        d.register(&["Ctrl+K", "S"], "save").unwrap();
        d.press("Ctrl+K", 0);
        // S pressed 2000ms later (> timeout 500). Buffer cleared first.
        match d.press("S", 2000) {
            PressVerdict::NoMatch => {}
            other => panic!("expected NoMatch, got {other:?}"),
        }
    }

    #[test]
    fn unrelated_key_clears_buffer() {
        let mut d = KeyboardChordDetector::new(1000);
        d.register(&["Ctrl+K", "S"], "save").unwrap();
        d.press("Ctrl+K", 0);
        // X is not a prefix of anything → no match, buffer clears.
        assert_eq!(d.press("X", 100), PressVerdict::NoMatch);
        assert!(d.buffer.is_empty());
    }

    #[test]
    fn reset_manually() {
        let mut d = KeyboardChordDetector::new(1000);
        d.register(&["a", "b"], "x").unwrap();
        d.press("a", 0);
        d.reset();
        assert!(d.buffer.is_empty());
    }

    #[test]
    fn duplicate_chord_rejected() {
        let mut d = KeyboardChordDetector::new(1000);
        d.register(&["a"], "x").unwrap();
        assert!(matches!(
            d.register(&["a"], "y").unwrap_err(),
            ChordError::DuplicateChord(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut d = KeyboardChordDetector::new(1000);
        assert!(matches!(
            d.register(&[], "x").unwrap_err(),
            ChordError::EmptyChord
        ));
        assert!(matches!(
            d.register(&[""], "x").unwrap_err(),
            ChordError::EmptyKey
        ));
        assert!(matches!(
            d.register(&["a"], "").unwrap_err(),
            ChordError::EmptyAction
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = KeyboardChordDetector::new(1000);
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            ChordError::SchemaMismatch
        ));
    }

    #[test]
    fn chord_serde_roundtrip() {
        let mut d = KeyboardChordDetector::new(1000);
        d.register(&["Ctrl+K", "S"], "save").unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: KeyboardChordDetector = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
