//! `sovereign-cockpit-resize-observer` — noise-filtered resize tracker.
//!
//! `observe(element_id, w, h)` returns:
//!   * `FirstSeen` — first observation, recorded.
//!   * `Changed { prev_w, prev_h, new_w, new_h }` — either dimension
//!     differs by ≥ `noise_threshold_px` from the prior observation;
//!     recorded.
//!   * `SubThreshold` — change too small; *not* recorded.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-element entry.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Size {
    /// width px.
    pub w: u32,
    /// height px.
    pub h: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ResizeObserver {
    /// Schema version.
    pub schema_version: String,
    /// Noise threshold (px).
    pub noise_threshold_px: u32,
    /// element_id → last recorded size.
    pub sizes: BTreeMap<String, Size>,
}

/// Verdict.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum ResizeVerdict {
    /// First observation.
    FirstSeen,
    /// Significant change recorded.
    Changed {
        /// prev w.
        prev_w: u32,
        /// prev h.
        prev_h: u32,
        /// new w.
        new_w: u32,
        /// new h.
        new_h: u32,
    },
    /// Below threshold.
    SubThreshold,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ObserverError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("element id empty")]
    EmptyId,
}

impl ResizeObserver {
    /// New.
    pub fn new(noise_threshold_px: u32) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            noise_threshold_px,
            sizes: BTreeMap::new(),
        }
    }

    /// Observe.
    pub fn observe(
        &mut self,
        element_id: &str,
        w: u32,
        h: u32,
    ) -> Result<ResizeVerdict, ObserverError> {
        if element_id.is_empty() {
            return Err(ObserverError::EmptyId);
        }
        let new_size = Size { w, h };
        match self.sizes.get(element_id).copied() {
            None => {
                self.sizes.insert(element_id.into(), new_size);
                Ok(ResizeVerdict::FirstSeen)
            }
            Some(prev) => {
                let dw = prev.w.abs_diff(w);
                let dh = prev.h.abs_diff(h);
                if dw >= self.noise_threshold_px || dh >= self.noise_threshold_px {
                    self.sizes.insert(element_id.into(), new_size);
                    Ok(ResizeVerdict::Changed {
                        prev_w: prev.w,
                        prev_h: prev.h,
                        new_w: w,
                        new_h: h,
                    })
                } else {
                    Ok(ResizeVerdict::SubThreshold)
                }
            }
        }
    }

    /// Forget an element (it unmounted).
    pub fn forget(&mut self, element_id: &str) -> bool {
        self.sizes.remove(element_id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ObserverError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ObserverError::SchemaMismatch);
        }
        for k in self.sizes.keys() {
            if k.is_empty() {
                return Err(ObserverError::EmptyId);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_seen() {
        let mut o = ResizeObserver::new(4);
        assert_eq!(
            o.observe("box", 100, 100).unwrap(),
            ResizeVerdict::FirstSeen
        );
    }

    #[test]
    fn small_change_subthreshold() {
        let mut o = ResizeObserver::new(4);
        o.observe("box", 100, 100).unwrap();
        let v = o.observe("box", 102, 100).unwrap();
        assert_eq!(v, ResizeVerdict::SubThreshold);
        // Not updated.
        assert_eq!(o.sizes["box"], Size { w: 100, h: 100 });
    }

    #[test]
    fn large_change_recorded() {
        let mut o = ResizeObserver::new(4);
        o.observe("box", 100, 100).unwrap();
        let v = o.observe("box", 100, 200).unwrap();
        match v {
            ResizeVerdict::Changed { prev_h, new_h, .. } => {
                assert_eq!(prev_h, 100);
                assert_eq!(new_h, 200);
            }
            _ => panic!(),
        }
        // Updated.
        assert_eq!(o.sizes["box"], Size { w: 100, h: 200 });
    }

    #[test]
    fn either_dim_triggers() {
        let mut o = ResizeObserver::new(5);
        o.observe("box", 100, 100).unwrap();
        // Width changes by exactly threshold (5).
        let v = o.observe("box", 105, 100).unwrap();
        assert!(matches!(v, ResizeVerdict::Changed { .. }));
    }

    #[test]
    fn forget_removes() {
        let mut o = ResizeObserver::new(4);
        o.observe("box", 100, 100).unwrap();
        assert!(o.forget("box"));
        assert_eq!(
            o.observe("box", 100, 100).unwrap(),
            ResizeVerdict::FirstSeen
        );
    }

    #[test]
    fn empty_id_rejected() {
        let mut o = ResizeObserver::new(4);
        assert!(matches!(
            o.observe("", 0, 0).unwrap_err(),
            ObserverError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut o = ResizeObserver::new(4);
        o.schema_version = "9.9.9".into();
        assert!(matches!(
            o.validate().unwrap_err(),
            ObserverError::SchemaMismatch
        ));
    }

    #[test]
    fn observer_serde_roundtrip() {
        let mut o = ResizeObserver::new(4);
        o.observe("box", 100, 100).unwrap();
        let j = serde_json::to_string(&o).unwrap();
        let back: ResizeObserver = serde_json::from_str(&j).unwrap();
        assert_eq!(o, back);
    }
}
