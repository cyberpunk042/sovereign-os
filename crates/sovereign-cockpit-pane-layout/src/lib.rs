//! `sovereign-cockpit-pane-layout` — operator-selectable window split.
//!
//! 4 modes:
//! - `Single`           — 1 pane, full window
//! - `SplitVertical`    — 2 panes side by side
//! - `SplitHorizontal`  — 2 panes top/bottom
//! - `QuadGrid`         — 4 panes in 2x2 grid
//!
//! Each pane carries a string ref to the active tab id (matches the
//! cockpit's tab strip). Validation enforces that the populated-pane
//! count matches the chosen mode.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Split mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SplitMode {
    /// Single pane.
    Single,
    /// 2 panes side by side.
    SplitVertical,
    /// 2 panes top/bottom.
    SplitHorizontal,
    /// 4 panes 2x2.
    QuadGrid,
}

/// Layout envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PaneLayout {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: SplitMode,
    /// Pane contents (tab ids). Length must match `mode`'s expected count.
    pub panes: Vec<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LayoutError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Pane count doesn't match mode.
    #[error("mode {mode:?} expects {expected} panes; got {got}")]
    CountMismatch {
        /// mode.
        mode: SplitMode,
        /// expected.
        expected: usize,
        /// got.
        got: usize,
    },
    /// Pane has empty tab id.
    #[error("pane {0} has empty tab id")]
    EmptyPane(usize),
}

impl SplitMode {
    /// Expected pane count for this mode.
    pub fn pane_count(self) -> usize {
        match self {
            SplitMode::Single => 1,
            SplitMode::SplitVertical | SplitMode::SplitHorizontal => 2,
            SplitMode::QuadGrid => 4,
        }
    }
}

impl PaneLayout {
    /// New single-pane layout with the given tab id.
    pub fn single(tab_id: &str) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: SplitMode::Single,
            panes: vec![tab_id.into()],
        }
    }

    /// Switch to a different mode. Right-pads or truncates panes.
    pub fn switch_mode(&mut self, mode: SplitMode) {
        let target = mode.pane_count();
        while self.panes.len() < target {
            // Inherit last pane's tab id, or empty.
            let inherit = self.panes.last().cloned().unwrap_or_default();
            self.panes.push(inherit);
        }
        while self.panes.len() > target {
            self.panes.pop();
        }
        self.mode = mode;
    }

    /// Set the tab id for one pane (by index).
    pub fn set_pane(&mut self, idx: usize, tab_id: &str) -> Result<(), LayoutError> {
        if idx >= self.panes.len() {
            return Err(LayoutError::CountMismatch {
                mode: self.mode,
                expected: idx + 1,
                got: self.panes.len(),
            });
        }
        if tab_id.is_empty() {
            return Err(LayoutError::EmptyPane(idx));
        }
        self.panes[idx] = tab_id.into();
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LayoutError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LayoutError::SchemaMismatch);
        }
        let expected = self.mode.pane_count();
        if self.panes.len() != expected {
            return Err(LayoutError::CountMismatch {
                mode: self.mode,
                expected,
                got: self.panes.len(),
            });
        }
        for (i, p) in self.panes.iter().enumerate() {
            if p.is_empty() {
                return Err(LayoutError::EmptyPane(i));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_layout_validates() {
        PaneLayout::single("tab-1").validate().unwrap();
    }

    #[test]
    fn pane_count_per_mode() {
        assert_eq!(SplitMode::Single.pane_count(), 1);
        assert_eq!(SplitMode::SplitVertical.pane_count(), 2);
        assert_eq!(SplitMode::SplitHorizontal.pane_count(), 2);
        assert_eq!(SplitMode::QuadGrid.pane_count(), 4);
    }

    #[test]
    fn switch_to_split_vertical_pads() {
        let mut l = PaneLayout::single("tab-1");
        l.switch_mode(SplitMode::SplitVertical);
        assert_eq!(l.panes.len(), 2);
        // Right pane inherits from left.
        assert_eq!(l.panes[0], "tab-1");
        assert_eq!(l.panes[1], "tab-1");
        l.validate().unwrap();
    }

    #[test]
    fn switch_to_quad_pads_to_four() {
        let mut l = PaneLayout::single("tab-1");
        l.switch_mode(SplitMode::QuadGrid);
        assert_eq!(l.panes.len(), 4);
        l.validate().unwrap();
    }

    #[test]
    fn switch_down_truncates() {
        let mut l = PaneLayout::single("tab-1");
        l.switch_mode(SplitMode::QuadGrid);
        l.switch_mode(SplitMode::Single);
        assert_eq!(l.panes.len(), 1);
    }

    #[test]
    fn set_pane_updates() {
        let mut l = PaneLayout::single("tab-1");
        l.switch_mode(SplitMode::SplitVertical);
        l.set_pane(1, "tab-2").unwrap();
        assert_eq!(l.panes[1], "tab-2");
    }

    #[test]
    fn set_pane_out_of_range_rejected() {
        let mut l = PaneLayout::single("tab-1");
        assert!(matches!(
            l.set_pane(5, "x").unwrap_err(),
            LayoutError::CountMismatch { .. }
        ));
    }

    #[test]
    fn set_empty_pane_rejected() {
        let mut l = PaneLayout::single("tab-1");
        assert!(matches!(
            l.set_pane(0, "").unwrap_err(),
            LayoutError::EmptyPane(0)
        ));
    }

    #[test]
    fn count_mismatch_caught_in_validate() {
        let l = PaneLayout {
            schema_version: SCHEMA_VERSION.into(),
            mode: SplitMode::QuadGrid,
            panes: vec!["a".into(), "b".into()],
        };
        assert!(matches!(
            l.validate().unwrap_err(),
            LayoutError::CountMismatch { .. }
        ));
    }

    #[test]
    fn empty_pane_caught_in_validate() {
        let l = PaneLayout {
            schema_version: SCHEMA_VERSION.into(),
            mode: SplitMode::SplitVertical,
            panes: vec!["a".into(), String::new()],
        };
        assert!(matches!(
            l.validate().unwrap_err(),
            LayoutError::EmptyPane(1)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = PaneLayout::single("a");
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            LayoutError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&SplitMode::Single).unwrap(),
            "\"single\""
        );
        assert_eq!(
            serde_json::to_string(&SplitMode::SplitVertical).unwrap(),
            "\"split-vertical\""
        );
        assert_eq!(
            serde_json::to_string(&SplitMode::SplitHorizontal).unwrap(),
            "\"split-horizontal\""
        );
        assert_eq!(
            serde_json::to_string(&SplitMode::QuadGrid).unwrap(),
            "\"quad-grid\""
        );
    }

    #[test]
    fn layout_serde_roundtrip() {
        let mut l = PaneLayout::single("tab-1");
        l.switch_mode(SplitMode::QuadGrid);
        let j = serde_json::to_string(&l).unwrap();
        let back: PaneLayout = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
