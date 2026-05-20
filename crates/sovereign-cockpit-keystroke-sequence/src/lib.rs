//! `sovereign-cockpit-keystroke-sequence` — multi-key sequence matcher.
//!
//! `register(action_id, sequence)` records an action that fires on a
//! key sequence. `observe(key, now_ms)` returns:
//!
//!   * `Matched { action_id }` — a registered sequence completed.
//!   * `Partial` — input so far is a prefix of ≥ 1 registered
//!     sequence.
//!   * `None` — no match, no prefix.
//!
//! Buffer resets when `now_ms - last_ms > sequence_timeout_ms`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeystrokeSequence {
    /// Schema version.
    pub schema_version: String,
    /// action_id → key sequence.
    pub sequences: BTreeMap<String, Vec<String>>,
    /// Inter-keystroke timeout ms.
    pub sequence_timeout_ms: u64,
    /// Current buffer.
    pub buffer: Vec<String>,
    /// Last key ts.
    pub last_ms: Option<u64>,
}

/// Verdict.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum SequenceVerdict {
    /// Full sequence matched.
    Matched {
        /// Which action_id.
        action_id: String,
    },
    /// Buffer is a prefix of ≥ 1 sequence.
    Partial,
    /// No match.
    None,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SeqError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty action id.
    #[error("action id empty")]
    EmptyId,
    /// Empty sequence.
    #[error("sequence empty")]
    EmptySeq,
    /// Empty key in sequence.
    #[error("key empty in sequence")]
    EmptyKey,
}

impl KeystrokeSequence {
    /// New.
    pub fn new(sequence_timeout_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            sequences: BTreeMap::new(),
            sequence_timeout_ms,
            buffer: Vec::new(),
            last_ms: None,
        }
    }

    /// Register.
    pub fn register(&mut self, action_id: &str, sequence: &[&str]) -> Result<(), SeqError> {
        if action_id.is_empty() { return Err(SeqError::EmptyId); }
        if sequence.is_empty() { return Err(SeqError::EmptySeq); }
        for k in sequence {
            if k.is_empty() { return Err(SeqError::EmptyKey); }
        }
        self.sequences.insert(action_id.into(), sequence.iter().map(|s| (*s).to_string()).collect());
        Ok(())
    }

    /// Observe.
    pub fn observe(&mut self, key: &str, now_ms: u64) -> SequenceVerdict {
        if key.is_empty() { return SequenceVerdict::None; }
        // Timeout the buffer.
        if let Some(last) = self.last_ms {
            if now_ms.saturating_sub(last) > self.sequence_timeout_ms {
                self.buffer.clear();
            }
        }
        self.last_ms = Some(now_ms);
        self.buffer.push(key.into());

        // Exact match?
        if let Some((action_id, _)) = self.sequences.iter().find(|(_, seq)| seq.as_slice() == self.buffer.as_slice()) {
            let id = action_id.clone();
            self.buffer.clear();
            return SequenceVerdict::Matched { action_id: id };
        }
        // Any prefix?
        let any_prefix = self.sequences.values()
            .any(|seq| seq.len() > self.buffer.len() && seq[..self.buffer.len()] == self.buffer[..]);
        if any_prefix {
            SequenceVerdict::Partial
        } else {
            self.buffer.clear();
            SequenceVerdict::None
        }
    }

    /// Cancel pending.
    pub fn cancel(&mut self) {
        self.buffer.clear();
        self.last_ms = None;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SeqError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SeqError::SchemaMismatch); }
        for (id, seq) in &self.sequences {
            if id.is_empty() { return Err(SeqError::EmptyId); }
            if seq.is_empty() { return Err(SeqError::EmptySeq); }
            for k in seq {
                if k.is_empty() { return Err(SeqError::EmptyKey); }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn full_match() {
        let mut s = KeystrokeSequence::new(1000);
        s.register("first-line", &["g", "g"]).unwrap();
        assert_eq!(s.observe("g", 0), SequenceVerdict::Partial);
        let v = s.observe("g", 100);
        assert_eq!(v, SequenceVerdict::Matched { action_id: "first-line".into() });
    }

    #[test]
    fn partial_then_unrelated_reset() {
        let mut s = KeystrokeSequence::new(1000);
        s.register("first-line", &["g", "g"]).unwrap();
        s.observe("g", 0);
        let v = s.observe("z", 100);
        assert_eq!(v, SequenceVerdict::None);
    }

    #[test]
    fn timeout_resets_buffer() {
        let mut s = KeystrokeSequence::new(500);
        s.register("first-line", &["g", "g"]).unwrap();
        s.observe("g", 0);
        // 2s later — past 500ms timeout — buffer resets, so 'g' alone is a fresh partial.
        let v = s.observe("g", 2000);
        assert_eq!(v, SequenceVerdict::Partial);
    }

    #[test]
    fn multiple_sequences_with_shared_prefix() {
        let mut s = KeystrokeSequence::new(1000);
        s.register("first-line", &["g", "g"]).unwrap();
        s.register("goto-end", &["g", "G"]).unwrap();
        assert_eq!(s.observe("g", 0), SequenceVerdict::Partial);
        assert_eq!(s.observe("G", 100), SequenceVerdict::Matched { action_id: "goto-end".into() });
    }

    #[test]
    fn cancel_clears_buffer() {
        let mut s = KeystrokeSequence::new(1000);
        s.register("first-line", &["g", "g"]).unwrap();
        s.observe("g", 0);
        s.cancel();
        assert!(s.buffer.is_empty());
    }

    #[test]
    fn empty_action_or_seq_rejected() {
        let mut s = KeystrokeSequence::new(1000);
        assert!(matches!(s.register("", &["a"]).unwrap_err(), SeqError::EmptyId));
        assert!(matches!(s.register("act", &[]).unwrap_err(), SeqError::EmptySeq));
        assert!(matches!(s.register("act", &[""]).unwrap_err(), SeqError::EmptyKey));
    }

    #[test]
    fn empty_key_observe_is_none() {
        let mut s = KeystrokeSequence::new(1000);
        assert_eq!(s.observe("", 0), SequenceVerdict::None);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = KeystrokeSequence::new(1000);
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SeqError::SchemaMismatch));
    }

    #[test]
    fn seq_serde_roundtrip() {
        let mut s = KeystrokeSequence::new(1000);
        s.register("first-line", &["g", "g"]).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: KeystrokeSequence = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
