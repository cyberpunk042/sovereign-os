//! `sovereign-cockpit-recipient-list` — to/cc/bcc lists.
//!
//! Three lists (to/cc/bcc) of recipient strings. add(line, recipient)
//! appends iff not already in any of the three lists (cross-list
//! dedup). remove(line, recipient) drops. all_recipients() returns
//! union.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Line.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Line {
    /// To.
    To,
    /// Cc.
    Cc,
    /// Bcc.
    Bcc,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RecipientList {
    /// Schema version.
    pub schema_version: String,
    /// To.
    pub to: Vec<String>,
    /// Cc.
    pub cc: Vec<String>,
    /// Bcc.
    pub bcc: Vec<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RecipientError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("recipient empty")]
    EmptyRecipient,
    /// Already.
    #[error("already in list: {0}")]
    AlreadyPresent(String),
}

impl RecipientList {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            to: Vec::new(),
            cc: Vec::new(),
            bcc: Vec::new(),
        }
    }

    fn contains_anywhere(&self, recipient: &str) -> bool {
        self.to.iter().any(|r| r == recipient)
            || self.cc.iter().any(|r| r == recipient)
            || self.bcc.iter().any(|r| r == recipient)
    }

    /// Add (cross-list dedup).
    pub fn add(&mut self, line: Line, recipient: &str) -> Result<(), RecipientError> {
        if recipient.is_empty() {
            return Err(RecipientError::EmptyRecipient);
        }
        if self.contains_anywhere(recipient) {
            return Err(RecipientError::AlreadyPresent(recipient.into()));
        }
        match line {
            Line::To => self.to.push(recipient.into()),
            Line::Cc => self.cc.push(recipient.into()),
            Line::Bcc => self.bcc.push(recipient.into()),
        }
        Ok(())
    }

    /// Remove from a specific line.
    pub fn remove(&mut self, line: Line, recipient: &str) -> bool {
        let list = match line {
            Line::To => &mut self.to,
            Line::Cc => &mut self.cc,
            Line::Bcc => &mut self.bcc,
        };
        if let Some(pos) = list.iter().position(|r| r == recipient) {
            list.remove(pos);
            true
        } else {
            false
        }
    }

    /// All recipients across all lines.
    pub fn all_recipients(&self) -> Vec<&str> {
        self.to
            .iter()
            .chain(self.cc.iter())
            .chain(self.bcc.iter())
            .map(|s| s.as_str())
            .collect()
    }

    /// Total count.
    pub fn total(&self) -> usize {
        self.to.len() + self.cc.len() + self.bcc.len()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RecipientError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RecipientError::SchemaMismatch);
        }
        for r in self.to.iter().chain(self.cc.iter()).chain(self.bcc.iter()) {
            if r.is_empty() {
                return Err(RecipientError::EmptyRecipient);
            }
        }
        Ok(())
    }
}

impl Default for RecipientList {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_per_line() {
        let mut r = RecipientList::new();
        r.add(Line::To, "alice@x").unwrap();
        r.add(Line::Cc, "bob@x").unwrap();
        r.add(Line::Bcc, "carol@x").unwrap();
        assert_eq!(r.total(), 3);
    }

    #[test]
    fn cross_list_dedup_rejected() {
        let mut r = RecipientList::new();
        r.add(Line::To, "alice@x").unwrap();
        assert!(matches!(
            r.add(Line::Cc, "alice@x").unwrap_err(),
            RecipientError::AlreadyPresent(_)
        ));
    }

    #[test]
    fn remove_from_line() {
        let mut r = RecipientList::new();
        r.add(Line::To, "alice@x").unwrap();
        assert!(r.remove(Line::To, "alice@x"));
        assert!(!r.remove(Line::To, "alice@x"));
    }

    #[test]
    fn all_recipients_union() {
        let mut r = RecipientList::new();
        r.add(Line::To, "a").unwrap();
        r.add(Line::Cc, "b").unwrap();
        r.add(Line::Bcc, "c").unwrap();
        assert_eq!(r.all_recipients(), vec!["a", "b", "c"]);
    }

    #[test]
    fn empty_recipient_rejected() {
        let mut r = RecipientList::new();
        assert!(matches!(
            r.add(Line::To, "").unwrap_err(),
            RecipientError::EmptyRecipient
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = RecipientList::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RecipientError::SchemaMismatch
        ));
    }

    #[test]
    fn list_serde_roundtrip() {
        let mut r = RecipientList::new();
        r.add(Line::To, "a").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: RecipientList = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
