//! `sovereign-cockpit-progress-bar` — progress widget state.
//!
//! Determinate (0..=100) or Indeterminate. Optional buffered head
//! (download ahead of playback). Warn/critical thresholds drive the
//! `zone()` color. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Progress mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Determinate (0..=100).
    Determinate,
    /// Indeterminate (spinner / marquee).
    Indeterminate,
}

/// Visual zone.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Zone {
    /// Healthy / normal.
    Normal,
    /// Approaching the threshold (warn).
    Warn,
    /// Past threshold (critical).
    Critical,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProgressBar {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: Mode,
    /// Progress percentage [0..=100] (ignored in Indeterminate).
    pub progress: u8,
    /// Buffered head [0..=100] (must be >= progress).
    pub buffered: u8,
    /// Warn threshold (% at which Zone::Warn begins).
    pub warn_pct: u8,
    /// Critical threshold (% at which Zone::Critical begins).
    pub critical_pct: u8,
    /// Critical interpretation: above OR below threshold? Below means
    /// "low progress = critical" (countdown timer); above means
    /// "high progress = critical" (memory bar).
    pub critical_above: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ProgressError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Progress > 100.
    #[error("progress {0} > 100")]
    ProgressOutOfRange(u8),
    /// Buffered > 100.
    #[error("buffered {0} > 100")]
    BufferedOutOfRange(u8),
    /// Buffered < progress.
    #[error("buffered {buffered} < progress {progress}")]
    BufferedBehindProgress {
        /// buffered.
        buffered: u8,
        /// progress.
        progress: u8,
    },
    /// Threshold out of range or warn > critical (when above) or warn < critical (when below).
    #[error("bad thresholds warn={warn} critical={critical} above={above}")]
    BadThresholds {
        /// warn.
        warn: u8,
        /// critical.
        critical: u8,
        /// above.
        above: bool,
    },
}

