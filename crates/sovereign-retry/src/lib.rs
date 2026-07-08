//! `sovereign-retry` — exponential backoff with deterministic jitter.
//!
//! Tools and networks fail transiently; an agent that gives up on the first
//! hiccup is brittle, and one that retries instantly hammers a struggling
//! service. The standard answer is exponential backoff with jitter, and this
//! crate is that policy: the delay for attempt `n` is
//! `base · multiplier^n`, capped at a maximum, with optional **deterministic**
//! jitter (so a seed reproduces the exact schedule — important for testing and
//! for the runtime's replay ledger).
//!
//! [`RetryPolicy::run_with`] drives a fallible operation, sleeping via an
//! injected callback between attempts, so the whole retry loop — including the
//! delays it would sleep — is observable in a test without real time passing.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the retry surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// An exponential-backoff retry policy.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct RetryPolicy {
    /// Total attempts allowed (including the first). Must be ≥ 1.
    pub max_attempts: usize,
    /// Delay before the *first* retry, in milliseconds.
    pub base_delay_ms: u64,
    /// Per-attempt multiplier (e.g. 2.0 doubles each time).
    pub multiplier: f64,
    /// Cap on any single delay, in milliseconds.
    pub max_delay_ms: u64,
    /// Jitter fraction in `[0, 1]`: the delay is spread ±`jitter/2` around its
    /// nominal value. `0.0` disables jitter.
    pub jitter: f64,
}

impl Default for RetryPolicy {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            base_delay_ms: 100,
            multiplier: 2.0,
            max_delay_ms: 10_000,
            jitter: 0.0,
        }
    }
}

impl RetryPolicy {
    /// A policy with `max_attempts` and a base delay, doubling each time.
    pub fn new(max_attempts: usize, base_delay_ms: u64) -> Self {
        Self {
            max_attempts: max_attempts.max(1),
            base_delay_ms,
            ..Self::default()
        }
    }

    /// Set the jitter fraction (clamped to `[0, 1]`).
    pub fn with_jitter(mut self, jitter: f64) -> Self {
        self.jitter = jitter.clamp(0.0, 1.0);
        self
    }

    /// Whether another attempt is allowed after `attempt` have completed
    /// (`attempt` is 1-based: after the 1st attempt, `attempt == 1`).
    pub fn should_retry(&self, attempt: usize) -> bool {
        attempt < self.max_attempts
    }

    /// The nominal (un-jittered) delay before retry number `n` (0-based: `n=0`
    /// is the delay before the *first* retry), capped at `max_delay_ms`.
    pub fn delay_for(&self, n: usize) -> u64 {
        let raw = self.base_delay_ms as f64 * self.multiplier.powi(n as i32);
        raw.min(self.max_delay_ms as f64).max(0.0) as u64
    }

    /// The delay for retry `n` with deterministic jitter applied, given `seed`.
    /// Stays within `[nominal·(1−j/2), nominal·(1+j/2)]`, capped.
    pub fn delay_for_seeded(&self, n: usize, seed: u64) -> u64 {
        let nominal = self.delay_for(n) as f64;
        if self.jitter <= 0.0 {
            return nominal as u64;
        }
        // deterministic r in [0,1) from (n, seed)
        let h = fnv1a(&[n as u64, seed]);
        let r = (h % 1_000_000) as f64 / 1_000_000.0;
        let factor = 1.0 - self.jitter / 2.0 + self.jitter * r;
        (nominal * factor).min(self.max_delay_ms as f64).max(0.0) as u64
    }

    /// Run `op` (called with the 1-based attempt number) with backoff. Between
    /// attempts it calls `sleep(delay_ms)` — inject a real sleep in production,
    /// a recorder in tests. Returns the last error if all attempts fail.
    pub fn run_with<T, E, F, S>(&self, seed: u64, mut op: F, mut sleep: S) -> Result<T, E>
    where
        F: FnMut(usize) -> Result<T, E>,
        S: FnMut(u64),
    {
        let mut attempt = 1;
        loop {
            match op(attempt) {
                Ok(v) => return Ok(v),
                Err(e) => {
                    if !self.should_retry(attempt) {
                        return Err(e);
                    }
                    sleep(self.delay_for_seeded(attempt - 1, seed));
                    attempt += 1;
                }
            }
        }
    }
}

