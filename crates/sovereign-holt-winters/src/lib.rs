//! `sovereign-holt-winters` — forecast the load curve instead of chasing it.
//!
//! Autoscaling that only reacts is always a step behind: by the time the queue is
//! deep, the latency damage is done. Most real load is not random — it has a
//! **level** (where it sits), a **trend** (whether it is climbing), and a
//! **seasonal cycle** (the daily or weekly shape). If you model those three, you
//! can forecast the next hour and provision *before* the spike. **Holt-Winters**
//! triple exponential smoothing does exactly that.
//!
//! Each observation updates three exponentially-weighted components: the level
//! `l`, smoothed with `alpha`; the trend `b`, with `beta`; and the seasonal
//! offsets `s`, one per position in the cycle, with `gamma`. A forecast `h` steps
//! ahead is `l + h·b + s[(t+h) mod period]` — current level, projected trend, and
//! the seasonal offset for that point in the cycle. Smaller smoothing constants
//! weight history more (steady but slow to adapt); larger ones track recent change
//! (responsive but jumpier).
//!
//! This is the **additive** variant (seasonal effects add a fixed amount), the
//! right choice when the swing's size is roughly constant regardless of level.
//! [`HoltWinters::fit`] seeds the components from a history of at least two full
//! cycles; [`HoltWinters::observe`] folds in a new point online;
//! [`HoltWinters::forecast`] projects one step, [`HoltWinters::forecast_n`] a whole
//! horizon. A period of 1 degenerates to Holt's linear (level + trend) method.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the Holt-Winters surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A fitted additive Holt-Winters model.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HoltWinters {
    alpha: f64,
    beta: f64,
    gamma: f64,
    period: usize,
    level: f64,
    trend: f64,
    /// Seasonal offsets, one per position in the cycle.
    seasonals: Vec<f64>,
    /// Number of observations folded in so far (the time index).
    t: usize,
    fitted: bool,
}

/// Errors from configuring or fitting the model.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum HwError {
    /// `period` was zero.
    ZeroPeriod,
    /// A smoothing constant was outside `[0, 1]`.
    BadSmoothing,
    /// Fitting needs at least two full seasonal cycles.
    InsufficientHistory {
        /// Observations supplied.
        have: usize,
        /// Minimum required (`2 * period`).
        need: usize,
    },
    /// A forecast was requested before the model was fitted.
    NotFitted,
}

impl std::fmt::Display for HwError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HwError::ZeroPeriod => write!(f, "period must be at least 1"),
            HwError::BadSmoothing => write!(f, "smoothing constants must be in [0, 1]"),
            HwError::InsufficientHistory { have, need } => {
                write!(f, "need at least {need} observations, got {have}")
            }
            HwError::NotFitted => write!(f, "model has not been fitted"),
        }
    }
}
impl std::error::Error for HwError {}

impl HoltWinters {
    /// Configure a model with smoothing constants and a seasonal `period`. Call
    /// [`HoltWinters::fit`] before forecasting. `period = 1` is non-seasonal.
    pub fn new(alpha: f64, beta: f64, gamma: f64, period: usize) -> Result<Self, HwError> {
        if period == 0 {
            return Err(HwError::ZeroPeriod);
        }
        for &c in &[alpha, beta, gamma] {
            if !(0.0..=1.0).contains(&c) {
                return Err(HwError::BadSmoothing);
            }
        }
        Ok(Self {
            alpha,
            beta,
            gamma,
            period,
            level: 0.0,
            trend: 0.0,
            seasonals: vec![0.0; period],
            t: 0,
            fitted: false,
        })
    }

    /// The seasonal period.
    pub fn period(&self) -> usize {
        self.period
    }
    /// Whether the model has been fitted.
    pub fn is_fitted(&self) -> bool {
        self.fitted
    }
    /// The current level estimate.
    pub fn level(&self) -> f64 {
        self.level
    }
    /// The current per-step trend estimate.
    pub fn trend(&self) -> f64 {
        self.trend
    }

