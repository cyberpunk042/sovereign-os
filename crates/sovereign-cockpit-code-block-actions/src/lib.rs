//! `sovereign-cockpit-code-block-actions` — per-block actions.
//!
//! Each rendered code block has a `Block { id, lang, wrap_lines,
//! expanded, copyable, runnable }`. Available actions depend on
//! flags: `Copy` is offered when `copyable`; `Wrap`/`Unwrap`
//! toggles `wrap_lines`; `Expand`/`Collapse` toggles `expanded`;
//! `Run` is offered when `runnable`. `actions_for(block)` returns
//! the action labels in display order.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One block.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Block {
    /// Stable id.
    pub id: String,
    /// Language tag.
    pub lang: String,
    /// Wrap lines?
    pub wrap_lines: bool,
    /// Expanded (else collapsed)?
    pub expanded: bool,
    /// Copy action available?
    pub copyable: bool,
    /// Run action available?
    pub runnable: bool,
    /// Total copies (telemetry).
    pub copies: u64,
    /// Total runs (telemetry).
    pub runs: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CodeBlockActions {
    /// Schema version.
    pub schema_version: String,
    /// id → block.
    pub blocks: BTreeMap<String, Block>,
}

/// Action label.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Action {
    /// Copy.
    Copy,
    /// Wrap lines.
    Wrap,
    /// Unwrap (stop wrapping).
    Unwrap,
    /// Expand.
    Expand,
    /// Collapse.
    Collapse,
    /// Run.
    Run,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BlockError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("block id empty")]
    EmptyId,
    /// Empty lang.
    #[error("block lang empty")]
    EmptyLang,
    /// Duplicate.
    #[error("duplicate block id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown block: {0}")]
    UnknownBlock(String),
    /// Action not allowed.
    #[error("action {action:?} not available on block {id}")]
    ActionNotAvailable {
        /// id.
        id: String,
        /// action.
        action: Action,
    },
}

impl CodeBlockActions {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            blocks: BTreeMap::new(),
        }
    }

    /// Register a block.
    pub fn register(&mut self, block: Block) -> Result<(), BlockError> {
        if block.id.is_empty() {
            return Err(BlockError::EmptyId);
        }
        if block.lang.is_empty() {
            return Err(BlockError::EmptyLang);
        }
        if self.blocks.contains_key(&block.id) {
            return Err(BlockError::DuplicateId(block.id));
        }
        self.blocks.insert(block.id.clone(), block);
        Ok(())
    }

    /// Available actions for a block.
    pub fn actions_for(&self, id: &str) -> Vec<Action> {
        let Some(b) = self.blocks.get(id) else {
            return Vec::new();
        };
        let mut out = Vec::with_capacity(4);
        if b.copyable {
            out.push(Action::Copy);
        }
        out.push(if b.wrap_lines {
            Action::Unwrap
        } else {
            Action::Wrap
        });
        out.push(if b.expanded {
            Action::Collapse
        } else {
            Action::Expand
        });
        if b.runnable {
            out.push(Action::Run);
        }
        out
    }

    /// Apply.
    pub fn apply(&mut self, id: &str, action: Action) -> Result<(), BlockError> {
        let b = self
            .blocks
            .get_mut(id)
            .ok_or_else(|| BlockError::UnknownBlock(id.into()))?;
        match action {
            Action::Copy => {
                if !b.copyable {
                    return Err(BlockError::ActionNotAvailable {
                        id: id.into(),
                        action,
                    });
                }
                b.copies = b.copies.saturating_add(1);
            }
            Action::Wrap => {
                b.wrap_lines = true;
            }
            Action::Unwrap => {
                b.wrap_lines = false;
            }
            Action::Expand => {
                b.expanded = true;
            }
            Action::Collapse => {
                b.expanded = false;
            }
            Action::Run => {
                if !b.runnable {
                    return Err(BlockError::ActionNotAvailable {
                        id: id.into(),
                        action,
                    });
                }
                b.runs = b.runs.saturating_add(1);
            }
        }
        Ok(())
    }

    /// Remove a block.
    pub fn remove(&mut self, id: &str) -> bool {
        self.blocks.remove(id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BlockError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BlockError::SchemaMismatch);
        }
        for (id, b) in &self.blocks {
            if id.is_empty() {
                return Err(BlockError::EmptyId);
            }
            if b.lang.is_empty() {
                return Err(BlockError::EmptyLang);
            }
        }
        Ok(())
    }
}

