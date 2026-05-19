//! `sovereign-cockpit-command-palette` — command catalog for Ctrl-K overlay.
//!
//! Each `Command` declares (id, label, group, allowed_modes, action_id).
//! The cockpit surfaces them grouped by `group`; the dispatcher uses
//! `action_id` to fire. Supports fuzzy substring matching on label.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_execution_mode_registry::ExecutionMode;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Command group.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CommandGroup {
    /// Mode switching.
    Mode,
    /// Conversation / thread.
    Conversation,
    /// Replay session.
    Replay,
    /// Tool invocation.
    Tool,
    /// Dashboard navigation.
    Dashboard,
    /// Workspace folder operations.
    Workspace,
    /// Settings / personalization.
    Settings,
}

/// One command.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Command {
    /// Unique id.
    pub id: String,
    /// Label shown in palette (non-empty).
    pub label: String,
    /// Group.
    pub group: CommandGroup,
    /// Modes in which this command appears.
    pub allowed_modes: Vec<ExecutionMode>,
    /// Action id the dispatcher fires.
    pub action_id: String,
}

/// Catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CommandPalette {
    /// Schema version.
    pub schema_version: String,
    /// Commands.
    pub commands: Vec<Command>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PaletteError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("command id empty")]
    EmptyId,
    /// Empty label.
    #[error("command {0} label empty")]
    EmptyLabel(String),
    /// Empty action_id.
    #[error("command {0} action_id empty")]
    EmptyActionId(String),
    /// allowed_modes empty.
    #[error("command {0} has no allowed_modes")]
    NoModes(String),
    /// Duplicate id.
    #[error("duplicate command id: {0}")]
    DuplicateId(String),
}

impl CommandPalette {
    /// Canonical palette — 16 baked-in commands across all groups.
    pub fn canonical() -> Self {
        let all_modes = vec![
            ExecutionMode::Plan, ExecutionMode::DryRun, ExecutionMode::Shadow,
            ExecutionMode::Sandbox, ExecutionMode::Execute, ExecutionMode::Replay,
            ExecutionMode::Debug,
        ];
        let commands = vec![
            Command { id: "mode.plan".into(), label: "Switch to Plan mode".into(), group: CommandGroup::Mode, allowed_modes: all_modes.clone(), action_id: "mode-switch:plan".into() },
            Command { id: "mode.dry-run".into(), label: "Switch to Dry-Run mode".into(), group: CommandGroup::Mode, allowed_modes: all_modes.clone(), action_id: "mode-switch:dry-run".into() },
            Command { id: "mode.sandbox".into(), label: "Switch to Sandbox mode".into(), group: CommandGroup::Mode, allowed_modes: all_modes.clone(), action_id: "mode-switch:sandbox".into() },
            Command { id: "mode.execute".into(), label: "Switch to Execute mode".into(), group: CommandGroup::Mode, allowed_modes: all_modes.clone(), action_id: "mode-switch:execute".into() },
            Command { id: "mode.replay".into(), label: "Open Replay session".into(), group: CommandGroup::Mode, allowed_modes: all_modes.clone(), action_id: "mode-switch:replay".into() },
            Command { id: "conv.new".into(), label: "New conversation".into(), group: CommandGroup::Conversation, allowed_modes: all_modes.clone(), action_id: "conv:new".into() },
            Command { id: "conv.search".into(), label: "Search conversations".into(), group: CommandGroup::Conversation, allowed_modes: all_modes.clone(), action_id: "conv:search".into() },
            Command { id: "conv.fork".into(), label: "Fork conversation branch".into(), group: CommandGroup::Conversation, allowed_modes: all_modes.clone(), action_id: "conv:fork".into() },
            Command { id: "replay.step".into(), label: "Step one turn".into(), group: CommandGroup::Replay, allowed_modes: vec![ExecutionMode::Replay, ExecutionMode::Debug], action_id: "replay:step".into() },
            Command { id: "replay.pause".into(), label: "Pause replay".into(), group: CommandGroup::Replay, allowed_modes: vec![ExecutionMode::Replay, ExecutionMode::Debug], action_id: "replay:pause".into() },
            Command { id: "tool.shell".into(), label: "Run shell command".into(), group: CommandGroup::Tool, allowed_modes: vec![ExecutionMode::Sandbox, ExecutionMode::Execute, ExecutionMode::Debug], action_id: "tool:shell".into() },
            Command { id: "tool.fs-read".into(), label: "Read file".into(), group: CommandGroup::Tool, allowed_modes: all_modes.clone(), action_id: "tool:fs-read".into() },
            Command { id: "dash.banner".into(), label: "Show banner state".into(), group: CommandGroup::Dashboard, allowed_modes: all_modes.clone(), action_id: "dash:banner".into() },
            Command { id: "dash.alerts".into(), label: "Show alerts".into(), group: CommandGroup::Dashboard, allowed_modes: all_modes.clone(), action_id: "dash:alerts".into() },
            Command { id: "workspace.add".into(), label: "Add workspace folder".into(), group: CommandGroup::Workspace, allowed_modes: all_modes.clone(), action_id: "workspace:add".into() },
            Command { id: "settings.toggles".into(), label: "Open toggles".into(), group: CommandGroup::Settings, allowed_modes: all_modes, action_id: "settings:toggles".into() },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            commands,
        }
    }

    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            commands: Vec::new(),
        }
    }

    /// Add a command.
    pub fn add(&mut self, c: Command) -> Result<(), PaletteError> {
        if c.id.is_empty() { return Err(PaletteError::EmptyId); }
        if c.label.is_empty() { return Err(PaletteError::EmptyLabel(c.id)); }
        if c.action_id.is_empty() { return Err(PaletteError::EmptyActionId(c.id)); }
        if c.allowed_modes.is_empty() { return Err(PaletteError::NoModes(c.id)); }
        if self.commands.iter().any(|x| x.id == c.id) {
            return Err(PaletteError::DuplicateId(c.id));
        }
        self.commands.push(c);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PaletteError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PaletteError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for c in &self.commands {
            if c.id.is_empty() { return Err(PaletteError::EmptyId); }
            if c.label.is_empty() { return Err(PaletteError::EmptyLabel(c.id.clone())); }
            if c.action_id.is_empty() { return Err(PaletteError::EmptyActionId(c.id.clone())); }
            if c.allowed_modes.is_empty() { return Err(PaletteError::NoModes(c.id.clone())); }
            if !seen.insert(c.id.as_str()) {
                return Err(PaletteError::DuplicateId(c.id.clone()));
            }
        }
        Ok(())
    }

    /// Filter by (mode, fuzzy substring on label, case-insensitive).
    pub fn fuzzy(&self, mode: ExecutionMode, needle: &str) -> Vec<&Command> {
        let n = needle.to_ascii_lowercase();
        self.commands.iter()
            .filter(|c| c.allowed_modes.contains(&mode))
            .filter(|c| n.is_empty() || c.label.to_ascii_lowercase().contains(&n))
            .collect()
    }

    /// Available commands in mode.
    pub fn available(&self, mode: ExecutionMode) -> Vec<&Command> {
        self.commands.iter().filter(|c| c.allowed_modes.contains(&mode)).collect()
    }

    /// Lookup by id.
    pub fn get(&self, id: &str) -> Option<&Command> {
        self.commands.iter().find(|c| c.id == id)
    }
}

