//! `sovereign-conversation-thread` — turn-by-turn conversation record.
//!
//! A thread is a sequence of turns. Each turn declares:
//! - `role` (Operator / Model / Tool / System)
//! - `tokens_in` / `tokens_out`
//! - `provider` (cloud / local / hybrid label)
//! - `started_at` / `completed_at` (ISO-8601 UTC)
//! - `branch_id` (M049 branch reference; enables fork/merge)
//! - `text` (verbatim turn content, may be empty for tool calls)
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Turn role.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TurnRole {
    /// Human operator input.
    Operator,
    /// Model assistant output.
    Model,
    /// Tool invocation result.
    Tool,
    /// System / cockpit metadata.
    System,
}

/// One conversation turn.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Turn {
    /// Monotonic per-thread turn index, starting at 0.
    pub index: u32,
    /// Role.
    pub role: TurnRole,
    /// Tokens in (prompt side).
    pub tokens_in: u32,
    /// Tokens out (completion side).
    pub tokens_out: u32,
    /// Provider label (e.g. "cloud-anthropic", "local:rocm-4090").
    pub provider: String,
    /// ISO-8601 UTC.
    pub started_at: String,
    /// ISO-8601 UTC; empty while in-progress.
    pub completed_at: String,
    /// M049 branch id.
    pub branch_id: String,
    /// Verbatim turn text (may be empty for tool calls).
    pub text: String,
}

/// Thread envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConversationThread {
    /// Schema version.
    pub schema_version: String,
    /// Thread id (operator-readable).
    pub thread_id: String,
    /// ISO-8601 UTC when thread opened.
    pub opened_at: String,
    /// Turns.
    pub turns: Vec<Turn>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ThreadError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty thread_id.
    #[error("thread_id missing")]
    MissingThreadId,
    /// Empty opened_at.
    #[error("opened_at missing")]
    MissingOpenedAt,
    /// Turn index non-monotonic.
    #[error("turn {idx} index {got} expected {want}")]
    NonMonotonic {
        /// Vec position.
        idx: usize,
        /// Got.
        got: u32,
        /// Want.
        want: u32,
    },
    /// Empty provider.
    #[error("turn {0} provider empty")]
    EmptyProvider(u32),
    /// Empty started_at.
    #[error("turn {0} started_at empty")]
    EmptyStartedAt(u32),
    /// completed_at precedes started_at.
    #[error("turn {idx} completed_at {completed} precedes started_at {started}")]
    CompletedBeforeStarted {
        /// Index.
        idx: u32,
        /// started.
        started: String,
        /// completed.
        completed: String,
    },
}