/// FNV-1a over a small slice of u64 words.
fn fnv1a(words: &[u64]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &w in words {
        for b in w.to_le_bytes() {
            h ^= b as u64;
            h = h.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
    h
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;

    #[test]
    fn exponential_schedule() {
        let p = RetryPolicy::new(5, 100); // multiplier 2
        assert_eq!(p.delay_for(0), 100);
        assert_eq!(p.delay_for(1), 200);
        assert_eq!(p.delay_for(2), 400);
        assert_eq!(p.delay_for(3), 800);
    }

    #[test]
    fn delay_is_capped() {
        let mut p = RetryPolicy::new(20, 1000);
        p.max_delay_ms = 5000;
        assert_eq!(p.delay_for(10), 5000); // would be huge, capped
    }

    #[test]
    fn should_retry_respects_max_attempts() {
        let p = RetryPolicy::new(3, 10);
        assert!(p.should_retry(1));
        assert!(p.should_retry(2));
        assert!(!p.should_retry(3)); // 3rd attempt is the last
    }

    #[test]
    fn run_succeeds_on_first_try() {
        let p = RetryPolicy::new(3, 10);
        let slept = RefCell::new(Vec::new());
        let r: Result<i32, ()> = p.run_with(0, |_| Ok(42), |d| slept.borrow_mut().push(d));
        assert_eq!(r, Ok(42));
        assert!(slept.borrow().is_empty()); // no sleeps
    }

    #[test]
    fn run_retries_then_succeeds() {
        let p = RetryPolicy::new(5, 100);
        let slept = RefCell::new(Vec::new());
        let attempts = RefCell::new(0);
        let r: Result<&str, &str> = p.run_with(
            0,
            |_a| {
                *attempts.borrow_mut() += 1;
                if *attempts.borrow() < 3 {
                    Err("transient")
                } else {
                    Ok("ok")
                }
            },
            |d| slept.borrow_mut().push(d),
        );
        assert_eq!(r, Ok("ok"));
        assert_eq!(*attempts.borrow(), 3);
        // slept before retry 1 (100) and retry 2 (200)
        assert_eq!(*slept.borrow(), vec![100, 200]);
    }

    #[test]
    fn run_exhausts_and_returns_last_error() {
        let p = RetryPolicy::new(3, 10);
        let slept = RefCell::new(Vec::new());
        let count = RefCell::new(0);
        let r: Result<(), i32> = p.run_with(
            0,
            |a| {
                *count.borrow_mut() += 1;
                Err(a as i32) // error carries the attempt number
            },
            |d| slept.borrow_mut().push(d),
        );
        assert_eq!(r, Err(3)); // last attempt's error
        assert_eq!(*count.borrow(), 3); // tried 3 times
        assert_eq!(slept.borrow().len(), 2); // slept between the 3 attempts
    }

    #[test]
    fn jitter_stays_in_band_and_is_deterministic() {
        let p = RetryPolicy::new(5, 1000).with_jitter(0.5);
        // nominal delay_for(0) = 1000; jitter 0.5 → band [750, 1250]
        let d = p.delay_for_seeded(0, 42);
        assert!((750..=1250).contains(&d), "{d}");
        // deterministic
        assert_eq!(d, p.delay_for_seeded(0, 42));
        // different seed → (generally) different value, still in band
        let d2 = p.delay_for_seeded(0, 99);
        assert!((750..=1250).contains(&d2));
    }

    #[test]
    fn zero_jitter_equals_nominal() {
        let p = RetryPolicy::new(5, 200); // jitter 0 by default
        assert_eq!(p.delay_for_seeded(1, 7), p.delay_for(1));
    }

    #[test]
    fn serde_round_trip() {
        let p = RetryPolicy::new(4, 250).with_jitter(0.3);
        let j = serde_json::to_string(&p).unwrap();
        let back: RetryPolicy = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
