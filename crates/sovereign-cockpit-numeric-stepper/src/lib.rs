//! `sovereign-cockpit-numeric-stepper` — bounded i64 stepper.
//!
//! Tracks `(value, step, min, max, wrap)`. `set(v)` clamps to the
//! valid range and snaps to the nearest multiple of `step` (anchored
//! at `min`). `inc()` / `dec()` move by `step`, optionally wrapping.
//! `large_inc(mult)` / `large_dec(mult)` move by `step * mult`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct NumericStepper {
    /// Schema version.
    pub schema_version: String,
    /// Current value.
    pub value: i64,
    /// Step size (> 0).
    pub step: i64,
    /// Min inclusive.
    pub min: i64,
    /// Max inclusive.
    pub max: i64,
    /// Wrap at edges.
    pub wrap: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StepperError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// step not positive.
    #[error("step {0} must be > 0")]
    StepNotPositive(i64),
    /// min > max.
    #[error("min {0} > max {1}")]
    BadRange(i64, i64),
}

impl NumericStepper {
    /// New.
    pub fn new(
        value: i64,
        step: i64,
        min: i64,
        max: i64,
        wrap: bool,
    ) -> Result<Self, StepperError> {
        if step <= 0 {
            return Err(StepperError::StepNotPositive(step));
        }
        if min > max {
            return Err(StepperError::BadRange(min, max));
        }
        let mut s = Self {
            schema_version: SCHEMA_VERSION.into(),
            value: min,
            step,
            min,
            max,
            wrap,
        };
        s.set(value);
        Ok(s)
    }

    /// Snap-to-step + clamp.
    pub fn set(&mut self, v: i64) {
        let clamped = v.max(self.min).min(self.max);
        let offset = clamped - self.min;
        let snapped = self.min + (offset / self.step) * self.step;
        // Round to nearest step.
        let rem = offset % self.step;
        let snapped = if rem >= self.step / 2 + (self.step & 1) {
            snapped + self.step
        } else {
            snapped
        };
        self.value = snapped.max(self.min).min(self.max);
    }

    /// Inc by step.
    pub fn inc(&mut self) {
        let next = self.value.saturating_add(self.step);
        if next > self.max {
            if self.wrap {
                self.value = self.min;
            } else {
                self.value = self.max;
            }
        } else {
            self.value = next;
        }
    }

    /// Dec by step.
    pub fn dec(&mut self) {
        let prev = self.value.saturating_sub(self.step);
        if prev < self.min {
            if self.wrap {
                self.value = self.max - ((self.max - self.min) % self.step);
            } else {
                self.value = self.min;
            }
        } else {
            self.value = prev;
        }
    }

    /// Big inc.
    pub fn large_inc(&mut self, mult: i64) {
        let next = self.value.saturating_add(self.step.saturating_mul(mult));
        self.value = next.max(self.min).min(self.max);
    }

    /// Big dec.
    pub fn large_dec(&mut self, mult: i64) {
        let prev = self.value.saturating_sub(self.step.saturating_mul(mult));
        self.value = prev.max(self.min).min(self.max);
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StepperError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(StepperError::SchemaMismatch);
        }
        if self.step <= 0 {
            return Err(StepperError::StepNotPositive(self.step));
        }
        if self.min > self.max {
            return Err(StepperError::BadRange(self.min, self.max));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn step_zero_rejected() {
        assert!(matches!(
            NumericStepper::new(0, 0, 0, 10, false).unwrap_err(),
            StepperError::StepNotPositive(_)
        ));
    }

    #[test]
    fn min_greater_than_max_rejected() {
        assert!(matches!(
            NumericStepper::new(0, 1, 10, 5, false).unwrap_err(),
            StepperError::BadRange(_, _)
        ));
    }

    #[test]
    fn set_snaps_and_clamps() {
        let mut s = NumericStepper::new(0, 5, 0, 100, false).unwrap();
        s.set(13); // nearest of 10 / 15 → 15
        assert_eq!(s.value, 15);
        s.set(7);
        assert_eq!(s.value, 5);
        s.set(200);
        assert_eq!(s.value, 100);
    }

    #[test]
    fn inc_no_wrap_clamps() {
        let mut s = NumericStepper::new(95, 5, 0, 100, false).unwrap();
        s.inc();
        assert_eq!(s.value, 100);
        s.inc();
        assert_eq!(s.value, 100);
    }

    #[test]
    fn inc_with_wrap() {
        let mut s = NumericStepper::new(95, 5, 0, 100, true).unwrap();
        s.inc();
        assert_eq!(s.value, 100);
        s.inc();
        assert_eq!(s.value, 0);
    }

    #[test]
    fn dec_clamps() {
        let mut s = NumericStepper::new(5, 5, 0, 100, false).unwrap();
        s.dec();
        assert_eq!(s.value, 0);
        s.dec();
        assert_eq!(s.value, 0);
    }

    #[test]
    fn large_inc_clamps() {
        let mut s = NumericStepper::new(0, 5, 0, 50, false).unwrap();
        s.large_inc(20);
        assert_eq!(s.value, 50);
    }

    #[test]
    fn large_dec_clamps() {
        let mut s = NumericStepper::new(50, 5, 0, 50, false).unwrap();
        s.large_dec(20);
        assert_eq!(s.value, 0);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = NumericStepper::new(0, 1, 0, 10, false).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            StepperError::SchemaMismatch
        ));
    }

    #[test]
    fn stepper_serde_roundtrip() {
        let s = NumericStepper::new(10, 5, 0, 100, true).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: NumericStepper = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
