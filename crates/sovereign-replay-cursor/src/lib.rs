//! `sovereign-replay-cursor` — turn-walking cursor for replay sessions.
//!
//! A `ReplayCursor` walks a `ConversationThread` under
//! `ExecutionMode::Replay`. Supports:
//! - `step()` — advance one turn
//! - `pause()` / `resume()`
//! - `jump_to(idx)` — seek
//! - optional `breakpoint_role` — auto-pause when the next turn matches
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_conversation_thread::{ConversationThread, Turn, TurnRole};
use sovereign_execution_mode_registry::ExecutionMode;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Playback state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PlaybackState {
    /// Cursor not started.
    Idle,
    /// Currently advancing.
    Running,
    /// Paused on breakpoint or manual pause.
    Paused,
    /// All turns consumed.
    Finished,
}

/// The cursor.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplayCursor {
    /// Schema version.
    pub schema_version: String,
    /// Thread id this cursor walks.
    pub thread_id: String,
    /// Total turns in the thread.
    pub total_turns: u32,
    /// Next turn index to play (0..=total_turns).
    pub next_index: u32,
    /// Current playback state.
    pub state: PlaybackState,
    /// Optional breakpoint role — pause before any turn of this role.
    pub breakpoint_role: Option<TurnRole>,
    /// Mode the cursor is operating under (must be Replay for advance).
    pub mode: ExecutionMode,
    /// Skip the next breakpoint check (set after `resume()` so we advance past).
    pub skip_next_breakpoint: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CursorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Cursor's thread_id doesn't match the supplied thread.
    #[error("thread mismatch: cursor={cursor} thread={thread}")]
    ThreadMismatch {
        /// cursor.
        cursor: String,
        /// thread.
        thread: String,
    },
    /// Cursor's total_turns doesn't match thread.
    #[error("turn count mismatch: cursor={cursor} thread={thread}")]
    CountMismatch {
        /// cursor.
        cursor: u32,
        /// thread.
        thread: u32,
    },
    /// Operation requires Replay mode.
    #[error("operation requires Replay mode (got {0:?})")]
    NotReplayMode(ExecutionMode),
    /// Jump out of bounds.
    #[error("jump_to {idx} out of bounds (total {total})")]
    JumpOutOfBounds {
        /// idx.
        idx: u32,
        /// total.
        total: u32,
    },
    /// Cursor finished — no more turns.
    #[error("cursor finished")]
    Finished,
    /// Cursor paused — call resume() first.
    #[error("cursor paused")]
    Paused,
}