    /// Seed the components from `history` (chronological), then fold the whole
    /// history through the online update so the state is current.
    pub fn fit(&mut self, history: &[f64]) -> Result<(), HwError> {
        let need = (2 * self.period).max(2);
        if history.len() < need {
            return Err(HwError::InsufficientHistory {
                have: history.len(),
                need,
            });
        }
        let m = self.period;

        // initial level: mean of the first full cycle.
        let level0 = history[..m].iter().sum::<f64>() / m as f64;

        // initial trend: average per-step slope between the first two cycles.
        let mean1 = level0;
        let mean2 = history[m..2 * m].iter().sum::<f64>() / m as f64;
        let trend0 = (mean2 - mean1) / m as f64;

        // initial seasonals: average deviation from the per-cycle mean at each
        // position across all complete cycles in the history.
        let cycles = history.len() / m;
        let mut seasonals = vec![0.0; m];
        for c in 0..cycles {
            let cycle = &history[c * m..(c + 1) * m];
            let cmean = cycle.iter().sum::<f64>() / m as f64;
            for (i, &y) in cycle.iter().enumerate() {
                seasonals[i] += y - cmean;
            }
        }
        for s in &mut seasonals {
            *s /= cycles as f64;
        }

        self.level = level0;
        self.trend = trend0;
        self.seasonals = seasonals;
        self.t = 0;
        self.fitted = true;

        // run the online recurrence over the whole history to bring state current.
        for &y in history {
            self.update(y);
        }
        Ok(())
    }

    /// The core recurrence: fold one observation into level, trend, and season.
    fn update(&mut self, y: f64) {
        let m = self.period;
        let idx = self.t % m;
        let prev_season = self.seasonals[idx];
        let prev_level = self.level;

        let new_level =
            self.alpha * (y - prev_season) + (1.0 - self.alpha) * (prev_level + self.trend);
        let new_trend = self.beta * (new_level - prev_level) + (1.0 - self.beta) * self.trend;
        let new_season = self.gamma * (y - new_level) + (1.0 - self.gamma) * prev_season;

        self.level = new_level;
        self.trend = new_trend;
        self.seasonals[idx] = new_season;
        self.t += 1;
    }

    /// Fold a new observation into the fitted model (online update).
    pub fn observe(&mut self, y: f64) -> Result<(), HwError> {
        if !self.fitted {
            return Err(HwError::NotFitted);
        }
        self.update(y);
        Ok(())
    }

    /// Forecast the value `h` steps ahead (`h >= 1`).
    pub fn forecast(&self, h: usize) -> Result<f64, HwError> {
        if !self.fitted {
            return Err(HwError::NotFitted);
        }
        let h = h.max(1);
        let m = self.period;
        // seasonal index for the target step (t is the next index to be observed).
        let season = self.seasonals[(self.t + h - 1) % m];
        Ok(self.level + h as f64 * self.trend + season)
    }

