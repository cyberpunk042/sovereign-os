//! `sovereign-sprt` — stop the test the moment the answer is clear.
//!
//! A fixed-size experiment commits up front to `N` samples whether or not the
//! verdict is obvious after ten. **Wald's sequential probability ratio test** does
//! the opposite: it watches the evidence accumulate and stops as soon as it crosses
//! a decision boundary, which on average needs far fewer observations than a
//! fixed-`N` test for the same error guarantees. That is exactly what you want when
//! each sample costs a real inference call — comparing a candidate model against a
//! baseline, or deciding whether a rollout's success rate is acceptable.
//!
//! The test pits two hypotheses about a Bernoulli success rate: `H0: p = p0` against
//! `H1: p = p1`. Each observation adds its **log-likelihood ratio** to a running
//! total — a success contributes `ln(p1/p0)`, a failure `ln((1−p1)/(1−p0))`. Two
//! boundaries, derived from the target type-I error `alpha` (wrongly choosing H1)
//! and type-II error `beta` (wrongly choosing H0), bracket the total: cross the
//! upper one and the test **accepts H1**, cross the lower and it **accepts H0**, and
//! in between it asks for **one more sample**. Wald's approximation sets those
//! boundaries at `ln((1−beta)/alpha)` and `ln(beta/(1−alpha))`.
//!
//! [`Sprt::observe`] feeds one outcome and returns the current [`Decision`];
//! [`Sprt::log_likelihood_ratio`] and [`Sprt::observations`] expose the state; and
//! [`Sprt::decision`] reports the verdict so far. Once a boundary is crossed the
//! decision is final and further observations leave it unchanged.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the SPRT surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The current verdict of a sequential test.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Decision {
    /// Not enough evidence yet — collect another sample.
    Continue,
    /// Evidence favours `H0` (`p = p0`).
    AcceptH0,
    /// Evidence favours `H1` (`p = p1`).
    AcceptH1,
}

/// A Wald sequential probability ratio test for a Bernoulli rate.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Sprt {
    p0: f64,
    p1: f64,
    /// Upper boundary `ln((1-beta)/alpha)` — cross it to accept H1.
    upper: f64,
    /// Lower boundary `ln(beta/(1-alpha))` — cross it to accept H0.
    lower: f64,
    /// Per-success and per-failure log-likelihood increments.
    inc_success: f64,
    inc_failure: f64,
    /// Running log-likelihood ratio.
    llr: f64,
    /// Observations seen.
    n: u64,
    /// Successes seen.
    successes: u64,
    decision: Decision,
}

impl Sprt {
    /// A test of `H0: p = p0` vs `H1: p = p1` with target error rates `alpha`
    /// (type-I) and `beta` (type-II). Probabilities are clamped into `(0, 1)` and
    /// error rates into a small open interval to keep the boundaries finite.
    pub fn new(p0: f64, p1: f64, alpha: f64, beta: f64) -> Self {
        let eps = 1e-9;
        let p0 = p0.clamp(eps, 1.0 - eps);
        let p1 = p1.clamp(eps, 1.0 - eps);
        let alpha = alpha.clamp(eps, 0.5);
        let beta = beta.clamp(eps, 0.5);
        let upper = ((1.0 - beta) / alpha).ln();
        let lower = (beta / (1.0 - alpha)).ln();
        Self {
            p0,
            p1,
            upper,
            lower,
            inc_success: (p1 / p0).ln(),
            inc_failure: ((1.0 - p1) / (1.0 - p0)).ln(),
            llr: 0.0,
            n: 0,
            successes: 0,
            decision: Decision::Continue,
        }
    }

    /// The current running log-likelihood ratio.
    pub fn log_likelihood_ratio(&self) -> f64 {
        self.llr
    }
    /// Number of observations so far.
    pub fn observations(&self) -> u64 {
        self.n
    }
    /// Number of successes so far.
    pub fn successes(&self) -> u64 {
        self.successes
    }
    /// The current decision.
    pub fn decision(&self) -> Decision {
        self.decision
    }
    /// Whether the test has reached a verdict.
    pub fn is_decided(&self) -> bool {
        self.decision != Decision::Continue
    }
    /// The decision boundaries `(lower, upper)` in log-likelihood units.
    pub fn boundaries(&self) -> (f64, f64) {
        (self.lower, self.upper)
    }

