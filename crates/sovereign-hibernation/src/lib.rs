//! `sovereign-hibernation` — E0453: Hibernated Thought.
//!
//! "Agents should hibernate when waiting." Rather than burn context and GPU
//! holding an idle branch open, the runtime saves a compact record and frees
//! the resources, resuming when the wake condition fires — AgentRM-style
//! resource management, made local and sovereign. This crate fixes the wait
//! conditions and the saved record (the [`sovereign_task_lifecycle`]
//! `Hibernated` state is the lifecycle counterpart).

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 6 conditions an agent hibernates on (E0453).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum WaitCondition {
    /// Waiting for the user (a human gate).
    WaitingForUser,
    /// Waiting for a long test to finish.
    WaitingForLongTest,
    /// Waiting for a download.
    WaitingForDownload,
    /// Waiting for an external event.
    WaitingForExternalEvent,
    /// A low-priority branch that can yield.
    LowPriorityBranch,
    /// Memory pressure forced it to yield.
    MemoryPressure,
}

impl WaitCondition {
    /// All 6 wait conditions.
    pub const ALL: [WaitCondition; 6] = [
        WaitCondition::WaitingForUser,
        WaitCondition::WaitingForLongTest,
        WaitCondition::WaitingForDownload,
        WaitCondition::WaitingForExternalEvent,
        WaitCondition::LowPriorityBranch,
        WaitCondition::MemoryPressure,
    ];

    /// Whether this condition is externally-driven (resolves on an outside
    /// event) vs resource-driven (the scheduler chose to yield). The former
    /// wake on their event; the latter resume when resources free up.
    #[must_use]
    pub fn is_externally_driven(self) -> bool {
        matches!(
            self,
            WaitCondition::WaitingForUser
                | WaitCondition::WaitingForLongTest
                | WaitCondition::WaitingForDownload
                | WaitCondition::WaitingForExternalEvent
        )
    }
}

/// The 5 fields the runtime saves to hibernate a branch and resume it later
/// (E0453).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HibernationRecord {
    /// 1. A summary of the branch so far.
    pub branch_summary: String,
    /// 2. The compact state vector.
    pub state_vector: Vec<u8>,
    /// 3. Identifiers of the tool futures left pending.
    pub tool_futures: Vec<String>,
    /// 4. The context (memory) references to restore.
    pub context_refs: Vec<String>,
    /// 5. The condition whose resolution wakes this branch.
    pub next_wake_condition: WaitCondition,
}

impl HibernationRecord {
    /// A new hibernation record with the wake condition; the saved buffers
    /// default empty and are filled by the runtime.
    #[must_use]
    pub fn new(branch_summary: impl Into<String>, next_wake_condition: WaitCondition) -> Self {
        Self {
            branch_summary: branch_summary.into(),
            state_vector: Vec::new(),
            tool_futures: Vec::new(),
            context_refs: Vec::new(),
            next_wake_condition,
        }
    }

    /// Whether the record carries enough to resume safely: a non-empty branch
    /// summary (so a resumer knows what it is reviving). The buffers may be
    /// empty for a branch that held no tool futures / context.
    #[must_use]
    pub fn is_resumable(&self) -> bool {
        !self.branch_summary.trim().is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn six_wait_conditions_split_external_vs_resource() {
        assert_eq!(WaitCondition::ALL.len(), 6);
        let external = WaitCondition::ALL
            .iter()
            .filter(|c| c.is_externally_driven())
            .count();
        let resource = WaitCondition::ALL
            .iter()
            .filter(|c| !c.is_externally_driven())
            .count();
        assert_eq!(external, 4); // user / long-test / download / external-event
        assert_eq!(resource, 2); // low-priority / memory-pressure
    }

    #[test]
    fn memory_pressure_is_resource_driven() {
        assert!(!WaitCondition::MemoryPressure.is_externally_driven());
        assert!(!WaitCondition::LowPriorityBranch.is_externally_driven());
        assert!(WaitCondition::WaitingForUser.is_externally_driven());
    }

    #[test]
    fn record_carries_wake_condition_and_resumability() {
        let mut r =
            HibernationRecord::new("drafting parser fix", WaitCondition::WaitingForLongTest);
        assert_eq!(r.next_wake_condition, WaitCondition::WaitingForLongTest);
        assert!(r.is_resumable());
        r.tool_futures.push("pytest-run-7".into());
        r.context_refs.push("mem:parser-files".into());
        assert!(r.is_resumable());
        // an empty summary is not safely resumable.
        let blank = HibernationRecord::new("   ", WaitCondition::MemoryPressure);
        assert!(!blank.is_resumable());
    }

    #[test]
    fn record_roundtrips() {
        let mut r = HibernationRecord::new("b1", WaitCondition::WaitingForUser);
        r.state_vector = vec![1, 2, 3];
        let j = serde_json::to_string(&r).unwrap();
        let back: HibernationRecord = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&WaitCondition::WaitingForExternalEvent).unwrap(),
            "\"waiting-for-external-event\""
        );
    }
}
