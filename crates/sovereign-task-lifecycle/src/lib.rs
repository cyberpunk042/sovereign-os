//! `sovereign-task-lifecycle` — E0548 / E0556: the Task Lifecycle.
//!
//! "We need to describe how a real task moves through the station from user
//! intent to durable learning." A task moves through 12 [`LifecycleStep`]s
//! (Intake → … → Resume/Archive) and lives in one of 9 [`TaskState`]s. This
//! crate fixes both, plus the validated state-machine transitions and the
//! resume requirements (E0556), so a task can never jump from, say, `Archived`
//! back into flight, and a paused task can always be resumed with the right
//! context.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 12 lifecycle steps a task moves through (E0548).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LifecycleStep {
    /// 1. Intake.
    Intake,
    /// 2. Normalize.
    Normalize,
    /// 3. Profile Resolve.
    ProfileResolve,
    /// 4. Map.
    Map,
    /// 5. Plan / Compile.
    PlanCompile,
    /// 6. Route.
    Route,
    /// 7. Execute.
    Execute,
    /// 8. Observe.
    Observe,
    /// 9. Evaluate.
    Evaluate,
    /// 10. Commit / Rollback.
    CommitRollback,
    /// 11. Learn.
    Learn,
    /// 12. Resume / Archive.
    ResumeArchive,
}

impl LifecycleStep {
    /// All 12 steps, in order.
    pub const ALL: [LifecycleStep; 12] = [
        LifecycleStep::Intake,
        LifecycleStep::Normalize,
        LifecycleStep::ProfileResolve,
        LifecycleStep::Map,
        LifecycleStep::PlanCompile,
        LifecycleStep::Route,
        LifecycleStep::Execute,
        LifecycleStep::Observe,
        LifecycleStep::Evaluate,
        LifecycleStep::CommitRollback,
        LifecycleStep::Learn,
        LifecycleStep::ResumeArchive,
    ];

    /// 1-based position in the lifecycle.
    #[must_use]
    pub fn position(self) -> u8 {
        (Self::ALL.iter().position(|s| *s == self).unwrap() + 1) as u8
    }

    /// The next step, or `None` at the end.
    #[must_use]
    pub fn next(self) -> Option<LifecycleStep> {
        let i = Self::ALL.iter().position(|s| *s == self).unwrap();
        Self::ALL.get(i + 1).copied()
    }
}

/// The 9 task states (E0556).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskState {
    /// Running.
    Active,
    /// Paused by the operator/scheduler.
    Paused,
    /// Blocked on a human gate.
    WaitingUser,
    /// Blocked on a tool/subprocess.
    WaitingTool,
    /// Hibernated (CRIU/checkpoint) to free resources.
    Hibernated,
    /// Finished successfully.
    Completed,
    /// Finished in failure.
    Failed,
    /// Rolled back to a snapshot.
    RolledBack,
    /// Archived (terminal).
    Archived,
}

impl TaskState {
    /// All 9 states.
    pub const ALL: [TaskState; 9] = [
        TaskState::Active,
        TaskState::Paused,
        TaskState::WaitingUser,
        TaskState::WaitingTool,
        TaskState::Hibernated,
        TaskState::Completed,
        TaskState::Failed,
        TaskState::RolledBack,
        TaskState::Archived,
    ];

    /// `Archived` is the only terminal state — nothing leaves it.
    #[must_use]
    pub fn is_terminal(self) -> bool {
        self == TaskState::Archived
    }

    /// Whether `self → to` is a permitted transition.
    ///
    /// Encodes the lifecycle's safety invariants: a terminal task never
    /// re-enters flight; blocked states only unblock back to `Active` (or fail);
    /// `Failed` must pass through `RolledBack` or be `Archived` (never silently
    /// `Completed`); `Completed`/`RolledBack` settle into `Archived`.
    #[must_use]
    pub fn can_transition_to(self, to: TaskState) -> bool {
        use TaskState::{
            Active, Archived, Completed, Failed, Hibernated, Paused, RolledBack, WaitingTool,
            WaitingUser,
        };
        match self {
            Active => matches!(
                to,
                Paused | WaitingUser | WaitingTool | Hibernated | Completed | Failed | RolledBack
            ),
            Paused => matches!(to, Active | Archived),
            WaitingUser | WaitingTool => matches!(to, Active | Failed),
            Hibernated => matches!(to, Active | Archived),
            Completed => to == Archived,
            Failed => matches!(to, RolledBack | Archived),
            RolledBack => matches!(to, Active | Archived), // retry or give up
            Archived => false,                             // terminal
        }
    }
}

