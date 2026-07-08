//! `sovereign-aimd-limiter` — find a server's capacity instead of guessing it.
//!
//! A fixed concurrency cap is always wrong: too low wastes a fast backend, too high
//! buries a slow one. The robust answer is the law that keeps the internet stable —
//! **AIMD**, additive-increase / multiplicative-decrease — applied to in-flight
//! requests instead of TCP segments. Probe upward gently while things are healthy;
//! back off hard the instant they are not. The limit then tracks the backend's real
//! capacity as a sawtooth, with no magic constant to tune.
//!
//! The rule: a request is admitted only while `in_flight < floor(limit)`. When a
//! request completes successfully *and the limiter is saturated* (we were actually
//! testing the ceiling), the limit rises by a small additive step. When a request
//! reports **overload** — a timeout, a dropped/5xx response, or a latency past a
//! threshold — the limit is multiplied by a backoff factor (e.g. `0.9`) and clamped
//! to a floor. Increasing only under saturation is what stops the limit from
//! drifting to infinity during light traffic; the multiplicative cut is what makes
//! it shed load fast when the backend buckles.
//!
//! [`AimdLimiter::try_acquire`] admits or rejects and tracks the in-flight count;
//! every admitted request must be returned with [`AimdLimiter::record_success`] or
//! [`AimdLimiter::record_overload`] (or [`AimdLimiter::record_latency`], which
//! classifies by a threshold). State is updated arithmetically with no clock, so a
//! given event sequence is fully reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the AIMD-limiter surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// An adaptive concurrency limiter governed by AIMD.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AimdLimiter {
    /// Current concurrency limit (fractional; admission uses its floor).
    limit: f64,
    /// Lower bound on the limit.
    min_limit: f64,
    /// Upper bound on the limit.
    max_limit: f64,
    /// Additive step applied on a saturated success.
    increase: f64,
    /// Multiplicative factor applied on overload (in `(0, 1)`).
    decrease: f64,
    /// Requests currently in flight.
    in_flight: usize,
}

/// The outcome of a completed request, fed back to the limiter.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Outcome {
    /// Completed within healthy bounds.
    Success,
    /// Timed out, was dropped/rejected, or breached the latency threshold.
    Overload,
    /// Do not adjust the limit from this sample (e.g. a client cancellation).
    Ignore,
}

impl AimdLimiter {
    /// A limiter starting at `initial`, bounded by `[min_limit, max_limit]`, rising
    /// by `increase` per saturated success and falling by factor `decrease` on
    /// overload. `decrease` is clamped to `(0, 1)`; bounds are kept ordered.
    pub fn new(initial: f64, min_limit: f64, max_limit: f64, increase: f64, decrease: f64) -> Self {
        let min_limit = min_limit.max(1.0);
        let max_limit = max_limit.max(min_limit);
        Self {
            limit: initial.clamp(min_limit, max_limit),
            min_limit,
            max_limit,
            increase: increase.max(0.0),
            decrease: decrease.clamp(0.01, 0.999),
            in_flight: 0,
        }
    }

    /// A limiter with common defaults: start 10, range `[1, 1000]`, `+1` increase,
    /// `0.9` backoff.
    pub fn with_defaults() -> Self {
        Self::new(10.0, 1.0, 1000.0, 1.0, 0.9)
    }

    /// The current (fractional) limit.
    pub fn limit(&self) -> f64 {
        self.limit
    }
    /// The current integer admission limit (`floor(limit)`).
    pub fn limit_floor(&self) -> usize {
        self.limit.floor() as usize
    }
    /// Requests currently in flight.
    pub fn in_flight(&self) -> usize {
        self.in_flight
    }
    /// Remaining admission slots right now.
    pub fn available(&self) -> usize {
        self.limit_floor().saturating_sub(self.in_flight)
    }
    /// Whether the limiter is saturated (in-flight at or above the floor).
    pub fn is_saturated(&self) -> bool {
        self.in_flight >= self.limit_floor()
    }

    /// Try to admit a request. On success the in-flight count rises and the caller
    /// must later report the outcome; on rejection nothing changes.
    pub fn try_acquire(&mut self) -> bool {
        if self.in_flight < self.limit_floor() {
            self.in_flight += 1;
            true
        } else {
            false
        }
    }

    /// Release an admitted request without adjusting the limit.
    fn release(&mut self) {
        self.in_flight = self.in_flight.saturating_sub(1);
    }

    /// Report a successful completion: release the slot and, if the limiter was
    /// saturated when admitted (we were probing the ceiling), additively increase.
    pub fn record_success(&mut self) {
        // saturation is judged *before* releasing: in_flight reflects the load that
        // just succeeded.
        let saturated = self.in_flight >= self.limit_floor();
        self.release();
        if saturated {
            self.limit = (self.limit + self.increase).min(self.max_limit);
        }
    }

    /// Report an overload: release the slot and multiplicatively decrease.
    pub fn record_overload(&mut self) {
        self.release();
        self.limit = (self.limit * self.decrease).max(self.min_limit);
    }

