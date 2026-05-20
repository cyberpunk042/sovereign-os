//! `sovereign-cockpit-consent-prompt` — consent prompt FSM.
//!
//! Each `prompt(id, scope, ts)` registers a pending consent. The
//! user may then `grant(id, ts)`, `deny(id, ts)`, or `defer(id, ts,
//! reminder_after_ms)`. A deferred prompt becomes due-again at
//! `ts + reminder_after_ms`.
//!
//! `state(id, now)` returns:
//!   * `Pending` — awaiting user action.
//!   * `Granted` / `Denied` — terminal.
//!   * `Deferred { reminder_at_ms }` — waiting until reminder time.
//!   * `Reminder` — deferred but reminder is now due.
//!   * `Unknown`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Stored state per prompt.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum PromptState {
    /// Pending.
    Pending,
    /// Granted (with ts).
    Granted {
        /// when.
        at_ms: u64,
    },
    /// Denied.
    Denied {
        /// when.
        at_ms: u64,
    },
    /// Deferred (with reminder time).
    Deferred {
        /// when reminder fires.
        reminder_at_ms: u64,
    },
}

/// Public verdict at `now_ms`.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Verdict {
    /// Pending action.
    Pending,
    /// Granted.
    Granted,
    /// Denied.
    Denied,
    /// Deferred, reminder later.
    Deferred {
        /// reminder.
        reminder_at_ms: u64,
    },
    /// Deferred but reminder is now due.
    Reminder,
    /// Unknown.
    Unknown,
}

/// One prompt record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Prompt {
    /// Scope label (e.g. "mic", "location", "agent-action-X").
    pub scope: String,
    /// Created ts.
    pub created_at_ms: u64,
    /// State.
    pub state: PromptState,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsentPrompt {
    /// Schema version.
    pub schema_version: String,
    /// id → prompt.
    pub prompts: BTreeMap<String, Prompt>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ConsentError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty scope.
    #[error("scope empty")]
    EmptyScope,
    /// Duplicate.
    #[error("duplicate prompt id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown prompt: {0}")]
    UnknownPrompt(String),
    /// Already terminal.
    #[error("prompt {0} is already in terminal state")]
    AlreadyTerminal(String),
}

impl ConsentPrompt {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            prompts: BTreeMap::new(),
        }
    }

    /// Register a pending prompt.
    pub fn prompt(&mut self, id: &str, scope: &str, ts_ms: u64) -> Result<(), ConsentError> {
        if id.is_empty() { return Err(ConsentError::EmptyId); }
        if scope.is_empty() { return Err(ConsentError::EmptyScope); }
        if self.prompts.contains_key(id) {
            return Err(ConsentError::DuplicateId(id.into()));
        }
        self.prompts.insert(id.into(), Prompt {
            scope: scope.into(),
            created_at_ms: ts_ms,
            state: PromptState::Pending,
        });
        Ok(())
    }

    /// Grant.
    pub fn grant(&mut self, id: &str, ts_ms: u64) -> Result<(), ConsentError> {
        let p = self.prompts.get_mut(id).ok_or_else(|| ConsentError::UnknownPrompt(id.into()))?;
        if matches!(p.state, PromptState::Granted { .. } | PromptState::Denied { .. }) {
            return Err(ConsentError::AlreadyTerminal(id.into()));
        }
        p.state = PromptState::Granted { at_ms: ts_ms };
        Ok(())
    }

    /// Deny.
    pub fn deny(&mut self, id: &str, ts_ms: u64) -> Result<(), ConsentError> {
        let p = self.prompts.get_mut(id).ok_or_else(|| ConsentError::UnknownPrompt(id.into()))?;
        if matches!(p.state, PromptState::Granted { .. } | PromptState::Denied { .. }) {
            return Err(ConsentError::AlreadyTerminal(id.into()));
        }
        p.state = PromptState::Denied { at_ms: ts_ms };
        Ok(())
    }

    /// Defer.
    pub fn defer(&mut self, id: &str, ts_ms: u64, reminder_after_ms: u64) -> Result<(), ConsentError> {
        let p = self.prompts.get_mut(id).ok_or_else(|| ConsentError::UnknownPrompt(id.into()))?;
        if matches!(p.state, PromptState::Granted { .. } | PromptState::Denied { .. }) {
            return Err(ConsentError::AlreadyTerminal(id.into()));
        }
        p.state = PromptState::Deferred { reminder_at_ms: ts_ms.saturating_add(reminder_after_ms) };
        Ok(())
    }

    /// State at now.
    pub fn state(&self, id: &str, now_ms: u64) -> Verdict {
        let Some(p) = self.prompts.get(id) else { return Verdict::Unknown; };
        match &p.state {
            PromptState::Pending => Verdict::Pending,
            PromptState::Granted { .. } => Verdict::Granted,
            PromptState::Denied { .. } => Verdict::Denied,
            PromptState::Deferred { reminder_at_ms } => {
                if now_ms >= *reminder_at_ms { Verdict::Reminder }
                else { Verdict::Deferred { reminder_at_ms: *reminder_at_ms } }
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ConsentError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ConsentError::SchemaMismatch); }
        for (id, p) in &self.prompts {
            if id.is_empty() { return Err(ConsentError::EmptyId); }
            if p.scope.is_empty() { return Err(ConsentError::EmptyScope); }
        }
        Ok(())
    }
}

