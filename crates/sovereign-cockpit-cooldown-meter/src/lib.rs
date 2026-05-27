//! `sovereign-cockpit-cooldown-meter` — gates an action for a fixed
//! duration after each fire.
//!
//! State{Ready/Cooling}. fire(now) → Cooling, sets next_ready_ms =
//! now + cooldown_ms. observe(now) returns Status with
//! remaining_ms + progress_bp (0..10000 toward Ready).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// Ready to fire.
    Ready,
    /// Cooling down.
    Cooling,
}

/// Status snapshot.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Status {
    /// Current state.
    pub state: State,
    /// Remaining cooldown ms (0 when Ready).
    pub remaining_ms: u64,
    /// Progress toward Ready in basis points (10000 = Ready).
    pub progress_bp: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CooldownMeter {
    /// Schema version.
    pub schema_version: String,
    /// Cooldown duration ms.
    pub cooldown_ms: u64,
    /// Last fire ts ms (None = never).
    pub last_fire_ms: Option<u64>,
    /// Fire count.
    pub fire_count: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CooldownError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero cooldown.
    #[error("cooldown must be >= 1")]
    ZeroCooldown,
    /// Still cooling.
    #[error("still cooling: {0} ms remaining")]
    StillCooling(u64),
}

impl CooldownMeter {
    /// New.
    pub fn new(cooldown_ms: u64) -> Result<Self, CooldownError> {
        if cooldown_ms == 0 {
            return Err(CooldownError::ZeroCooldown);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            cooldown_ms,
            last_fire_ms: None,
            fire_count: 0,
        })
    }

    /// Try to fire (errors if still cooling).
    pub fn fire(&mut self, now_ms: u64) -> Result<(), CooldownError> {
        if let Some(last) = self.last_fire_ms {
            let elapsed = now_ms.saturating_sub(last);
            if elapsed < self.cooldown_ms {
                return Err(CooldownError::StillCooling(self.cooldown_ms - elapsed));
            }
        }
        self.last_fire_ms = Some(now_ms);
        self.fire_count = self.fire_count.saturating_add(1);
        Ok(())
    }

    /// Force reset to Ready (operator override).
    pub fn reset(&mut self) {
        self.last_fire_ms = None;
    }

    /// Observe status at now.
    pub fn observe(&self, now_ms: u64) -> Status {
        match self.last_fire_ms {
            None => Status {
                state: State::Ready,
                remaining_ms: 0,
                progress_bp: 10000,
            },
            Some(last) => {
                let elapsed = now_ms.saturating_sub(last);
                if elapsed >= self.cooldown_ms {
                    Status {
                        state: State::Ready,
                        remaining_ms: 0,
                        progress_bp: 10000,
                    }
                } else {
                    let remaining = self.cooldown_ms - elapsed;
                    let progress_bp = ((elapsed.saturating_mul(10_000)) / self.cooldown_ms) as u32;
                    Status {
                        state: State::Cooling,
                        remaining_ms: remaining,
                        progress_bp,
                    }
                }
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CooldownError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CooldownError::SchemaMismatch);
        }
        if self.cooldown_ms == 0 {
            return Err(CooldownError::ZeroCooldown);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_is_ready() {
        let m = CooldownMeter::new(1000).unwrap();
        assert_eq!(m.observe(0).state, State::Ready);
    }

    #[test]
    fn fire_starts_cooling() {
        let mut m = CooldownMeter::new(1000).unwrap();
        m.fire(0).unwrap();
        let s = m.observe(500);
        assert_eq!(s.state, State::Cooling);
        assert_eq!(s.remaining_ms, 500);
        assert_eq!(s.progress_bp, 5000);
    }

    #[test]
    fn ready_after_cooldown() {
        let mut m = CooldownMeter::new(1000).unwrap();
        m.fire(0).unwrap();
        assert_eq!(m.observe(1000).state, State::Ready);
        assert_eq!(m.observe(2000).state, State::Ready);
    }

    #[test]
    fn fire_while_cooling_rejected() {
        let mut m = CooldownMeter::new(1000).unwrap();
        m.fire(0).unwrap();
        assert!(matches!(
            m.fire(500).unwrap_err(),
            CooldownError::StillCooling(_)
        ));
    }

    #[test]
    fn fire_after_cooldown_accepted() {
        let mut m = CooldownMeter::new(1000).unwrap();
        m.fire(0).unwrap();
        m.fire(1000).unwrap();
        assert_eq!(m.fire_count, 2);
    }

    #[test]
    fn reset_clears_cooldown() {
        let mut m = CooldownMeter::new(1000).unwrap();
        m.fire(0).unwrap();
        m.reset();
        assert_eq!(m.observe(100).state, State::Ready);
    }

    #[test]
    fn zero_cooldown_rejected() {
        assert!(matches!(
            CooldownMeter::new(0).unwrap_err(),
            CooldownError::ZeroCooldown
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = CooldownMeter::new(1000).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            CooldownError::SchemaMismatch
        ));
    }

    #[test]
    fn meter_serde_roundtrip() {
        let mut m = CooldownMeter::new(1000).unwrap();
        m.fire(0).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: CooldownMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
