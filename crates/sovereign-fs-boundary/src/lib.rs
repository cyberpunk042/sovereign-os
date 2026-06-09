//! `sovereign-fs-boundary` — E0123 / M00231: the Filesystem Boundary.
//!
//! Sandboxes never touch host files directly. Everything crosses through
//! explicit exchange directories under `/ai-exchange`, and anything coming IN
//! runs a host import-validation pipeline before it is trusted. This crate
//! fixes the exchange-directory layout and the validation steps.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The exchange directories under `/ai-exchange` (M00231).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ExchangeDir {
    /// Files coming IN from a sandbox (must pass import validation).
    Inbox,
    /// Files going OUT to a sandbox.
    Outbox,
    /// Durable build/artifact outputs.
    Artifacts,
}

impl ExchangeDir {
    /// All three exchange directories.
    pub const ALL: [ExchangeDir; 3] = [
        ExchangeDir::Inbox,
        ExchangeDir::Outbox,
        ExchangeDir::Artifacts,
    ];

    /// The leaf directory name.
    #[must_use]
    pub fn leaf(self) -> &'static str {
        match self {
            ExchangeDir::Inbox => "inbox",
            ExchangeDir::Outbox => "outbox",
            ExchangeDir::Artifacts => "artifacts",
        }
    }

    /// The absolute path under `/ai-exchange`.
    #[must_use]
    pub fn path(self) -> String {
        format!("/ai-exchange/{}", self.leaf())
    }
}

/// The host import-validation pipeline steps (M00231), in order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ImportStep {
    /// 1. Parse the incoming file.
    Parse,
    /// 2. Scan for malware / secrets.
    Scan,
    /// 3. Diff against the current host state.
    Diff,
    /// 4. Policy check the proposed change.
    PolicyCheck,
    /// 5. Oracle review — only when the earlier steps flag it as needed.
    OracleReview,
    /// 6. Commit the validated import.
    Commit,
}

impl ImportStep {
    /// All 6 steps, in order.
    pub const ALL: [ImportStep; 6] = [
        ImportStep::Parse,
        ImportStep::Scan,
        ImportStep::Diff,
        ImportStep::PolicyCheck,
        ImportStep::OracleReview,
        ImportStep::Commit,
    ];

    /// 1-based position.
    #[must_use]
    pub fn position(self) -> u8 {
        (Self::ALL.iter().position(|s| *s == self).unwrap() + 1) as u8
    }

    /// The next step, or `None` after commit.
    #[must_use]
    pub fn next(self) -> Option<ImportStep> {
        let i = Self::ALL.iter().position(|s| *s == self).unwrap();
        Self::ALL.get(i + 1).copied()
    }

    /// Whether this step is conditional ("if needed"). Only `OracleReview` is
    /// skippable when the earlier steps raised no concern; the rest are
    /// mandatory.
    #[must_use]
    pub fn is_conditional(self) -> bool {
        matches!(self, ImportStep::OracleReview)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn three_exchange_dirs_with_paths() {
        assert_eq!(ExchangeDir::ALL.len(), 3);
        assert_eq!(ExchangeDir::Inbox.path(), "/ai-exchange/inbox");
        assert_eq!(ExchangeDir::Artifacts.path(), "/ai-exchange/artifacts");
    }

    #[test]
    fn six_steps_ordered_and_chained() {
        assert_eq!(ImportStep::ALL.len(), 6);
        assert_eq!(ImportStep::Parse.position(), 1);
        assert_eq!(ImportStep::Commit.position(), 6);
        assert_eq!(ImportStep::Parse.next(), Some(ImportStep::Scan));
        assert_eq!(ImportStep::Commit.next(), None);
    }

    #[test]
    fn validation_precedes_commit() {
        // scan + policy-check must come before commit — never commit unvetted.
        assert!(ImportStep::Scan.position() < ImportStep::Commit.position());
        assert!(ImportStep::PolicyCheck.position() < ImportStep::Commit.position());
    }

    #[test]
    fn only_oracle_review_is_conditional() {
        assert!(ImportStep::OracleReview.is_conditional());
        for s in ImportStep::ALL
            .into_iter()
            .filter(|s| *s != ImportStep::OracleReview)
        {
            assert!(!s.is_conditional(), "{s:?} must be mandatory");
        }
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ExchangeDir::Inbox).unwrap(),
            "\"inbox\""
        );
        assert_eq!(
            serde_json::to_string(&ImportStep::PolicyCheck).unwrap(),
            "\"policy-check\""
        );
    }
}
