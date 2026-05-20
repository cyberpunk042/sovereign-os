//! `sovereign-cockpit-tooltip-delay` — open/close delay + group cool.
//!
//! Lifecycle:
//!   * `enter(now)` — pointer entered the anchor.
//!   * `visible(now)` — true iff (`now - entered_at >= open_delay_ms`)
//!     OR (the group is still cool from a recent close).
//!   * `leave(now)` — pointer left; tooltip will close after
//!     close_delay_ms; group cool starts.
//!   * `anchor_hidden(now)` — anchor scrolled / unmounted; closes
//!     instantly and starts group cool.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Phase {
    /// Pointer outside.
    Idle,
    /// Pointer inside, not yet shown.
    Dwelling {
        /// when pointer entered.
        entered_at_ms: u64,
    },
    /// Tooltip visible.
    Open {
        /// when it opened.
        opened_at_ms: u64,
    },
    /// Pointer left; closing.
    Closing {
        /// when pointer left.
        left_at_ms: u64,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TooltipDelay {
    /// Schema version.
    pub schema_version: String,
    /// Open delay (ms).
    pub open_delay_ms: u64,
    /// Close delay (ms).
    pub close_delay_ms: u64,
    /// Group cool (ms after close where the next tooltip opens instantly).
    pub cool_ms: u64,
    /// Current phase.
    pub phase: Phase,
    /// When the group last closed (for cool).
    pub last_closed_ms: Option<u64>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DelayError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl TooltipDelay {
    /// New.
    pub fn new(open_delay_ms: u64, close_delay_ms: u64, cool_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            open_delay_ms,
            close_delay_ms,
            cool_ms,
            phase: Phase::Idle,
            last_closed_ms: None,
        }
    }

    fn cool_active(&self, now: u64) -> bool {
        match self.last_closed_ms {
            Some(t) => now.saturating_sub(t) < self.cool_ms,
            None => false,
        }
    }

    /// Pointer entered.
    pub fn enter(&mut self, now_ms: u64) {
        // If within cool window → skip dwell, open immediately.
        if self.cool_active(now_ms) {
            self.phase = Phase::Open { opened_at_ms: now_ms };
        } else {
            self.phase = Phase::Dwelling { entered_at_ms: now_ms };
        }
    }

    /// Pointer left.
    pub fn leave(&mut self, now_ms: u64) {
        match self.phase {
            Phase::Open { .. } => {
                self.phase = Phase::Closing { left_at_ms: now_ms };
            }
            Phase::Dwelling { .. } | Phase::Closing { .. } | Phase::Idle => {
                self.phase = Phase::Idle;
                self.last_closed_ms = Some(now_ms);
            }
        }
    }

    /// Anchor hidden.
    pub fn anchor_hidden(&mut self, now_ms: u64) {
        self.phase = Phase::Idle;
        self.last_closed_ms = Some(now_ms);
    }

    /// Tick: returns true if tooltip should be visible at `now`.
    pub fn visible(&mut self, now_ms: u64) -> bool {
        match self.phase {
            Phase::Idle => false,
            Phase::Dwelling { entered_at_ms } => {
                if now_ms.saturating_sub(entered_at_ms) >= self.open_delay_ms {
                    self.phase = Phase::Open { opened_at_ms: now_ms };
                    true
                } else {
                    false
                }
            }
            Phase::Open { .. } => true,
            Phase::Closing { left_at_ms } => {
                if now_ms.saturating_sub(left_at_ms) >= self.close_delay_ms {
                    self.phase = Phase::Idle;
                    self.last_closed_ms = Some(now_ms);
                    false
                } else {
                    true
                }
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DelayError> {
        if self.schema_version != SCHEMA_VERSION { return Err(DelayError::SchemaMismatch); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn idle_not_visible() {
        let mut t = TooltipDelay::new(500, 200, 1000);
        assert!(!t.visible(0));
    }

    #[test]
    fn dwell_then_show() {
        let mut t = TooltipDelay::new(500, 200, 1000);
        t.enter(0);
        assert!(!t.visible(200));
        assert!(t.visible(600));
    }

    #[test]
    fn close_after_delay() {
        let mut t = TooltipDelay::new(500, 200, 1000);
        t.enter(0);
        t.visible(600);
        t.leave(700);
        assert!(t.visible(800));
        assert!(!t.visible(950));
    }

    #[test]
    fn cool_window_skips_dwell() {
        let mut t = TooltipDelay::new(500, 200, 1000);
        t.enter(0);
        t.visible(600);
        t.leave(700);
        // close at 900 (700 + 200).
        t.visible(950);
        // enter again at 1000 — within cool window (1000 - 900 = 100 < 1000).
        t.enter(1000);
        assert!(t.visible(1000));
    }

    #[test]
    fn cool_window_expired_dwells_again() {
        let mut t = TooltipDelay::new(500, 200, 1000);
        t.enter(0);
        t.visible(600);
        t.leave(700);
        t.visible(950);
        // way past cool.
        t.enter(5000);
        assert!(!t.visible(5100));
        assert!(t.visible(5600));
    }

    #[test]
    fn anchor_hidden_closes_instantly() {
        let mut t = TooltipDelay::new(500, 200, 1000);
        t.enter(0);
        t.visible(600);
        t.anchor_hidden(700);
        assert!(!t.visible(700));
    }

    #[test]
    fn leave_during_dwell_resets_to_idle() {
        let mut t = TooltipDelay::new(500, 200, 1000);
        t.enter(0);
        t.leave(100);
        assert!(matches!(t.phase, Phase::Idle));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TooltipDelay::new(1, 1, 1);
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), DelayError::SchemaMismatch));
    }

    #[test]
    fn delay_serde_roundtrip() {
        let mut t = TooltipDelay::new(500, 200, 1000);
        t.enter(0);
        let j = serde_json::to_string(&t).unwrap();
        let back: TooltipDelay = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
