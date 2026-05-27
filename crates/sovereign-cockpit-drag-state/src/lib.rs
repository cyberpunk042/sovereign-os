//! `sovereign-cockpit-drag-state` — drag lifecycle.
//!
//! Phase{Idle/Dragging{item_id, hovered_zone}/Completed}.
//! start enters Dragging; hover sets/clears hovered_zone; drop
//! transitions to Completed; cancel returns Idle.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Dragging.
    Dragging {
        /// Item being dragged.
        item_id: String,
        /// Hovered drop zone (None = nothing under pointer).
        hovered_zone: Option<String>,
    },
    /// Completed (terminal until reset).
    Completed {
        /// Item that was dragged.
        item_id: String,
        /// Zone it was dropped on.
        dropped_zone: String,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DragState {
    /// Schema version.
    pub schema_version: String,
    /// Phase.
    pub phase: Phase,
    /// Drag operations completed.
    pub drops: u64,
    /// Drag operations cancelled.
    pub cancels: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DragError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("item id empty")]
    EmptyItem,
    /// Empty.
    #[error("zone empty")]
    EmptyZone,
    /// Wrong phase.
    #[error("invalid transition from current phase")]
    InvalidTransition,
}

impl DragState {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            phase: Phase::Idle,
            drops: 0,
            cancels: 0,
        }
    }

    /// Start dragging.
    pub fn start(&mut self, item_id: &str) -> Result<(), DragError> {
        if item_id.is_empty() {
            return Err(DragError::EmptyItem);
        }
        if !matches!(self.phase, Phase::Idle | Phase::Completed { .. }) {
            return Err(DragError::InvalidTransition);
        }
        self.phase = Phase::Dragging {
            item_id: item_id.into(),
            hovered_zone: None,
        };
        Ok(())
    }

    /// Set hovered zone.
    pub fn hover(&mut self, zone: Option<&str>) -> Result<(), DragError> {
        if let Some(z) = zone
            && z.is_empty()
        {
            return Err(DragError::EmptyZone);
        }
        match &mut self.phase {
            Phase::Dragging { hovered_zone, .. } => {
                *hovered_zone = zone.map(|s| s.into());
                Ok(())
            }
            _ => Err(DragError::InvalidTransition),
        }
    }

    /// Drop onto hovered zone (or specified zone).
    pub fn drop(&mut self) -> Result<(String, String), DragError> {
        let (item, zone) = match &self.phase {
            Phase::Dragging {
                item_id,
                hovered_zone: Some(z),
            } => (item_id.clone(), z.clone()),
            _ => return Err(DragError::InvalidTransition),
        };
        self.phase = Phase::Completed {
            item_id: item.clone(),
            dropped_zone: zone.clone(),
        };
        self.drops = self.drops.saturating_add(1);
        Ok((item, zone))
    }

    /// Cancel drag.
    pub fn cancel(&mut self) -> Result<(), DragError> {
        if !matches!(self.phase, Phase::Dragging { .. }) {
            return Err(DragError::InvalidTransition);
        }
        self.phase = Phase::Idle;
        self.cancels = self.cancels.saturating_add(1);
        Ok(())
    }

    /// Reset to Idle (from any phase).
    pub fn reset(&mut self) {
        self.phase = Phase::Idle;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DragError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DragError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for DragState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_drop() {
        let mut d = DragState::new();
        d.start("item1").unwrap();
        d.hover(Some("zoneA")).unwrap();
        let (item, zone) = d.drop().unwrap();
        assert_eq!(item, "item1");
        assert_eq!(zone, "zoneA");
        assert_eq!(d.drops, 1);
    }

    #[test]
    fn drop_without_hover_rejected() {
        let mut d = DragState::new();
        d.start("item1").unwrap();
        assert!(matches!(
            d.drop().unwrap_err(),
            DragError::InvalidTransition
        ));
    }

    #[test]
    fn cancel_returns_idle() {
        let mut d = DragState::new();
        d.start("item1").unwrap();
        d.cancel().unwrap();
        assert!(matches!(d.phase, Phase::Idle));
        assert_eq!(d.cancels, 1);
    }

    #[test]
    fn hover_outside_drag_rejected() {
        let mut d = DragState::new();
        assert!(matches!(
            d.hover(Some("z")).unwrap_err(),
            DragError::InvalidTransition
        ));
    }

    #[test]
    fn start_can_follow_completed() {
        let mut d = DragState::new();
        d.start("a").unwrap();
        d.hover(Some("z")).unwrap();
        d.drop().unwrap();
        d.start("b").unwrap();
        assert!(matches!(d.phase, Phase::Dragging { .. }));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut d = DragState::new();
        assert!(matches!(d.start("").unwrap_err(), DragError::EmptyItem));
        d.start("a").unwrap();
        assert!(matches!(
            d.hover(Some("")).unwrap_err(),
            DragError::EmptyZone
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DragState::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DragError::SchemaMismatch
        ));
    }

    #[test]
    fn drag_serde_roundtrip() {
        let mut d = DragState::new();
        d.start("item1").unwrap();
        d.hover(Some("zoneA")).unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: DragState = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
