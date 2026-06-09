//! `sovereign-kalman` — a smooth, responsive estimate from jittery measurements.
//!
//! A runtime constantly estimates a quantity it can only measure noisily: current
//! latency, throughput, a queue's drain rate, a drifting setpoint. A plain moving
//! average is either too sluggish (long window) or too jumpy (short window), and it
//! offers no sense of how sure it is. A **Kalman filter** does better by reasoning
//! about *uncertainty*: it carries an estimate and a variance, and each step fuses
//! its own prediction with a new measurement weighted by which of the two it trusts
//! more.
//!
//! This is the scalar **local-level** model — the quantity is assumed roughly
//! constant but free to drift. Each cycle has two steps. **Predict** keeps the
//! estimate and inflates its variance by the *process noise* `q` (how much the true
//! value can wander between samples). **Update** takes a measurement of *measurement
//! noise* `r`, computes the **Kalman gain** `k = p / (p + r)` — the fraction of the
//! way to move toward the measurement — and shrinks the variance accordingly. Large
//! `q` or small `r` makes the filter nimble; small `q` or large `r` makes it steady.
//! Over time the variance settles and the gain reaches a constant, the optimal
//! smoothing for that noise ratio.
//!
//! [`KalmanFilter::observe`] runs predict-then-update for one sample and returns the
//! new estimate; [`KalmanFilter::value`] and [`KalmanFilter::variance`] read the
//! current state, and [`KalmanFilter::gain`] reports the last blend factor. The math
//! is deterministic, so a sample sequence always yields the same track.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the Kalman surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A scalar Kalman filter over a local-level (random-walk) model.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct KalmanFilter {
    /// Current state estimate.
    x: f64,
    /// Current estimate variance (uncertainty).
    p: f64,
    /// Process noise: how much the true value may drift per step.
    q: f64,
    /// Measurement noise: the variance of each observation.
    r: f64,
    /// Last Kalman gain applied.
    last_gain: f64,
}

impl KalmanFilter {
    /// A filter starting at `initial_value` with `initial_variance`, process noise
    /// `process_noise`, and measurement noise `measurement_noise`. Noise terms are
    /// clamped to be non-negative; measurement noise is kept strictly positive.
    pub fn new(
        initial_value: f64,
        initial_variance: f64,
        process_noise: f64,
        measurement_noise: f64,
    ) -> Self {
        Self {
            x: initial_value,
            p: initial_variance.max(0.0),
            q: process_noise.max(0.0),
            r: measurement_noise.max(f64::MIN_POSITIVE),
            last_gain: 0.0,
        }
    }

    /// The current estimate.
    pub fn value(&self) -> f64 {
        self.x
    }
    /// The current estimate variance.
    pub fn variance(&self) -> f64 {
        self.p
    }
    /// The standard deviation of the current estimate.
    pub fn std_dev(&self) -> f64 {
        self.p.sqrt()
    }
    /// The most recently applied Kalman gain (`0` before any update).
    pub fn gain(&self) -> f64 {
        self.last_gain
    }
    /// The configured process noise.
    pub fn process_noise(&self) -> f64 {
        self.q
    }
    /// The configured measurement noise.
    pub fn measurement_noise(&self) -> f64 {
        self.r
    }

    /// Predict step: the estimate is unchanged but its uncertainty grows by the
    /// process noise.
    pub fn predict(&mut self) {
        self.p += self.q;
    }

    /// Update step: fold in a `measurement` (with the configured measurement noise),
    /// moving the estimate toward it by the Kalman gain and shrinking the variance.
    /// Returns the new estimate.
    pub fn update(&mut self, measurement: f64) -> f64 {
        if !measurement.is_finite() {
            return self.x;
        }
        let k = self.p / (self.p + self.r);
        self.x += k * (measurement - self.x);
        self.p *= 1.0 - k;
        self.last_gain = k;
        self.x
    }

    /// Run a full predict-then-update cycle for one `measurement`. Returns the new
    /// estimate.
    pub fn observe(&mut self, measurement: f64) -> f64 {
        self.predict();
        self.update(measurement)
    }

    /// Update with a measurement that has its own one-off `noise` variance (instead
    /// of the configured measurement noise), after predicting. Returns the estimate.
    pub fn observe_with_noise(&mut self, measurement: f64, noise: f64) -> f64 {
        self.predict();
        if !measurement.is_finite() {
            return self.x;
        }
        let r = noise.max(f64::MIN_POSITIVE);
        let k = self.p / (self.p + r);
        self.x += k * (measurement - self.x);
        self.p *= 1.0 - k;
        self.last_gain = k;
        self.x
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Deterministic noise generator in roughly `[-1, 1]`.
    fn noise_seq(seed: u64) -> impl FnMut() -> f64 {
        let mut s = seed | 1;
        move || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            ((s >> 40) as f64 / (1u64 << 24) as f64) * 2.0 - 1.0
        }
    }

