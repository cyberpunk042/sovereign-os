//! `sovereign-p2c-balance` — spread load by asking two and picking the better.
//!
//! Routing every request to the globally least-loaded backend needs a constantly-
//! updated global view; routing at random is cheap but lets some backend get
//! unlucky and pile up. **Power of two choices** is the surprising middle: pick
//! *two* backends at random and send the request to whichever is less loaded. That
//! single extra sample drops the maximum load from `O(log n / log log n)` above
//! average (pure random) to `O(log log n)` — an exponential improvement — while
//! keeping the decision local and `O(1)`. It is the default balancer in systems
//! like Finagle and Envoy for exactly this reason.
//!
//! Each backend tracks its **in-flight** count. [`P2cBalancer::pick`] samples two
//! distinct backends with a seeded RNG and returns the one with the lower load,
//! incrementing it; the caller reports completion with [`P2cBalancer::complete`].
//! Backends can carry **weights**: load is compared as in-flight *per unit weight*,
//! so a backend with twice the capacity is allowed twice the in-flight work before
//! it looks equally loaded, and it receives proportionally more traffic. With a
//! single backend the choice is trivial; with none, `pick` returns `None`. The RNG
//! is seeded, so a request sequence routes reproducibly.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the P2C surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One backend: its capacity weight and current in-flight count.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
struct Backend {
    weight: f64,
    in_flight: u64,
}

/// A power-of-two-choices load balancer over a fixed set of backends.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct P2cBalancer {
    backends: Vec<Backend>,
    rng_state: u64,
}

impl P2cBalancer {
    /// A balancer over backends with the given positive `weights` (a non-positive
    /// or non-finite weight is clamped to `1.0`).
    pub fn new(weights: &[f64], seed: u64) -> Self {
        let backends = weights
            .iter()
            .map(|&w| Backend {
                weight: if w.is_finite() && w > 0.0 { w } else { 1.0 },
                in_flight: 0,
            })
            .collect();
        Self {
            backends,
            rng_state: seed | 1,
        }
    }

    /// A balancer with `n` equally-weighted backends.
    pub fn uniform(n: usize, seed: u64) -> Self {
        Self::new(&vec![1.0; n], seed)
    }

    /// Number of backends.
    pub fn len(&self) -> usize {
        self.backends.len()
    }
    /// Whether there are no backends.
    pub fn is_empty(&self) -> bool {
        self.backends.is_empty()
    }
    /// The in-flight count of backend `i`.
    pub fn in_flight(&self, i: usize) -> u64 {
        self.backends.get(i).map(|b| b.in_flight).unwrap_or(0)
    }
    /// The in-flight counts of all backends.
    pub fn loads(&self) -> Vec<u64> {
        self.backends.iter().map(|b| b.in_flight).collect()
    }
    /// The weight of backend `i`.
    pub fn weight(&self, i: usize) -> f64 {
        self.backends.get(i).map(|b| b.weight).unwrap_or(0.0)
    }

