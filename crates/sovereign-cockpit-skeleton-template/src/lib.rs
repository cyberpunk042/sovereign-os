//! `sovereign-cockpit-skeleton-template` — row-template skeleton registry.
//!
//! Templates: `Vec<Block{ kind: Line/Circle/Box, w_px, h_px }>`.
//! `render(template_id, count)` returns `Vec<RenderedRow>` for the
//! chrome (one row per requested item).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Block kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum BlockKind {
    /// Text line.
    Line,
    /// Avatar circle.
    Circle,
    /// Generic box.
    Box,
}

/// One block.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Block {
    /// Kind.
    pub kind: BlockKind,
    /// width px.
    pub w_px: u32,
    /// height px.
    pub h_px: u32,
}

/// One rendered row (one copy of the template).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RenderedRow {
    /// Blocks in row order.
    pub blocks: Vec<Block>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkeletonTemplate {
    /// Schema version.
    pub schema_version: String,
    /// template_id → blocks.
    pub templates: BTreeMap<String, Vec<Block>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SkeletonError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("template id empty")]
    EmptyId,
    /// Unknown id.
    #[error("unknown template id: {0}")]
    UnknownId(String),
    /// Empty blocks.
    #[error("template {0} has no blocks")]
    EmptyBlocks(String),
    /// Zero dims.
    #[error("block has zero dimension")]
    ZeroDim,
}

impl SkeletonTemplate {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            templates: BTreeMap::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, template_id: &str, blocks: Vec<Block>) -> Result<(), SkeletonError> {
        if template_id.is_empty() { return Err(SkeletonError::EmptyId); }
        if blocks.is_empty() { return Err(SkeletonError::EmptyBlocks(template_id.into())); }
        for b in &blocks {
            if b.w_px == 0 || b.h_px == 0 { return Err(SkeletonError::ZeroDim); }
        }
        self.templates.insert(template_id.into(), blocks);
        Ok(())
    }

    /// Render.
    pub fn render(&self, template_id: &str, count: usize) -> Result<Vec<RenderedRow>, SkeletonError> {
        let blocks = self.templates.get(template_id)
            .ok_or_else(|| SkeletonError::UnknownId(template_id.into()))?;
        Ok((0..count).map(|_| RenderedRow { blocks: blocks.clone() }).collect())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SkeletonError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SkeletonError::SchemaMismatch); }
        for (id, blocks) in &self.templates {
            if id.is_empty() { return Err(SkeletonError::EmptyId); }
            if blocks.is_empty() { return Err(SkeletonError::EmptyBlocks(id.clone())); }
            for b in blocks {
                if b.w_px == 0 || b.h_px == 0 { return Err(SkeletonError::ZeroDim); }
            }
        }
        Ok(())
    }
}

impl Default for SkeletonTemplate {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn line(w: u32) -> Block { Block { kind: BlockKind::Line, w_px: w, h_px: 16 } }
    fn circle(d: u32) -> Block { Block { kind: BlockKind::Circle, w_px: d, h_px: d } }

    #[test]
    fn register_and_render() {
        let mut s = SkeletonTemplate::new();
        s.register("avatar-name", vec![circle(40), line(200)]).unwrap();
        let rows = s.render("avatar-name", 3).unwrap();
        assert_eq!(rows.len(), 3);
        assert_eq!(rows[0].blocks.len(), 2);
        assert_eq!(rows[0].blocks[0].kind, BlockKind::Circle);
    }

    #[test]
    fn render_unknown() {
        let s = SkeletonTemplate::new();
        assert!(matches!(s.render("nope", 2).unwrap_err(), SkeletonError::UnknownId(_)));
    }

    #[test]
    fn empty_blocks_rejected() {
        let mut s = SkeletonTemplate::new();
        assert!(matches!(s.register("x", vec![]).unwrap_err(), SkeletonError::EmptyBlocks(_)));
    }

    #[test]
    fn zero_dim_rejected() {
        let mut s = SkeletonTemplate::new();
        assert!(matches!(
            s.register("x", vec![Block { kind: BlockKind::Line, w_px: 0, h_px: 10 }]).unwrap_err(),
            SkeletonError::ZeroDim
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = SkeletonTemplate::new();
        assert!(matches!(s.register("", vec![line(10)]).unwrap_err(), SkeletonError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SkeletonTemplate::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SkeletonError::SchemaMismatch));
    }

    #[test]
    fn skeleton_serde_roundtrip() {
        let mut s = SkeletonTemplate::new();
        s.register("x", vec![line(10)]).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SkeletonTemplate = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