impl Default for ConsentPrompt {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pending_initially() {
        let mut c = ConsentPrompt::new();
        c.prompt("p1", "mic", 0).unwrap();
        assert_eq!(c.state("p1", 1), Verdict::Pending);
    }

    #[test]
    fn grant_then_terminal() {
        let mut c = ConsentPrompt::new();
        c.prompt("p1", "mic", 0).unwrap();
        c.grant("p1", 100).unwrap();
        assert_eq!(c.state("p1", 200), Verdict::Granted);
        assert!(matches!(c.deny("p1", 300).unwrap_err(), ConsentError::AlreadyTerminal(_)));
    }

    #[test]
    fn deny_terminal() {
        let mut c = ConsentPrompt::new();
        c.prompt("p1", "mic", 0).unwrap();
        c.deny("p1", 100).unwrap();
        assert_eq!(c.state("p1", 200), Verdict::Denied);
        assert!(matches!(c.grant("p1", 300).unwrap_err(), ConsentError::AlreadyTerminal(_)));
    }

    #[test]
    fn defer_then_reminder() {
        let mut c = ConsentPrompt::new();
        c.prompt("p1", "mic", 0).unwrap();
        c.defer("p1", 100, 1000).unwrap();
        // Reminder at 1100.
        match c.state("p1", 500) {
            Verdict::Deferred { reminder_at_ms } => assert_eq!(reminder_at_ms, 1100),
            _ => panic!(),
        }
        assert_eq!(c.state("p1", 1200), Verdict::Reminder);
    }

    #[test]
    fn defer_then_grant() {
        let mut c = ConsentPrompt::new();
        c.prompt("p1", "mic", 0).unwrap();
        c.defer("p1", 100, 1000).unwrap();
        // User clicks Grant on the reminder.
        c.grant("p1", 1200).unwrap();
        assert_eq!(c.state("p1", 2000), Verdict::Granted);
    }

    #[test]
    fn duplicate_rejected() {
        let mut c = ConsentPrompt::new();
        c.prompt("p1", "mic", 0).unwrap();
        assert!(matches!(c.prompt("p1", "mic", 0).unwrap_err(), ConsentError::DuplicateId(_)));
    }

    #[test]
    fn unknown_rejected() {
        let mut c = ConsentPrompt::new();
        assert!(matches!(c.grant("nope", 0).unwrap_err(), ConsentError::UnknownPrompt(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut c = ConsentPrompt::new();
        assert!(matches!(c.prompt("", "mic", 0).unwrap_err(), ConsentError::EmptyId));
        assert!(matches!(c.prompt("p", "", 0).unwrap_err(), ConsentError::EmptyScope));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ConsentPrompt::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), ConsentError::SchemaMismatch));
    }

    #[test]
    fn consent_serde_roundtrip() {
        let mut c = ConsentPrompt::new();
        c.prompt("p1", "mic", 0).unwrap();
        c.defer("p1", 100, 1000).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: ConsentPrompt = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
