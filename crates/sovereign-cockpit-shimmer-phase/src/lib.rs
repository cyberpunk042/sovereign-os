//! `sovereign-cockpit-shimmer-phase` — skeleton-shimmer phase calc.
//!
//! `phase(now_ms)` returns 0..1000 (per-mille of the cycle).
//! `offset_for_anchor(anchor_id, now_ms)` adds a deterministic
//! per-anchor stagger so two adjacent skeletons don't pulse in
//! lockstep. The stagger uses an FNV-1a-style hash of the
//! anchor_id mod period_ms.
//!
//! `reduced_motion` flag freezes phase at 500 (mid-tone).
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
pub struct ShimmerPhase {
    /// Schema version.
    pub schema_version: String,
    /// Period in ms.
    pub period_ms: u64,
    /// Reduced-motion freezes phase.
    pub reduced_motion: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ShimmerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// period zero.
    #[error("period_ms must be > 0")]
    PeriodZero,
}

fn hash_fnv1a64(s: &str) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in s.as_bytes() {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

impl ShimmerPhase {
    /// New.
    pub fn new(period_ms: u64, reduced_motion: bool) -> Result<Self, ShimmerError> {
        if period_ms == 0 { return Err(ShimmerError::PeriodZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            period_ms,
            reduced_motion,
        })
    }

    /// Phase 0..1000 (per-mille).
    pub fn phase(&self, now_ms: u64) -> u16 {
        if self.reduced_motion { return 500; }
        let pos = now_ms % self.period_ms;
        ((pos as u128 * 1000) / self.period_ms as u128) as u16
    }

    /// Phase for a specific anchor (staggered by FNV-1a of anchor_id).
    pub fn phase_for_anchor(&self, anchor_id: &str, now_ms: u64) -> u16 {
        if self.reduced_motion { return 500; }
        let stagger = (hash_fnv1a64(anchor_id) % self.period_ms) as u64;
        let shifted = now_ms.wrapping_add(stagger);
        self.phase(shifted)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ShimmerError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ShimmerError::SchemaMismatch); }
        if self.period_ms == 0 { return Err(ShimmerError::PeriodZero); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn period_zero_rejected() {
        assert!(matches!(ShimmerPhase::new(0, false).unwrap_err(), ShimmerError::PeriodZero));
    }

    #[test]
    fn phase_at_zero_is_zero() {
        let s = ShimmerPhase::new(2000, false).unwrap();
        assert_eq!(s.phase(0), 0);
    }

    #[test]
    fn phase_at_half_is_500() {
        let s = ShimmerPhase::new(2000, false).unwrap();
        assert_eq!(s.phase(1000), 500);
    }

    #[test]
    fn phase_wraps_after_period() {
        let s = ShimmerPhase::new(2000, false).unwrap();
        // 5000 = 2*2000 + 1000 → same as t=1000 → 500.
        assert_eq!(s.phase(5000), 500);
    }

    #[test]
    fn reduced_motion_freezes_at_500() {
        let s = ShimmerPhase::new(2000, true).unwrap();
        assert_eq!(s.phase(0), 500);
        assert_eq!(s.phase(2000), 500);
        assert_eq!(s.phase_for_anchor("a", 1234), 500);
    }

    #[test]
    fn anchor_stagger_differs() {
        let s = ShimmerPhase::new(2000, false).unwrap();
        let a = s.phase_for_anchor("anchor-a", 1000);
        let b = s.phase_for_anchor("anchor-b", 1000);
        // Almost-certainly different.
        assert_ne!(a, b);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ShimmerPhase::new(2000, false).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), ShimmerError::SchemaMismatch));
    }

    #[test]
    fn shimmer_serde_roundtrip() {
        let s = ShimmerPhase::new(2000, false).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ShimmerPhase = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