impl Default for CodeBlockActions {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b(id: &str, copyable: bool, runnable: bool) -> Block {
        Block {
            id: id.into(),
            lang: "rust".into(),
            wrap_lines: false,
            expanded: true,
            copyable,
            runnable,
            copies: 0,
            runs: 0,
        }
    }

    #[test]
    fn actions_full() {
        let mut s = CodeBlockActions::new();
        s.register(b("b1", true, true)).unwrap();
        let a = s.actions_for("b1");
        assert_eq!(
            a,
            vec![Action::Copy, Action::Wrap, Action::Collapse, Action::Run]
        );
    }

    #[test]
    fn actions_minimal() {
        let mut s = CodeBlockActions::new();
        s.register(b("b1", false, false)).unwrap();
        let a = s.actions_for("b1");
        assert_eq!(a, vec![Action::Wrap, Action::Collapse]);
    }

    #[test]
    fn wrap_unwrap_toggles() {
        let mut s = CodeBlockActions::new();
        s.register(b("b1", false, false)).unwrap();
        s.apply("b1", Action::Wrap).unwrap();
        assert!(s.blocks["b1"].wrap_lines);
        // Now offered Unwrap.
        assert_eq!(s.actions_for("b1")[0], Action::Unwrap);
        s.apply("b1", Action::Unwrap).unwrap();
        assert!(!s.blocks["b1"].wrap_lines);
    }

    #[test]
    fn copy_unavailable_errors() {
        let mut s = CodeBlockActions::new();
        s.register(b("b1", false, true)).unwrap();
        assert!(matches!(
            s.apply("b1", Action::Copy).unwrap_err(),
            BlockError::ActionNotAvailable { .. }
        ));
    }

    #[test]
    fn run_unavailable_errors() {
        let mut s = CodeBlockActions::new();
        s.register(b("b1", true, false)).unwrap();
        assert!(matches!(
            s.apply("b1", Action::Run).unwrap_err(),
            BlockError::ActionNotAvailable { .. }
        ));
    }

    #[test]
    fn telemetry_counters() {
        let mut s = CodeBlockActions::new();
        s.register(b("b1", true, true)).unwrap();
        s.apply("b1", Action::Copy).unwrap();
        s.apply("b1", Action::Copy).unwrap();
        s.apply("b1", Action::Run).unwrap();
        assert_eq!(s.blocks["b1"].copies, 2);
        assert_eq!(s.blocks["b1"].runs, 1);
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = CodeBlockActions::new();
        s.register(b("b1", true, true)).unwrap();
        assert!(matches!(
            s.register(b("b1", true, true)).unwrap_err(),
            BlockError::DuplicateId(_)
        ));
    }

    #[test]
    fn unknown_block() {
        let mut s = CodeBlockActions::new();
        assert!(matches!(
            s.apply("nope", Action::Wrap).unwrap_err(),
            BlockError::UnknownBlock(_)
        ));
        assert!(s.actions_for("nope").is_empty());
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = CodeBlockActions::new();
        assert!(matches!(
            s.register(Block {
                id: "".into(),
                ..b("x", true, true)
            })
            .unwrap_err(),
            BlockError::EmptyId
        ));
        assert!(matches!(
            s.register(Block {
                lang: "".into(),
                ..b("y", true, true)
            })
            .unwrap_err(),
            BlockError::EmptyLang
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = CodeBlockActions::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            BlockError::SchemaMismatch
        ));
    }

    #[test]
    fn block_serde_roundtrip() {
        let mut s = CodeBlockActions::new();
        s.register(b("b1", true, true)).unwrap();
        s.apply("b1", Action::Copy).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: CodeBlockActions = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
