//! `sovereign-cockpit-cell-format` — per-column-kind cell formatter.
//!
//! `format(kind, value, opts)` returns the rendered string.
//!
//!   * `Plain` — value as-is.
//!   * `Number` — i64 with thousands separator.
//!   * `Pct` — i64 (basis points x10? no: percent x100) as "12.34%".
//!   * `CurrencyMinor { code }` — cents → "USD 12.34".
//!   * `BytesIec` — bytes → "1.5 GiB" / "234 KiB" / "12 B".
//!   * `DurationMs` — ms → "1h 02m 30s" / "45s" / "750ms".
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Cell kind.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum CellKind {
    /// Plain string.
    Plain,
    /// Integer number with thousands separator.
    Number,
    /// Percentage in basis points × 100 (12.34% = 1234).
    Pct,
    /// Currency in minor units (cents).
    CurrencyMinor {
        /// ISO 4217-like code.
        code: String,
    },
    /// IEC bytes (1024-based).
    BytesIec,
    /// Duration in milliseconds.
    DurationMs,
}

/// Format options.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct FormatOpts {
    /// Thousands separator.
    pub thousands: char,
    /// Decimal separator.
    pub decimal: char,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CellFormatter {
    /// Schema version.
    pub schema_version: String,
    /// Default options.
    pub opts: FormatOpts,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FormatError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl CellFormatter {
    /// New.
    pub fn new(opts: FormatOpts) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            opts,
        }
    }

    /// Format.
    pub fn format(&self, kind: &CellKind, value: i64, plain: Option<&str>) -> String {
        match kind {
            CellKind::Plain => plain.unwrap_or("").to_string(),
            CellKind::Number => self.fmt_int(value),
            CellKind::Pct => format!("{}{}{}%", self.fmt_int(value / 100), self.opts.decimal,
                                     format!("{:02}", (value.unsigned_abs() % 100))),
            CellKind::CurrencyMinor { code } => {
                let neg = value < 0;
                let abs = value.unsigned_abs();
                let major = abs / 100;
                let minor = abs % 100;
                let sign = if neg { "-" } else { "" };
                format!("{} {}{}{}{}", code, sign, self.fmt_int(major as i64), self.opts.decimal, format!("{:02}", minor))
            }
            CellKind::BytesIec => fmt_bytes_iec(value),
            CellKind::DurationMs => fmt_duration_ms(value),
        }
    }

    fn fmt_int(&self, n: i64) -> String {
        let neg = n < 0;
        let abs = if n == i64::MIN { (i64::MAX as u64) + 1 } else { n.unsigned_abs() };
        let s = abs.to_string();
        let mut out = String::with_capacity(s.len() + s.len() / 3 + 1);
        if neg { out.push('-'); }
        let len = s.len();
        for (i, ch) in s.chars().enumerate() {
            if i > 0 && (len - i) % 3 == 0 { out.push(self.opts.thousands); }
            out.push(ch);
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FormatError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FormatError::SchemaMismatch); }
        Ok(())
    }
}

fn fmt_bytes_iec(n: i64) -> String {
    let neg = n < 0;
    let mut v = n.unsigned_abs() as u128;
    let units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];
    let mut i = 0usize;
    while v >= 1024 && i + 1 < units.len() {
        v /= 1024;
        i += 1;
    }
    let s = if i == 0 { format!("{} {}", v, units[i]) } else { format!("{} {}", v, units[i]) };
    if neg { format!("-{}", s) } else { s }
}

fn fmt_duration_ms(n: i64) -> String {
    let neg = n < 0;
    let mut ms = n.unsigned_abs();
    let h = ms / 3_600_000; ms %= 3_600_000;
    let m = ms / 60_000;   ms %= 60_000;
    let s = ms / 1000;     ms %= 1000;
    let body = if h > 0 {
        format!("{}h {:02}m {:02}s", h, m, s)
    } else if m > 0 {
        format!("{}m {:02}s", m, s)
    } else if s > 0 {
        format!("{}s", s)
    } else {
        format!("{}ms", ms)
    };
    if neg { format!("-{}", body) } else { body }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn en() -> CellFormatter {
        CellFormatter::new(FormatOpts { thousands: ',', decimal: '.' })
    }

    #[test]
    fn plain() {
        assert_eq!(en().format(&CellKind::Plain, 0, Some("hello")), "hello");
    }

    #[test]
    fn number_thousands() {
        assert_eq!(en().format(&CellKind::Number, 1234567, None), "1,234,567");
        assert_eq!(en().format(&CellKind::Number, -42, None), "-42");
    }

    #[test]
    fn pct() {
        // 1234 → 12.34%
        assert_eq!(en().format(&CellKind::Pct, 1234, None), "12.34%");
    }

    #[test]
    fn currency_minor() {
        let v = en().format(&CellKind::CurrencyMinor { code: "USD".into() }, 12345, None);
        assert_eq!(v, "USD 123.45");
    }

    #[test]
    fn currency_minor_negative() {
        let v = en().format(&CellKind::CurrencyMinor { code: "USD".into() }, -12345, None);
        assert_eq!(v, "USD -123.45");
    }

    #[test]
    fn bytes_iec() {
        assert_eq!(en().format(&CellKind::BytesIec, 1024, None), "1 KiB");
        assert_eq!(en().format(&CellKind::BytesIec, 1024 * 1024, None), "1 MiB");
        assert_eq!(en().format(&CellKind::BytesIec, 12, None), "12 B");
    }

    #[test]
    fn duration_ms_buckets() {
        assert_eq!(en().format(&CellKind::DurationMs, 750, None), "750ms");
        assert_eq!(en().format(&CellKind::DurationMs, 45_000, None), "45s");
        assert_eq!(en().format(&CellKind::DurationMs, 90_000, None), "1m 30s");
        assert_eq!(en().format(&CellKind::DurationMs, 3_660_000, None), "1h 01m 00s");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = en();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FormatError::SchemaMismatch));
    }

    #[test]
    fn formatter_serde_roundtrip() {
        let f = en();
        let j = serde_json::to_string(&f).unwrap();
        let back: CellFormatter = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
