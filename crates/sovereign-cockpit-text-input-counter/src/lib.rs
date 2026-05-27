//! `sovereign-cockpit-text-input-counter` — text-input with counter.
//!
//! Soft mode: keystrokes always accepted; counter goes red over max.
//! Hard mode: keystrokes rejected when buffer would exceed max.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Soft (counter only).
    Soft,
    /// Hard (rejects over-max).
    Hard,
}

/// Counter color.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CounterColor {
    /// Normal.
    Normal,
    /// Warn (>= warn_pct of max).
    Warn,
    /// Over (used > max).
    Over,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TextInputCounter {
    /// Schema version.
    pub schema_version: String,
    /// Buffer.
    pub buffer: String,
    /// Min length required for valid.
    pub min: u32,
    /// Max length.
    pub max: u32,
    /// Warn % of max.
    pub warn_pct: u8,
    /// Mode.
    pub mode: Mode,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CounterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Max zero.
    #[error("max is zero")]
    MaxZero,
    /// Bad warn_pct.
    #[error("warn_pct {0} > 100")]
    BadWarnPct(u8),
    /// min > max.
    #[error("min {0} > max {1}")]
    BadMinMax(u32, u32),
}

impl TextInputCounter {
    /// New.
    pub fn new(min: u32, max: u32, warn_pct: u8, mode: Mode) -> Result<Self, CounterError> {
        if max == 0 {
            return Err(CounterError::MaxZero);
        }
        if warn_pct > 100 {
            return Err(CounterError::BadWarnPct(warn_pct));
        }
        if min > max {
            return Err(CounterError::BadMinMax(min, max));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            buffer: String::new(),
            min,
            max,
            warn_pct,
            mode,
        })
    }

    /// Type text. Returns number of chars actually accepted.
    pub fn type_text(&mut self, s: &str) -> usize {
        let current = self.buffer.chars().count() as u32;
        match self.mode {
            Mode::Soft => {
                self.buffer.push_str(s);
                s.chars().count()
            }
            Mode::Hard => {
                let avail = self.max.saturating_sub(current) as usize;
                let mut taken = 0;
                for c in s.chars().take(avail) {
                    self.buffer.push(c);
                    taken += 1;
                }
                taken
            }
        }
    }

    /// Backspace one char.
    pub fn backspace(&mut self) -> bool {
        self.buffer.pop().is_some()
    }

    /// Used count.
    pub fn used(&self) -> u32 {
        self.buffer.chars().count() as u32
    }

    /// Counter color.
    pub fn color(&self) -> CounterColor {
        let used = self.used();
        let warn_threshold = (self.max as u64 * self.warn_pct as u64 / 100) as u32;
        if used > self.max {
            CounterColor::Over
        } else if used >= warn_threshold && self.max > 0 {
            CounterColor::Warn
        } else {
            CounterColor::Normal
        }
    }

    /// Valid (within min/max).
    pub fn is_valid(&self) -> bool {
        let u = self.used();
        u >= self.min && u <= self.max
    }

    /// Counter text 'used/max'.
    pub fn render_counter(&self) -> String {
        format!("{}/{}", self.used(), self.max)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CounterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CounterError::SchemaMismatch);
        }
        if self.max == 0 {
            return Err(CounterError::MaxZero);
        }
        if self.warn_pct > 100 {
            return Err(CounterError::BadWarnPct(self.warn_pct));
        }
        if self.min > self.max {
            return Err(CounterError::BadMinMax(self.min, self.max));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn max_zero_rejected() {
        assert!(matches!(
            TextInputCounter::new(0, 0, 80, Mode::Soft).unwrap_err(),
            CounterError::MaxZero
        ));
    }

    #[test]
    fn min_over_max_rejected() {
        assert!(matches!(
            TextInputCounter::new(20, 10, 80, Mode::Soft).unwrap_err(),
            CounterError::BadMinMax(20, 10)
        ));
    }

    #[test]
    fn soft_accepts_over_max() {
        let mut c = TextInputCounter::new(0, 5, 80, Mode::Soft).unwrap();
        let taken = c.type_text("123456789");
        assert_eq!(taken, 9);
        assert_eq!(c.used(), 9);
        assert_eq!(c.color(), CounterColor::Over);
    }

    #[test]
    fn hard_clips_to_max() {
        let mut c = TextInputCounter::new(0, 5, 80, Mode::Hard).unwrap();
        let taken = c.type_text("123456789");
        assert_eq!(taken, 5);
        assert_eq!(c.used(), 5);
        assert_ne!(c.color(), CounterColor::Over);
    }

    #[test]
    fn warn_at_threshold() {
        let mut c = TextInputCounter::new(0, 10, 80, Mode::Soft).unwrap();
        c.type_text("12345678");
        assert_eq!(c.color(), CounterColor::Warn);
    }

    #[test]
    fn normal_below_warn() {
        let mut c = TextInputCounter::new(0, 10, 80, Mode::Soft).unwrap();
        c.type_text("1234");
        assert_eq!(c.color(), CounterColor::Normal);
    }

    #[test]
    fn is_valid_within_range() {
        let mut c = TextInputCounter::new(3, 10, 80, Mode::Soft).unwrap();
        assert!(!c.is_valid());
        c.type_text("ab");
        assert!(!c.is_valid());
        c.type_text("c");
        assert!(c.is_valid());
    }

    #[test]
    fn backspace_works() {
        let mut c = TextInputCounter::new(0, 10, 80, Mode::Soft).unwrap();
        c.type_text("ab");
        assert!(c.backspace());
        assert_eq!(c.used(), 1);
        c.backspace();
        assert!(!c.backspace()); // empty
    }

    #[test]
    fn render_counter_format() {
        let mut c = TextInputCounter::new(0, 10, 80, Mode::Soft).unwrap();
        c.type_text("ab");
        assert_eq!(c.render_counter(), "2/10");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = TextInputCounter::new(0, 10, 80, Mode::Soft).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            CounterError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(serde_json::to_string(&Mode::Soft).unwrap(), "\"soft\"");
    }

    #[test]
    fn counter_serde_roundtrip() {
        let mut c = TextInputCounter::new(0, 10, 80, Mode::Soft).unwrap();
        c.type_text("hi");
        let j = serde_json::to_string(&c).unwrap();
        let back: TextInputCounter = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
