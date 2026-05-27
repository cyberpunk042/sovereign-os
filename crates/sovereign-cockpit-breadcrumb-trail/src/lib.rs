//! `sovereign-cockpit-breadcrumb-trail` — navigation breadcrumb state.
//!
//! Tracks the path (root → section → … → leaf) shown in the cockpit
//! header bar. When the path exceeds `max_visible`, the middle is
//! collapsed into a single "…" crumb leaving root + last-N visible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One breadcrumb.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Crumb {
    /// Stable id (route / section / item).
    pub id: String,
    /// Display label.
    pub label: String,
}

/// A rendered crumb — either a real one or the collapsed ellipsis.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum RenderedCrumb {
    /// Real crumb (carries id + label).
    Real {
        /// id.
        id: String,
        /// label.
        label: String,
    },
    /// Collapsed-middle marker.
    Ellipsis,
}

/// Breadcrumb trail envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BreadcrumbTrail {
    /// Schema version.
    pub schema_version: String,
    /// Crumbs in order, root → leaf.
    pub crumbs: Vec<Crumb>,
    /// Max crumbs rendered before middle collapses. Must be ≥ 3.
    pub max_visible: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BreadcrumbError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("crumb id empty")]
    EmptyId,
    /// Empty label.
    #[error("crumb {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate crumb id: {0}")]
    DuplicateId(String),
    /// max_visible too small.
    #[error("max_visible {0} < 3")]
    MaxVisibleTooSmall(u32),
    /// Unknown id.
    #[error("unknown crumb id: {0}")]
    Unknown(String),
}

