//! `sovereign-cockpit-snapshot-toolbar` — replay scrubber.
//!
//! Ordered snapshot list + current index + playback state.
//! play/pause/step_forward/step_back/jump_to mutators.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Snapshot {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Wall-clock unix seconds.
    pub at_unix: u64,
}

/// Playback state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PlaybackState {
    /// Paused.
    Paused,
    /// Playing.
    Playing,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SnapshotToolbar {
    /// Schema version.
    pub schema_version: String,
    /// Snapshots in time order.
    pub snapshots: Vec<Snapshot>,
    /// Current 0-based index.
    pub current: usize,
    /// Playback.
    pub playback: PlaybackState,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToolbarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty snapshots.
    #[error("snapshots empty")]
    EmptySnapshots,
    /// Empty id.
    #[error("snapshot id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate snapshot id: {0}")]
    DuplicateId(String),
    /// Out of range index.
    #[error("index {0} out of range (len {1})")]
    OutOfRange(usize, usize),
    /// At edge (cannot step further).
    #[error("at edge")]
    AtEdge,
}

impl SnapshotToolbar {
    /// New (paused at index 0).
    pub fn new(snapshots: Vec<Snapshot>) -> Result<Self, ToolbarError> {
        check_snapshots(&snapshots)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            snapshots,
            current: 0,
            playback: PlaybackState::Paused,
        })
    }

    /// Step forward.
    pub fn step_forward(&mut self) -> Result<(), ToolbarError> {
        if self.current + 1 >= self.snapshots.len() {
            return Err(ToolbarError::AtEdge);
        }
        self.current += 1;
        Ok(())
    }

    /// Step back.
    pub fn step_back(&mut self) -> Result<(), ToolbarError> {
        if self.current == 0 {
            return Err(ToolbarError::AtEdge);
        }
        self.current -= 1;
        Ok(())
    }

    /// Jump.
    pub fn jump_to(&mut self, idx: usize) -> Result<(), ToolbarError> {
        if idx >= self.snapshots.len() {
            return Err(ToolbarError::OutOfRange(idx, self.snapshots.len()));
        }
        self.current = idx;
        Ok(())
    }

    /// Play.
    pub fn play(&mut self) {
        self.playback = PlaybackState::Playing;
    }

    /// Pause.
    pub fn pause(&mut self) {
        self.playback = PlaybackState::Paused;
    }

    /// Toggle play/pause.
    pub fn toggle(&mut self) {
        self.playback = match self.playback {
            PlaybackState::Paused => PlaybackState::Playing,
            PlaybackState::Playing => PlaybackState::Paused,
        };
    }

    /// Current snapshot.
    pub fn current_snapshot(&self) -> &Snapshot {
        &self.snapshots[self.current]
    }

    /// Progress 0..=100.
    pub fn progress_pct(&self) -> u8 {
        if self.snapshots.len() <= 1 {
            return 100;
        }
        ((self.current as u64 * 100) / (self.snapshots.len() - 1) as u64) as u8
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToolbarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToolbarError::SchemaMismatch);
        }
        check_snapshots(&self.snapshots)?;
        if self.current >= self.snapshots.len() {
            return Err(ToolbarError::OutOfRange(self.current, self.snapshots.len()));
        }
        Ok(())
    }
}

fn check_snapshots(s: &[Snapshot]) -> Result<(), ToolbarError> {
    if s.is_empty() {
        return Err(ToolbarError::EmptySnapshots);
    }
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for x in s {
        if x.id.is_empty() {
            return Err(ToolbarError::EmptyId);
        }
        if !seen.insert(x.id.as_str()) {
            return Err(ToolbarError::DuplicateId(x.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snap(id: &str, at: u64) -> Snapshot {
        Snapshot {
            id: id.into(),
            label: format!("L-{id}"),
            at_unix: at,
        }
    }

    #[test]
    fn empty_snapshots_rejected() {
        assert!(matches!(
            SnapshotToolbar::new(vec![]).unwrap_err(),
            ToolbarError::EmptySnapshots
        ));
    }

    #[test]
    fn duplicate_rejected() {
        assert!(matches!(
            SnapshotToolbar::new(vec![snap("a", 1), snap("a", 2)]).unwrap_err(),
            ToolbarError::DuplicateId(_)
        ));
    }

    #[test]
    fn initial_index_zero_paused() {
        let t = SnapshotToolbar::new(vec![snap("a", 1)]).unwrap();
        assert_eq!(t.current, 0);
        assert_eq!(t.playback, PlaybackState::Paused);
    }

    #[test]
    fn step_forward() {
        let mut t = SnapshotToolbar::new(vec![snap("a", 1), snap("b", 2)]).unwrap();
        t.step_forward().unwrap();
        assert_eq!(t.current, 1);
        assert!(matches!(
            t.step_forward().unwrap_err(),
            ToolbarError::AtEdge
        ));
    }

    #[test]
    fn step_back() {
        let mut t = SnapshotToolbar::new(vec![snap("a", 1), snap("b", 2)]).unwrap();
        t.step_forward().unwrap();
        t.step_back().unwrap();
        assert_eq!(t.current, 0);
        assert!(matches!(t.step_back().unwrap_err(), ToolbarError::AtEdge));
    }

    #[test]
    fn jump_to() {
        let mut t = SnapshotToolbar::new(vec![snap("a", 1), snap("b", 2), snap("c", 3)]).unwrap();
        t.jump_to(2).unwrap();
        assert_eq!(t.current_snapshot().id, "c");
        assert!(matches!(
            t.jump_to(99).unwrap_err(),
            ToolbarError::OutOfRange(_, _)
        ));
    }

    #[test]
    fn toggle_play_pause() {
        let mut t = SnapshotToolbar::new(vec![snap("a", 1)]).unwrap();
        t.toggle();
        assert_eq!(t.playback, PlaybackState::Playing);
        t.toggle();
        assert_eq!(t.playback, PlaybackState::Paused);
    }

    #[test]
    fn progress_pct_full_range() {
        let mut t = SnapshotToolbar::new(vec![snap("a", 1), snap("b", 2), snap("c", 3)]).unwrap();
        assert_eq!(t.progress_pct(), 0);
        t.step_forward().unwrap();
        assert_eq!(t.progress_pct(), 50);
        t.step_forward().unwrap();
        assert_eq!(t.progress_pct(), 100);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = SnapshotToolbar::new(vec![snap("a", 1)]).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            ToolbarError::SchemaMismatch
        ));
    }

    #[test]
    fn playback_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&PlaybackState::Playing).unwrap(),
            "\"playing\""
        );
    }

    #[test]
    fn toolbar_serde_roundtrip() {
        let t = SnapshotToolbar::new(vec![snap("a", 1), snap("b", 2)]).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: SnapshotToolbar = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
