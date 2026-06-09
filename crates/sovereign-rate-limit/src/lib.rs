//! `sovereign-rate-limit` — token-bucket request throttling.
//!
//! A serving runtime must bound how fast requests arrive — to protect a
//! downstream model, stay within a provider's quota, or shape a fair share.
//! The token bucket is the standard mechanism: tokens drip in at a fixed
//! `refill_per_sec` up to a `capacity`, and each request spends some; a request
//! is allowed only if enough tokens are available. The capacity sets the burst
//! size (how many requests can fire back-to-back after idle), the refill rate
//! sets the sustained throughput.
//!
//! Time is **injected** as `now_ms` rather than read from a clock, so the
//! limiter is fully deterministic and testable — the same call sequence always
//! produces the same allow/deny decisions, which matters for the replay ledger.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the rate-limit surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A token-bucket rate limiter with injected time.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct TokenBucket {
    capacity: f64,
    refill_per_sec: f64,
    tokens: f64,
    last_ms: u64,
}

impl TokenBucket {
    /// A bucket that holds up to `capacity` tokens and refills `refill_per_sec`,
    /// starting full at time `start_ms`.
    ///
    /// # Panics
    /// Panics if `capacity <= 0` or `refill_per_sec < 0`.
    pub fn new(capacity: f64, refill_per_sec: f64, start_ms: u64) -> Self {
        assert!(capacity > 0.0, "capacity must be > 0");
        assert!(refill_per_sec >= 0.0, "refill must be >= 0");
        Self {
            capacity,
            refill_per_sec,
            tokens: capacity,
            last_ms: start_ms,
        }
    }

    /// Drip in tokens accrued since the last update, capped at capacity.
    fn refill(&mut self, now_ms: u64) {
        if now_ms <= self.last_ms {
            return;
        }
        let elapsed_s = (now_ms - self.last_ms) as f64 / 1000.0;
        self.tokens = (self.tokens + elapsed_s * self.refill_per_sec).min(self.capacity);
        self.last_ms = now_ms;
    }

    /// Tokens available at `now_ms` (refills first).
    pub fn available(&mut self, now_ms: u64) -> f64 {
        self.refill(now_ms);
        self.tokens
    }

    /// Try to spend `cost` tokens at `now_ms`. Returns `true` and deducts them
    /// if available; otherwise returns `false` and leaves the bucket unchanged.
    pub fn try_acquire(&mut self, now_ms: u64, cost: f64) -> bool {
        self.refill(now_ms);
        if cost <= self.tokens {
            self.tokens -= cost;
            true
        } else {
            false
        }
    }

    /// Convenience: try to spend exactly one token.
    pub fn try_one(&mut self, now_ms: u64) -> bool {
        self.try_acquire(now_ms, 1.0)
    }

    /// Earliest time (ms) at which `cost` tokens would be available, given the
    /// current state. `None` if `cost` exceeds capacity (never satisfiable), or
    /// the current time if already available.
    pub fn time_until(&self, now_ms: u64, cost: f64) -> Option<u64> {
        if cost > self.capacity {
            return None;
        }
        // project tokens at now (without mutating)
        let elapsed_s = now_ms.saturating_sub(self.last_ms) as f64 / 1000.0;
        let tokens_now = (self.tokens + elapsed_s * self.refill_per_sec).min(self.capacity);
        if cost <= tokens_now {
            return Some(now_ms);
        }
        if self.refill_per_sec <= 0.0 {
            return None; // never refills
        }
        let deficit = cost - tokens_now;
        let wait_ms = (deficit / self.refill_per_sec * 1000.0).ceil() as u64;
        Some(now_ms + wait_ms)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_full() {
        let mut b = TokenBucket::new(5.0, 1.0, 0);
        assert_eq!(b.available(0), 5.0);
    }

    #[test]
    fn allows_a_burst_up_to_capacity_then_denies() {
        let mut b = TokenBucket::new(3.0, 1.0, 0);
        assert!(b.try_one(0));
        assert!(b.try_one(0));
        assert!(b.try_one(0));
        assert!(!b.try_one(0)); // bucket empty, no time passed
    }

    #[test]
    fn refills_over_time() {
        let mut b = TokenBucket::new(2.0, 2.0, 0); // 2 tokens/sec
        assert!(b.try_acquire(0, 2.0)); // drain
        assert!(!b.try_one(0));
        // after 500ms → 1 token refilled
        assert!(b.try_one(500));
        assert!(!b.try_one(500));
        // after another 1000ms → 2 more (capped at capacity 2)
        assert_eq!(b.available(1500), 2.0);
    }

    #[test]
    fn refill_is_capped_at_capacity() {
        let mut b = TokenBucket::new(5.0, 10.0, 0);
        b.try_acquire(0, 5.0); // drain
        // huge elapsed time → capped at capacity, not unbounded
        assert_eq!(b.available(1_000_000), 5.0);
    }

    #[test]
    fn cost_exceeding_capacity_is_never_allowed() {
        let mut b = TokenBucket::new(3.0, 1.0, 0);
        assert!(!b.try_acquire(0, 4.0));
        assert_eq!(b.time_until(0, 4.0), None);
        // bucket unchanged by the failed acquire
        assert_eq!(b.available(0), 3.0);
    }

    #[test]
    fn fractional_cost() {
        let mut b = TokenBucket::new(1.0, 1.0, 0);
        assert!(b.try_acquire(0, 0.6));
        assert!(b.try_acquire(0, 0.4));
        assert!(!b.try_acquire(0, 0.1)); // empty
    }

    #[test]
    fn time_until_projects_the_wait() {
        let mut b = TokenBucket::new(10.0, 5.0, 0); // 5/sec
        b.try_acquire(0, 10.0); // drain
        // need 5 tokens at 5/sec → 1000ms
        assert_eq!(b.time_until(0, 5.0), Some(1000));
        // already-available case
        assert_eq!(b.time_until(2000, 5.0), Some(2000));
    }

    #[test]
    fn no_refill_bucket_never_recovers() {
        let mut b = TokenBucket::new(2.0, 0.0, 0);
        assert!(b.try_acquire(0, 2.0));
        assert!(!b.try_one(1_000_000));
        assert_eq!(b.time_until(0, 1.0), None);
    }

    #[test]
    fn serde_round_trip() {
        let mut b = TokenBucket::new(5.0, 2.0, 100);
        b.try_one(100);
        let j = serde_json::to_string(&b).unwrap();
        let back: TokenBucket = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