impl ConversationThread {
    /// New thread.
    pub fn new(thread_id: &str, opened_at: &str) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            thread_id: thread_id.into(),
            opened_at: opened_at.into(),
            turns: Vec::new(),
        }
    }

    /// Append a turn; assigns next monotonic index automatically.
    pub fn append(&mut self, mut t: Turn) -> u32 {
        t.index = self.turns.len() as u32;
        let idx = t.index;
        self.turns.push(t);
        idx
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ThreadError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ThreadError::SchemaMismatch);
        }
        if self.thread_id.is_empty() {
            return Err(ThreadError::MissingThreadId);
        }
        if self.opened_at.is_empty() {
            return Err(ThreadError::MissingOpenedAt);
        }
        for (idx, t) in self.turns.iter().enumerate() {
            let want = idx as u32;
            if t.index != want {
                return Err(ThreadError::NonMonotonic {
                    idx,
                    got: t.index,
                    want,
                });
            }
            if t.provider.is_empty() {
                return Err(ThreadError::EmptyProvider(t.index));
            }
            if t.started_at.is_empty() {
                return Err(ThreadError::EmptyStartedAt(t.index));
            }
            if !t.completed_at.is_empty() && t.completed_at < t.started_at {
                return Err(ThreadError::CompletedBeforeStarted {
                    idx: t.index,
                    started: t.started_at.clone(),
                    completed: t.completed_at.clone(),
                });
            }
        }
        Ok(())
    }

    /// Total tokens in across all turns.
    pub fn total_tokens_in(&self) -> u64 {
        self.turns.iter().map(|t| t.tokens_in as u64).sum()
    }

    /// Total tokens out across all turns.
    pub fn total_tokens_out(&self) -> u64 {
        self.turns.iter().map(|t| t.tokens_out as u64).sum()
    }

    /// Count turns by role.
    pub fn count_by_role(&self, role: TurnRole) -> usize {
        self.turns.iter().filter(|t| t.role == role).count()
    }

    /// Distinct branch ids.
    pub fn branches(&self) -> Vec<String> {
        let mut s = std::collections::BTreeSet::new();
        for t in &self.turns {
            s.insert(t.branch_id.clone());
        }
        s.into_iter().collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn turn(role: TurnRole, tokens_in: u32, tokens_out: u32, branch: &str, text: &str) -> Turn {
        Turn {
            index: 0,
            role,
            tokens_in,
            tokens_out,
            provider: "local:rocm-4090".into(),
            started_at: "2026-05-19T03:00:00Z".into(),
            completed_at: "2026-05-19T03:00:01Z".into(),
            branch_id: branch.into(),
            text: text.into(),
        }
    }

    #[test]
    fn empty_thread_validates() {
        ConversationThread::new("th-1", "2026-05-19T03:00:00Z")
            .validate()
            .unwrap();
    }

    #[test]
    fn append_assigns_monotonic_index() {
        let mut t = ConversationThread::new("th-1", "t");
        let i0 = t.append(turn(TurnRole::Operator, 10, 0, "main", "hi"));
        let i1 = t.append(turn(TurnRole::Model, 0, 5, "main", "hello"));
        assert_eq!(i0, 0);
        assert_eq!(i1, 1);
        t.validate().unwrap();
    }

    #[test]
    fn token_totals_sum() {
        let mut t = ConversationThread::new("th-1", "t");
        t.append(turn(TurnRole::Operator, 100, 0, "main", ""));
        t.append(turn(TurnRole::Model, 0, 50, "main", ""));
        t.append(turn(TurnRole::Operator, 30, 0, "main", ""));
        t.append(turn(TurnRole::Model, 0, 80, "main", ""));
        assert_eq!(t.total_tokens_in(), 130);
        assert_eq!(t.total_tokens_out(), 130);
    }

    #[test]
    fn count_by_role() {
        let mut t = ConversationThread::new("th-1", "t");
        t.append(turn(TurnRole::Operator, 1, 0, "main", ""));
        t.append(turn(TurnRole::Model, 0, 1, "main", ""));
        t.append(turn(TurnRole::Tool, 0, 0, "main", ""));
        t.append(turn(TurnRole::System, 0, 0, "main", ""));
        for r in [
            TurnRole::Operator,
            TurnRole::Model,
            TurnRole::Tool,
            TurnRole::System,
        ] {
            assert_eq!(t.count_by_role(r), 1);
        }
    }

    #[test]
    fn branches_distinct_sorted() {
        let mut t = ConversationThread::new("th-1", "t");
        t.append(turn(TurnRole::Operator, 1, 0, "main", ""));
        t.append(turn(TurnRole::Model, 0, 1, "main", ""));
        t.append(turn(TurnRole::Operator, 1, 0, "experiment", ""));
        let b = t.branches();
        assert_eq!(b, vec!["experiment".to_string(), "main".to_string()]);
    }

    #[test]
    fn non_monotonic_caught() {
        let mut t = ConversationThread::new("th-1", "t");
        t.append(turn(TurnRole::Operator, 1, 0, "main", ""));
        // Tamper turn index
        t.turns[0].index = 5;
        match t.validate().unwrap_err() {
            ThreadError::NonMonotonic { idx, got, want } => {
                assert_eq!(idx, 0);
                assert_eq!(got, 5);
                assert_eq!(want, 0);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn empty_provider_caught() {
        let mut t = ConversationThread::new("th-1", "t");
        let mut tu = turn(TurnRole::Operator, 1, 0, "main", "");
        tu.provider = String::new();
        t.append(tu);
        assert!(matches!(
            t.validate().unwrap_err(),
            ThreadError::EmptyProvider(0)
        ));
    }

    #[test]
    fn completed_before_started_caught() {
        let mut t = ConversationThread::new("th-1", "t");
        let mut tu = turn(TurnRole::Operator, 1, 0, "main", "");
        tu.started_at = "2026-05-19T03:00:05Z".into();
        tu.completed_at = "2026-05-19T03:00:00Z".into();
        t.append(tu);
        match t.validate().unwrap_err() {
            ThreadError::CompletedBeforeStarted { idx, .. } => assert_eq!(idx, 0),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = ConversationThread::new("th-1", "t");
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            ThreadError::SchemaMismatch
        ));
    }

    #[test]
    fn empty_thread_id_caught() {
        let mut t = ConversationThread::new("", "t");
        assert!(matches!(
            t.validate().unwrap_err(),
            ThreadError::MissingThreadId
        ));
        t.thread_id = "th-1".into();
        t.opened_at = String::new();
        assert!(matches!(
            t.validate().unwrap_err(),
            ThreadError::MissingOpenedAt
        ));
    }

    #[test]
    fn role_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&TurnRole::Operator).unwrap(),
            "\"operator\""
        );
        assert_eq!(
            serde_json::to_string(&TurnRole::Model).unwrap(),
            "\"model\""
        );
        assert_eq!(serde_json::to_string(&TurnRole::Tool).unwrap(), "\"tool\"");
        assert_eq!(
            serde_json::to_string(&TurnRole::System).unwrap(),
            "\"system\""
        );
    }

    #[test]
    fn thread_serde_roundtrip() {
        let mut t = ConversationThread::new("th-1", "t");
        t.append(turn(TurnRole::Operator, 1, 0, "main", "hi"));
        t.append(turn(TurnRole::Model, 0, 2, "main", "hello"));
        let j = serde_json::to_string(&t).unwrap();
        let back: ConversationThread = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
