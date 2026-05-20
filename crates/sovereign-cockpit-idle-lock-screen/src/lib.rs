//! `sovereign-cockpit-idle-lock-screen` — auto-lock state.
//!
//! Tracks `last_activity_ms`. Phase derived from elapsed idle:
//!   * `Active` — under `idle_warn_ms`.
//!   * `Warning` — at/over warn, under lock.
//!   * `Locked` — at/over `idle_lock_ms`.
//!
//! `observe_activity(ts)` resets the clock — only if NOT in Locked
//! (Locked requires explicit `unlock` to leave). `phase_at(now)`
//! returns the current state.
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
    /// Active.
    Active,
    /// Warning (about to lock).
    Warning,
    /// Locked.
    Locked,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct IdleLockScreen {
    /// Schema version.
    pub schema_version: String,
    /// Last activity.
    pub last_activity_ms: u64,
    /// Warn at idle (must be < lock).
    pub idle_warn_ms: u64,
    /// Lock at idle.
    pub idle_lock_ms: u64,
    /// Manually locked? (sticky until unlocked).
    pub locked: bool,
    /// Unlock attempt counter.
    pub unlock_attempts: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LockError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad windows.
    #[error("warn ({warn}) must be < lock ({lock})")]
    BadWindows {
        /// warn.
        warn: u64,
        /// lock.
        lock: u64,
    },
}

impl IdleLockScreen {
    /// New (active, last activity at 0).
    pub fn new(idle_warn_ms: u64, idle_lock_ms: u64) -> Result<Self, LockError> {
        if idle_warn_ms >= idle_lock_ms {
            return Err(LockError::BadWindows { warn: idle_warn_ms, lock: idle_lock_ms });
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            last_activity_ms: 0,
            idle_warn_ms,
            idle_lock_ms,
            locked: false,
            unlock_attempts: 0,
        })
    }

    /// Observe user activity (resets idle, but does NOT leave Locked phase).
    pub fn observe_activity(&mut self, ts_ms: u64) -> bool {
        if self.locked {
            return false;
        }
        // Even if currently in Warning, activity bumps clock.
        // Only update if ts moves forward (no time travel).
        if ts_ms > self.last_activity_ms {
            self.last_activity_ms = ts_ms;
        }
        true
    }

    /// Force lock.
    pub fn lock(&mut self) {
        self.locked = true;
    }

    /// Unlock attempt.
    pub fn unlock(&mut self, now_ms: u64) {
        if self.locked {
            self.locked = false;
            self.last_activity_ms = now_ms;
        }
        self.unlock_attempts = self.unlock_attempts.saturating_add(1);
    }

    /// Phase at now.
    pub fn phase_at(&self, now_ms: u64) -> Phase {
        if self.locked { return Phase::Locked; }
        let idle = now_ms.saturating_sub(self.last_activity_ms);
        if idle >= self.idle_lock_ms { Phase::Locked }
        else if idle >= self.idle_warn_ms { Phase::Warning }
        else { Phase::Active }
    }

    /// Idle duration at now (irrespective of phase).
    pub fn idle_ms(&self, now_ms: u64) -> u64 {
        now_ms.saturating_sub(self.last_activity_ms)
    }

    /// Auto-lock if past threshold (returns true if newly locked).
    pub fn tick(&mut self, now_ms: u64) -> bool {
        if self.locked { return false; }
        let idle = now_ms.saturating_sub(self.last_activity_ms);
        if idle >= self.idle_lock_ms {
            self.locked = true;
            true
        } else {
            false
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LockError> {
        if self.schema_version != SCHEMA_VERSION { return Err(LockError::SchemaMismatch); }
        if self.idle_warn_ms >= self.idle_lock_ms {
            return Err(LockError::BadWindows { warn: self.idle_warn_ms, lock: self.idle_lock_ms });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn active_initially() {
        let s = IdleLockScreen::new(1000, 5000).unwrap();
        assert_eq!(s.phase_at(0), Phase::Active);
    }

    #[test]
    fn phases_advance_with_idle() {
        let s = IdleLockScreen::new(1000, 5000).unwrap();
        assert_eq!(s.phase_at(500), Phase::Active);
        assert_eq!(s.phase_at(2000), Phase::Warning);
        assert_eq!(s.phase_at(6000), Phase::Locked);
    }

    #[test]
    fn observe_activity_resets() {
        let mut s = IdleLockScreen::new(1000, 5000).unwrap();
        // After 2s — Warning.
        assert_eq!(s.phase_at(2000), Phase::Warning);
        s.observe_activity(2000);
        // Back to Active at slightly later time.
        assert_eq!(s.phase_at(2100), Phase::Active);
    }

    #[test]
    fn locked_sticky_through_observe() {
        let mut s = IdleLockScreen::new(1000, 5000).unwrap();
        s.lock();
        // Activity rejected.
        assert!(!s.observe_activity(100));
        assert_eq!(s.phase_at(100), Phase::Locked);
    }

    #[test]
    fn unlock_returns_to_active() {
        let mut s = IdleLockScreen::new(1000, 5000).unwrap();
        s.lock();
        s.unlock(100);
        assert_eq!(s.phase_at(200), Phase::Active);
        assert_eq!(s.unlock_attempts, 1);
    }

    #[test]
    fn tick_locks_when_due() {
        let mut s = IdleLockScreen::new(1000, 5000).unwrap();
        assert!(!s.tick(2000)); // warning, not lock
        assert!(s.tick(6000));
        assert!(s.locked);
    }

    #[test]
    fn tick_idempotent_when_locked() {
        let mut s = IdleLockScreen::new(1000, 5000).unwrap();
        s.lock();
        assert!(!s.tick(10_000));
    }

    #[test]
    fn idle_ms_helper() {
        let s = IdleLockScreen::new(1000, 5000).unwrap();
        assert_eq!(s.idle_ms(7000), 7000);
    }

    #[test]
    fn bad_windows_rejected() {
        assert!(matches!(IdleLockScreen::new(5000, 1000).unwrap_err(), LockError::BadWindows { .. }));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = IdleLockScreen::new(1, 2).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), LockError::SchemaMismatch));
    }

    #[test]
    fn lock_serde_roundtrip() {
        let mut s = IdleLockScreen::new(1000, 5000).unwrap();
        s.observe_activity(100);
        s.lock();
        let j = serde_json::to_string(&s).unwrap();
        let back: IdleLockScreen = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
