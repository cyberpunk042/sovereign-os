//! `sovereign-typed-state` — E0557: the Critical Data Flow Law.
//!
//! "Text is not the system state. Text is payload inside typed state. This is
//! what makes the system programmable and continuous." A task's real state is
//! eight typed components, not a transcript: frames, routes, policies, memory
//! references, tool observations, eval results, commits, and traces. This crate
//! fixes that typed shape so the runtime carries structured state (and text
//! only as payload inside it). `commits`/`traces` reuse the
//! [`sovereign_trace_context`] ids, so the typed state and the reconstructable
//! trace (E0112) share one vocabulary.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_trace_context::{CommitId, TraceId};

/// One reasoning frame (a unit of structured task context).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Frame {
    /// Frame id.
    pub id: String,
    /// Typed kind (e.g. `goal`, `constraint`, `observation`).
    pub kind: String,
}

/// A routing decision (which node went to which hardware/model).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RouteRecord {
    /// The workflow node routed.
    pub node: String,
    /// The hardware/model target chosen.
    pub target: String,
}

/// A policy result (a decision the policy fabric returned).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyResult {
    /// The question answered (e.g. `file-mutation`).
    pub question: String,
    /// The decision (e.g. `allow` / `deny`).
    pub decision: String,
}

/// A tool observation (typed, not raw text — the text is in `output`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ToolObservation {
    /// Tool id.
    pub tool: String,
    /// Exit code, if any.
    pub exit_code: Option<i32>,
    /// Captured output (the text payload inside the typed observation).
    pub output: String,
}

/// An eval result on one axis.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EvalResult {
    /// Eval axis (tests / schema / policy / trajectory / cost / risk / …).
    pub axis: String,
    /// Score 0.0..=1.0.
    pub score: f32,
}

/// The real task state — eight typed components (E0557). Text lives only inside
/// the typed records (e.g. [`ToolObservation::output`]), never as the state
/// itself.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct TypedState {
    /// 1. frames.
    pub frames: Vec<Frame>,
    /// 2. routes.
    pub routes: Vec<RouteRecord>,
    /// 3. policies.
    pub policies: Vec<PolicyResult>,
    /// 4. memory references.
    pub memory_refs: Vec<String>,
    /// 5. tool observations.
    pub tool_observations: Vec<ToolObservation>,
    /// 6. eval results.
    pub eval_results: Vec<EvalResult>,
    /// 7. commits (accepted transitions; the E0112 ids).
    pub commits: Vec<CommitId>,
    /// 8. traces (the E0112 trace ids this state spans).
    pub traces: Vec<TraceId>,
}

impl TypedState {
    /// A fresh empty typed state.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// The number of populated components (0..=8) — a cheap legibility gauge:
    /// a richly-typed state has many components, a thin one few.
    #[must_use]
    pub fn populated_components(&self) -> u8 {
        u8::from(!self.frames.is_empty())
            + u8::from(!self.routes.is_empty())
            + u8::from(!self.policies.is_empty())
            + u8::from(!self.memory_refs.is_empty())
            + u8::from(!self.tool_observations.is_empty())
            + u8::from(!self.eval_results.is_empty())
            + u8::from(!self.commits.is_empty())
            + u8::from(!self.traces.is_empty())
    }

    /// Whether the state carries nothing yet.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.populated_components() == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_trace_context::{CommitId, TraceId};

    #[test]
    fn empty_state_has_zero_components() {
        let s = TypedState::new();
        assert!(s.is_empty());
        assert_eq!(s.populated_components(), 0);
    }

    #[test]
    fn populated_components_counts_the_eight() {
        let mut s = TypedState::new();
        s.frames.push(Frame {
            id: "f1".into(),
            kind: "goal".into(),
        });
        s.routes.push(RouteRecord {
            node: "draft".into(),
            target: "rocm-3090".into(),
        });
        s.policies.push(PolicyResult {
            question: "file-mutation".into(),
            decision: "allow".into(),
        });
        s.memory_refs.push("m1".into());
        s.tool_observations.push(ToolObservation {
            tool: "pytest".into(),
            exit_code: Some(0),
            output: "1 passed".into(),
        });
        s.eval_results.push(EvalResult {
            axis: "tests".into(),
            score: 1.0,
        });
        s.commits.push(CommitId(1));
        s.traces.push(TraceId(0xabc));
        assert_eq!(s.populated_components(), 8);
        assert!(!s.is_empty());
    }

    #[test]
    fn text_is_payload_inside_typed_records_not_the_state() {
        // The tool *output* text lives inside a typed ToolObservation; the
        // state itself is structured, satisfying the E0557 law.
        let mut s = TypedState::new();
        s.tool_observations.push(ToolObservation {
            tool: "shell".into(),
            exit_code: Some(127),
            output: "command not found".into(),
        });
        assert_eq!(s.tool_observations[0].output, "command not found");
        assert_eq!(s.populated_components(), 1);
    }

    #[test]
    fn state_roundtrips_with_trace_ids() {
        let mut s = TypedState::new();
        s.commits = vec![CommitId(1), CommitId(2)];
        s.traces = vec![TraceId(9)];
        let j = serde_json::to_string(&s).unwrap();
        let back: TypedState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
        assert_eq!(back.commits, vec![CommitId(1), CommitId(2)]);
    }
}
