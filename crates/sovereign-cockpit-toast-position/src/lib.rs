//! `sovereign-cockpit-toast-position` — toast corner anchor + stacking.
//!
//! 4 Corner anchors. layout() takes per-toast heights and the
//! container height; emits PositionedToast{id, x, y}. Stacking:
//! Top-* fills from top down; Bottom-* fills from bottom up. Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Corner anchor.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Corner {
    /// Top-left.
    TopLeft,
    /// Top-right.
    TopRight,
    /// Bottom-left.
    BottomLeft,
    /// Bottom-right.
    BottomRight,
}

/// One toast input.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToastInput {
    /// Stable id.
    pub id: String,
    /// Height in px.
    pub height_px: u32,
    /// Width in px (used for x positioning).
    pub width_px: u32,
}

/// Positioned toast.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PositionedToast {
    /// Id.
    pub id: String,
    /// x.
    pub x: u32,
    /// y.
    pub y: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToastPosition {
    /// Schema version.
    pub schema_version: String,
    /// Edge inset px.
    pub inset_px: u32,
    /// Gap between stacked toasts.
    pub gap_px: u32,
    /// Corner.
    pub corner: Corner,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToastPosError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("toast id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate toast id: {0}")]
    DuplicateId(String),
}

impl ToastPosition {
    /// New.
    pub fn new(corner: Corner, inset_px: u32, gap_px: u32) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            inset_px,
            gap_px,
            corner,
        }
    }

    /// Layout.
    pub fn layout(
        &self,
        toasts: &[ToastInput],
        container_w: u32,
        container_h: u32,
    ) -> Result<Vec<PositionedToast>, ToastPosError> {
        check_toasts(toasts)?;
        let mut out: Vec<PositionedToast> = Vec::with_capacity(toasts.len());
        match self.corner {
            Corner::TopLeft | Corner::TopRight => {
                let mut y = self.inset_px;
                for t in toasts {
                    let x = if self.corner == Corner::TopLeft {
                        self.inset_px
                    } else {
                        container_w.saturating_sub(self.inset_px + t.width_px)
                    };
                    out.push(PositionedToast {
                        id: t.id.clone(),
                        x,
                        y,
                    });
                    y = y.saturating_add(t.height_px + self.gap_px);
                }
            }
            Corner::BottomLeft | Corner::BottomRight => {
                let mut y_bottom = container_h.saturating_sub(self.inset_px);
                for t in toasts {
                    let y = y_bottom.saturating_sub(t.height_px);
                    let x = if self.corner == Corner::BottomLeft {
                        self.inset_px
                    } else {
                        container_w.saturating_sub(self.inset_px + t.width_px)
                    };
                    out.push(PositionedToast {
                        id: t.id.clone(),
                        x,
                        y,
                    });
                    y_bottom = y.saturating_sub(self.gap_px);
                }
            }
        }
        Ok(out)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToastPosError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToastPosError::SchemaMismatch);
        }
        Ok(())
    }
}

fn check_toasts(t: &[ToastInput]) -> Result<(), ToastPosError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for x in t {
        if x.id.is_empty() {
            return Err(ToastPosError::EmptyId);
        }
        if !seen.insert(x.id.as_str()) {
            return Err(ToastPosError::DuplicateId(x.id.clone()));
        }
    }
    Ok(())
}

impl Default for ToastPosition {
    fn default() -> Self {
        Self::new(Corner::BottomRight, 16, 8)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(id: &str, h: u32, w: u32) -> ToastInput {
        ToastInput {
            id: id.into(),
            height_px: h,
            width_px: w,
        }
    }

    #[test]
    fn top_right_stacks_down() {
        let p = ToastPosition::new(Corner::TopRight, 10, 5);
        let out = p
            .layout(&[t("a", 40, 200), t("b", 40, 200)], 800, 600)
            .unwrap();
        assert_eq!(out[0].y, 10);
        assert_eq!(out[1].y, 10 + 40 + 5);
        // x = 800 - 10 - 200 = 590
        assert_eq!(out[0].x, 590);
    }

    #[test]
    fn bottom_right_stacks_up() {
        let p = ToastPosition::new(Corner::BottomRight, 10, 5);
        let out = p
            .layout(&[t("a", 40, 200), t("b", 40, 200)], 800, 600)
            .unwrap();
        // first toast y = 600 - 10 - 40 = 550.
        assert_eq!(out[0].y, 550);
        // second toast y = 550 - 5 - 40 = 505.
        assert_eq!(out[1].y, 505);
    }

    #[test]
    fn bottom_left_x_at_inset() {
        let p = ToastPosition::new(Corner::BottomLeft, 10, 5);
        let out = p.layout(&[t("a", 40, 200)], 800, 600).unwrap();
        assert_eq!(out[0].x, 10);
    }

    #[test]
    fn top_left_x_at_inset() {
        let p = ToastPosition::new(Corner::TopLeft, 10, 5);
        let out = p.layout(&[t("a", 40, 200)], 800, 600).unwrap();
        assert_eq!(out[0].x, 10);
        assert_eq!(out[0].y, 10);
    }

    #[test]
    fn empty_input_returns_empty() {
        let p = ToastPosition::default();
        let out = p.layout(&[], 800, 600).unwrap();
        assert!(out.is_empty());
    }

    #[test]
    fn duplicate_id_rejected() {
        let p = ToastPosition::default();
        assert!(matches!(
            p.layout(&[t("a", 10, 10), t("a", 10, 10)], 800, 600)
                .unwrap_err(),
            ToastPosError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let p = ToastPosition::default();
        assert!(matches!(
            p.layout(&[t("", 10, 10)], 800, 600).unwrap_err(),
            ToastPosError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ToastPosition::default();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            ToastPosError::SchemaMismatch
        ));
    }

    #[test]
    fn corner_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Corner::BottomRight).unwrap(),
            "\"bottom-right\""
        );
    }

    #[test]
    fn position_serde_roundtrip() {
        let p = ToastPosition::new(Corner::TopRight, 10, 5);
        let j = serde_json::to_string(&p).unwrap();
        let back: ToastPosition = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
