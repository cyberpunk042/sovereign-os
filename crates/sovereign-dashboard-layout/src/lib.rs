//! `sovereign-dashboard-layout` — per-dashboard 12-column widget grid.
//!
//! Each dashboard slot (D-NN, see `sovereign-dashboard-coverage`) carries
//! an ordered list of widgets with (x, y, w, h, kind). The grid is
//! 12 columns wide; rows are unbounded vertically. Validator detects:
//! - x + w > 12 (out of bounds)
//! - any two widgets overlap
//! - widget kind unknown
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_dashboard_coverage::CoverageManifest;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Grid width (columns).
pub const GRID_COLS: u8 = 12;

/// Widget kind — 8 canonical kinds.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum WidgetKind {
    /// Time-series line chart.
    LineChart,
    /// Numeric KPI tile.
    KpiTile,
    /// Status indicator (color-coded).
    Status,
    /// Log feed (auto-scrolling).
    LogFeed,
    /// Table with rows.
    Table,
    /// Free-form text panel.
    Text,
    /// Action button row.
    ActionRow,
    /// 2D heatmap.
    Heatmap,
}

/// Widget placement.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Widget {
    /// Column origin (0..12).
    pub x: u8,
    /// Row origin (0..).
    pub y: u8,
    /// Width in columns (≥1).
    pub w: u8,
    /// Height in rows (≥1).
    pub h: u8,
    /// Kind.
    pub kind: WidgetKind,
    /// Source-binding (operator-readable identifier; non-empty).
    pub binding: String,
}

/// Dashboard layout — one per D-NN slot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DashboardLayout {
    /// Slot id ("D-NN").
    pub slot: String,
    /// Widget grid.
    pub widgets: Vec<Widget>,
}

/// Layout manifest envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LayoutManifest {
    /// Schema version.
    pub schema_version: String,
    /// Per-slot layouts (subset of dashboard-coverage slots).
    pub layouts: Vec<DashboardLayout>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LayoutError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Slot id not in dashboard-coverage manifest.
    #[error("unknown slot: {0}")]
    UnknownSlot(String),
    /// Duplicate slot in layout list.
    #[error("duplicate slot: {0}")]
    DuplicateSlot(String),
    /// Widget dimension zero.
    #[error("slot {slot} widget {idx}: dimension zero (w={w} h={h})")]
    ZeroDim {
        /// slot.
        slot: String,
        /// idx.
        idx: usize,
        /// w.
        w: u8,
        /// h.
        h: u8,
    },
    /// Widget out of bounds horizontally.
    #[error("slot {slot} widget {idx}: x+w={x_plus_w} > {GRID_COLS}")]
    OutOfBounds {
        /// slot.
        slot: String,
        /// idx.
        idx: usize,
        /// x+w.
        x_plus_w: u8,
    },
    /// Widget bindings empty.
    #[error("slot {slot} widget {idx}: binding empty")]
    EmptyBinding {
        /// slot.
        slot: String,
        /// idx.
        idx: usize,
    },
    /// Two widgets overlap.
    #[error("slot {slot}: widgets {a} and {b} overlap")]
    Overlap {
        /// slot.
        slot: String,
        /// a.
        a: usize,
        /// b.
        b: usize,
    },
}

fn overlaps(a: &Widget, b: &Widget) -> bool {
    let a_x1 = a.x;
    let a_x2 = a.x + a.w;
    let a_y1 = a.y;
    let a_y2 = a.y + a.h;
    let b_x1 = b.x;
    let b_x2 = b.x + b.w;
    let b_y1 = b.y;
    let b_y2 = b.y + b.h;
    a_x1 < b_x2 && b_x1 < a_x2 && a_y1 < b_y2 && b_y1 < a_y2
}

impl DashboardLayout {
    /// Validate a single dashboard's grid (internal invariants).
    pub fn validate(&self) -> Result<(), LayoutError> {
        for (idx, w) in self.widgets.iter().enumerate() {
            if w.w == 0 || w.h == 0 {
                return Err(LayoutError::ZeroDim {
                    slot: self.slot.clone(),
                    idx,
                    w: w.w,
                    h: w.h,
                });
            }
            let x_plus_w = w.x.saturating_add(w.w);
            if x_plus_w > GRID_COLS {
                return Err(LayoutError::OutOfBounds {
                    slot: self.slot.clone(),
                    idx,
                    x_plus_w,
                });
            }
            if w.binding.is_empty() {
                return Err(LayoutError::EmptyBinding {
                    slot: self.slot.clone(),
                    idx,
                });
            }
        }
        for i in 0..self.widgets.len() {
            for j in (i + 1)..self.widgets.len() {
                if overlaps(&self.widgets[i], &self.widgets[j]) {
                    return Err(LayoutError::Overlap {
                        slot: self.slot.clone(),
                        a: i,
                        b: j,
                    });
                }
            }
        }
        Ok(())
    }

    /// Total cells used by widgets.
    pub fn cells_used(&self) -> u32 {
        self.widgets.iter().map(|w| w.w as u32 * w.h as u32).sum()
    }
}

impl LayoutManifest {
    /// New empty manifest.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            layouts: Vec::new(),
        }
    }

    /// Add a dashboard layout.
    pub fn add(
        &mut self,
        layout: DashboardLayout,
        coverage: &CoverageManifest,
    ) -> Result<(), LayoutError> {
        if !coverage.entries.iter().any(|e| e.slot == layout.slot) {
            return Err(LayoutError::UnknownSlot(layout.slot));
        }
        if self.layouts.iter().any(|l| l.slot == layout.slot) {
            return Err(LayoutError::DuplicateSlot(layout.slot));
        }
        layout.validate()?;
        self.layouts.push(layout);
        Ok(())
    }

    /// Validate full manifest against the coverage manifest.
    pub fn validate(&self, coverage: &CoverageManifest) -> Result<(), LayoutError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LayoutError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for l in &self.layouts {
            if !coverage.entries.iter().any(|e| e.slot == l.slot) {
                return Err(LayoutError::UnknownSlot(l.slot.clone()));
            }
            if !seen.insert(l.slot.as_str()) {
                return Err(LayoutError::DuplicateSlot(l.slot.clone()));
            }
            l.validate()?;
        }
        Ok(())
    }
}