    /// Forecast the next `n` steps (`1..=n`).
    pub fn forecast_n(&self, n: usize) -> Result<Vec<f64>, HwError> {
        if !self.fitted {
            return Err(HwError::NotFitted);
        }
        (1..=n).map(|h| self.forecast(h)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mape(actual: &[f64], pred: &[f64]) -> f64 {
        let mut s = 0.0;
        let mut n = 0;
        for (a, p) in actual.iter().zip(pred) {
            if a.abs() > 1e-9 {
                s += (a - p).abs() / a.abs();
                n += 1;
            }
        }
        if n == 0 { 0.0 } else { s / n as f64 }
    }

    #[test]
    fn bad_config_rejected() {
        assert_eq!(HoltWinters::new(0.5, 0.5, 0.5, 0), Err(HwError::ZeroPeriod));
        assert_eq!(
            HoltWinters::new(1.5, 0.5, 0.5, 4),
            Err(HwError::BadSmoothing)
        );
        assert!(HoltWinters::new(0.5, 0.1, 0.1, 4).is_ok());
    }

    #[test]
    fn insufficient_history() {
        let mut hw = HoltWinters::new(0.5, 0.1, 0.1, 7).unwrap();
        let short: Vec<f64> = (0..10).map(|i| i as f64).collect(); // < 14
        assert_eq!(
            hw.fit(&short),
            Err(HwError::InsufficientHistory { have: 10, need: 14 })
        );
    }

    #[test]
    fn forecast_before_fit_errors() {
        let hw = HoltWinters::new(0.5, 0.1, 0.1, 4).unwrap();
        assert_eq!(hw.forecast(1), Err(HwError::NotFitted));
    }

    #[test]
    fn pure_linear_trend() {
        // period 1 (non-seasonal): y = 2t + 5, should forecast the line.
        let mut hw = HoltWinters::new(0.6, 0.4, 0.0, 1).unwrap();
        let hist: Vec<f64> = (0..20).map(|t| 2.0 * t as f64 + 5.0).collect();
        hw.fit(&hist).unwrap();
        // next points are 2*20+5=45, 2*21+5=47, ...
        let f = hw.forecast_n(3).unwrap();
        assert!((f[0] - 45.0).abs() < 1.0, "f0 {}", f[0]);
        assert!((f[1] - 47.0).abs() < 1.0, "f1 {}", f[1]);
        assert!((f[2] - 49.0).abs() < 1.5, "f2 {}", f[2]);
    }

    #[test]
    fn constant_series() {
        let mut hw = HoltWinters::new(0.5, 0.1, 0.1, 4).unwrap();
        let hist = vec![100.0; 24];
        hw.fit(&hist).unwrap();
        let f = hw.forecast(1).unwrap();
        assert!((f - 100.0).abs() < 1.0, "forecast {f}");
    }

    #[test]
    fn seasonal_pattern_recovered() {
        // additive season of period 4 over a flat level, several cycles.
        let season = [10.0, -5.0, 3.0, -8.0];
        let base = 50.0;
        let hist: Vec<f64> = (0..40).map(|t| base + season[t % 4]).collect();
        let mut hw = HoltWinters::new(0.3, 0.05, 0.3, 4).unwrap();
        hw.fit(&hist).unwrap();
        // forecast the next full cycle; it should track the seasonal shape.
        let f = hw.forecast_n(4).unwrap();
        // the next index after 40 observations is 40 ≡ 0 (mod 4).
        let expected = [
            base + season[0],
            base + season[1],
            base + season[2],
            base + season[3],
        ];
        let err = mape(&expected, &f);
        assert!(err < 0.05, "seasonal MAPE {err}: f={f:?} exp={expected:?}");
    }

    #[test]
    fn trend_plus_season() {
        // level rises and a daily cycle rides on top.
        let season = [5.0, 15.0, 0.0, -10.0, -8.0, 2.0, 6.0];
        let hist: Vec<f64> = (0..70)
            .map(|t| 20.0 + 0.5 * t as f64 + season[t % 7])
            .collect();
        let mut hw = HoltWinters::new(0.4, 0.1, 0.2, 7).unwrap();
        hw.fit(&hist).unwrap();
        let f = hw.forecast_n(7).unwrap();
        let expected: Vec<f64> = (70..77)
            .map(|t| 20.0 + 0.5 * t as f64 + season[t % 7])
            .collect();
        let err = mape(&expected, &f);
        assert!(err < 0.05, "trend+season MAPE {err}");
    }

    #[test]
    fn online_observe_updates_state() {
        let season = [10.0, -5.0, 3.0, -8.0];
        let hist: Vec<f64> = (0..40).map(|t| 50.0 + season[t % 4]).collect();
        let mut hw = HoltWinters::new(0.3, 0.05, 0.3, 4).unwrap();
        hw.fit(&hist).unwrap();
        let before = hw.forecast(1).unwrap();
        // observing a continuation should keep forecasts sane.
        hw.observe(50.0 + season[40 % 4]).unwrap();
        let after = hw.forecast(1).unwrap();
        assert!(after.is_finite() && (after - before).abs() < 20.0);
    }

    #[test]
    fn forecast_n_length() {
        let mut hw = HoltWinters::new(0.5, 0.1, 0.1, 4).unwrap();
        hw.fit(&[10.0; 16]).unwrap();
        assert_eq!(hw.forecast_n(5).unwrap().len(), 5);
    }

    #[test]
    fn deterministic() {
        let hist: Vec<f64> = (0..40).map(|t| (t as f64).sin() + 10.0).collect();
        let mut a = HoltWinters::new(0.4, 0.1, 0.2, 8).unwrap();
        let mut b = HoltWinters::new(0.4, 0.1, 0.2, 8).unwrap();
        a.fit(&hist).unwrap();
        b.fit(&hist).unwrap();
        assert_eq!(a.forecast_n(8).unwrap(), b.forecast_n(8).unwrap());
    }

    #[test]
    fn serde_round_trip() {
        let mut hw = HoltWinters::new(0.4, 0.1, 0.2, 4).unwrap();
        hw.fit(&[1.0, 2.0, 3.0, 4.0, 2.0, 3.0, 4.0, 5.0]).unwrap();
        let j = serde_json::to_string(&hw).unwrap();
        let back: HoltWinters = serde_json::from_str(&j).unwrap();
        // JSON serializes f64 to shortest-round-trippable text, which can drift by
        // a ULP, so compare behaviour within tolerance rather than bit-for-bit.
        assert_eq!(hw.period(), back.period());
        assert_eq!(hw.is_fitted(), back.is_fitted());
        let (a, b) = (hw.forecast(1).unwrap(), back.forecast(1).unwrap());
        assert!((a - b).abs() < 1e-6, "forecast drift {a} vs {b}");
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
