//! `sovereign-circuit-breaker` — stop hammering a failing downstream.
//!
//! Retry rides out a transient blip; a circuit breaker handles a *persistent*
//! outage. When a downstream (a cloud model, a tool service) has failed enough
//! times in a row, continuing to call it just wastes time and piles load on a
//! service that's already down — so the breaker **opens** and rejects calls
//! immediately. After a cooldown it goes **half-open** and lets a single trial
//! through; if that succeeds it **closes** (back to normal), and if it fails it
//! opens again. The three states are the classic Closed → Open → Half-Open
//! cycle.
//!
//! Time is injected (`now_ms`), so every transition is deterministic and
//! testable without a real clock.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the circuit-breaker surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The breaker's state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// Normal operation; calls pass through.
    Closed,
    /// Tripped; calls are rejected until the cooldown elapses.
    Open,
    /// Cooldown elapsed; one trial call is allowed to test recovery.
    HalfOpen,
}

/// A failure-threshold circuit breaker.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct CircuitBreaker {
    failure_threshold: u32,
    cooldown_ms: u64,
    state: State,
    consecutive_failures: u32,
    opened_at: u64,
}

impl CircuitBreaker {
    /// A breaker that opens after `failure_threshold` consecutive failures and
    /// waits `cooldown_ms` before allowing a trial.
    ///
    /// # Panics
    /// Panics if `failure_threshold == 0`.
    pub fn new(failure_threshold: u32, cooldown_ms: u64) -> Self {
        assert!(failure_threshold > 0, "failure_threshold must be > 0");
        Self {
            failure_threshold,
            cooldown_ms,
            state: State::Closed,
            consecutive_failures: 0,
            opened_at: 0,
        }
    }

    /// The current state (after any time-based transition for `now_ms`).
    pub fn state(&self) -> State {
        self.state
    }

    /// Consecutive failures recorded since the last success.
    pub fn consecutive_failures(&self) -> u32 {
        self.consecutive_failures
    }

    /// Whether a call should be allowed at `now_ms`. Drives the Open →
    /// Half-Open transition once the cooldown has elapsed.
    pub fn allow(&mut self, now_ms: u64) -> bool {
        match self.state {
            State::Closed => true,
            State::HalfOpen => true,
            State::Open => {
                if now_ms.saturating_sub(self.opened_at) >= self.cooldown_ms {
                    self.state = State::HalfOpen;
                    true
                } else {
                    false
                }
            }
        }
    }

    /// Record a successful call: the breaker closes and the failure count resets.
    pub fn record_success(&mut self) {
        self.state = State::Closed;
        self.consecutive_failures = 0;
    }

    /// Record a failed call at `now_ms`. In Closed, enough failures trip it
    /// Open; in Half-Open, a single failure re-opens it.
    pub fn record_failure(&mut self, now_ms: u64) {
        match self.state {
            State::HalfOpen => {
                self.state = State::Open;
                self.opened_at = now_ms;
            }
            State::Closed => {
                self.consecutive_failures += 1;
                if self.consecutive_failures >= self.failure_threshold {
                    self.state = State::Open;
                    self.opened_at = now_ms;
                }
            }
            State::Open => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_closed_and_allows() {
        let mut cb = CircuitBreaker::new(3, 1000);
        assert_eq!(cb.state(), State::Closed);
        assert!(cb.allow(0));
    }

    #[test]
    fn consecutive_failures_trip_open() {
        let mut cb = CircuitBreaker::new(3, 1000);
        cb.record_failure(0);
        cb.record_failure(0);
        assert_eq!(cb.state(), State::Closed); // not yet
        cb.record_failure(0);
        assert_eq!(cb.state(), State::Open); // 3rd failure trips it
        assert!(!cb.allow(0)); // rejects immediately
    }

    #[test]
    fn success_resets_failure_count() {
        let mut cb = CircuitBreaker::new(3, 1000);
        cb.record_failure(0);
        cb.record_failure(0);
        cb.record_success();
        assert_eq!(cb.consecutive_failures(), 0);
        cb.record_failure(0); // count restarts → still closed
        assert_eq!(cb.state(), State::Closed);
    }

    #[test]
    fn opens_then_half_opens_after_cooldown() {
        let mut cb = CircuitBreaker::new(1, 1000);
        cb.record_failure(0); // threshold 1 → open
        assert!(!cb.allow(500)); // still within cooldown
        assert!(cb.allow(1000)); // cooldown elapsed → half-open, trial allowed
        assert_eq!(cb.state(), State::HalfOpen);
    }

    #[test]
    fn half_open_success_closes() {
        let mut cb = CircuitBreaker::new(1, 1000);
        cb.record_failure(0);
        cb.allow(1000); // → half-open
        cb.record_success();
        assert_eq!(cb.state(), State::Closed);
        assert!(cb.allow(1000));
    }

    #[test]
    fn half_open_failure_reopens() {
        let mut cb = CircuitBreaker::new(1, 1000);
        cb.record_failure(0);
        cb.allow(1000); // → half-open
        cb.record_failure(1000); // trial failed → reopen
        assert_eq!(cb.state(), State::Open);
        assert!(!cb.allow(1500)); // new cooldown from 1000
        assert!(cb.allow(2000)); // cooldown elapsed again
    }

    #[test]
    fn open_rejects_until_cooldown() {
        let mut cb = CircuitBreaker::new(2, 2000);
        cb.record_failure(100);
        cb.record_failure(100); // open at t=100
        assert!(!cb.allow(100));
        assert!(!cb.allow(2099)); // 1999ms < 2000
        assert!(cb.allow(2100)); // 2000ms elapsed
    }

    #[test]
    fn serde_round_trip() {
        let mut cb = CircuitBreaker::new(3, 1000);
        cb.record_failure(0);
        let j = serde_json::to_string(&cb).unwrap();
        let back: CircuitBreaker = serde_json::from_str(&j).unwrap();
        assert_eq!(cb, back);
    }
}
