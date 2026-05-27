//! `sovereign-cockpit-rich-text-toolbar` — RTE toolbar state.
//!
//! Tracks 5 inline marks (Bold/Italic/Underline/Code/Strike) and
//! 7 block kinds (Paragraph/H1/H2/H3/List/Quote/CodeBlock). The
//! toolbar reflects the marks/block active for the cursor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Inline mark.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Ord, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum InlineMark {
    /// Bold.
    Bold,
    /// Italic.
    Italic,
    /// Underline.
    Underline,
    /// Inline code.
    Code,
    /// Strike-through.
    Strike,
}

/// Block kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum BlockKind {
    /// Paragraph.
    Paragraph,
    /// H1.
    H1,
    /// H2.
    H2,
    /// H3.
    H3,
    /// List item.
    List,
    /// Block quote.
    Quote,
    /// Code block.
    CodeBlock,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RichTextToolbar {
    /// Schema version.
    pub schema_version: String,
    /// Active inline marks (sorted set).
    pub marks: BTreeSet<InlineMark>,
    /// Active block.
    pub block: BlockKind,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToolbarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Code mark conflicts with CodeBlock block.
    #[error("inline Code mark conflicts with CodeBlock block")]
    InlineCodeInCodeBlock,
}

impl RichTextToolbar {
    /// New (Paragraph, no marks).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            marks: BTreeSet::new(),
            block: BlockKind::Paragraph,
        }
    }

    /// Toggle a mark.
    pub fn toggle_mark(&mut self, m: InlineMark) -> Result<(), ToolbarError> {
        if m == InlineMark::Code && self.block == BlockKind::CodeBlock {
            return Err(ToolbarError::InlineCodeInCodeBlock);
        }
        if !self.marks.insert(m) {
            self.marks.remove(&m);
        }
        Ok(())
    }

    /// Set block kind (clears marks when block becomes CodeBlock).
    pub fn set_block(&mut self, b: BlockKind) {
        self.block = b;
        if b == BlockKind::CodeBlock {
            self.marks.clear();
        }
    }

    /// Is the mark currently active?
    pub fn is_mark_active(&self, m: InlineMark) -> bool {
        self.marks.contains(&m)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToolbarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToolbarError::SchemaMismatch);
        }
        if self.block == BlockKind::CodeBlock && self.marks.contains(&InlineMark::Code) {
            return Err(ToolbarError::InlineCodeInCodeBlock);
        }
        Ok(())
    }
}

impl Default for RichTextToolbar {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn initial_paragraph_no_marks() {
        let t = RichTextToolbar::new();
        assert_eq!(t.block, BlockKind::Paragraph);
        assert!(t.marks.is_empty());
    }

    #[test]
    fn toggle_mark_on_off() {
        let mut t = RichTextToolbar::new();
        t.toggle_mark(InlineMark::Bold).unwrap();
        assert!(t.is_mark_active(InlineMark::Bold));
        t.toggle_mark(InlineMark::Bold).unwrap();
        assert!(!t.is_mark_active(InlineMark::Bold));
    }

    #[test]
    fn multiple_marks() {
        let mut t = RichTextToolbar::new();
        t.toggle_mark(InlineMark::Bold).unwrap();
        t.toggle_mark(InlineMark::Italic).unwrap();
        assert!(t.is_mark_active(InlineMark::Bold));
        assert!(t.is_mark_active(InlineMark::Italic));
    }

    #[test]
    fn set_block_heading() {
        let mut t = RichTextToolbar::new();
        t.set_block(BlockKind::H2);
        assert_eq!(t.block, BlockKind::H2);
    }

    #[test]
    fn code_block_clears_marks() {
        let mut t = RichTextToolbar::new();
        t.toggle_mark(InlineMark::Bold).unwrap();
        t.set_block(BlockKind::CodeBlock);
        assert!(t.marks.is_empty());
    }

    #[test]
    fn inline_code_in_code_block_rejected() {
        let mut t = RichTextToolbar::new();
        t.set_block(BlockKind::CodeBlock);
        assert!(matches!(
            t.toggle_mark(InlineMark::Code).unwrap_err(),
            ToolbarError::InlineCodeInCodeBlock
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = RichTextToolbar::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            ToolbarError::SchemaMismatch
        ));
    }

    #[test]
    fn mark_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&InlineMark::Strike).unwrap(),
            "\"strike\""
        );
    }

    #[test]
    fn block_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&BlockKind::CodeBlock).unwrap(),
            "\"code-block\""
        );
    }

    #[test]
    fn toolbar_serde_roundtrip() {
        let mut t = RichTextToolbar::new();
        t.toggle_mark(InlineMark::Bold).unwrap();
        t.set_block(BlockKind::H1);
        let j = serde_json::to_string(&t).unwrap();
        let back: RichTextToolbar = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