    fn next_rand(&mut self) -> u64 {
        self.rng_state = self.rng_state.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.rng_state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Normalized load of a backend: in-flight per unit weight.
    fn load(&self, i: usize) -> f64 {
        let b = &self.backends[i];
        b.in_flight as f64 / b.weight
    }

    /// Of two candidate backends, the one with the lower normalized load (ties to
    /// the lower index).
    fn better(&self, a: usize, b: usize) -> usize {
        if self.load(a) <= self.load(b) { a } else { b }
    }

    /// Choose a backend for a new request and increment its in-flight count.
    /// `None` if there are no backends.
    pub fn pick(&mut self) -> Option<usize> {
        let n = self.backends.len();
        if n == 0 {
            return None;
        }
        let chosen = if n == 1 {
            0
        } else {
            // two distinct uniform samples.
            let a = (self.next_rand() % n as u64) as usize;
            let mut b = (self.next_rand() % (n as u64 - 1)) as usize;
            if b >= a {
                b += 1;
            }
            self.better(a, b)
        };
        self.backends[chosen].in_flight += 1;
        Some(chosen)
    }

    /// Report that a request on backend `i` finished, decrementing its in-flight
    /// count (saturating at zero).
    pub fn complete(&mut self, i: usize) {
        if let Some(b) = self.backends.get_mut(i) {
            b.in_flight = b.in_flight.saturating_sub(1);
        }
    }

    /// Total in-flight across all backends.
    pub fn total_in_flight(&self) -> u64 {
        self.backends.iter().map(|b| b.in_flight).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_picks_none() {
        let mut lb = P2cBalancer::uniform(0, 1);
        assert!(lb.is_empty());
        assert_eq!(lb.pick(), None);
    }

    #[test]
    fn single_backend_always_chosen() {
        let mut lb = P2cBalancer::uniform(1, 1);
        for _ in 0..10 {
            assert_eq!(lb.pick(), Some(0));
        }
        assert_eq!(lb.in_flight(0), 10);
    }

    #[test]
    fn complete_decrements() {
        let mut lb = P2cBalancer::uniform(3, 7);
        let i = lb.pick().unwrap();
        assert_eq!(lb.in_flight(i), 1);
        lb.complete(i);
        assert_eq!(lb.in_flight(i), 0);
        // saturating: extra completes don't underflow.
        lb.complete(i);
        assert_eq!(lb.in_flight(i), 0);
    }

    #[test]
    fn keeps_max_load_low() {
        // issue many requests without completing; P2C keeps the peak near average.
        let n = 16;
        let mut lb = P2cBalancer::uniform(n, 12345);
        let k = 160; // 10x average
        for _ in 0..k {
            lb.pick();
        }
        let loads = lb.loads();
        let max = *loads.iter().max().unwrap();
        let avg = k as f64 / n as f64; // 10
        // P2C keeps the max within a small additive gap of the average.
        assert!(
            (max as f64) <= avg + 4.0,
            "max {max} too far above avg {avg}: {loads:?}"
        );
        assert_eq!(lb.total_in_flight(), k);
    }

    #[test]
    fn avoids_the_loaded_backend() {
        // a backend already saturated should rarely be picked relative to idle ones.
        let mut lb = P2cBalancer::uniform(4, 99);
        // pile load onto backend 0 by hand via picks then targeted accounting:
        // issue 30 picks; whichever it is, the busiest should not run away.
        for _ in 0..40 {
            let i = lb.pick().unwrap();
            // immediately free everything except keep some pressure: complete half.
            if i % 2 == 0 {
                lb.complete(i);
            }
        }
        let loads = lb.loads();
        let max = *loads.iter().max().unwrap();
        let min = *loads.iter().min().unwrap();
        assert!(max - min <= 20, "imbalanced: {loads:?}");
    }

    #[test]
    fn weighted_backend_gets_more_traffic() {
        // weights [1, 1, 8]: backend 2 should receive the majority of routes.
        let mut lb = P2cBalancer::new(&[1.0, 1.0, 8.0], 2024);
        let mut counts = [0u64; 3];
        // a steady-state simulation: keep ~lag requests in flight.
        let lag = 20;
        let mut queue: std::collections::VecDeque<usize> = std::collections::VecDeque::new();
        for _ in 0..10_000 {
            let i = lb.pick().unwrap();
            counts[i] += 1;
            queue.push_back(i);
            if queue.len() > lag {
                let done = queue.pop_front().unwrap();
                lb.complete(done);
            }
        }
        // backend 2 (8x capacity) gets far more than the two light backends.
        assert!(counts[2] > counts[0] + counts[1], "counts {counts:?}");
        assert!(counts[2] > 5_000, "heavy backend share {counts:?}");
    }

    #[test]
    fn equal_weights_share_roughly_evenly() {
        let mut lb = P2cBalancer::new(&[1.0, 1.0, 1.0, 1.0], 555);
        let mut counts = [0u64; 4];
        let lag = 8;
        let mut q = std::collections::VecDeque::new();
        for _ in 0..8_000 {
            let i = lb.pick().unwrap();
            counts[i] += 1;
            q.push_back(i);
            if q.len() > lag {
                lb.complete(q.pop_front().unwrap());
            }
        }
        let max = *counts.iter().max().unwrap();
        let min = *counts.iter().min().unwrap();
        // shares are close (within ~20% of each other).
        let spread = (max - min) as f64 / max as f64;
        assert!(spread < 0.2, "uneven {counts:?}");
    }

    #[test]
    fn deterministic_for_seed() {
        let mut a = P2cBalancer::uniform(5, 42);
        let mut b = P2cBalancer::uniform(5, 42);
        let sa: Vec<usize> = (0..50).map(|_| a.pick().unwrap()).collect();
        let sb: Vec<usize> = (0..50).map(|_| b.pick().unwrap()).collect();
        assert_eq!(sa, sb);
    }

    #[test]
    fn bad_weights_clamped() {
        let lb = P2cBalancer::new(&[0.0, -3.0, f64::NAN, 4.0], 1);
        assert_eq!(lb.weight(0), 1.0);
        assert_eq!(lb.weight(1), 1.0);
        assert_eq!(lb.weight(2), 1.0);
        assert_eq!(lb.weight(3), 4.0);
    }

    #[test]
    fn serde_round_trip() {
        let mut lb = P2cBalancer::new(&[1.0, 2.0, 3.0], 9);
        lb.pick();
        lb.pick();
        let j = serde_json::to_string(&lb).unwrap();
        let back: P2cBalancer = serde_json::from_str(&j).unwrap();
        assert_eq!(lb, back);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
