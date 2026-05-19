//! `sovereign-cockpit-vim-mode-indicator` — vim-mode status line.
//!
//! 5 modes (Normal/Insert/Visual/Command/Replace) + pending buffer.
//! display() returns the operator-facing status text.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Vim mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum VimMode {
    /// Normal.
    Normal,
    /// Insert.
    Insert,
    /// Visual.
    Visual,
    /// Command (`:`).
    Command,
    /// Replace.
    Replace,
}

impl VimMode {
    /// Short label.
    pub fn label(self) -> &'static str {
        match self {
            VimMode::Normal => "NORMAL",
            VimMode::Insert => "INSERT",
            VimMode::Visual => "VISUAL",
            VimMode::Command => "COMMAND",
            VimMode::Replace => "REPLACE",
        }
    }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct VimModeIndicator {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: VimMode,
    /// Pending command-line buffer (Command mode).
    pub command_buffer: String,
    /// Pending operator-count (Normal mode "3" before "dw").
    pub operator_count: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum VimError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad transition.
    #[error("cannot transition from {0:?} to {1:?} mid-command")]
    BadTransition(VimMode, VimMode),
}

impl VimModeIndicator {
    /// New (Normal).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: VimMode::Normal,
            command_buffer: String::new(),
            operator_count: 0,
        }
    }

    /// Switch mode (clears buffer + count).
    pub fn enter(&mut self, mode: VimMode) -> Result<(), VimError> {
        // Cannot go from Command mid-buffer to anything except Normal.
        if self.mode == VimMode::Command && !self.command_buffer.is_empty() && mode != VimMode::Normal {
            return Err(VimError::BadTransition(self.mode, mode));
        }
        self.mode = mode;
        self.command_buffer.clear();
        self.operator_count = 0;
        Ok(())
    }

    /// Append to command buffer (only valid in Command mode).
    pub fn append_command(&mut self, s: &str) {
        if self.mode == VimMode::Command {
            self.command_buffer.push_str(s);
        }
    }

    /// Bump operator count.
    pub fn bump_count(&mut self, n: u32) {
        if self.mode == VimMode::Normal {
            self.operator_count = self.operator_count.saturating_add(n);
        }
    }

    /// Display string for status line.
    pub fn display(&self) -> String {
        match self.mode {
            VimMode::Command => format!(":{}", self.command_buffer),
            VimMode::Normal if self.operator_count > 0 => format!("NORMAL  {}", self.operator_count),
            _ => self.mode.label().to_string(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), VimError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(VimError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for VimModeIndicator {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_in_normal() {
        let v = VimModeIndicator::new();
        assert_eq!(v.mode, VimMode::Normal);
        assert_eq!(v.display(), "NORMAL");
    }

    #[test]
    fn enter_insert() {
        let mut v = VimModeIndicator::new();
        v.enter(VimMode::Insert).unwrap();
        assert_eq!(v.display(), "INSERT");
    }

    #[test]
    fn command_buffer_builds() {
        let mut v = VimModeIndicator::new();
        v.enter(VimMode::Command).unwrap();
        v.append_command("wq");
        assert_eq!(v.display(), ":wq");
    }

    #[test]
    fn bump_count_only_in_normal() {
        let mut v = VimModeIndicator::new();
        v.bump_count(3);
        assert_eq!(v.operator_count, 3);
        assert_eq!(v.display(), "NORMAL  3");
        v.enter(VimMode::Insert).unwrap();
        v.bump_count(5);
        assert_eq!(v.operator_count, 0); // cleared on enter
    }

    #[test]
    fn enter_clears_buffer() {
        let mut v = VimModeIndicator::new();
        v.enter(VimMode::Command).unwrap();
        v.append_command("q!");
        v.enter(VimMode::Normal).unwrap();
        assert_eq!(v.display(), "NORMAL");
    }

    #[test]
    fn mid_command_bad_transition_rejected() {
        let mut v = VimModeIndicator::new();
        v.enter(VimMode::Command).unwrap();
        v.append_command("partial");
        assert!(matches!(v.enter(VimMode::Insert).unwrap_err(), VimError::BadTransition(_, _)));
    }

    #[test]
    fn command_to_normal_allowed() {
        let mut v = VimModeIndicator::new();
        v.enter(VimMode::Command).unwrap();
        v.append_command("anything");
        v.enter(VimMode::Normal).unwrap();
        assert_eq!(v.mode, VimMode::Normal);
    }

    #[test]
    fn append_outside_command_noop() {
        let mut v = VimModeIndicator::new();
        v.append_command("wq");
        assert!(v.command_buffer.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut v = VimModeIndicator::new();
        v.schema_version = "9.9.9".into();
        assert!(matches!(v.validate().unwrap_err(), VimError::SchemaMismatch));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(serde_json::to_string(&VimMode::Visual).unwrap(), "\"visual\"");
    }

    #[test]
    fn indicator_serde_roundtrip() {
        let mut v = VimModeIndicator::new();
        v.enter(VimMode::Command).unwrap();
        v.append_command("set nu");
        let j = serde_json::to_string(&v).unwrap();
        let back: VimModeIndicator = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }
}