    /// Report by outcome.
    pub fn record(&mut self, outcome: Outcome) {
        match outcome {
            Outcome::Success => self.record_success(),
            Outcome::Overload => self.record_overload(),
            Outcome::Ignore => self.release(),
        }
    }

    /// Report by latency: a sample at or below `threshold` is a success, above it an
    /// overload.
    pub fn record_latency(&mut self, latency: f64, threshold: f64) {
        if latency > threshold {
            self.record_overload();
        } else {
            self.record_success();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn admits_up_to_limit() {
        let mut l = AimdLimiter::new(3.0, 1.0, 100.0, 1.0, 0.9);
        assert!(l.try_acquire());
        assert!(l.try_acquire());
        assert!(l.try_acquire());
        assert!(!l.try_acquire()); // 4th rejected at limit 3
        assert_eq!(l.in_flight(), 3);
        assert_eq!(l.available(), 0);
    }

    #[test]
    fn saturated_success_increases() {
        let mut l = AimdLimiter::new(2.0, 1.0, 100.0, 1.0, 0.9);
        l.try_acquire();
        l.try_acquire(); // saturated at 2
        assert!(l.is_saturated());
        l.record_success(); // was saturated → +1
        assert!(approx(l.limit(), 3.0));
    }

    #[test]
    fn unsaturated_success_does_not_inflate() {
        let mut l = AimdLimiter::new(10.0, 1.0, 100.0, 1.0, 0.9);
        l.try_acquire(); // 1 in flight, limit 10 → not saturated
        l.record_success();
        assert!(approx(l.limit(), 10.0), "limit {}", l.limit());
    }

    #[test]
    fn overload_decreases_multiplicatively() {
        let mut l = AimdLimiter::new(100.0, 1.0, 1000.0, 1.0, 0.5);
        l.try_acquire();
        l.record_overload();
        assert!(approx(l.limit(), 50.0));
    }

    #[test]
    fn limit_respects_bounds() {
        // cannot exceed max.
        let mut l = AimdLimiter::new(99.0, 1.0, 100.0, 5.0, 0.9);
        l.try_acquire();
        while l.try_acquire() {}
        l.record_success();
        assert!(l.limit() <= 100.0);
        // cannot drop below min.
        let mut l2 = AimdLimiter::new(2.0, 2.0, 100.0, 1.0, 0.1);
        l2.try_acquire();
        l2.record_overload();
        assert!(l2.limit() >= 2.0);
    }

    #[test]
    fn in_flight_tracking() {
        let mut l = AimdLimiter::with_defaults();
        l.try_acquire();
        l.try_acquire();
        assert_eq!(l.in_flight(), 2);
        l.record_success();
        assert_eq!(l.in_flight(), 1);
        l.record_overload();
        assert_eq!(l.in_flight(), 0);
    }

    #[test]
    fn latency_classifies() {
        let mut l = AimdLimiter::new(10.0, 1.0, 100.0, 1.0, 0.9);
        l.try_acquire();
        l.record_latency(200.0, 100.0); // over threshold → overload
        assert!(l.limit() < 10.0);
        let before = l.limit();
        // make it saturated then a fast sample increases.
        let target = l.limit_floor();
        for _ in 0..target {
            l.try_acquire();
        }
        l.record_latency(50.0, 100.0); // under threshold → success (saturated)
        assert!(l.limit() >= before);
    }

    #[test]
    fn ignore_releases_without_adjusting() {
        let mut l = AimdLimiter::new(5.0, 1.0, 100.0, 1.0, 0.9);
        l.try_acquire();
        l.try_acquire();
        l.record(Outcome::Ignore);
        assert_eq!(l.in_flight(), 1);
        assert!(approx(l.limit(), 5.0));
    }

    #[test]
    fn converges_near_true_capacity() {
        // simulate a backend whose real capacity is 20: a request overloads if it
        // would push concurrent load above capacity.
        let capacity = 20usize;
        let mut l = AimdLimiter::new(5.0, 1.0, 200.0, 1.0, 0.9);
        // run many admission/completion rounds.
        let mut samples = Vec::new();
        for _round in 0..4000 {
            // admit as many as allowed, recording the concurrency each sees.
            let mut admitted = Vec::new();
            while l.try_acquire() {
                admitted.push(l.in_flight());
            }
            // complete them: those admitted beyond capacity report overload.
            for conc in admitted {
                if conc > capacity {
                    l.record_overload();
                } else {
                    l.record_success();
                }
            }
            samples.push(l.limit());
        }
        // the limit should hover around the true capacity (sawtooth), not run away.
        let tail = &samples[samples.len() - 500..];
        let avg: f64 = tail.iter().sum::<f64>() / tail.len() as f64;
        assert!(
            (10.0..=30.0).contains(&avg),
            "converged average {avg}, expected near {capacity}"
        );
    }

    #[test]
    fn serde_round_trip() {
        let mut l = AimdLimiter::with_defaults();
        l.try_acquire();
        l.record_overload();
        let j = serde_json::to_string(&l).unwrap();
        let back: AimdLimiter = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