    /// Feed one Bernoulli outcome and return the updated decision. Once decided,
    /// further observations are ignored and the verdict stands.
    pub fn observe(&mut self, success: bool) -> Decision {
        if self.decision != Decision::Continue {
            return self.decision;
        }
        self.n += 1;
        if success {
            self.successes += 1;
            self.llr += self.inc_success;
        } else {
            self.llr += self.inc_failure;
        }
        if self.llr >= self.upper {
            self.decision = Decision::AcceptH1;
        } else if self.llr <= self.lower {
            self.decision = Decision::AcceptH0;
        }
        self.decision
    }

    /// Feed a batch with `successes` out of `total`, returning the final decision.
    pub fn observe_batch(&mut self, successes: u64, total: u64) -> Decision {
        for i in 0..total {
            if self.observe(i < successes) != Decision::Continue {
                break;
            }
        }
        self.decision
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A seeded Bernoulli source.
    fn bernoulli(seed: u64, p: f64) -> impl FnMut() -> bool {
        let mut s = seed | 1;
        move || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            let u = (s >> 40) as f64 / (1u64 << 24) as f64;
            u < p
        }
    }

    #[test]
    fn boundaries_are_correct() {
        let t = Sprt::new(0.5, 0.7, 0.05, 0.1);
        let (lo, hi) = t.boundaries();
        assert!((hi - ((1.0 - 0.1) / 0.05_f64).ln()).abs() < 1e-9);
        assert!((lo - (0.1_f64 / (1.0 - 0.05)).ln()).abs() < 1e-9);
        // upper positive, lower negative.
        assert!(hi > 0.0 && lo < 0.0);
    }

    #[test]
    fn accepts_h1_when_rate_is_high() {
        // true p = 0.8, testing p0=0.5 vs p1=0.7 → should accept H1.
        let mut t = Sprt::new(0.5, 0.7, 0.05, 0.05);
        let mut src = bernoulli(1, 0.85);
        let mut decided = Decision::Continue;
        for _ in 0..5000 {
            decided = t.observe(src());
            if decided != Decision::Continue {
                break;
            }
        }
        assert_eq!(decided, Decision::AcceptH1);
    }

    #[test]
    fn accepts_h0_when_rate_is_low() {
        // true p = 0.4 → should accept H0 (p=0.5) over H1 (p=0.7).
        let mut t = Sprt::new(0.5, 0.7, 0.05, 0.05);
        let mut src = bernoulli(2, 0.4);
        let mut decided = Decision::Continue;
        for _ in 0..5000 {
            decided = t.observe(src());
            if decided != Decision::Continue {
                break;
            }
        }
        assert_eq!(decided, Decision::AcceptH0);
    }

    #[test]
    fn stops_early_on_clear_signal() {
        // an overwhelming signal should decide in far fewer than a fixed-N test.
        let mut t = Sprt::new(0.5, 0.9, 0.05, 0.05);
        let mut src = bernoulli(3, 0.99);
        while t.observe(src()) == Decision::Continue {}
        assert!(t.is_decided());
        assert!(t.observations() < 50, "took {} samples", t.observations());
    }

    #[test]
    fn decision_is_final() {
        let mut t = Sprt::new(0.5, 0.7, 0.05, 0.05);
        let mut src = bernoulli(4, 0.95);
        while t.observe(src()) == Decision::Continue {}
        let d = t.decision();
        let n = t.observations();
        // further observations of the opposite outcome do not change the verdict.
        for _ in 0..100 {
            t.observe(false);
        }
        assert_eq!(t.decision(), d);
        assert_eq!(t.observations(), n);
    }

    #[test]
    fn error_rates_roughly_controlled() {
        // over many trials with true p = p1, false H0 acceptances stay rare.
        let mut wrong = 0;
        let trials = 300;
        for trial in 0..trials {
            let mut t = Sprt::new(0.5, 0.7, 0.05, 0.05);
            let mut src = bernoulli(1000 + trial, 0.7);
            while t.observe(src()) == Decision::Continue {}
            if t.decision() == Decision::AcceptH0 {
                wrong += 1;
            }
        }
        // beta target 0.05; allow slack for the Wald approximation and sampling.
        let rate = wrong as f64 / trials as f64;
        assert!(rate < 0.15, "type-II rate {wrong}/{trials}");
    }

    #[test]
    fn observe_batch() {
        let mut t = Sprt::new(0.5, 0.7, 0.05, 0.05);
        // a strongly-successful batch.
        let d = t.observe_batch(95, 100);
        assert_eq!(d, Decision::AcceptH1);
    }

    #[test]
    fn serde_round_trip() {
        let mut t = Sprt::new(0.5, 0.7, 0.05, 0.1);
        t.observe(true);
        t.observe(false);
        let j = serde_json::to_string(&t).unwrap();
        let back: Sprt = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