/// What a [`TaskState::Paused`]/`Hibernated` task needs to resume (E0556): the
/// five things "Resume requires."
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ResumeContext {
    /// A summary of the trace so far.
    pub trace_summary: String,
    /// The current state.
    pub current_state: TaskState,
    /// Open risks to be aware of on resume.
    pub open_risks: Vec<String>,
    /// The next action to take.
    pub next_action: String,
    /// Whether the cached context is still fresh enough to trust.
    pub stale: bool,
}

impl ResumeContext {
    /// True when the context is complete + fresh enough to resume safely:
    /// non-empty trace summary + next action, a resumable current state, and
    /// not stale.
    #[must_use]
    pub fn is_resumable(&self) -> bool {
        !self.trace_summary.trim().is_empty()
            && !self.next_action.trim().is_empty()
            && !self.stale
            && self.current_state.can_transition_to(TaskState::Active)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn twelve_steps_ordered_and_chained() {
        assert_eq!(LifecycleStep::ALL.len(), 12);
        assert_eq!(LifecycleStep::Intake.position(), 1);
        assert_eq!(LifecycleStep::ResumeArchive.position(), 12);
        assert_eq!(LifecycleStep::Intake.next(), Some(LifecycleStep::Normalize));
        assert_eq!(LifecycleStep::ResumeArchive.next(), None);
    }

    #[test]
    fn nine_states() {
        assert_eq!(TaskState::ALL.len(), 9);
    }

    #[test]
    fn archived_is_terminal() {
        assert!(TaskState::Archived.is_terminal());
        for to in TaskState::ALL {
            assert!(!TaskState::Archived.can_transition_to(to), "{to:?}");
        }
    }

    #[test]
    fn failed_cannot_silently_complete() {
        // Failed must go through RolledBack or Archived — never Completed.
        assert!(!TaskState::Failed.can_transition_to(TaskState::Completed));
        assert!(TaskState::Failed.can_transition_to(TaskState::RolledBack));
        assert!(TaskState::Failed.can_transition_to(TaskState::Archived));
    }

    #[test]
    fn blocked_states_only_unblock_to_active_or_fail() {
        for blocked in [TaskState::WaitingUser, TaskState::WaitingTool] {
            assert!(blocked.can_transition_to(TaskState::Active));
            assert!(blocked.can_transition_to(TaskState::Failed));
            assert!(!blocked.can_transition_to(TaskState::Completed));
            assert!(!blocked.can_transition_to(TaskState::Archived));
        }
    }

    #[test]
    fn paused_and_hibernated_resume_to_active() {
        assert!(TaskState::Paused.can_transition_to(TaskState::Active));
        assert!(TaskState::Hibernated.can_transition_to(TaskState::Active));
    }

    #[test]
    fn resume_context_requires_completeness_and_freshness() {
        let mut ctx = ResumeContext {
            trace_summary: "read files, ran test".into(),
            current_state: TaskState::Paused,
            open_risks: vec!["uncommitted diff".into()],
            next_action: "apply patch".into(),
            stale: false,
        };
        assert!(ctx.is_resumable());
        ctx.stale = true;
        assert!(!ctx.is_resumable(), "stale context is not resumable");
        ctx.stale = false;
        ctx.next_action = "  ".into();
        assert!(!ctx.is_resumable(), "no next action → not resumable");
        ctx.next_action = "apply patch".into();
        ctx.current_state = TaskState::Archived;
        assert!(!ctx.is_resumable(), "terminal state → not resumable");
    }

    #[test]
    fn state_and_step_serialize() {
        assert_eq!(
            serde_json::to_string(&TaskState::RolledBack).unwrap(),
            "\"rolled_back\""
        );
        assert_eq!(
            serde_json::to_string(&LifecycleStep::CommitRollback).unwrap(),
            "\"commit-rollback\""
        );
    }
}