impl Default for CommandPalette {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        CommandPalette::canonical().validate().unwrap();
    }

    #[test]
    fn canonical_has_sixteen_commands() {
        assert_eq!(CommandPalette::canonical().commands.len(), 16);
    }

    #[test]
    fn fuzzy_matches_substring() {
        let p = CommandPalette::canonical();
        let r = p.fuzzy(ExecutionMode::Plan, "switch");
        // Several "Switch to X mode" commands.
        assert!(r.len() >= 4);
    }

    #[test]
    fn fuzzy_empty_needle_returns_mode_filtered() {
        let p = CommandPalette::canonical();
        let r = p.fuzzy(ExecutionMode::Plan, "");
        let avail = p.available(ExecutionMode::Plan);
        assert_eq!(r.len(), avail.len());
    }

    #[test]
    fn replay_only_commands_hidden_in_plan() {
        let p = CommandPalette::canonical();
        let avail = p.available(ExecutionMode::Plan);
        assert!(!avail.iter().any(|c| c.id == "replay.step"));
    }

    #[test]
    fn shell_visible_only_in_sandbox_execute_debug() {
        let p = CommandPalette::canonical();
        assert!(p.available(ExecutionMode::Plan).iter().all(|c| c.id != "tool.shell"));
        assert!(p.available(ExecutionMode::Sandbox).iter().any(|c| c.id == "tool.shell"));
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut p = CommandPalette::new();
        let c = Command {
            id: "x".into(), label: "X".into(), group: CommandGroup::Tool,
            allowed_modes: vec![ExecutionMode::Plan], action_id: "x".into(),
        };
        p.add(c.clone()).unwrap();
        assert!(matches!(p.add(c).unwrap_err(), PaletteError::DuplicateId(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut p = CommandPalette::new();
        let c = Command {
            id: String::new(), label: "X".into(), group: CommandGroup::Tool,
            allowed_modes: vec![ExecutionMode::Plan], action_id: "x".into(),
        };
        assert!(matches!(p.add(c).unwrap_err(), PaletteError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut p = CommandPalette::new();
        let c = Command {
            id: "x".into(), label: String::new(), group: CommandGroup::Tool,
            allowed_modes: vec![ExecutionMode::Plan], action_id: "x".into(),
        };
        assert!(matches!(p.add(c).unwrap_err(), PaletteError::EmptyLabel(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = CommandPalette::canonical();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), PaletteError::SchemaMismatch));
    }

    #[test]
    fn group_serde_kebab() {
        assert_eq!(serde_json::to_string(&CommandGroup::Conversation).unwrap(), "\"conversation\"");
        assert_eq!(serde_json::to_string(&CommandGroup::Replay).unwrap(), "\"replay\"");
        assert_eq!(serde_json::to_string(&CommandGroup::Workspace).unwrap(), "\"workspace\"");
    }

    #[test]
    fn palette_serde_roundtrip() {
        let p = CommandPalette::canonical();
        let j = serde_json::to_string(&p).unwrap();
        let back: CommandPalette = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
