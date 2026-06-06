//! `sovereign-cockpit-byte-size-formatter` — bytes → human string.
//!
//! Unit{Si/Iec}: SI uses 1000-base + suffixes B/kB/MB/GB/TB/PB/EB;
//! IEC uses 1024-base + B/KiB/MiB/GiB/TiB/PiB/EiB. Precision sets
//! decimal places (clamped 0..=3). format(bytes) picks the largest
//! unit where value >= 1 (except B which always shows).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Unit base.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Unit {
    /// SI (1000-base): B, kB, MB, GB, TB, PB, EB.
    Si,
    /// IEC (1024-base): B, KiB, MiB, GiB, TiB, PiB, EiB.
    Iec,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ByteSizeFormatter {
    /// Schema version.
    pub schema_version: String,
    /// Unit base.
    pub unit: Unit,
    /// Decimal precision (0..=3).
    pub precision: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FormatError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad precision.
    #[error("precision must be 0..=3")]
    BadPrecision,
}

const SI_SUFFIXES: [&str; 7] = ["B", "kB", "MB", "GB", "TB", "PB", "EB"];
const IEC_SUFFIXES: [&str; 7] = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"];

impl ByteSizeFormatter {
    /// New.
    pub fn new(unit: Unit, precision: u8) -> Result<Self, FormatError> {
        if precision > 3 {
            return Err(FormatError::BadPrecision);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            unit,
            precision,
        })
    }

    /// Format bytes as human string.
    pub fn format(&self, bytes: u64) -> String {
        let (base, suffixes): (u64, &[&str; 7]) = match self.unit {
            Unit::Si => (1000, &SI_SUFFIXES),
            Unit::Iec => (1024, &IEC_SUFFIXES),
        };
        if bytes < base {
            return format!("{} {}", bytes, suffixes[0]);
        }
        let mut value = bytes as f64;
        let mut idx = 0usize;
        let base_f = base as f64;
        while value >= base_f && idx + 1 < suffixes.len() {
            value /= base_f;
            idx += 1;
        }
        format!("{:.*} {}", self.precision as usize, value, suffixes[idx])
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FormatError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FormatError::SchemaMismatch);
        }
        if self.precision > 3 {
            return Err(FormatError::BadPrecision);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bytes_under_base_shown_as_b_si() {
        let f = ByteSizeFormatter::new(Unit::Si, 2).unwrap();
        assert_eq!(f.format(0), "0 B");
        assert_eq!(f.format(999), "999 B");
    }

    #[test]
    fn si_units() {
        let f = ByteSizeFormatter::new(Unit::Si, 2).unwrap();
        assert_eq!(f.format(1_000), "1.00 kB");
        assert_eq!(f.format(1_500_000), "1.50 MB");
        assert_eq!(f.format(2_000_000_000), "2.00 GB");
    }

    #[test]
    fn iec_units() {
        let f = ByteSizeFormatter::new(Unit::Iec, 2).unwrap();
        assert_eq!(f.format(1024), "1.00 KiB");
        assert_eq!(f.format(1024 * 1024), "1.00 MiB");
        assert_eq!(f.format(1024 * 1024 * 1024), "1.00 GiB");
    }

    #[test]
    fn precision_zero() {
        let f = ByteSizeFormatter::new(Unit::Si, 0).unwrap();
        assert_eq!(f.format(1_500), "2 kB"); // 1.5 rounds to 2
        assert_eq!(f.format(1_400), "1 kB");
    }

    #[test]
    fn bytes_under_iec_base_shown_as_b() {
        let f = ByteSizeFormatter::new(Unit::Iec, 1).unwrap();
        assert_eq!(f.format(1023), "1023 B");
    }

    #[test]
    fn very_large_caps_at_eb() {
        let f = ByteSizeFormatter::new(Unit::Si, 1).unwrap();
        let s = f.format(u64::MAX);
        assert!(s.ends_with("EB"), "got: {s}");
    }

    #[test]
    fn bad_precision_rejected() {
        assert!(matches!(
            ByteSizeFormatter::new(Unit::Si, 4).unwrap_err(),
            FormatError::BadPrecision
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = ByteSizeFormatter::new(Unit::Si, 2).unwrap();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FormatError::SchemaMismatch
        ));
    }

    #[test]
    fn formatter_serde_roundtrip() {
        let f = ByteSizeFormatter::new(Unit::Iec, 3).unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: ByteSizeFormatter = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
