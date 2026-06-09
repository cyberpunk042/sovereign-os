//! `sovereign-semantic-checkpoint` — E0450: Semantic Checkpoints.
//!
//! "Raw process checkpoint is not enough. Agent checkpoint needs semantic
//! state." A CRIU/ZFS save-state can restore the *machinery*, but resuming a
//! reasoning agent also needs to know where in the workflow it was, what it was
//! about to do, what it had spent, and whether it was blocked on a human. This
//! crate fixes those ten fields — "continuity with meaning" — and the gate that
//! distinguishes a semantically-complete checkpoint from a bare process dump.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 10-field semantic checkpoint (E0450).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SemanticCheckpoint {
    /// 1. Reference to the container/process state (e.g. the CRIU checkpoint).
    pub container_process_state: String,
    /// 2. Reference to the filesystem snapshot (e.g. the ZFS snapshot).
    pub filesystem_snapshot: String,
    /// 3. The workflow node the agent was at.
    pub workflow_node: String,
    /// 4. The branch state.
    pub branch_state: String,
    /// 5. Identifiers of the open tool futures.
    pub open_tool_futures: Vec<String>,
    /// 6. The memory references in play.
    pub memory_refs: Vec<String>,
    /// 7. The risk state.
    pub risk_state: String,
    /// 8. Cost spent so far (USD).
    pub cost_so_far: f64,
    /// 9. The expected next action.
    pub expected_next_action: String,
    /// 10. The human-gate state (none / pending / granted / denied).
    pub human_gate_state: String,
}

impl SemanticCheckpoint {
    /// Whether the checkpoint carries the *semantic* state that makes it more
    /// than a raw process dump: it knows where it was (`workflow_node`), what
    /// branch (`branch_state`), and what it was about to do
    /// (`expected_next_action`). Without these, restoring the machinery leaves
    /// the agent unable to meaningfully resume.
    #[must_use]
    pub fn is_semantically_complete(&self) -> bool {
        !self.workflow_node.trim().is_empty()
            && !self.branch_state.trim().is_empty()
            && !self.expected_next_action.trim().is_empty()
    }

    /// Whether the underlying machinery references are present (process +
    /// filesystem). A checkpoint can be machinery-complete but
    /// semantically-empty — exactly the "raw checkpoint is not enough" case.
    #[must_use]
    pub fn has_machinery(&self) -> bool {
        !self.container_process_state.trim().is_empty()
            && !self.filesystem_snapshot.trim().is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn full() -> SemanticCheckpoint {
        SemanticCheckpoint {
            container_process_state: "criu:ckpt-42".into(),
            filesystem_snapshot: "rpool@ckpt-42".into(),
            workflow_node: "apply-patch".into(),
            branch_state: "branch-3 active".into(),
            open_tool_futures: vec!["pytest-7".into()],
            memory_refs: vec!["mem:parser".into()],
            risk_state: "medium".into(),
            cost_so_far: 0.42,
            expected_next_action: "run targeted test".into(),
            human_gate_state: "none".into(),
        }
    }

    #[test]
    fn full_checkpoint_is_complete_with_machinery() {
        let c = full();
        assert!(c.is_semantically_complete());
        assert!(c.has_machinery());
    }

    #[test]
    fn raw_dump_has_machinery_but_no_meaning() {
        // The E0450 point: process + filesystem captured, but no workflow node
        // / branch / next action → machinery-complete yet semantically empty.
        let mut c = full();
        c.workflow_node = String::new();
        c.branch_state = String::new();
        c.expected_next_action = "   ".into();
        assert!(c.has_machinery());
        assert!(!c.is_semantically_complete());
    }

    #[test]
    fn missing_next_action_alone_breaks_completeness() {
        let mut c = full();
        c.expected_next_action = String::new();
        assert!(!c.is_semantically_complete());
    }

    #[test]
    fn roundtrips_all_ten_fields() {
        let c = full();
        let j = serde_json::to_string(&c).unwrap();
        let back: SemanticCheckpoint = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
        // cost + human-gate survive.
        assert!((back.cost_so_far - 0.42).abs() < 1e-9);
        assert_eq!(back.human_gate_state, "none");
    }
}
