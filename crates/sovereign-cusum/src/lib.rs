//! `sovereign-cusum` — notice when a metric quietly shifts.
//!
//! A self-watching system needs to tell a *persistent* change from ordinary
//! noise: latency creeping up, the speculative acceptance rate dropping, output
//! quality sliding. Comparing each sample to a threshold is too jumpy; averaging
//! over a window is too slow. **CUSUM** (the cumulative-sum control chart) gets
//! both: it accumulates how far each sample strays from a target *beyond a slack
//! band*, so small random deviations cancel out but a sustained drift adds up
//! until it crosses a decision threshold and raises an alarm.
//!
//! Two running sums are kept. The upper sum `S⁺` grows by `x − (target + k)` (and
//! floors at zero), catching an upward shift; the lower sum `S⁻` grows by
//! `(target − k) − x`, catching a downward one. Here `k` is the slack (half the
//! shift you want to detect, in the metric's units) and `h` the alarm threshold.
//! When either sum exceeds `h`, [`observe`] returns an [`Alarm`] naming the
//! direction and resets that sum so detection continues.
//!
//! [`CusumDetector::observe`] feeds one sample; [`reset`] clears the sums (e.g.
//! after you have responded to an alarm). Everything is deterministic.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the cusum surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The direction of a detected change.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Direction {
    /// The metric shifted persistently *above* target.
    Up,
    /// The metric shifted persistently *below* target.
    Down,
}

/// An alarm raised when a sum crosses the threshold.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Alarm {
    /// Which way the shift went.
    pub direction: Direction,
    /// The cumulative-sum value at the moment of alarm (how far past threshold).
    pub value: f64,
    /// How many samples since the last reset/alarm (the run length).
    pub run_length: usize,
}

/// A two-sided CUSUM change-point detector.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CusumDetector {
    target: f64,
    /// slack `k`: half the shift magnitude to detect (in metric units).
    slack: f64,
    /// decision threshold `h`.
    threshold: f64,
    s_hi: f64,
    s_lo: f64,
    since_reset: usize,
}

impl CusumDetector {
    /// A detector for a metric whose normal level is `target`, with slack `k` and
    /// alarm threshold `h` (both in the metric's units; common rules of thumb set
    /// `k` to half the shift you care about and `h` around 4–5 standard
    /// deviations of the metric).
    ///
    /// # Panics
    /// Panics if `slack < 0` or `threshold <= 0`.
    pub fn new(target: f64, slack: f64, threshold: f64) -> Self {
        assert!(slack >= 0.0, "slack must be >= 0");
        assert!(threshold > 0.0, "threshold must be > 0");
        Self {
            target,
            slack,
            threshold,
            s_hi: 0.0,
            s_lo: 0.0,
            since_reset: 0,
        }
    }

    /// The current upper cumulative sum `S⁺`.
    pub fn upper(&self) -> f64 {
        self.s_hi
    }

    /// The current lower cumulative sum `S⁻`.
    pub fn lower(&self) -> f64 {
        self.s_lo
    }

    /// Samples observed since the last reset or alarm.
    pub fn run_length(&self) -> usize {
        self.since_reset
    }

    /// Clear both sums and the run length.
    pub fn reset(&mut self) {
        self.s_hi = 0.0;
        self.s_lo = 0.0;
        self.since_reset = 0;
    }

