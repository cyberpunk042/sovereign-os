//! `sovereign-cockpit-hover-preview` — rich peek-window state machine.
//!
//! Phases:
//!   * `Idle` — nothing showing.
//!   * `Dwelling{id, entered_at}` — pointer is over the anchor but
//!     dwell_ms hasn't elapsed.
//!   * `Visible{id}` — peek window shown; cleared by `leave` unless
//!     `pinned == true`.
//!   * `Pinned{id}` — operator clicked to pin; only `unpin()` or
//!     `anchor_hidden()` closes.
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
    /// Nothing showing.
    Idle,
    /// Pointer over anchor, not yet shown.
    Dwelling {
        /// anchor id.
        id: String,
        /// entered ts.
        entered_at_ms: u64,
    },
    /// Peek visible.
    Visible {
        /// anchor id.
        id: String,
    },
    /// Pinned.
    Pinned {
        /// anchor id.
        id: String,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HoverPreview {
    /// Schema version.
    pub schema_version: String,
    /// Dwell delay (ms).
    pub dwell_ms: u64,
    /// Current phase.
    pub phase: Phase,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PreviewError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
}

impl HoverPreview {
    /// New.
    pub fn new(dwell_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            dwell_ms,
            phase: Phase::Idle,
        }
    }

    /// Enter anchor.
    pub fn enter(&mut self, id: &str, now_ms: u64) -> Result<(), PreviewError> {
        if id.is_empty() {
            return Err(PreviewError::EmptyId);
        }
        // Don't disturb pinned state.
        if matches!(&self.phase, Phase::Pinned { id: pid } if pid != id) {
            // pointer moved to a different anchor → keep pinned.
            return Ok(());
        }
        if let Phase::Pinned { .. } = self.phase {
            return Ok(());
        }
        self.phase = Phase::Dwelling {
            id: id.into(),
            entered_at_ms: now_ms,
        };
        Ok(())
    }

    /// Pointer left.
    pub fn leave(&mut self, _now_ms: u64) {
        match &self.phase {
            Phase::Pinned { .. } => { /* keep pinned */ }
            _ => self.phase = Phase::Idle,
        }
    }

    /// Pin.
    pub fn pin(&mut self) -> Result<(), PreviewError> {
        let id = match &self.phase {
            Phase::Visible { id } => id.clone(),
            Phase::Dwelling { id, .. } => id.clone(),
            _ => return Err(PreviewError::EmptyId),
        };
        self.phase = Phase::Pinned { id };
        Ok(())
    }

    /// Unpin.
    pub fn unpin(&mut self) {
        if let Phase::Pinned { id } = &self.phase {
            self.phase = Phase::Visible { id: id.clone() };
        }
    }

    /// Anchor hidden (scroll, unmount, etc.).
    pub fn anchor_hidden(&mut self) {
        self.phase = Phase::Idle;
    }

    /// Tick: drive Dwelling → Visible at dwell expiry.
    pub fn visible(&mut self, now_ms: u64) -> bool {
        if let Phase::Dwelling { id, entered_at_ms } = &self.phase
            && now_ms.saturating_sub(*entered_at_ms) >= self.dwell_ms
        {
            self.phase = Phase::Visible { id: id.clone() };
        }
        matches!(self.phase, Phase::Visible { .. } | Phase::Pinned { .. })
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PreviewError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PreviewError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dwell_then_visible() {
        let mut p = HoverPreview::new(500);
        p.enter("a", 0).unwrap();
        assert!(!p.visible(100));
        assert!(p.visible(600));
    }

    #[test]
    fn leave_clears_visible() {
        let mut p = HoverPreview::new(500);
        p.enter("a", 0).unwrap();
        p.visible(600);
        p.leave(700);
        assert_eq!(p.phase, Phase::Idle);
    }

    #[test]
    fn pin_holds_through_leave() {
        let mut p = HoverPreview::new(500);
        p.enter("a", 0).unwrap();
        p.visible(600);
        p.pin().unwrap();
        p.leave(700);
        assert!(matches!(p.phase, Phase::Pinned { .. }));
    }

    #[test]
    fn unpin_returns_to_visible() {
        let mut p = HoverPreview::new(500);
        p.enter("a", 0).unwrap();
        p.visible(600);
        p.pin().unwrap();
        p.unpin();
        assert!(matches!(p.phase, Phase::Visible { .. }));
    }

    #[test]
    fn anchor_hidden_clears_even_when_pinned() {
        let mut p = HoverPreview::new(500);
        p.enter("a", 0).unwrap();
        p.visible(600);
        p.pin().unwrap();
        p.anchor_hidden();
        assert_eq!(p.phase, Phase::Idle);
    }

    #[test]
    fn enter_other_anchor_keeps_pinned() {
        let mut p = HoverPreview::new(500);
        p.enter("a", 0).unwrap();
        p.visible(600);
        p.pin().unwrap();
        p.enter("b", 700).unwrap();
        assert!(matches!(p.phase, Phase::Pinned { id } if id == "a"));
    }

    #[test]
    fn empty_id_rejected() {
        let mut p = HoverPreview::new(500);
        assert!(matches!(p.enter("", 0).unwrap_err(), PreviewError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = HoverPreview::new(500);
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PreviewError::SchemaMismatch
        ));
    }

    #[test]
    fn preview_serde_roundtrip() {
        let mut p = HoverPreview::new(500);
        p.enter("a", 0).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: HoverPreview = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
