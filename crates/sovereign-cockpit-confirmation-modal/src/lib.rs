//! `sovereign-cockpit-confirmation-modal` — yes/no dialog state.
//!
//! Each `Confirmation` carries (id, title, body, danger_level,
//! confirm_phrase, countdown_seconds). The operator must (a) type
//! `confirm_phrase` exactly and (b) wait `countdown_seconds` before the
//! confirm button activates. Pure UX gate.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Danger level (cosmetic styling).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DangerLevel {
    /// Routine confirm.
    Routine,
    /// Caution.
    Caution,
    /// Destructive — long countdown + phrase required.
    Destructive,
    /// Irreversible.
    Irreversible,
}

/// One confirmation dialog.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Confirmation {
    /// Stable id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Body explanation.
    pub body: String,
    /// Danger level.
    pub danger: DangerLevel,
    /// Operator must type this phrase before confirm (empty = none).
    pub confirm_phrase: String,
    /// Countdown seconds before confirm button activates.
    pub countdown_seconds: u8,
    /// Operator's typed phrase (compared against confirm_phrase).
    pub typed_phrase: String,
    /// Elapsed seconds since modal opened.
    pub elapsed_seconds: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ConfirmationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id / title / body.
    #[error("missing required field: {0}")]
    MissingField(&'static str),
    /// Phrase mismatch.
    #[error("typed phrase doesn't match")]
    PhraseMismatch,
    /// Countdown not elapsed.
    #[error("countdown not elapsed: {elapsed} < {required}")]
    CountdownNotElapsed {
        /// elapsed.
        elapsed: u8,
        /// required.
        required: u8,
    },
}

impl Confirmation {
    /// Build a new confirmation dialog.
    pub fn new(id: &str, title: &str, body: &str, danger: DangerLevel) -> Self {
        let (phrase, countdown) = match danger {
            DangerLevel::Routine => (String::new(), 0),
            DangerLevel::Caution => (String::new(), 2),
            DangerLevel::Destructive => ("DESTROY".into(), 5),
            DangerLevel::Irreversible => ("IRREVERSIBLE".into(), 10),
        };
        Self {
            id: id.into(),
            title: title.into(),
            body: body.into(),
            danger,
            confirm_phrase: phrase,
            countdown_seconds: countdown,
            typed_phrase: String::new(),
            elapsed_seconds: 0,
        }
    }

    /// Update the operator's typed phrase.
    pub fn type_phrase(&mut self, s: &str) {
        self.typed_phrase = s.into();
    }

    /// Tick the countdown by one second (caller-driven).
    pub fn tick(&mut self) {
        self.elapsed_seconds = self.elapsed_seconds.saturating_add(1);
    }

    /// Validate fields.
    pub fn validate(&self) -> Result<(), ConfirmationError> {
        if self.id.is_empty() {
            return Err(ConfirmationError::MissingField("id"));
        }
        if self.title.is_empty() {
            return Err(ConfirmationError::MissingField("title"));
        }
        if self.body.is_empty() {
            return Err(ConfirmationError::MissingField("body"));
        }
        Ok(())
    }

    /// Can the confirm button be pressed right now?
    pub fn can_confirm(&self) -> Result<(), ConfirmationError> {
        if self.elapsed_seconds < self.countdown_seconds {
            return Err(ConfirmationError::CountdownNotElapsed {
                elapsed: self.elapsed_seconds,
                required: self.countdown_seconds,
            });
        }
        if !self.confirm_phrase.is_empty() && self.typed_phrase != self.confirm_phrase {
            return Err(ConfirmationError::PhraseMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn routine_confirms_immediately() {
        let c = Confirmation::new("a", "Title", "Body", DangerLevel::Routine);
        c.can_confirm().unwrap();
    }

    #[test]
    fn destructive_requires_phrase_and_countdown() {
        let mut c = Confirmation::new("a", "Title", "Body", DangerLevel::Destructive);
        // Initially blocked by countdown.
        assert!(matches!(
            c.can_confirm().unwrap_err(),
            ConfirmationError::CountdownNotElapsed { .. }
        ));
        for _ in 0..5 {
            c.tick();
        }
        // Now blocked by phrase.
        assert!(matches!(
            c.can_confirm().unwrap_err(),
            ConfirmationError::PhraseMismatch
        ));
        c.type_phrase("DESTROY");
        c.can_confirm().unwrap();
    }

    #[test]
    fn irreversible_longer_countdown() {
        let c = Confirmation::new("a", "Title", "Body", DangerLevel::Irreversible);
        assert_eq!(c.countdown_seconds, 10);
        assert_eq!(c.confirm_phrase, "IRREVERSIBLE");
    }

    #[test]
    fn caution_no_phrase_but_short_countdown() {
        let mut c = Confirmation::new("a", "Title", "Body", DangerLevel::Caution);
        assert!(matches!(
            c.can_confirm().unwrap_err(),
            ConfirmationError::CountdownNotElapsed { .. }
        ));
        c.tick();
        c.tick();
        c.can_confirm().unwrap();
    }

    #[test]
    fn validate_empty_id_rejected() {
        let mut c = Confirmation::new("a", "T", "B", DangerLevel::Routine);
        c.id = String::new();
        assert!(matches!(
            c.validate().unwrap_err(),
            ConfirmationError::MissingField("id")
        ));
    }

    #[test]
    fn validate_empty_title_rejected() {
        let mut c = Confirmation::new("a", "T", "B", DangerLevel::Routine);
        c.title = String::new();
        assert!(matches!(
            c.validate().unwrap_err(),
            ConfirmationError::MissingField("title")
        ));
    }

    #[test]
    fn type_phrase_updates() {
        let mut c = Confirmation::new("a", "T", "B", DangerLevel::Destructive);
        c.type_phrase("DESTROY");
        assert_eq!(c.typed_phrase, "DESTROY");
    }

    #[test]
    fn tick_saturates_at_u8_max() {
        let mut c = Confirmation::new("a", "T", "B", DangerLevel::Routine);
        for _ in 0..300 {
            c.tick();
        }
        assert_eq!(c.elapsed_seconds, 255);
    }

    #[test]
    fn danger_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&DangerLevel::Routine).unwrap(),
            "\"routine\""
        );
        assert_eq!(
            serde_json::to_string(&DangerLevel::Destructive).unwrap(),
            "\"destructive\""
        );
        assert_eq!(
            serde_json::to_string(&DangerLevel::Irreversible).unwrap(),
            "\"irreversible\""
        );
    }

    #[test]
    fn confirmation_serde_roundtrip() {
        let c = Confirmation::new("a", "T", "B", DangerLevel::Destructive);
        let j = serde_json::to_string(&c).unwrap();
        let back: Confirmation = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