    /// Feed one sample `x`. Returns `Some(Alarm)` if a sustained shift just crossed
    /// the threshold (the triggering sum is reset; the run length is reported then
    /// cleared). Non-finite samples are ignored.
    pub fn observe(&mut self, x: f64) -> Option<Alarm> {
        if !x.is_finite() {
            return None;
        }
        self.since_reset += 1;
        // upper: accumulate excess above (target + slack), floored at 0.
        self.s_hi = (self.s_hi + (x - (self.target + self.slack))).max(0.0);
        // lower: accumulate deficit below (target - slack), floored at 0.
        self.s_lo = (self.s_lo + ((self.target - self.slack) - x)).max(0.0);

        if self.s_hi > self.threshold {
            let alarm = Alarm {
                direction: Direction::Up,
                value: self.s_hi,
                run_length: self.since_reset,
            };
            self.s_hi = 0.0;
            self.since_reset = 0;
            return Some(alarm);
        }
        if self.s_lo > self.threshold {
            let alarm = Alarm {
                direction: Direction::Down,
                value: self.s_lo,
                run_length: self.since_reset,
            };
            self.s_lo = 0.0;
            self.since_reset = 0;
            return Some(alarm);
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stable_stream_no_alarm() {
        // samples hovering at target with small noise → no alarm.
        let mut c = CusumDetector::new(100.0, 1.0, 10.0);
        let noise = [100.0, 101.0, 99.0, 100.5, 99.5, 100.0, 101.0, 98.0];
        for _ in 0..20 {
            for &x in &noise {
                assert!(c.observe(x).is_none(), "false alarm at {x}");
            }
        }
    }

    #[test]
    fn detects_upward_shift() {
        let mut c = CusumDetector::new(100.0, 1.0, 8.0);
        // stable, then a sustained jump to ~110.
        for _ in 0..10 {
            assert!(c.observe(100.0).is_none());
        }
        let mut alarm = None;
        for _ in 0..20 {
            if let Some(a) = c.observe(110.0) {
                alarm = Some(a);
                break;
            }
        }
        let a = alarm.expect("should detect upward shift");
        assert_eq!(a.direction, Direction::Up);
    }

    #[test]
    fn detects_downward_shift() {
        let mut c = CusumDetector::new(0.8, 0.05, 0.5);
        // an acceptance rate that drops from 0.8 to 0.5.
        for _ in 0..10 {
            assert!(c.observe(0.8).is_none());
        }
        let mut alarm = None;
        for _ in 0..30 {
            if let Some(a) = c.observe(0.5) {
                alarm = Some(a);
                break;
            }
        }
        assert_eq!(alarm.unwrap().direction, Direction::Down);
    }

    #[test]
    fn bigger_shift_detected_faster() {
        let detect_after = |shift: f64| -> usize {
            let mut c = CusumDetector::new(100.0, 1.0, 10.0);
            for i in 1.. {
                if c.observe(100.0 + shift).is_some() {
                    return i;
                }
                if i > 1000 {
                    return i;
                }
            }
            unreachable!()
        };
        // a 20-unit shift should alarm sooner than a 5-unit shift.
        assert!(detect_after(20.0) < detect_after(5.0));
    }

    #[test]
    fn alarm_resets_the_triggering_sum() {
        let mut c = CusumDetector::new(0.0, 0.0, 5.0);
        let mut alarms = 0;
        // a steady positive drift should alarm repeatedly (reset each time).
        for _ in 0..100 {
            if c.observe(2.0).is_some() {
                alarms += 1;
            }
        }
        assert!(alarms > 1, "should re-alarm after reset, got {alarms}");
    }

    #[test]
    fn manual_reset_clears_sums() {
        let mut c = CusumDetector::new(0.0, 0.0, 100.0);
        c.observe(10.0);
        assert!(c.upper() > 0.0);
        c.reset();
        assert_eq!(c.upper(), 0.0);
        assert_eq!(c.run_length(), 0);
    }

    #[test]
    fn ignores_non_finite() {
        let mut c = CusumDetector::new(0.0, 0.0, 5.0);
        assert!(c.observe(f64::NAN).is_none());
        assert!(c.observe(f64::INFINITY).is_none());
        assert_eq!(c.run_length(), 0);
    }

    #[test]
    fn serde_round_trip() {
        let mut c = CusumDetector::new(50.0, 2.0, 10.0);
        c.observe(55.0);
        let j = serde_json::to_string(&c).unwrap();
        let back: CusumDetector = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
