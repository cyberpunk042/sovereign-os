//! `sovereign-cockpit-message-composer` — composer state.
//!
//! Holds: `body` (multi-line text), attached file ids, an optional
//! `reply_to` parent message, a `Phase` (Editing/Sending/Sent/
//! Failed), a `send_at_ms` for scheduled sends, and counters for
//! `send_attempts` and `last_error`. Operations:
//!   * `set_body(s)`, `attach(file_id)`, `detach(file_id)`,
//!     `set_reply_to(parent)`.
//!   * `is_ready_to_send()` true iff body or attachments non-empty.
//!   * `try_send(now_ms)` Editing → Sending; rejects if not ready
//!     or scheduled in future.
//!   * `mark_sent(now_ms)` / `mark_failed(now_ms, error)`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Composer phase.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Phase {
    /// Editing.
    Editing,
    /// Sending.
    Sending,
    /// Sent.
    Sent,
    /// Failed.
    Failed,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MessageComposer {
    /// Schema version.
    pub schema_version: String,
    /// Body.
    pub body: String,
    /// Attached file ids.
    pub attachments: BTreeSet<String>,
    /// Reply target.
    pub reply_to: Option<String>,
    /// Phase.
    pub phase: Phase,
    /// Scheduled send (None = immediate).
    pub send_at_ms: Option<u64>,
    /// Send attempts.
    pub send_attempts: u64,
    /// Last error.
    pub last_error: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ComposerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty attachment id.
    #[error("attachment id empty")]
    EmptyAttachment,
    /// Empty parent id.
    #[error("reply parent empty")]
    EmptyParent,
    /// Empty error string.
    #[error("error empty")]
    EmptyError,
    /// Nothing to send.
    #[error("composer has no body and no attachments")]
    NothingToSend,
    /// Wrong phase.
    #[error("composer phase {0:?} doesn't allow this transition")]
    WrongPhase(Phase),
    /// Scheduled in future.
    #[error("scheduled send {send_at_ms} > now {now_ms}")]
    NotYetDue {
        /// scheduled.
        send_at_ms: u64,
        /// now.
        now_ms: u64,
    },
}

impl MessageComposer {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            body: String::new(),
            attachments: BTreeSet::new(),
            reply_to: None,
            phase: Phase::Editing,
            send_at_ms: None,
            send_attempts: 0,
            last_error: None,
        }
    }

    /// Set body.
    pub fn set_body(&mut self, body: &str) -> Result<(), ComposerError> {
        if !matches!(self.phase, Phase::Editing | Phase::Failed) {
            return Err(ComposerError::WrongPhase(self.phase));
        }
        self.body = body.into();
        Ok(())
    }

    /// Attach.
    pub fn attach(&mut self, file_id: &str) -> Result<bool, ComposerError> {
        if !matches!(self.phase, Phase::Editing | Phase::Failed) {
            return Err(ComposerError::WrongPhase(self.phase));
        }
        if file_id.is_empty() {
            return Err(ComposerError::EmptyAttachment);
        }
        Ok(self.attachments.insert(file_id.into()))
    }

    /// Detach.
    pub fn detach(&mut self, file_id: &str) -> Result<bool, ComposerError> {
        if !matches!(self.phase, Phase::Editing | Phase::Failed) {
            return Err(ComposerError::WrongPhase(self.phase));
        }
        Ok(self.attachments.remove(file_id))
    }

    /// Set reply target.
    pub fn set_reply_to(&mut self, parent: &str) -> Result<(), ComposerError> {
        if !matches!(self.phase, Phase::Editing | Phase::Failed) {
            return Err(ComposerError::WrongPhase(self.phase));
        }
        if parent.is_empty() {
            return Err(ComposerError::EmptyParent);
        }
        self.reply_to = Some(parent.into());
        Ok(())
    }

    /// Schedule send.
    pub fn schedule(&mut self, at_ms: u64) -> Result<(), ComposerError> {
        if !matches!(self.phase, Phase::Editing | Phase::Failed) {
            return Err(ComposerError::WrongPhase(self.phase));
        }
        self.send_at_ms = Some(at_ms);
        Ok(())
    }

    /// Has content?
    pub fn is_ready_to_send(&self) -> bool {
        !self.body.is_empty() || !self.attachments.is_empty()
    }

    /// Try send.
    pub fn try_send(&mut self, now_ms: u64) -> Result<(), ComposerError> {
        if !matches!(self.phase, Phase::Editing | Phase::Failed) {
            return Err(ComposerError::WrongPhase(self.phase));
        }
        if !self.is_ready_to_send() {
            return Err(ComposerError::NothingToSend);
        }
        if let Some(scheduled) = self.send_at_ms {
            if now_ms < scheduled {
                return Err(ComposerError::NotYetDue {
                    send_at_ms: scheduled,
                    now_ms,
                });
            }
        }
        self.phase = Phase::Sending;
        self.send_attempts = self.send_attempts.saturating_add(1);
        self.last_error = None;
        Ok(())
    }

    /// Mark sent.
    pub fn mark_sent(&mut self, _now_ms: u64) -> Result<(), ComposerError> {
        if self.phase != Phase::Sending {
            return Err(ComposerError::WrongPhase(self.phase));
        }
        self.phase = Phase::Sent;
        Ok(())
    }

    /// Mark failed.
    pub fn mark_failed(&mut self, _now_ms: u64, error: &str) -> Result<(), ComposerError> {
        if self.phase != Phase::Sending {
            return Err(ComposerError::WrongPhase(self.phase));
        }
        if error.is_empty() {
            return Err(ComposerError::EmptyError);
        }
        self.phase = Phase::Failed;
        self.last_error = Some(error.into());
        Ok(())
    }

    /// Reset to Editing (e.g. user wants to keep typing after Sent or Failed).
    pub fn reset_to_editing(&mut self) {
        self.phase = Phase::Editing;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ComposerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ComposerError::SchemaMismatch);
        }
        for a in &self.attachments {
            if a.is_empty() {
                return Err(ComposerError::EmptyAttachment);
            }
        }
        if let Some(p) = &self.reply_to {
            if p.is_empty() {
                return Err(ComposerError::EmptyParent);
            }
        }
        Ok(())
    }
}