impl BreadcrumbTrail {
    /// New empty trail.
    pub fn new(max_visible: u32) -> Result<Self, BreadcrumbError> {
        if max_visible < 3 {
            return Err(BreadcrumbError::MaxVisibleTooSmall(max_visible));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            crumbs: Vec::new(),
            max_visible,
        })
    }

    /// Append a crumb (drill down).
    pub fn push(&mut self, crumb: Crumb) -> Result<(), BreadcrumbError> {
        check_crumb(&crumb)?;
        if self.crumbs.iter().any(|c| c.id == crumb.id) {
            return Err(BreadcrumbError::DuplicateId(crumb.id));
        }
        self.crumbs.push(crumb);
        Ok(())
    }

    /// Pop (go up one).
    pub fn pop(&mut self) -> Option<Crumb> {
        self.crumbs.pop()
    }

    /// Truncate path back to a known id (inclusive — that crumb remains tail).
    pub fn truncate_to(&mut self, id: &str) -> Result<(), BreadcrumbError> {
        let pos = self
            .crumbs
            .iter()
            .position(|c| c.id == id)
            .ok_or_else(|| BreadcrumbError::Unknown(id.into()))?;
        self.crumbs.truncate(pos + 1);
        Ok(())
    }

    /// Compute the rendered sequence with middle collapsed when long.
    /// Layout: [root, ellipsis, last (max_visible - 2) crumbs].
    pub fn render(&self) -> Vec<RenderedCrumb> {
        let n = self.crumbs.len();
        let max = self.max_visible as usize;
        if n <= max {
            return self
                .crumbs
                .iter()
                .map(|c| RenderedCrumb::Real {
                    id: c.id.clone(),
                    label: c.label.clone(),
                })
                .collect();
        }
        let mut out: Vec<RenderedCrumb> = Vec::with_capacity(max);
        // Always show root.
        let root = &self.crumbs[0];
        out.push(RenderedCrumb::Real {
            id: root.id.clone(),
            label: root.label.clone(),
        });
        out.push(RenderedCrumb::Ellipsis);
        let tail_count = max - 2;
        let tail_start = n - tail_count;
        for c in &self.crumbs[tail_start..] {
            out.push(RenderedCrumb::Real {
                id: c.id.clone(),
                label: c.label.clone(),
            });
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BreadcrumbError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BreadcrumbError::SchemaMismatch);
        }
        if self.max_visible < 3 {
            return Err(BreadcrumbError::MaxVisibleTooSmall(self.max_visible));
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for c in &self.crumbs {
            check_crumb(c)?;
            if !seen.insert(c.id.as_str()) {
                return Err(BreadcrumbError::DuplicateId(c.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_crumb(c: &Crumb) -> Result<(), BreadcrumbError> {
    if c.id.is_empty() {
        return Err(BreadcrumbError::EmptyId);
    }
    if c.label.is_empty() {
        return Err(BreadcrumbError::EmptyLabel(c.id.clone()));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn crumb(id: &str) -> Crumb {
        Crumb {
            id: id.into(),
            label: format!("L-{id}"),
        }
    }

    #[test]
    fn max_visible_too_small_rejected() {
        assert!(matches!(
            BreadcrumbTrail::new(2).unwrap_err(),
            BreadcrumbError::MaxVisibleTooSmall(2)
        ));
    }

    #[test]
    fn empty_validates() {
        BreadcrumbTrail::new(5).unwrap().validate().unwrap();
    }

    #[test]
    fn push_pop() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        t.push(crumb("a")).unwrap();
        t.push(crumb("b")).unwrap();
        assert_eq!(t.pop().unwrap().id, "b");
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        t.push(crumb("a")).unwrap();
        assert!(matches!(
            t.push(crumb("a")).unwrap_err(),
            BreadcrumbError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        let mut c = crumb("a");
        c.id = String::new();
        assert!(matches!(t.push(c).unwrap_err(), BreadcrumbError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        let mut c = crumb("a");
        c.label = String::new();
        assert!(matches!(
            t.push(c).unwrap_err(),
            BreadcrumbError::EmptyLabel(_)
        ));
    }

    #[test]
    fn truncate_to_known() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        for id in ["a", "b", "c", "d"] {
            t.push(crumb(id)).unwrap();
        }
        t.truncate_to("b").unwrap();
        assert_eq!(t.crumbs.len(), 2);
        assert_eq!(t.crumbs.last().unwrap().id, "b");
    }

    #[test]
    fn truncate_to_unknown_rejected() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        t.push(crumb("a")).unwrap();
        assert!(matches!(
            t.truncate_to("z").unwrap_err(),
            BreadcrumbError::Unknown(_)
        ));
    }

    #[test]
    fn render_under_limit_returns_all() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        t.push(crumb("a")).unwrap();
        t.push(crumb("b")).unwrap();
        let r = t.render();
        assert_eq!(r.len(), 2);
        assert!(matches!(r[0], RenderedCrumb::Real { .. }));
    }

    #[test]
    fn render_over_limit_collapses_middle() {
        let mut t = BreadcrumbTrail::new(4).unwrap();
        for id in ["a", "b", "c", "d", "e", "f"] {
            t.push(crumb(id)).unwrap();
        }
        let r = t.render();
        assert_eq!(r.len(), 4);
        match &r[0] {
            RenderedCrumb::Real { id, .. } => assert_eq!(id, "a"),
            _ => panic!("first should be root"),
        }
        assert!(matches!(r[1], RenderedCrumb::Ellipsis));
        match &r[2] {
            RenderedCrumb::Real { id, .. } => assert_eq!(id, "e"),
            _ => panic!(),
        }
        match &r[3] {
            RenderedCrumb::Real { id, .. } => assert_eq!(id, "f"),
            _ => panic!(),
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            BreadcrumbError::SchemaMismatch
        ));
    }

    #[test]
    fn rendered_serde_kebab() {
        let r = RenderedCrumb::Ellipsis;
        assert_eq!(
            serde_json::to_string(&r).unwrap(),
            "{\"kind\":\"ellipsis\"}"
        );
    }

    #[test]
    fn trail_serde_roundtrip() {
        let mut t = BreadcrumbTrail::new(5).unwrap();
        t.push(crumb("a")).unwrap();
        t.push(crumb("b")).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: BreadcrumbTrail = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