impl ProgressBar {
    /// Determinate constructor.
    pub fn determinate(progress: u8) -> Result<Self, ProgressError> {
        if progress > 100 {
            return Err(ProgressError::ProgressOutOfRange(progress));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: Mode::Determinate,
            progress,
            buffered: progress,
            warn_pct: 75,
            critical_pct: 90,
            critical_above: true,
        })
    }

    /// Indeterminate constructor.
    pub fn indeterminate() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: Mode::Indeterminate,
            progress: 0,
            buffered: 0,
            warn_pct: 75,
            critical_pct: 90,
            critical_above: true,
        }
    }

    /// Set progress (clamped 0..=100). Indeterminate becomes Determinate.
    pub fn set_progress(&mut self, p: u8) -> Result<(), ProgressError> {
        if p > 100 {
            return Err(ProgressError::ProgressOutOfRange(p));
        }
        self.mode = Mode::Determinate;
        self.progress = p;
        if self.buffered < p {
            self.buffered = p;
        }
        Ok(())
    }

    /// Set buffered head.
    pub fn set_buffered(&mut self, b: u8) -> Result<(), ProgressError> {
        if b > 100 {
            return Err(ProgressError::BufferedOutOfRange(b));
        }
        if b < self.progress {
            return Err(ProgressError::BufferedBehindProgress {
                buffered: b,
                progress: self.progress,
            });
        }
        self.buffered = b;
        Ok(())
    }

    /// Compute current zone (Indeterminate → Normal).
    pub fn zone(&self) -> Zone {
        if self.mode == Mode::Indeterminate {
            return Zone::Normal;
        }
        if self.critical_above {
            if self.progress >= self.critical_pct {
                Zone::Critical
            } else if self.progress >= self.warn_pct {
                Zone::Warn
            } else {
                Zone::Normal
            }
        } else {
            if self.progress <= self.critical_pct {
                Zone::Critical
            } else if self.progress <= self.warn_pct {
                Zone::Warn
            } else {
                Zone::Normal
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ProgressError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ProgressError::SchemaMismatch);
        }
        if self.progress > 100 {
            return Err(ProgressError::ProgressOutOfRange(self.progress));
        }
        if self.buffered > 100 {
            return Err(ProgressError::BufferedOutOfRange(self.buffered));
        }
        if self.buffered < self.progress {
            return Err(ProgressError::BufferedBehindProgress {
                buffered: self.buffered,
                progress: self.progress,
            });
        }
        if self.warn_pct > 100 || self.critical_pct > 100 {
            return Err(ProgressError::BadThresholds {
                warn: self.warn_pct,
                critical: self.critical_pct,
                above: self.critical_above,
            });
        }
        if self.critical_above {
            if self.warn_pct > self.critical_pct {
                return Err(ProgressError::BadThresholds {
                    warn: self.warn_pct,
                    critical: self.critical_pct,
                    above: true,
                });
            }
        } else {
            if self.warn_pct < self.critical_pct {
                return Err(ProgressError::BadThresholds {
                    warn: self.warn_pct,
                    critical: self.critical_pct,
                    above: false,
                });
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn determinate_basic() {
        let p = ProgressBar::determinate(40).unwrap();
        assert_eq!(p.progress, 40);
        assert_eq!(p.zone(), Zone::Normal);
    }

    #[test]
    fn determinate_over_range_rejected() {
        assert!(matches!(
            ProgressBar::determinate(150).unwrap_err(),
            ProgressError::ProgressOutOfRange(150)
        ));
    }

    #[test]
    fn zone_thresholds_above() {
        let mut p = ProgressBar::determinate(50).unwrap();
        p.warn_pct = 75;
        p.critical_pct = 90;
        p.critical_above = true;
        assert_eq!(p.zone(), Zone::Normal);
        p.set_progress(80).unwrap();
        assert_eq!(p.zone(), Zone::Warn);
        p.set_progress(95).unwrap();
        assert_eq!(p.zone(), Zone::Critical);
    }

    #[test]
    fn zone_thresholds_below() {
        let mut p = ProgressBar::determinate(50).unwrap();
        p.warn_pct = 25;
        p.critical_pct = 10;
        p.critical_above = false;
        assert_eq!(p.zone(), Zone::Normal);
        p.set_progress(20).unwrap();
        assert_eq!(p.zone(), Zone::Warn);
        p.set_progress(5).unwrap();
        assert_eq!(p.zone(), Zone::Critical);
    }

    #[test]
    fn indeterminate_zone_normal() {
        let p = ProgressBar::indeterminate();
        assert_eq!(p.zone(), Zone::Normal);
    }

    #[test]
    fn buffered_advances_with_progress() {
        let mut p = ProgressBar::determinate(10).unwrap();
        p.set_progress(50).unwrap();
        assert!(p.buffered >= 50);
    }

    #[test]
    fn buffered_behind_progress_rejected() {
        let mut p = ProgressBar::determinate(50).unwrap();
        assert!(matches!(
            p.set_buffered(30).unwrap_err(),
            ProgressError::BufferedBehindProgress { .. }
        ));
    }

    #[test]
    fn set_progress_switches_mode() {
        let mut p = ProgressBar::indeterminate();
        p.set_progress(30).unwrap();
        assert_eq!(p.mode, Mode::Determinate);
    }

    #[test]
    fn validate_bad_above_thresholds_rejected() {
        let mut p = ProgressBar::determinate(0).unwrap();
        p.warn_pct = 95;
        p.critical_pct = 80;
        p.critical_above = true;
        assert!(matches!(
            p.validate().unwrap_err(),
            ProgressError::BadThresholds { .. }
        ));
    }

    #[test]
    fn validate_bad_below_thresholds_rejected() {
        let mut p = ProgressBar::determinate(50).unwrap();
        p.warn_pct = 10;
        p.critical_pct = 25;
        p.critical_above = false;
        assert!(matches!(
            p.validate().unwrap_err(),
            ProgressError::BadThresholds { .. }
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ProgressBar::determinate(50).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            ProgressError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Mode::Indeterminate).unwrap(),
            "\"indeterminate\""
        );
        assert_eq!(
            serde_json::to_string(&Zone::Critical).unwrap(),
            "\"critical\""
        );
    }

    #[test]
    fn bar_serde_roundtrip() {
        let p = ProgressBar::determinate(75).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: ProgressBar = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