impl Default for MessageComposer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_send_path() {
        let mut c = MessageComposer::new();
        c.set_body("hi").unwrap();
        c.try_send(100).unwrap();
        c.mark_sent(200).unwrap();
        assert_eq!(c.phase, Phase::Sent);
    }

    #[test]
    fn nothing_to_send_rejected() {
        let mut c = MessageComposer::new();
        assert!(matches!(
            c.try_send(0).unwrap_err(),
            ComposerError::NothingToSend
        ));
    }

    #[test]
    fn attachments_count_as_content() {
        let mut c = MessageComposer::new();
        c.attach("file1").unwrap();
        assert!(c.is_ready_to_send());
        c.try_send(0).unwrap();
    }

    #[test]
    fn scheduled_blocks_early_send() {
        let mut c = MessageComposer::new();
        c.set_body("hi").unwrap();
        c.schedule(1000).unwrap();
        match c.try_send(500).unwrap_err() {
            ComposerError::NotYetDue { send_at_ms, now_ms } => {
                assert_eq!(send_at_ms, 1000);
                assert_eq!(now_ms, 500);
            }
            _ => panic!(),
        }
    }

    #[test]
    fn scheduled_at_or_after_allowed() {
        let mut c = MessageComposer::new();
        c.set_body("hi").unwrap();
        c.schedule(1000).unwrap();
        c.try_send(1000).unwrap();
    }

    #[test]
    fn failed_path_can_resend() {
        let mut c = MessageComposer::new();
        c.set_body("hi").unwrap();
        c.try_send(0).unwrap();
        c.mark_failed(0, "network").unwrap();
        c.try_send(1).unwrap();
        assert_eq!(c.send_attempts, 2);
    }

    #[test]
    fn cant_edit_while_sending() {
        let mut c = MessageComposer::new();
        c.set_body("hi").unwrap();
        c.try_send(0).unwrap();
        assert!(matches!(
            c.set_body("oops").unwrap_err(),
            ComposerError::WrongPhase(_)
        ));
    }

    #[test]
    fn detach() {
        let mut c = MessageComposer::new();
        c.attach("a").unwrap();
        assert!(c.detach("a").unwrap());
        assert!(!c.detach("a").unwrap());
    }

    #[test]
    fn reply_to_set() {
        let mut c = MessageComposer::new();
        c.set_reply_to("m1").unwrap();
        assert_eq!(c.reply_to.as_deref(), Some("m1"));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut c = MessageComposer::new();
        assert!(matches!(
            c.attach("").unwrap_err(),
            ComposerError::EmptyAttachment
        ));
        assert!(matches!(
            c.set_reply_to("").unwrap_err(),
            ComposerError::EmptyParent
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = MessageComposer::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            ComposerError::SchemaMismatch
        ));
    }

    #[test]
    fn composer_serde_roundtrip() {
        let mut c = MessageComposer::new();
        c.set_body("hi").unwrap();
        c.attach("file1").unwrap();
        c.try_send(0).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: MessageComposer = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
