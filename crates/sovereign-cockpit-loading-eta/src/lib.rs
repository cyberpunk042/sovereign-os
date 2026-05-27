//! `sovereign-cockpit-loading-eta` — linear ETA from progress samples.
//!
//! `observe(progress_pct, now_ms)` records up to `capacity` samples
//! (ring-buffered). `eta_ms(now_ms)` returns the estimated remaining
//! milliseconds to 100% based on the last two distinct progress
//! samples; `None` when too few samples, when progress isn't
//! advancing, or when already at 100%.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One sample.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Sample {
    /// ts ms.
    pub ts_ms: u64,
    /// progress 0..=100.
    pub progress_pct: u8,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LoadingEta {
    /// Schema version.
    pub schema_version: String,
    /// Ring capacity.
    pub capacity: u32,
    /// Samples (oldest → newest).
    pub samples: Vec<Sample>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum EtaError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// capacity zero.
    #[error("capacity must be > 0")]
    CapacityZero,
    /// progress > 100.
    #[error("progress {0} > 100")]
    ProgressOver100(u8),
    /// Non-monotonic.
    #[error("non-monotonic ts: prev {prev} > new {new}")]
    NonMonotonic {
        /// prev.
        prev: u64,
        /// new.
        new: u64,
    },
}

impl LoadingEta {
    /// New.
    pub fn new(capacity: u32) -> Result<Self, EtaError> {
        if capacity == 0 {
            return Err(EtaError::CapacityZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            samples: Vec::new(),
        })
    }

    /// Observe.
    pub fn observe(&mut self, progress_pct: u8, ts_ms: u64) -> Result<(), EtaError> {
        if progress_pct > 100 {
            return Err(EtaError::ProgressOver100(progress_pct));
        }
        if let Some(last) = self.samples.last()
            && ts_ms < last.ts_ms
        {
            return Err(EtaError::NonMonotonic {
                prev: last.ts_ms,
                new: ts_ms,
            });
        }
        self.samples.push(Sample {
            ts_ms,
            progress_pct,
        });
        if self.samples.len() as u32 > self.capacity {
            let drop = self.samples.len() - self.capacity as usize;
            self.samples.drain(0..drop);
        }
        Ok(())
    }

    /// ETA.
    pub fn eta_ms(&self, _now_ms: u64) -> Option<u64> {
        if self.samples.len() < 2 {
            return None;
        }
        let last = *self.samples.last()?;
        if last.progress_pct >= 100 {
            return None;
        }
        // Find the most recent prior sample with different progress.
        let prior = self
            .samples
            .iter()
            .rev()
            .skip(1)
            .find(|s| s.progress_pct < last.progress_pct)?;
        let dt = last.ts_ms.checked_sub(prior.ts_ms)?;
        if dt == 0 {
            return None;
        }
        let dpct = (last.progress_pct - prior.progress_pct) as u64;
        if dpct == 0 {
            return None;
        }
        let remaining_pct = (100 - last.progress_pct) as u64;
        // remaining_ms = dt * remaining_pct / dpct
        Some(dt.saturating_mul(remaining_pct) / dpct)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), EtaError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(EtaError::SchemaMismatch);
        }
        if self.capacity == 0 {
            return Err(EtaError::CapacityZero);
        }
        let mut prev = 0u64;
        for s in &self.samples {
            if s.progress_pct > 100 {
                return Err(EtaError::ProgressOver100(s.progress_pct));
            }
            if s.ts_ms < prev {
                return Err(EtaError::NonMonotonic { prev, new: s.ts_ms });
            }
            prev = s.ts_ms;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capacity_zero_rejected() {
        assert!(matches!(
            LoadingEta::new(0).unwrap_err(),
            EtaError::CapacityZero
        ));
    }

    #[test]
    fn none_with_zero_samples() {
        let e = LoadingEta::new(8).unwrap();
        assert!(e.eta_ms(1000).is_none());
    }

    #[test]
    fn none_with_one_sample() {
        let mut e = LoadingEta::new(8).unwrap();
        e.observe(20, 0).unwrap();
        assert!(e.eta_ms(100).is_none());
    }

    #[test]
    fn eta_linear() {
        let mut e = LoadingEta::new(8).unwrap();
        e.observe(0, 0).unwrap();
        e.observe(20, 1000).unwrap();
        // 20 pct in 1000 ms → remaining 80 pct → 4000 ms.
        assert_eq!(e.eta_ms(1000), Some(4000));
    }

    #[test]
    fn none_when_at_100() {
        let mut e = LoadingEta::new(8).unwrap();
        e.observe(50, 0).unwrap();
        e.observe(100, 1000).unwrap();
        assert!(e.eta_ms(1000).is_none());
    }

    #[test]
    fn none_when_no_progress() {
        let mut e = LoadingEta::new(8).unwrap();
        e.observe(30, 0).unwrap();
        e.observe(30, 1000).unwrap();
        assert!(e.eta_ms(1000).is_none());
    }

    #[test]
    fn progress_over_100_rejected() {
        let mut e = LoadingEta::new(8).unwrap();
        assert!(matches!(
            e.observe(150, 0).unwrap_err(),
            EtaError::ProgressOver100(_)
        ));
    }

    #[test]
    fn nonmonotonic_rejected() {
        let mut e = LoadingEta::new(8).unwrap();
        e.observe(20, 1000).unwrap();
        assert!(matches!(
            e.observe(30, 500).unwrap_err(),
            EtaError::NonMonotonic { .. }
        ));
    }

    #[test]
    fn ring_drops_oldest() {
        let mut e = LoadingEta::new(2).unwrap();
        e.observe(10, 0).unwrap();
        e.observe(20, 1000).unwrap();
        e.observe(30, 2000).unwrap();
        assert_eq!(e.samples.len(), 2);
        assert_eq!(e.samples[0].progress_pct, 20);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut e = LoadingEta::new(8).unwrap();
        e.schema_version = "9.9.9".into();
        assert!(matches!(
            e.validate().unwrap_err(),
            EtaError::SchemaMismatch
        ));
    }

    #[test]
    fn eta_serde_roundtrip() {
        let mut e = LoadingEta::new(8).unwrap();
        e.observe(20, 1000).unwrap();
        let j = serde_json::to_string(&e).unwrap();
        let back: LoadingEta = serde_json::from_str(&j).unwrap();
        assert_eq!(e, back);
    }
}
