//! `sovereign-cockpit-frame-budget` — per-frame work budget.
//!
//! begin_frame(now_us) resets work counter. record(work_us)
//! accumulates. should_yield returns true once accumulated >=
//! budget_us. usage_bp returns 0..=10000+ (over-budget allowed
//! for reporting). end_frame returns FrameStats and counts
//! over-budget frames.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Frame stats snapshot.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct FrameStats {
    /// Work accumulated this frame (µs).
    pub work_us: u64,
    /// Budget (µs).
    pub budget_us: u64,
    /// Usage in basis points (10000 = 100%).
    pub usage_bp: u32,
    /// Over-budget for this frame.
    pub over_budget: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FrameBudget {
    /// Schema version.
    pub schema_version: String,
    /// Budget per frame (µs).
    pub budget_us: u64,
    /// Work accumulated this frame.
    pub work_us: u64,
    /// Total frames begun.
    pub frames: u64,
    /// Frames that went over budget.
    pub over_budget_frames: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BudgetError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero budget.
    #[error("budget_us must be >= 1")]
    ZeroBudget,
}

impl FrameBudget {
    /// New.
    pub fn new(budget_us: u64) -> Result<Self, BudgetError> {
        if budget_us == 0 { return Err(BudgetError::ZeroBudget); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            budget_us,
            work_us: 0,
            frames: 0,
            over_budget_frames: 0,
        })
    }

    /// Start a new frame; resets work counter.
    pub fn begin_frame(&mut self) {
        self.work_us = 0;
        self.frames = self.frames.saturating_add(1);
    }

    /// Record work done.
    pub fn record(&mut self, work_us: u64) {
        self.work_us = self.work_us.saturating_add(work_us);
    }

    /// True once work >= budget.
    pub fn should_yield(&self) -> bool {
        self.work_us >= self.budget_us
    }

    /// Usage in basis points (10000 = budget; may exceed).
    pub fn usage_bp(&self) -> u32 {
        let ratio = (self.work_us.saturating_mul(10_000)) / self.budget_us;
        if ratio > u32::MAX as u64 { u32::MAX } else { ratio as u32 }
    }

    /// Close out the frame; returns stats.
    pub fn end_frame(&mut self) -> FrameStats {
        let usage_bp = self.usage_bp();
        let over_budget = self.work_us > self.budget_us;
        if over_budget {
            self.over_budget_frames = self.over_budget_frames.saturating_add(1);
        }
        FrameStats {
            work_us: self.work_us,
            budget_us: self.budget_us,
            usage_bp,
            over_budget,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BudgetError> {
        if self.schema_version != SCHEMA_VERSION { return Err(BudgetError::SchemaMismatch); }
        if self.budget_us == 0 { return Err(BudgetError::ZeroBudget); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_does_not_yield() {
        let b = FrameBudget::new(16_000).unwrap();
        assert!(!b.should_yield());
    }

    #[test]
    fn yields_once_budget_used() {
        let mut b = FrameBudget::new(16_000).unwrap();
        b.begin_frame();
        b.record(8_000);
        assert!(!b.should_yield());
        b.record(8_000);
        assert!(b.should_yield());
    }

    #[test]
    fn usage_bp_half() {
        let mut b = FrameBudget::new(10_000).unwrap();
        b.begin_frame();
        b.record(5_000);
        assert_eq!(b.usage_bp(), 5000);
    }

    #[test]
    fn over_budget_reported() {
        let mut b = FrameBudget::new(10_000).unwrap();
        b.begin_frame();
        b.record(15_000);
        let s = b.end_frame();
        assert!(s.over_budget);
        assert_eq!(s.usage_bp, 15000);
        assert_eq!(b.over_budget_frames, 1);
    }

    #[test]
    fn within_budget_not_over() {
        let mut b = FrameBudget::new(10_000).unwrap();
        b.begin_frame();
        b.record(8_000);
        let s = b.end_frame();
        assert!(!s.over_budget);
        assert_eq!(b.over_budget_frames, 0);
    }

    #[test]
    fn begin_resets_work() {
        let mut b = FrameBudget::new(10_000).unwrap();
        b.begin_frame();
        b.record(5_000);
        b.begin_frame();
        assert_eq!(b.work_us, 0);
        assert_eq!(b.frames, 2);
    }

    #[test]
    fn zero_budget_rejected() {
        assert!(matches!(FrameBudget::new(0).unwrap_err(), BudgetError::ZeroBudget));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = FrameBudget::new(10_000).unwrap();
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), BudgetError::SchemaMismatch));
    }

    #[test]
    fn budget_serde_roundtrip() {
        let mut b = FrameBudget::new(16_000).unwrap();
        b.begin_frame();
        b.record(4_000);
        let j = serde_json::to_string(&b).unwrap();
        let back: FrameBudget = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
