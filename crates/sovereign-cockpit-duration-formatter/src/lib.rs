//! `sovereign-cockpit-duration-formatter` — ms → human string.
//!
//! Style{Compact/Long}. Compact emits "2d4h17m" (top max_units
//! non-zero); Long emits "2 days, 4 hours, 17 minutes". Units
//! considered: d, h, m, s, ms. Sub-second ms shown when total
//! < 1000 ms; otherwise ms is omitted unless max_units permits.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Style.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Style {
    /// Compact ("2d4h17m").
    Compact,
    /// Long ("2 days, 4 hours, 17 minutes").
    Long,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DurationFormatter {
    /// Schema version.
    pub schema_version: String,
    /// Style.
    pub style: Style,
    /// Max non-zero units shown (1..=5).
    pub max_units: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FormatError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad max units.
    #[error("max_units must be 1..=5")]
    BadMaxUnits,
}

const MS_PER_S: u64 = 1_000;
const MS_PER_M: u64 = 60_000;
const MS_PER_H: u64 = 3_600_000;
const MS_PER_D: u64 = 86_400_000;

impl DurationFormatter {
    /// New.
    pub fn new(style: Style, max_units: u8) -> Result<Self, FormatError> {
        if max_units == 0 || max_units > 5 { return Err(FormatError::BadMaxUnits); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            style,
            max_units,
        })
    }

    /// Format ms.
    pub fn format(&self, ms: u64) -> String {
        if ms == 0 {
            return match self.style {
                Style::Compact => "0ms".into(),
                Style::Long => "0 milliseconds".into(),
            };
        }
        let d = ms / MS_PER_D;
        let h = (ms % MS_PER_D) / MS_PER_H;
        let m = (ms % MS_PER_H) / MS_PER_M;
        let s = (ms % MS_PER_M) / MS_PER_S;
        let mss = ms % MS_PER_S;
        let parts: [(u64, &str, &str, &str); 5] = [
            (d, "d", "day", "days"),
            (h, "h", "hour", "hours"),
            (m, "m", "minute", "minutes"),
            (s, "s", "second", "seconds"),
            (mss, "ms", "millisecond", "milliseconds"),
        ];
        let mut out_compact = String::new();
        let mut out_long: Vec<String> = Vec::new();
        let mut emitted = 0u8;
        for (val, short, sing, plur) in parts.iter() {
            if *val == 0 { continue; }
            if emitted >= self.max_units { break; }
            match self.style {
                Style::Compact => {
                    out_compact.push_str(&format!("{}{}", val, short));
                }
                Style::Long => {
                    let unit = if *val == 1 { *sing } else { *plur };
                    out_long.push(format!("{} {}", val, unit));
                }
            }
            emitted += 1;
        }
        match self.style {
            Style::Compact => out_compact,
            Style::Long => out_long.join(", "),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FormatError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FormatError::SchemaMismatch); }
        if self.max_units == 0 || self.max_units > 5 { return Err(FormatError::BadMaxUnits); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_ms() {
        let f = DurationFormatter::new(Style::Compact, 3).unwrap();
        assert_eq!(f.format(0), "0ms");
        let f2 = DurationFormatter::new(Style::Long, 3).unwrap();
        assert_eq!(f2.format(0), "0 milliseconds");
    }

    #[test]
    fn sub_second_compact() {
        let f = DurationFormatter::new(Style::Compact, 3).unwrap();
        assert_eq!(f.format(250), "250ms");
    }

    #[test]
    fn h_m_s_compact() {
        let f = DurationFormatter::new(Style::Compact, 3).unwrap();
        // 1h 23m 45s = 5025000 ms
        assert_eq!(f.format(5_025_000), "1h23m45s");
    }

    #[test]
    fn day_h_m_long() {
        let f = DurationFormatter::new(Style::Long, 3).unwrap();
        // 2d 4h 17m = 2*86400000 + 4*3600000 + 17*60000 = 188_220_000 ms
        assert_eq!(f.format(188_220_000), "2 days, 4 hours, 17 minutes");
    }

    #[test]
    fn max_units_truncates() {
        let f = DurationFormatter::new(Style::Compact, 2).unwrap();
        // 1h 23m 45s 100ms → "1h23m"
        assert_eq!(f.format(5_025_100), "1h23m");
    }

    #[test]
    fn singular_units_in_long() {
        let f = DurationFormatter::new(Style::Long, 4).unwrap();
        // 1d 1h 1m 1s
        let total = MS_PER_D + MS_PER_H + MS_PER_M + MS_PER_S;
        assert_eq!(f.format(total), "1 day, 1 hour, 1 minute, 1 second");
    }

    #[test]
    fn skips_zero_units() {
        let f = DurationFormatter::new(Style::Compact, 3).unwrap();
        // 1d 0h 30m → "1d30m"
        assert_eq!(f.format(MS_PER_D + 30 * MS_PER_M), "1d30m");
    }

    #[test]
    fn bad_max_units_rejected() {
        assert!(matches!(DurationFormatter::new(Style::Compact, 0).unwrap_err(), FormatError::BadMaxUnits));
        assert!(matches!(DurationFormatter::new(Style::Compact, 6).unwrap_err(), FormatError::BadMaxUnits));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = DurationFormatter::new(Style::Compact, 3).unwrap();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FormatError::SchemaMismatch));
    }

    #[test]
    fn formatter_serde_roundtrip() {
        let f = DurationFormatter::new(Style::Long, 4).unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: DurationFormatter = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
