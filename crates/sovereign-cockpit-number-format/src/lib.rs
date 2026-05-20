//! `sovereign-cockpit-number-format` — integer / minor-unit / compact format.
//!
//! `integer(n)` renders an i64 with the configured thousands separator.
//! `minor_unit(n, minor_digits)` renders `n` as a fixed-point value
//! with `minor_digits` decimal places (e.g. cents → dollars when
//! `minor_digits == 2`).
//! `compact(n)` renders with k/M/B/T suffixes at 1-decimal precision.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct NumberFormat {
    /// Schema version.
    pub schema_version: String,
    /// Thousands separator.
    pub thousands: char,
    /// Decimal separator.
    pub decimal: char,
    /// Minus sign.
    pub minus: char,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FormatError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// minor_digits out of range.
    #[error("minor_digits {0} > 9")]
    MinorTooLarge(u8),
}

impl NumberFormat {
    /// New.
    pub fn new(thousands: char, decimal: char, minus: char) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            thousands,
            decimal,
            minus,
        }
    }

    /// Render plain integer with thousands separator.
    pub fn integer(&self, n: i64) -> String {
        let neg = n < 0;
        let abs = if n == i64::MIN { i64::MAX as u64 + 1 } else { n.unsigned_abs() };
        let digits = abs.to_string();
        let mut out = String::with_capacity(digits.len() + digits.len() / 3 + 1);
        if neg { out.push(self.minus); }
        let len = digits.len();
        for (i, ch) in digits.chars().enumerate() {
            if i > 0 && (len - i) % 3 == 0 {
                out.push(self.thousands);
            }
            out.push(ch);
        }
        out
    }

    /// Render fixed-point.
    pub fn minor_unit(&self, n: i64, minor_digits: u8) -> Result<String, FormatError> {
        if minor_digits > 9 { return Err(FormatError::MinorTooLarge(minor_digits)); }
        let scale = 10i64.pow(minor_digits as u32);
        let neg = n < 0;
        let abs = if n == i64::MIN { (i64::MAX as i128 + 1) as u128 } else { n.unsigned_abs() as u128 };
        let major = abs / scale as u128;
        let minor = abs % scale as u128;
        let major_str = self.integer(major as i64);
        let mut out = String::with_capacity(major_str.len() + 1 + minor_digits as usize);
        if neg && (major != 0 || minor != 0) {
            // integer() already adds minus when negative; here major was unsigned, so prepend.
            out.push(self.minus);
        }
        out.push_str(&major_str.trim_start_matches(self.minus));
        if minor_digits > 0 {
            out.push(self.decimal);
            let s = format!("{:0width$}", minor, width = minor_digits as usize);
            out.push_str(&s);
        }
        Ok(out)
    }

    /// Compact format (k/M/B/T).
    pub fn compact(&self, n: i64) -> String {
        let neg = n < 0;
        let abs = if n == i64::MIN { i64::MAX as u128 + 1 } else { n.unsigned_abs() as u128 };
        let (suffix, divisor): (&str, u128) = if abs >= 1_000_000_000_000 {
            ("T", 1_000_000_000_000)
        } else if abs >= 1_000_000_000 {
            ("B", 1_000_000_000)
        } else if abs >= 1_000_000 {
            ("M", 1_000_000)
        } else if abs >= 1_000 {
            ("k", 1_000)
        } else {
            return self.integer(n);
        };
        let major = abs / divisor;
        let tenths = (abs % divisor) * 10 / divisor;
        let sign = if neg { self.minus.to_string() } else { String::new() };
        if tenths == 0 {
            format!("{}{}{}", sign, major, suffix)
        } else {
            format!("{}{}{}{}{}", sign, major, self.decimal, tenths, suffix)
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FormatError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FormatError::SchemaMismatch); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn en() -> NumberFormat { NumberFormat::new(',', '.', '-') }
    fn fr() -> NumberFormat { NumberFormat::new(' ', ',', '−') }

    #[test]
    fn integer_basic_en() {
        assert_eq!(en().integer(1234567), "1,234,567");
        assert_eq!(en().integer(-42), "-42");
        assert_eq!(en().integer(0), "0");
    }

    #[test]
    fn integer_basic_fr() {
        assert_eq!(fr().integer(1234567), "1 234 567");
        assert_eq!(fr().integer(-42), "−42");
    }

    #[test]
    fn minor_unit_cents() {
        assert_eq!(en().minor_unit(12345, 2).unwrap(), "123.45");
        assert_eq!(en().minor_unit(7, 2).unwrap(), "0.07");
        assert_eq!(en().minor_unit(-12345, 2).unwrap(), "-123.45");
    }

    #[test]
    fn minor_unit_zero_minor() {
        assert_eq!(en().minor_unit(1234567, 0).unwrap(), "1,234,567");
    }

    #[test]
    fn minor_unit_too_large_rejected() {
        assert!(matches!(en().minor_unit(1, 10).unwrap_err(), FormatError::MinorTooLarge(_)));
    }

    #[test]
    fn compact_k() {
        assert_eq!(en().compact(1500), "1.5k");
        assert_eq!(en().compact(1000), "1k");
    }

    #[test]
    fn compact_m_b_t() {
        assert_eq!(en().compact(2_500_000), "2.5M");
        assert_eq!(en().compact(3_000_000_000), "3B");
        assert_eq!(en().compact(1_500_000_000_000), "1.5T");
    }

    #[test]
    fn compact_under_1k() {
        assert_eq!(en().compact(999), "999");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = en();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FormatError::SchemaMismatch));
    }

    #[test]
    fn format_serde_roundtrip() {
        let f = fr();
        let j = serde_json::to_string(&f).unwrap();
        let back: NumberFormat = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
