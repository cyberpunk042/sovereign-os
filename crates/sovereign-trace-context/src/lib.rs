//! `sovereign-trace-context` — E0112 / M00215: the runtime trace mapping.
//!
//! "Tracing is crucial." Every unit of work in the runtime is locatable by
//! four ids whose meaning the catalogue fixes (M00215):
//!
//! - `trace_id`  — one per **user request** (F01089 / R02136)
//! - `span_id`   — one per **branch step / model call / tool call** (F01090)
//! - `branch_id` — a **deterministic runtime object** (F01091)
//! - `commit_id` — an **accepted transition** (F01092)
//!
//! The load-bearing requirement is R02147 — *reconstructable per-trace*: from
//! the spans of a trace you can replay the accepted path (the ordered
//! `commit_id`s) that produced the final answer. This crate fixes the id model
//! and provides that reconstruction; the engine emits the spans.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// One per user request.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct TraceId(pub u128);

/// One per branch step / model call / tool call.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct SpanId(pub u64);

/// A deterministic runtime object (a reasoning branch).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct BranchId(pub u64);

/// An accepted transition (a committed step in the final path).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct CommitId(pub u64);

/// What a span represents (M00215: branch step / model call / tool call).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SpanKind {
    /// A deterministic branch step.
    BranchStep,
    /// A model (oracle/scout) call.
    ModelCall,
    /// A tool call.
    ToolCall,
}

/// One span within a trace.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Span {
    /// Span id.
    pub span_id: SpanId,
    /// What this span is.
    pub kind: SpanKind,
    /// The runtime branch this span belongs to.
    pub branch_id: BranchId,
    /// Set when this span's transition was ACCEPTED into the final path;
    /// `None` for explored-but-rejected work.
    pub commit_id: Option<CommitId>,
}

/// Errors validating a trace.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TraceError {
    /// Two spans share a `span_id`.
    DuplicateSpanId(SpanId),
    /// Two distinct spans claim the same `commit_id` — a commit must be a
    /// single accepted transition, not a fork.
    DuplicateCommitId(CommitId),
}

impl std::fmt::Display for TraceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TraceError::DuplicateSpanId(s) => write!(f, "duplicate span_id {}", s.0),
            TraceError::DuplicateCommitId(c) => write!(f, "duplicate commit_id {}", c.0),
        }
    }
}

impl std::error::Error for TraceError {}

/// A whole trace: one user request and its spans.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Trace {
    /// The user request id.
    pub trace_id: TraceId,
    /// Every span emitted under this trace (committed and rejected).
    pub spans: Vec<Span>,
}

impl Trace {
    /// A new, empty trace.
    #[must_use]
    pub fn new(trace_id: TraceId) -> Self {
        Self {
            trace_id,
            spans: Vec::new(),
        }
    }

    /// Append a span.
    pub fn push(&mut self, span: Span) {
        self.spans.push(span);
    }

    /// Validate uniqueness: span ids and commit ids are each unique within the
    /// trace (a `commit_id` is a single accepted transition).
    pub fn validate(&self) -> Result<(), TraceError> {
        use std::collections::HashSet;
        let mut spans = HashSet::new();
        let mut commits = HashSet::new();
        for s in &self.spans {
            if !spans.insert(s.span_id) {
                return Err(TraceError::DuplicateSpanId(s.span_id));
            }
            if let Some(c) = s.commit_id
                && !commits.insert(c)
            {
                return Err(TraceError::DuplicateCommitId(c));
            }
        }
        Ok(())
    }

    /// R02147 — reconstruct the accepted path: the spans whose transition was
    /// committed, in `commit_id` order. This is the replayable sequence that
    /// produced the final answer (rejected/explored spans are dropped).
    #[must_use]
    pub fn committed_path(&self) -> Vec<&Span> {
        let mut committed: Vec<&Span> = self
            .spans
            .iter()
            .filter(|s| s.commit_id.is_some())
            .collect();
        committed.sort_by_key(|s| s.commit_id.expect("filtered to Some"));
        committed
    }

    /// The distinct runtime branches that contributed a span to this trace.
    #[must_use]
    pub fn branches(&self) -> Vec<BranchId> {
        let mut b: Vec<BranchId> = self.spans.iter().map(|s| s.branch_id).collect();
        b.sort_unstable();
        b.dedup();
        b
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn span(id: u64, kind: SpanKind, branch: u64, commit: Option<u64>) -> Span {
        Span {
            span_id: SpanId(id),
            kind,
            branch_id: BranchId(branch),
            commit_id: commit.map(CommitId),
        }
    }

    fn sample_trace() -> Trace {
        let mut t = Trace::new(TraceId(0xdead_beef));
        // branch 1 explores two steps; only the second commits (order 2).
        t.push(span(1, SpanKind::BranchStep, 1, None));
        t.push(span(2, SpanKind::ModelCall, 1, Some(2)));
        // branch 2: a tool call that commits first (order 1).
        t.push(span(3, SpanKind::ToolCall, 2, Some(1)));
        // branch 3: explored and rejected.
        t.push(span(4, SpanKind::BranchStep, 3, None));
        t
    }

    #[test]
    fn validate_accepts_unique_ids() {
        sample_trace().validate().unwrap();
    }

    #[test]
    fn validate_rejects_duplicate_span_id() {
        let mut t = sample_trace();
        t.push(span(2, SpanKind::ToolCall, 9, None)); // span_id 2 reused
        assert_eq!(t.validate(), Err(TraceError::DuplicateSpanId(SpanId(2))));
    }

    #[test]
    fn validate_rejects_duplicate_commit_id() {
        let mut t = sample_trace();
        t.push(span(5, SpanKind::ModelCall, 2, Some(2))); // commit 2 reused
        assert_eq!(
            t.validate(),
            Err(TraceError::DuplicateCommitId(CommitId(2)))
        );
    }

    #[test]
    fn committed_path_is_accepted_transitions_in_commit_order() {
        let t = sample_trace();
        let path = t.committed_path();
        // commit 1 (tool call, span 3) before commit 2 (model call, span 2);
        // rejected spans (1, 4) excluded.
        let ids: Vec<u64> = path.iter().map(|s| s.span_id.0).collect();
        assert_eq!(ids, [3, 2]);
        let commits: Vec<u64> = path.iter().map(|s| s.commit_id.unwrap().0).collect();
        assert_eq!(commits, [1, 2]);
    }

    #[test]
    fn branches_are_distinct_contributors() {
        assert_eq!(
            sample_trace().branches(),
            [BranchId(1), BranchId(2), BranchId(3)]
        );
    }

    #[test]
    fn empty_trace_has_empty_path() {
        let t = Trace::new(TraceId(1));
        t.validate().unwrap();
        assert!(t.committed_path().is_empty());
        assert!(t.branches().is_empty());
    }

    #[test]
    fn span_kind_serializes_kebab() {
        assert_eq!(
            serde_json::to_string(&SpanKind::ModelCall).unwrap(),
            "\"model-call\""
        );
        assert_eq!(
            serde_json::to_string(&SpanKind::ToolCall).unwrap(),
            "\"tool-call\""
        );
    }

    #[test]
    fn trace_serde_roundtrip() {
        let t = sample_trace();
        let j = serde_json::to_string(&t).unwrap();
        let back: Trace = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