    #[test]
    fn converges_to_constant() {
        // true value 10, noisy measurements; the filter should settle near 10.
        let mut kf = KalmanFilter::new(0.0, 1.0, 0.001, 1.0);
        let mut noise = noise_seq(42);
        let mut est = 0.0;
        for _ in 0..500 {
            est = kf.observe(10.0 + noise() * 2.0);
        }
        assert!((est - 10.0).abs() < 0.5, "estimate {est}");
    }

    #[test]
    fn tracks_a_step_change() {
        // value jumps from 5 to 20 partway; the filter should follow.
        let mut kf = KalmanFilter::new(5.0, 1.0, 0.05, 1.0);
        let mut noise = noise_seq(7);
        for _ in 0..200 {
            kf.observe(5.0 + noise() * 0.5);
        }
        let before = kf.value();
        assert!((before - 5.0).abs() < 0.5);
        for _ in 0..200 {
            kf.observe(20.0 + noise() * 0.5);
        }
        assert!((kf.value() - 20.0).abs() < 0.5, "after step {}", kf.value());
    }

    #[test]
    fn variance_decreases_then_stabilizes() {
        let mut kf = KalmanFilter::new(0.0, 10.0, 0.01, 1.0);
        let v0 = kf.variance();
        for _ in 0..5 {
            kf.observe(1.0);
        }
        let v_early = kf.variance();
        assert!(v_early < v0, "variance should drop: {v0} -> {v_early}");
        for _ in 0..100 {
            kf.observe(1.0);
        }
        let v_late = kf.variance();
        // steady-state variance is positive and not larger than the early value.
        assert!(v_late > 0.0 && v_late <= v_early + 1e-9);
    }

    #[test]
    fn gain_in_unit_interval() {
        let mut kf = KalmanFilter::new(0.0, 1.0, 0.1, 2.0);
        for _ in 0..50 {
            kf.observe(3.0);
            let g = kf.gain();
            assert!((0.0..=1.0).contains(&g), "gain {g}");
        }
    }

    #[test]
    fn high_measurement_noise_tracks_slowly() {
        // a single big jump: high r moves less than low r in one step.
        let mut trusting = KalmanFilter::new(0.0, 1.0, 0.0, 0.1); // low r
        let mut skeptical = KalmanFilter::new(0.0, 1.0, 0.0, 100.0); // high r
        trusting.observe(100.0);
        skeptical.observe(100.0);
        assert!(
            trusting.value() > skeptical.value(),
            "trusting {} skeptical {}",
            trusting.value(),
            skeptical.value()
        );
    }

    #[test]
    fn smooths_noise_better_than_raw() {
        // the filtered track should be closer to the truth than raw measurements.
        let truth = 50.0;
        let mut kf = KalmanFilter::new(50.0, 1.0, 0.001, 4.0);
        let mut noise = noise_seq(99);
        let mut sum_raw_err = 0.0;
        let mut sum_filt_err = 0.0;
        for _ in 0..300 {
            let z = truth + noise() * 4.0;
            let est = kf.observe(z);
            sum_raw_err += (z - truth).abs();
            sum_filt_err += (est - truth).abs();
        }
        assert!(
            sum_filt_err < sum_raw_err,
            "filt {sum_filt_err} raw {sum_raw_err}"
        );
    }

    #[test]
    fn per_measurement_noise() {
        // a low-noise measurement should move the estimate more than a high-noise one.
        let mut a = KalmanFilter::new(0.0, 1.0, 0.0, 1.0);
        let mut b = a;
        a.observe_with_noise(10.0, 0.01); // very trustworthy
        b.observe_with_noise(10.0, 1000.0); // barely trusted
        assert!(a.value() > b.value());
    }

    #[test]
    fn ignores_non_finite_measurement() {
        let mut kf = KalmanFilter::new(5.0, 1.0, 0.1, 1.0);
        kf.observe(5.0);
        let before = kf.value();
        let after = kf.observe(f64::NAN);
        assert_eq!(before, after);
    }

    #[test]
    fn deterministic() {
        let run = || {
            let mut kf = KalmanFilter::new(0.0, 1.0, 0.01, 1.0);
            let mut noise = noise_seq(123);
            let mut v = 0.0;
            for _ in 0..100 {
                v = kf.observe(7.0 + noise());
            }
            v
        };
        assert_eq!(run(), run());
    }

    #[test]
    fn serde_round_trip() {
        let mut kf = KalmanFilter::new(1.0, 2.0, 0.1, 0.5);
        kf.observe(3.0);
        let j = serde_json::to_string(&kf).unwrap();
        let back: KalmanFilter = serde_json::from_str(&j).unwrap();
        assert_eq!(kf, back);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
