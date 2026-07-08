//! `sovereign-cockpit-permission-prompt` — permission UX state.
//!
//! State{Idle/Pending/Granted/Denied} per (subject, capability).
//! request(subject, cap, rationale) transitions to Pending and
//! records the rationale. resolve(subject, cap, decision,
//! remember) transitions to Granted/Denied; when remember=true,
//! the choice is sticky and later requests skip the prompt
//! (auto-resolved). reset clears a remembered choice.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Permission state.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// Idle (no decision).
    Idle,
    /// Pending (asked, awaiting response).
    Pending,
    /// Granted.
    Granted,
    /// Denied.
    Denied,
}

/// Decision.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Decision {
    /// Grant.
    Grant,
    /// Deny.
    Deny,
}

/// Record per (subject, cap).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Record {
    /// State.
    pub state: State,
    /// Last rationale (None outside of Pending).
    pub rationale: Option<String>,
    /// Remember choice across requests.
    pub remember: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PermissionPrompt {
    /// Schema version.
    pub schema_version: String,
    /// "subject||cap" → record.
    pub records: BTreeMap<String, Record>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PromptError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("subject empty")]
    EmptySubject,
    /// Empty.
    #[error("capability empty")]
    EmptyCapability,
    /// Empty.
    #[error("rationale empty")]
    EmptyRationale,
    /// Already pending.
    #[error("already pending")]
    AlreadyPending,
    /// Not pending.
    #[error("not pending")]
    NotPending,
}

fn key(subject: &str, cap: &str) -> String {
    format!("{subject}||{cap}")
}

impl PermissionPrompt {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            records: BTreeMap::new(),
        }
    }

    /// Current state for (subject, cap).
    pub fn state(&self, subject: &str, cap: &str) -> State {
        self.records
            .get(&key(subject, cap))
            .map(|r| r.state)
            .unwrap_or(State::Idle)
    }

    /// Submit a request. If a remembered decision exists, transitions
    /// directly to that state and returns it. Otherwise transitions to
    /// Pending and stores the rationale.
    pub fn request(
        &mut self,
        subject: &str,
        cap: &str,
        rationale: &str,
    ) -> Result<State, PromptError> {
        if subject.is_empty() {
            return Err(PromptError::EmptySubject);
        }
        if cap.is_empty() {
            return Err(PromptError::EmptyCapability);
        }
        if rationale.is_empty() {
            return Err(PromptError::EmptyRationale);
        }
        let k = key(subject, cap);
        if let Some(r) = self.records.get(&k) {
            if r.remember && (r.state == State::Granted || r.state == State::Denied) {
                return Ok(r.state);
            }
            if r.state == State::Pending {
                return Err(PromptError::AlreadyPending);
            }
        }
        self.records.insert(
            k,
            Record {
                state: State::Pending,
                rationale: Some(rationale.into()),
                remember: false,
            },
        );
        Ok(State::Pending)
    }

    /// Resolve a pending request.
    pub fn resolve(
        &mut self,
        subject: &str,
        cap: &str,
        decision: Decision,
        remember: bool,
    ) -> Result<State, PromptError> {
        let k = key(subject, cap);
        let r = self.records.get_mut(&k).ok_or(PromptError::NotPending)?;
        if r.state != State::Pending {
            return Err(PromptError::NotPending);
        }
        r.state = match decision {
            Decision::Grant => State::Granted,
            Decision::Deny => State::Denied,
        };
        r.rationale = None;
        r.remember = remember;
        Ok(r.state)
    }

    /// Reset (clear remembered choice and state).
    pub fn reset(&mut self, subject: &str, cap: &str) -> bool {
        self.records.remove(&key(subject, cap)).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PromptError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PromptError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for PermissionPrompt {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_is_idle() {
        let p = PermissionPrompt::new();
        assert_eq!(p.state("user", "fs.read"), State::Idle);
    }

    #[test]
    fn request_goes_pending() {
        let mut p = PermissionPrompt::new();
        let s = p.request("user", "fs.read", "Read config").unwrap();
        assert_eq!(s, State::Pending);
    }

    #[test]
    fn resolve_grant() {
        let mut p = PermissionPrompt::new();
        p.request("u", "c", "r").unwrap();
        let s = p.resolve("u", "c", Decision::Grant, false).unwrap();
        assert_eq!(s, State::Granted);
    }

    #[test]
    fn resolve_deny() {
        let mut p = PermissionPrompt::new();
        p.request("u", "c", "r").unwrap();
        let s = p.resolve("u", "c", Decision::Deny, false).unwrap();
        assert_eq!(s, State::Denied);
    }

    #[test]
    fn remember_skips_prompt() {
        let mut p = PermissionPrompt::new();
        p.request("u", "c", "r").unwrap();
        p.resolve("u", "c", Decision::Grant, true).unwrap();
        // Subsequent request auto-resolves to Granted.
        let s = p.request("u", "c", "again").unwrap();
        assert_eq!(s, State::Granted);
    }

    #[test]
    fn without_remember_re_prompts() {
        let mut p = PermissionPrompt::new();
        p.request("u", "c", "r").unwrap();
        p.resolve("u", "c", Decision::Grant, false).unwrap();
        let s = p.request("u", "c", "again").unwrap();
        assert_eq!(s, State::Pending);
    }

    #[test]
    fn double_request_pending_rejected() {
        let mut p = PermissionPrompt::new();
        p.request("u", "c", "r").unwrap();
        assert!(matches!(
            p.request("u", "c", "r2").unwrap_err(),
            PromptError::AlreadyPending
        ));
    }

    #[test]
    fn resolve_without_pending_rejected() {
        let mut p = PermissionPrompt::new();
        assert!(matches!(
            p.resolve("u", "c", Decision::Grant, false).unwrap_err(),
            PromptError::NotPending
        ));
    }

    #[test]
    fn reset_clears() {
        let mut p = PermissionPrompt::new();
        p.request("u", "c", "r").unwrap();
        p.resolve("u", "c", Decision::Grant, true).unwrap();
        assert!(p.reset("u", "c"));
        assert_eq!(p.state("u", "c"), State::Idle);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut p = PermissionPrompt::new();
        assert!(matches!(
            p.request("", "c", "r").unwrap_err(),
            PromptError::EmptySubject
        ));
        assert!(matches!(
            p.request("u", "", "r").unwrap_err(),
            PromptError::EmptyCapability
        ));
        assert!(matches!(
            p.request("u", "c", "").unwrap_err(),
            PromptError::EmptyRationale
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = PermissionPrompt::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PromptError::SchemaMismatch
        ));
    }

    #[test]
    fn prompt_serde_roundtrip() {
        let mut p = PermissionPrompt::new();
        p.request("u", "c", "r").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: PermissionPrompt = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
