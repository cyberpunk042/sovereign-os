//! `sovereign-cockpit-breakpoint-state` — viewport → breakpoint.
//!
//! Breakpoint{Xs/Sm/Md/Lg/Xl}. Default thresholds in px:
//! Sm=640, Md=768, Lg=1024, Xl=1280. update(width) recomputes;
//! transitions counted. Custom thresholds must be strictly
//! increasing.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Breakpoint.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Breakpoint {
    /// Extra small.
    Xs,
    /// Small.
    Sm,
    /// Medium.
    Md,
    /// Large.
    Lg,
    /// Extra large.
    Xl,
}

/// Thresholds.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Thresholds {
    /// Sm threshold (width >= sm → Sm).
    pub sm: u32,
    /// Md threshold.
    pub md: u32,
    /// Lg threshold.
    pub lg: u32,
    /// Xl threshold.
    pub xl: u32,
}

impl Thresholds {
    /// Default thresholds (Tailwind-ish).
    pub const fn defaults() -> Self {
        Self {
            sm: 640,
            md: 768,
            lg: 1024,
            xl: 1280,
        }
    }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BreakpointState {
    /// Schema version.
    pub schema_version: String,
    /// Thresholds.
    pub thresholds: Thresholds,
    /// Current width (px).
    pub width: u32,
    /// Current breakpoint.
    pub current: Breakpoint,
    /// Transitions observed.
    pub transitions: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BreakpointError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad thresholds.
    #[error("thresholds must be strictly increasing")]
    BadThresholds,
}

fn classify(width: u32, t: &Thresholds) -> Breakpoint {
    if width >= t.xl {
        Breakpoint::Xl
    } else if width >= t.lg {
        Breakpoint::Lg
    } else if width >= t.md {
        Breakpoint::Md
    } else if width >= t.sm {
        Breakpoint::Sm
    } else {
        Breakpoint::Xs
    }
}

fn check_thresholds(t: &Thresholds) -> Result<(), BreakpointError> {
    if !(t.sm < t.md && t.md < t.lg && t.lg < t.xl) {
        return Err(BreakpointError::BadThresholds);
    }
    Ok(())
}

impl BreakpointState {
    /// New with default thresholds + initial width.
    pub fn new(width: u32) -> Self {
        let thresholds = Thresholds::defaults();
        let current = classify(width, &thresholds);
        Self {
            schema_version: SCHEMA_VERSION.into(),
            thresholds,
            width,
            current,
            transitions: 0,
        }
    }

    /// New with custom thresholds.
    pub fn with_thresholds(thresholds: Thresholds, width: u32) -> Result<Self, BreakpointError> {
        check_thresholds(&thresholds)?;
        let current = classify(width, &thresholds);
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            thresholds,
            width,
            current,
            transitions: 0,
        })
    }

    /// Update width; returns new breakpoint.
    pub fn update(&mut self, width: u32) -> Breakpoint {
        self.width = width;
        let bp = classify(width, &self.thresholds);
        if bp != self.current {
            self.current = bp;
            self.transitions = self.transitions.saturating_add(1);
        }
        self.current
    }

    /// True if current >= other (Xs<Sm<Md<Lg<Xl).
    pub fn at_least(&self, other: Breakpoint) -> bool {
        rank(self.current) >= rank(other)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BreakpointError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BreakpointError::SchemaMismatch);
        }
        check_thresholds(&self.thresholds)?;
        Ok(())
    }
}

fn rank(b: Breakpoint) -> u8 {
    match b {
        Breakpoint::Xs => 0,
        Breakpoint::Sm => 1,
        Breakpoint::Md => 2,
        Breakpoint::Lg => 3,
        Breakpoint::Xl => 4,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_xs_below_sm() {
        let s = BreakpointState::new(500);
        assert_eq!(s.current, Breakpoint::Xs);
    }

    #[test]
    fn default_sm_at_640() {
        let s = BreakpointState::new(640);
        assert_eq!(s.current, Breakpoint::Sm);
    }

    #[test]
    fn default_md_at_768() {
        let s = BreakpointState::new(800);
        assert_eq!(s.current, Breakpoint::Md);
    }

    #[test]
    fn default_xl_above_1280() {
        let s = BreakpointState::new(1920);
        assert_eq!(s.current, Breakpoint::Xl);
    }

    #[test]
    fn update_counts_transitions() {
        let mut s = BreakpointState::new(500);
        s.update(500); // no change
        s.update(800); // Xs→Md
        s.update(1500); // Md→Xl
        assert_eq!(s.transitions, 2);
    }

    #[test]
    fn at_least_orders_correctly() {
        let s = BreakpointState::new(1024);
        assert!(s.at_least(Breakpoint::Lg));
        assert!(s.at_least(Breakpoint::Md));
        assert!(!s.at_least(Breakpoint::Xl));
    }

    #[test]
    fn custom_thresholds_ok() {
        let t = Thresholds {
            sm: 500,
            md: 700,
            lg: 900,
            xl: 1100,
        };
        let s = BreakpointState::with_thresholds(t, 800).unwrap();
        assert_eq!(s.current, Breakpoint::Md);
    }

    #[test]
    fn bad_thresholds_rejected() {
        let t = Thresholds {
            sm: 700,
            md: 500,
            lg: 900,
            xl: 1100,
        };
        assert!(matches!(
            BreakpointState::with_thresholds(t, 800).unwrap_err(),
            BreakpointError::BadThresholds
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = BreakpointState::new(800);
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            BreakpointError::SchemaMismatch
        ));
    }

    #[test]
    fn bp_serde_roundtrip() {
        let s = BreakpointState::new(1200);
        let j = serde_json::to_string(&s).unwrap();
        let back: BreakpointState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