impl ReplayCursor {
    /// Open a cursor over a thread under the given mode.
    /// The mode must be `ExecutionMode::Replay`.
    pub fn open(thread: &ConversationThread, mode: ExecutionMode) -> Result<Self, CursorError> {
        if mode != ExecutionMode::Replay {
            return Err(CursorError::NotReplayMode(mode));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            thread_id: thread.thread_id.clone(),
            total_turns: thread.turns.len() as u32,
            next_index: 0,
            state: PlaybackState::Idle,
            breakpoint_role: None,
            mode,
            skip_next_breakpoint: false,
        })
    }

    /// Set breakpoint role.
    pub fn with_breakpoint(mut self, role: TurnRole) -> Self {
        self.breakpoint_role = Some(role);
        self
    }

    /// Pause.
    pub fn pause(&mut self) {
        if self.state == PlaybackState::Running {
            self.state = PlaybackState::Paused;
        }
    }

    /// Resume from Paused. The next `step()` will not re-arm the breakpoint
    /// on the same turn that caused the pause.
    pub fn resume(&mut self) {
        if self.state == PlaybackState::Paused {
            self.state = PlaybackState::Running;
            self.skip_next_breakpoint = true;
        }
    }

    /// Step one turn forward.
    /// Returns the played `Turn` clone, or `None` if at end.
    /// Honors the breakpoint role (pauses before a matching role).
    pub fn step<'a>(
        &mut self,
        thread: &'a ConversationThread,
    ) -> Result<Option<&'a Turn>, CursorError> {
        self.validate(thread)?;
        if self.mode != ExecutionMode::Replay {
            return Err(CursorError::NotReplayMode(self.mode));
        }
        if self.state == PlaybackState::Paused {
            return Err(CursorError::Paused);
        }
        if self.state == PlaybackState::Finished || self.next_index >= self.total_turns {
            return Ok(None);
        }
        let idx = self.next_index as usize;
        let next = &thread.turns[idx];
        if let Some(bp) = self.breakpoint_role
            && next.role == bp
            && !self.skip_next_breakpoint
        {
            self.state = PlaybackState::Paused;
            return Err(CursorError::Paused);
        }
        // Advance.
        self.skip_next_breakpoint = false;
        self.state = PlaybackState::Running;
        self.next_index += 1;
        if self.next_index == self.total_turns {
            self.state = PlaybackState::Finished;
        }
        Ok(Some(next))
    }

    /// Seek to an arbitrary index.
    pub fn jump_to(&mut self, idx: u32) -> Result<(), CursorError> {
        if idx > self.total_turns {
            return Err(CursorError::JumpOutOfBounds {
                idx,
                total: self.total_turns,
            });
        }
        self.next_index = idx;
        self.state = if idx == self.total_turns {
            PlaybackState::Finished
        } else {
            PlaybackState::Running
        };
        Ok(())
    }

    /// True if cursor is at end.
    pub fn is_finished(&self) -> bool {
        self.state == PlaybackState::Finished || self.next_index >= self.total_turns
    }

    /// Validate that the cursor is consistent with the supplied thread.
    pub fn validate(&self, thread: &ConversationThread) -> Result<(), CursorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CursorError::SchemaMismatch);
        }
        if self.thread_id != thread.thread_id {
            return Err(CursorError::ThreadMismatch {
                cursor: self.thread_id.clone(),
                thread: thread.thread_id.clone(),
            });
        }
        if self.total_turns as usize != thread.turns.len() {
            return Err(CursorError::CountMismatch {
                cursor: self.total_turns,
                thread: thread.turns.len() as u32,
            });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn turn(role: TurnRole, idx: u32) -> Turn {
        Turn {
            index: idx,
            role,
            tokens_in: 0,
            tokens_out: 0,
            provider: "local:rocm-4090".into(),
            started_at: "2026-05-19T03:00:00Z".into(),
            completed_at: "2026-05-19T03:00:01Z".into(),
            branch_id: "main".into(),
            text: String::new(),
        }
    }

    fn thread_3() -> ConversationThread {
        let mut t = ConversationThread::new("th-1", "2026-05-19T03:00:00Z");
        t.append(turn(TurnRole::Operator, 0));
        t.append(turn(TurnRole::Model, 0));
        t.append(turn(TurnRole::Tool, 0));
        t
    }

    #[test]
    fn open_requires_replay_mode() {
        let th = thread_3();
        assert!(matches!(
            ReplayCursor::open(&th, ExecutionMode::Execute).unwrap_err(),
            CursorError::NotReplayMode(_)
        ));
    }

    #[test]
    fn step_walks_all_turns() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay).unwrap();
        for _ in 0..3 {
            assert!(c.step(&th).unwrap().is_some());
        }
        assert!(c.is_finished());
        assert!(c.step(&th).unwrap().is_none());
    }

    #[test]
    fn breakpoint_pauses_before_role() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay)
            .unwrap()
            .with_breakpoint(TurnRole::Tool);
        // Operator advances, Model advances, then Tool triggers breakpoint pause.
        assert!(c.step(&th).unwrap().is_some()); // Operator
        assert!(c.step(&th).unwrap().is_some()); // Model
        // Next is Tool → breakpoint pauses
        let err = c.step(&th).unwrap_err();
        assert!(matches!(err, CursorError::Paused));
        assert_eq!(c.state, PlaybackState::Paused);
    }

    #[test]
    fn resume_after_breakpoint_advances() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay)
            .unwrap()
            .with_breakpoint(TurnRole::Tool);
        c.step(&th).unwrap();
        c.step(&th).unwrap();
        c.step(&th).unwrap_err(); // breakpoint
        c.resume();
        let t = c.step(&th).unwrap().unwrap();
        assert_eq!(t.role, TurnRole::Tool);
    }

    #[test]
    fn jump_to_seeks() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay).unwrap();
        c.jump_to(2).unwrap();
        assert_eq!(c.next_index, 2);
        let t = c.step(&th).unwrap().unwrap();
        assert_eq!(t.role, TurnRole::Tool);
    }

    #[test]
    fn jump_out_of_bounds_rejected() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay).unwrap();
        assert!(matches!(
            c.jump_to(10).unwrap_err(),
            CursorError::JumpOutOfBounds { .. }
        ));
    }

    #[test]
    fn pause_then_step_blocked() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay).unwrap();
        c.step(&th).unwrap();
        c.pause();
        assert!(matches!(c.step(&th).unwrap_err(), CursorError::Paused));
    }

    #[test]
    fn validate_mismatch_caught() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay).unwrap();
        c.thread_id = "wrong".into();
        assert!(matches!(
            c.validate(&th).unwrap_err(),
            CursorError::ThreadMismatch { .. }
        ));
    }

    #[test]
    fn validate_count_mismatch_caught() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay).unwrap();
        c.total_turns = 99;
        assert!(matches!(
            c.validate(&th).unwrap_err(),
            CursorError::CountMismatch {
                cursor: 99,
                thread: 3
            }
        ));
    }

    #[test]
    fn jump_to_end_marks_finished() {
        let th = thread_3();
        let mut c = ReplayCursor::open(&th, ExecutionMode::Replay).unwrap();
        c.jump_to(3).unwrap();
        assert!(c.is_finished());
    }

    #[test]
    fn cursor_serde_roundtrip() {
        let th = thread_3();
        let c = ReplayCursor::open(&th, ExecutionMode::Replay)
            .unwrap()
            .with_breakpoint(TurnRole::Operator);
        let j = serde_json::to_string(&c).unwrap();
        let back: ReplayCursor = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
