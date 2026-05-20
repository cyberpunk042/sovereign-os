//! `sovereign-cockpit-attention-cue` — pulsing UI attention.
//!
//! Phase{Off/Pulsing}. notify(now) sets phase=Pulsing,
//! intensity=10000, last_event_ms=now. observe(now) computes
//! intensity = max(0, 10000 - decay_bp_per_sec * (now-last)/1000).
//! When intensity hits 0, phase flips Off. acknowledge(now)
//! explicitly resets to Off. Pure deterministic.
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
#[serde(rename_all = "kebab-case")]
pub enum Phase {
    /// Off.
    Off,
    /// Pulsing.
    Pulsing,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AttentionCue {
    /// Schema version.
    pub schema_version: String,
    /// Phase.
    pub phase: Phase,
    /// Intensity bp 0..=10000.
    pub intensity_bp: u32,
    /// Decay rate (bp/sec) applied while pulsing.
    pub decay_bp_per_sec: u32,
    /// When notify(...) last fired.
    pub last_event_ms: u64,
    /// notify count.
    pub notifies: u64,
    /// acknowledge count.
    pub acks: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CueError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero decay.
    #[error("decay_bp_per_sec must be >= 1")]
    ZeroDecay,
}

impl AttentionCue {
    /// New.
    pub fn new(decay_bp_per_sec: u32) -> Result<Self, CueError> {
        if decay_bp_per_sec == 0 { return Err(CueError::ZeroDecay); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            phase: Phase::Off,
            intensity_bp: 0,
            decay_bp_per_sec,
            last_event_ms: 0,
            notifies: 0,
            acks: 0,
        })
    }

    /// Fire a pulse.
    pub fn notify(&mut self, now_ms: u64) {
        self.phase = Phase::Pulsing;
        self.intensity_bp = 10_000;
        self.last_event_ms = now_ms;
        self.notifies = self.notifies.saturating_add(1);
    }

    /// Update phase + intensity per current time.
    pub fn observe(&mut self, now_ms: u64) -> u32 {
        if self.phase == Phase::Off { return 0; }
        let elapsed = now_ms.saturating_sub(self.last_event_ms);
        let decay = (self.decay_bp_per_sec as u64).saturating_mul(elapsed) / 1000;
        let decay = decay.min(10_000) as u32;
        if decay >= self.intensity_bp {
            self.intensity_bp = 0;
            self.phase = Phase::Off;
            self.last_event_ms = now_ms;
            return 0;
        }
        // Don't mutate intensity_bp here — keep ground truth at 10000 at last_event;
        // intensity is derived from elapsed each observe.
        let cur = self.intensity_bp.saturating_sub(decay);
        cur
    }

    /// Acknowledge (explicit dismiss).
    pub fn acknowledge(&mut self) {
        self.phase = Phase::Off;
        self.intensity_bp = 0;
        self.acks = self.acks.saturating_add(1);
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CueError> {
        if self.schema_version != SCHEMA_VERSION { return Err(CueError::SchemaMismatch); }
        if self.decay_bp_per_sec == 0 { return Err(CueError::ZeroDecay); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_is_off() {
        let c = AttentionCue::new(1000).unwrap();
        assert_eq!(c.phase, Phase::Off);
    }

    #[test]
    fn notify_starts_pulsing() {
        let mut c = AttentionCue::new(1000).unwrap();
        c.notify(0);
        assert_eq!(c.phase, Phase::Pulsing);
        assert_eq!(c.intensity_bp, 10000);
    }

    #[test]
    fn observe_returns_decaying_intensity() {
        let mut c = AttentionCue::new(2000).unwrap(); // 2000 bp/sec
        c.notify(0);
        let at_500 = c.observe(500); // 500ms decay = 1000 bp → 9000
        assert_eq!(at_500, 9000);
        assert_eq!(c.phase, Phase::Pulsing);
    }

    #[test]
    fn auto_off_when_intensity_zero() {
        let mut c = AttentionCue::new(2000).unwrap();
        c.notify(0);
        c.observe(10_000); // huge decay; should clamp to Off
        assert_eq!(c.phase, Phase::Off);
    }

    #[test]
    fn acknowledge_resets() {
        let mut c = AttentionCue::new(1000).unwrap();
        c.notify(0);
        c.acknowledge();
        assert_eq!(c.phase, Phase::Off);
        assert_eq!(c.intensity_bp, 0);
        assert_eq!(c.acks, 1);
    }

    #[test]
    fn renotify_resets_intensity() {
        let mut c = AttentionCue::new(2000).unwrap();
        c.notify(0);
        c.observe(500);
        c.notify(1000); // re-pulse
        assert_eq!(c.intensity_bp, 10000);
        assert_eq!(c.last_event_ms, 1000);
    }

    #[test]
    fn zero_decay_rejected() {
        assert!(matches!(AttentionCue::new(0).unwrap_err(), CueError::ZeroDecay));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = AttentionCue::new(1000).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), CueError::SchemaMismatch));
    }

    #[test]
    fn cue_serde_roundtrip() {
        let mut c = AttentionCue::new(1000).unwrap();
        c.notify(50);
        let j = serde_json::to_string(&c).unwrap();
        let back: AttentionCue = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
