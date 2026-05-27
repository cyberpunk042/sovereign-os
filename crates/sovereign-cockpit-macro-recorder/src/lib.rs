//! `sovereign-cockpit-macro-recorder` — record + save action sequences.
//!
//! `start(name)` opens a recording session; `observe(action_id, now)`
//! appends an event with `delay_ms` since the previous event (0 for
//! the first); `cancel()` discards; `stop()` seals the recording
//! into a `SavedMacro { id, name, events }` keyed by an auto-incremented
//! id. `play_sequence(id)` returns the events for the playback engine.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One recorded event.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Event {
    /// Action id.
    pub action_id: String,
    /// ms since the previous event in this recording.
    pub delay_ms: u64,
}

/// In-flight recording.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Recording {
    /// Working name.
    pub name: String,
    /// Events so far.
    pub events: Vec<Event>,
    /// Last observed ts.
    pub last_ts_ms: Option<u64>,
}

/// Saved macro.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SavedMacro {
    /// Stable id.
    pub id: u64,
    /// Name.
    pub name: String,
    /// Events.
    pub events: Vec<Event>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MacroRecorder {
    /// Schema version.
    pub schema_version: String,
    /// Active recording.
    pub active: Option<Recording>,
    /// Saved macros.
    pub saved: BTreeMap<u64, SavedMacro>,
    /// Next id.
    pub next_id: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MacroError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty name.
    #[error("name empty")]
    EmptyName,
    /// Empty action id.
    #[error("action id empty")]
    EmptyActionId,
    /// No active recording.
    #[error("no active recording")]
    NotRecording,
    /// Already recording.
    #[error("already recording")]
    AlreadyRecording,
    /// Non-monotonic.
    #[error("non-monotonic ts: prev {prev} > new {new}")]
    NonMonotonic {
        /// prev.
        prev: u64,
        /// new.
        new: u64,
    },
    /// Unknown id.
    #[error("unknown macro id: {0}")]
    UnknownId(u64),
}

impl MacroRecorder {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            active: None,
            saved: BTreeMap::new(),
            next_id: 1,
        }
    }

    /// Start.
    pub fn start(&mut self, name: &str) -> Result<(), MacroError> {
        if name.is_empty() {
            return Err(MacroError::EmptyName);
        }
        if self.active.is_some() {
            return Err(MacroError::AlreadyRecording);
        }
        self.active = Some(Recording {
            name: name.into(),
            events: Vec::new(),
            last_ts_ms: None,
        });
        Ok(())
    }

    /// Observe.
    pub fn observe(&mut self, action_id: &str, now_ms: u64) -> Result<(), MacroError> {
        if action_id.is_empty() {
            return Err(MacroError::EmptyActionId);
        }
        let r = self.active.as_mut().ok_or(MacroError::NotRecording)?;
        let delay = if let Some(prev) = r.last_ts_ms {
            if now_ms < prev {
                return Err(MacroError::NonMonotonic { prev, new: now_ms });
            }
            now_ms - prev
        } else {
            0
        };
        r.events.push(Event {
            action_id: action_id.into(),
            delay_ms: delay,
        });
        r.last_ts_ms = Some(now_ms);
        Ok(())
    }

    /// Cancel.
    pub fn cancel(&mut self) -> Result<(), MacroError> {
        self.active.take().ok_or(MacroError::NotRecording)?;
        Ok(())
    }

    /// Stop + save.
    pub fn stop(&mut self) -> Result<u64, MacroError> {
        let r = self.active.take().ok_or(MacroError::NotRecording)?;
        let id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1);
        self.saved.insert(
            id,
            SavedMacro {
                id,
                name: r.name,
                events: r.events,
            },
        );
        Ok(id)
    }

    /// Get sequence.
    pub fn play_sequence(&self, id: u64) -> Result<&[Event], MacroError> {
        let m = self.saved.get(&id).ok_or(MacroError::UnknownId(id))?;
        Ok(&m.events)
    }

    /// Delete.
    pub fn delete(&mut self, id: u64) -> Result<(), MacroError> {
        self.saved.remove(&id).ok_or(MacroError::UnknownId(id))?;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MacroError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MacroError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for MacroRecorder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_and_save() {
        let mut r = MacroRecorder::new();
        r.start("save-then-export").unwrap();
        r.observe("save", 0).unwrap();
        r.observe("export", 500).unwrap();
        let id = r.stop().unwrap();
        let seq = r.play_sequence(id).unwrap();
        assert_eq!(seq.len(), 2);
        assert_eq!(seq[0].delay_ms, 0);
        assert_eq!(seq[1].delay_ms, 500);
    }

    #[test]
    fn cancel_discards() {
        let mut r = MacroRecorder::new();
        r.start("x").unwrap();
        r.observe("a", 100).unwrap();
        r.cancel().unwrap();
        assert!(r.active.is_none());
        assert!(r.saved.is_empty());
    }

    #[test]
    fn cannot_start_twice() {
        let mut r = MacroRecorder::new();
        r.start("x").unwrap();
        assert!(matches!(
            r.start("y").unwrap_err(),
            MacroError::AlreadyRecording
        ));
    }

    #[test]
    fn observe_without_start() {
        let mut r = MacroRecorder::new();
        assert!(matches!(
            r.observe("a", 0).unwrap_err(),
            MacroError::NotRecording
        ));
    }

    #[test]
    fn nonmonotonic_rejected() {
        let mut r = MacroRecorder::new();
        r.start("x").unwrap();
        r.observe("a", 200).unwrap();
        assert!(matches!(
            r.observe("b", 100).unwrap_err(),
            MacroError::NonMonotonic { .. }
        ));
    }

    #[test]
    fn empty_name_or_action_rejected() {
        let mut r = MacroRecorder::new();
        assert!(matches!(r.start("").unwrap_err(), MacroError::EmptyName));
        r.start("x").unwrap();
        assert!(matches!(
            r.observe("", 0).unwrap_err(),
            MacroError::EmptyActionId
        ));
    }

    #[test]
    fn delete_unknown_rejected() {
        let mut r = MacroRecorder::new();
        assert!(matches!(
            r.delete(999).unwrap_err(),
            MacroError::UnknownId(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = MacroRecorder::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            MacroError::SchemaMismatch
        ));
    }

    #[test]
    fn macro_serde_roundtrip() {
        let mut r = MacroRecorder::new();
        r.start("x").unwrap();
        r.observe("a", 0).unwrap();
        r.stop().unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: MacroRecorder = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