impl Default for LayoutManifest {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn widget(x: u8, y: u8, w: u8, h: u8, kind: WidgetKind) -> Widget {
        Widget {
            x,
            y,
            w,
            h,
            kind,
            binding: "binding".into(),
        }
    }

    fn cov() -> CoverageManifest {
        CoverageManifest::canonical()
    }

    fn dash_slot() -> String {
        // pick first known slot from coverage
        cov().entries[0].slot.clone()
    }

    #[test]
    fn empty_manifest_validates() {
        LayoutManifest::new().validate(&cov()).unwrap();
    }

    #[test]
    fn single_widget_ok() {
        let mut m = LayoutManifest::new();
        let l = DashboardLayout {
            slot: dash_slot(),
            widgets: vec![widget(0, 0, 6, 4, WidgetKind::LineChart)],
        };
        m.add(l, &cov()).unwrap();
        m.validate(&cov()).unwrap();
    }

    #[test]
    fn zero_dim_rejected() {
        let l = DashboardLayout {
            slot: dash_slot(),
            widgets: vec![widget(0, 0, 0, 4, WidgetKind::Text)],
        };
        assert!(matches!(
            l.validate().unwrap_err(),
            LayoutError::ZeroDim { .. }
        ));
    }

    #[test]
    fn out_of_bounds_rejected() {
        let l = DashboardLayout {
            slot: dash_slot(),
            widgets: vec![widget(8, 0, 6, 4, WidgetKind::Table)], // 8+6=14 > 12
        };
        assert!(matches!(
            l.validate().unwrap_err(),
            LayoutError::OutOfBounds { x_plus_w: 14, .. }
        ));
    }

    #[test]
    fn overlap_rejected() {
        let l = DashboardLayout {
            slot: dash_slot(),
            widgets: vec![
                widget(0, 0, 6, 4, WidgetKind::LineChart),
                widget(4, 2, 6, 4, WidgetKind::Heatmap), // overlaps
            ],
        };
        match l.validate().unwrap_err() {
            LayoutError::Overlap { a, b, .. } => {
                assert_eq!(a, 0);
                assert_eq!(b, 1);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn adjacent_widgets_no_overlap() {
        let l = DashboardLayout {
            slot: dash_slot(),
            widgets: vec![
                widget(0, 0, 6, 4, WidgetKind::LineChart),
                widget(6, 0, 6, 4, WidgetKind::Heatmap),
            ],
        };
        l.validate().unwrap();
    }

    #[test]
    fn unknown_slot_rejected() {
        let mut m = LayoutManifest::new();
        let l = DashboardLayout {
            slot: "D-99".into(),
            widgets: vec![widget(0, 0, 4, 4, WidgetKind::KpiTile)],
        };
        assert!(matches!(
            m.add(l, &cov()).unwrap_err(),
            LayoutError::UnknownSlot(_)
        ));
    }

    #[test]
    fn duplicate_slot_rejected() {
        let mut m = LayoutManifest::new();
        let slot = dash_slot();
        m.add(
            DashboardLayout {
                slot: slot.clone(),
                widgets: vec![widget(0, 0, 4, 4, WidgetKind::KpiTile)],
            },
            &cov(),
        )
        .unwrap();
        let err = m
            .add(
                DashboardLayout {
                    slot,
                    widgets: vec![widget(0, 0, 4, 4, WidgetKind::KpiTile)],
                },
                &cov(),
            )
            .unwrap_err();
        assert!(matches!(err, LayoutError::DuplicateSlot(_)));
    }

    #[test]
    fn empty_binding_rejected() {
        let mut bad = widget(0, 0, 4, 4, WidgetKind::KpiTile);
        bad.binding = String::new();
        let l = DashboardLayout {
            slot: dash_slot(),
            widgets: vec![bad],
        };
        assert!(matches!(
            l.validate().unwrap_err(),
            LayoutError::EmptyBinding { .. }
        ));
    }

    #[test]
    fn cells_used_sums() {
        let l = DashboardLayout {
            slot: dash_slot(),
            widgets: vec![
                widget(0, 0, 6, 4, WidgetKind::LineChart), // 24
                widget(6, 0, 6, 4, WidgetKind::Heatmap),   // 24
            ],
        };
        assert_eq!(l.cells_used(), 48);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = LayoutManifest::new();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate(&cov()).unwrap_err(),
            LayoutError::SchemaMismatch
        ));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&WidgetKind::LineChart).unwrap(),
            "\"line-chart\""
        );
        assert_eq!(
            serde_json::to_string(&WidgetKind::LogFeed).unwrap(),
            "\"log-feed\""
        );
        assert_eq!(
            serde_json::to_string(&WidgetKind::ActionRow).unwrap(),
            "\"action-row\""
        );
    }

    #[test]
    fn manifest_serde_roundtrip() {
        let mut m = LayoutManifest::new();
        m.add(
            DashboardLayout {
                slot: dash_slot(),
                widgets: vec![widget(0, 0, 6, 4, WidgetKind::LineChart)],
            },
            &cov(),
        )
        .unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: LayoutManifest = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
