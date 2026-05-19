//! `sovereign-cockpit-skeleton-loader` — loading-placeholder shapes.
//!
//! 4 canonical view types × placeholder shapes. The cockpit renders
//! these while real content loads. Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// View type.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ViewType {
    /// Conversation thread view.
    Conversation,
    /// Dashboard widget grid.
    Dashboard,
    /// Replay timeline.
    Replay,
    /// Tabular view.
    Table,
}

/// Skeleton shape.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Shape {
    /// Rectangle.
    Rect,
    /// Circle.
    Circle,
    /// Line.
    Line,
}

/// One placeholder.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Placeholder {
    /// Shape.
    pub shape: Shape,
    /// Width (px or %).
    pub width: u16,
    /// Height (px or %).
    pub height: u16,
}

/// Per-view-type skeleton.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ViewSkeleton {
    /// View type.
    pub view: ViewType,
    /// Placeholders rendered top→bottom.
    pub placeholders: Vec<Placeholder>,
}

/// Catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkeletonCatalog {
    /// Schema version.
    pub schema_version: String,
    /// 4 view skeletons.
    pub skeletons: Vec<ViewSkeleton>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SkeletonError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 4.
    #[error("skeleton count {0} != 4 canonical")]
    CountInvalid(usize),
    /// Missing.
    #[error("missing view: {0:?}")]
    Missing(ViewType),
    /// Empty placeholders list.
    #[error("view {0:?} has empty placeholders")]
    EmptyPlaceholders(ViewType),
    /// Zero dimension.
    #[error("placeholder zero dim in {0:?}")]
    ZeroDim(ViewType),
}

const REQUIRED: [ViewType; 4] = [
    ViewType::Conversation, ViewType::Dashboard, ViewType::Replay, ViewType::Table,
];

impl SkeletonCatalog {
    /// Canonical catalog.
    pub fn canonical() -> Self {
        let skeletons = vec![
            ViewSkeleton {
                view: ViewType::Conversation,
                placeholders: vec![
                    Placeholder { shape: Shape::Circle, width: 40, height: 40 },
                    Placeholder { shape: Shape::Line, width: 60, height: 12 },
                    Placeholder { shape: Shape::Rect, width: 100, height: 80 },
                    Placeholder { shape: Shape::Rect, width: 100, height: 60 },
                ],
            },
            ViewSkeleton {
                view: ViewType::Dashboard,
                placeholders: vec![
                    Placeholder { shape: Shape::Rect, width: 50, height: 200 },
                    Placeholder { shape: Shape::Rect, width: 50, height: 200 },
                    Placeholder { shape: Shape::Rect, width: 100, height: 300 },
                ],
            },
            ViewSkeleton {
                view: ViewType::Replay,
                placeholders: vec![
                    Placeholder { shape: Shape::Line, width: 100, height: 8 },
                    Placeholder { shape: Shape::Rect, width: 100, height: 400 },
                ],
            },
            ViewSkeleton {
                view: ViewType::Table,
                placeholders: vec![
                    Placeholder { shape: Shape::Line, width: 100, height: 16 },
                    Placeholder { shape: Shape::Line, width: 100, height: 16 },
                    Placeholder { shape: Shape::Line, width: 100, height: 16 },
                    Placeholder { shape: Shape::Line, width: 100, height: 16 },
                    Placeholder { shape: Shape::Line, width: 100, height: 16 },
                ],
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            skeletons,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SkeletonError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SkeletonError::SchemaMismatch);
        }
        if self.skeletons.len() != 4 {
            return Err(SkeletonError::CountInvalid(self.skeletons.len()));
        }
        for v in REQUIRED {
            if !self.skeletons.iter().any(|s| s.view == v) {
                return Err(SkeletonError::Missing(v));
            }
        }
        for s in &self.skeletons {
            if s.placeholders.is_empty() {
                return Err(SkeletonError::EmptyPlaceholders(s.view));
            }
            for p in &s.placeholders {
                if p.width == 0 || p.height == 0 {
                    return Err(SkeletonError::ZeroDim(s.view));
                }
            }
        }
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, v: ViewType) -> Option<&ViewSkeleton> {
        self.skeletons.iter().find(|s| s.view == v)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        SkeletonCatalog::canonical().validate().unwrap();
    }

    #[test]
    fn four_views_present() {
        let c = SkeletonCatalog::canonical();
        for v in REQUIRED { assert!(c.get(v).is_some(), "missing {v:?}"); }
    }

    #[test]
    fn conversation_starts_with_avatar_circle() {
        let c = SkeletonCatalog::canonical();
        let s = c.get(ViewType::Conversation).unwrap();
        assert_eq!(s.placeholders[0].shape, Shape::Circle);
    }

    #[test]
    fn table_uses_only_lines() {
        let c = SkeletonCatalog::canonical();
        let s = c.get(ViewType::Table).unwrap();
        for p in &s.placeholders {
            assert_eq!(p.shape, Shape::Line);
        }
    }

    #[test]
    fn zero_dim_rejected() {
        let mut c = SkeletonCatalog::canonical();
        c.skeletons[0].placeholders[0].width = 0;
        assert!(matches!(c.validate().unwrap_err(), SkeletonError::ZeroDim(_)));
    }

    #[test]
    fn empty_placeholders_rejected() {
        let mut c = SkeletonCatalog::canonical();
        c.skeletons[0].placeholders.clear();
        assert!(matches!(c.validate().unwrap_err(), SkeletonError::EmptyPlaceholders(_)));
    }

    #[test]
    fn count_invalid_caught() {
        let mut c = SkeletonCatalog::canonical();
        c.skeletons.pop();
        assert!(matches!(c.validate().unwrap_err(), SkeletonError::CountInvalid(3)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = SkeletonCatalog::canonical();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), SkeletonError::SchemaMismatch));
    }

    #[test]
    fn shape_serde_kebab() {
        assert_eq!(serde_json::to_string(&Shape::Rect).unwrap(), "\"rect\"");
        assert_eq!(serde_json::to_string(&Shape::Circle).unwrap(), "\"circle\"");
        assert_eq!(serde_json::to_string(&Shape::Line).unwrap(), "\"line\"");
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let c = SkeletonCatalog::canonical();
        let j = serde_json::to_string(&c).unwrap();
        let back: SkeletonCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
