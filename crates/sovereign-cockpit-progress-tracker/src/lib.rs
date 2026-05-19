//! `sovereign-cockpit-progress-tracker` — running task progress state.
//!
//! Each `Task` carries (id, label, kind, progress, eta_seconds,
//! started_at). Pure UX. The cockpit renders a tray + per-task overlays.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Progress kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ProgressKind {
    /// Determinate (0..100).
    Determinate,
    /// Indeterminate (spinner).
    Indeterminate,
}

/// One task.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Task {
    /// Id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Kind.
    pub kind: ProgressKind,
    /// Progress percentage (0..=100) — meaningful only for Determinate.
    pub progress: u8,
    /// Estimated remaining seconds (0 = unknown).
    pub eta_seconds: u32,
    /// ISO-8601 UTC started_at.
    pub started_at: String,
}

/// Tracker envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProgressTracker {
    /// Schema version.
    pub schema_version: String,
    /// Tasks.
    pub tasks: Vec<Task>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ProgressError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("task id empty")]
    EmptyId,
    /// Empty label.
    #[error("task {0} label empty")]
    EmptyLabel(String),
    /// Progress > 100.
    #[error("task {id} progress {progress} > 100")]
    ProgressOutOfRange {
        /// id.
        id: String,
        /// progress.
        progress: u8,
    },
    /// Duplicate.
    #[error("duplicate task id: {0}")]
    DuplicateId(String),
    /// Unknown task.
    #[error("unknown task id: {0}")]
    Unknown(String),
}

impl ProgressTracker {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tasks: Vec::new(),
        }
    }

    /// Start a task.
    pub fn start(&mut self, task: Task) -> Result<(), ProgressError> {
        check_shape(&task)?;
        if self.tasks.iter().any(|t| t.id == task.id) {
            return Err(ProgressError::DuplicateId(task.id));
        }
        self.tasks.push(task);
        Ok(())
    }

    /// Update progress for a Determinate task.
    pub fn update_progress(&mut self, id: &str, progress: u8, eta_seconds: u32) -> Result<(), ProgressError> {
        if progress > 100 {
            return Err(ProgressError::ProgressOutOfRange { id: id.into(), progress });
        }
        let task = self.tasks.iter_mut().find(|t| t.id == id)
            .ok_or_else(|| ProgressError::Unknown(id.into()))?;
        task.progress = progress;
        task.eta_seconds = eta_seconds;
        Ok(())
    }

    /// Finish a task — removes from tray.
    pub fn finish(&mut self, id: &str) -> Result<(), ProgressError> {
        let pos = self.tasks.iter().position(|t| t.id == id)
            .ok_or_else(|| ProgressError::Unknown(id.into()))?;
        self.tasks.remove(pos);
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, id: &str) -> Option<&Task> {
        self.tasks.iter().find(|t| t.id == id)
    }

    /// Average progress across Determinate tasks. 0 if none.
    pub fn average_progress(&self) -> u8 {
        let v: Vec<&Task> = self.tasks.iter().filter(|t| t.kind == ProgressKind::Determinate).collect();
        if v.is_empty() { return 0; }
        let sum: u32 = v.iter().map(|t| t.progress as u32).sum();
        (sum / v.len() as u32) as u8
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ProgressError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ProgressError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.tasks {
            check_shape(t)?;
            if !seen.insert(t.id.as_str()) {
                return Err(ProgressError::DuplicateId(t.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_shape(t: &Task) -> Result<(), ProgressError> {
    if t.id.is_empty() { return Err(ProgressError::EmptyId); }
    if t.label.is_empty() { return Err(ProgressError::EmptyLabel(t.id.clone())); }
    if t.progress > 100 {
        return Err(ProgressError::ProgressOutOfRange { id: t.id.clone(), progress: t.progress });
    }
    Ok(())
}

impl Default for ProgressTracker {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn task(id: &str, kind: ProgressKind) -> Task {
        Task {
            id: id.into(),
            label: format!("Task {id}"),
            kind,
            progress: 0,
            eta_seconds: 0,
            started_at: "2026-05-19T03:00:00Z".into(),
        }
    }

    #[test]
    fn empty_tracker_validates() {
        ProgressTracker::new().validate().unwrap();
    }

    #[test]
    fn start_finish_cycle() {
        let mut t = ProgressTracker::new();
        t.start(task("a", ProgressKind::Determinate)).unwrap();
        t.update_progress("a", 50, 30).unwrap();
        assert_eq!(t.get("a").unwrap().progress, 50);
        t.finish("a").unwrap();
        assert!(t.tasks.is_empty());
    }

    #[test]
    fn duplicate_start_rejected() {
        let mut t = ProgressTracker::new();
        t.start(task("a", ProgressKind::Determinate)).unwrap();
        assert!(matches!(t.start(task("a", ProgressKind::Determinate)).unwrap_err(),
            ProgressError::DuplicateId(_)));
    }

    #[test]
    fn unknown_update_rejected() {
        let mut t = ProgressTracker::new();
        assert!(matches!(t.update_progress("none", 10, 0).unwrap_err(),
            ProgressError::Unknown(_)));
    }

    #[test]
    fn progress_out_of_range_rejected() {
        let mut t = ProgressTracker::new();
        t.start(task("a", ProgressKind::Determinate)).unwrap();
        assert!(matches!(t.update_progress("a", 150, 0).unwrap_err(),
            ProgressError::ProgressOutOfRange { .. }));
    }

    #[test]
    fn empty_id_rejected() {
        let mut t = ProgressTracker::new();
        let mut bad = task("a", ProgressKind::Determinate);
        bad.id = String::new();
        assert!(matches!(t.start(bad).unwrap_err(), ProgressError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut t = ProgressTracker::new();
        let mut bad = task("a", ProgressKind::Determinate);
        bad.label = String::new();
        assert!(matches!(t.start(bad).unwrap_err(), ProgressError::EmptyLabel(_)));
    }

    #[test]
    fn average_progress_excludes_indeterminate() {
        let mut t = ProgressTracker::new();
        t.start(task("a", ProgressKind::Determinate)).unwrap();
        t.start(task("b", ProgressKind::Indeterminate)).unwrap();
        t.update_progress("a", 80, 0).unwrap();
        assert_eq!(t.average_progress(), 80);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = ProgressTracker::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), ProgressError::SchemaMismatch));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(serde_json::to_string(&ProgressKind::Determinate).unwrap(), "\"determinate\"");
        assert_eq!(serde_json::to_string(&ProgressKind::Indeterminate).unwrap(), "\"indeterminate\"");
    }

    #[test]
    fn tracker_serde_roundtrip() {
        let mut t = ProgressTracker::new();
        t.start(task("a", ProgressKind::Determinate)).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: ProgressTracker = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
