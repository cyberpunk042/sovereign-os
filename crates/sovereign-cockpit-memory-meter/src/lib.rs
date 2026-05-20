//! `sovereign-cockpit-memory-meter` — memory gauge with auto-unit.
//!
//! Tracks used / total bytes. Zone derived from used_pct vs
//! warn_pct + critical_pct thresholds. render_display picks the
//! best unit (B/KB/MB/GB) for human-readable display.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Zone.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Zone {
    /// Normal.
    Normal,
    /// Warn.
    Warn,
    /// Critical.
    Critical,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MemoryMeter {
    /// Schema version.
    pub schema_version: String,
    /// Used bytes.
    pub used_bytes: u64,
    /// Total bytes.
    pub total_bytes: u64,
    /// Warn %.
    pub warn_pct: u8,
    /// Critical %.
    pub critical_pct: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MeterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad thresholds.
    #[error("warn {0} >= critical {1}")]
    BadThresholds(u8, u8),
    /// Critical over 100.
    #[error("critical_pct {0} > 100")]
    CriticalOver100(u8),
    /// total zero.
    #[error("total_bytes zero")]
    TotalZero,
    /// used > total.
    #[error("used {0} > total {1}")]
    UsedOverTotal(u64, u64),
}

impl MemoryMeter {
    /// New.
    pub fn new(total_bytes: u64, warn_pct: u8, critical_pct: u8) -> Result<Self, MeterError> {
        if total_bytes == 0 { return Err(MeterError::TotalZero); }
        if warn_pct >= critical_pct { return Err(MeterError::BadThresholds(warn_pct, critical_pct)); }
        if critical_pct > 100 { return Err(MeterError::CriticalOver100(critical_pct)); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            used_bytes: 0,
            total_bytes, warn_pct, critical_pct,
        })
    }

    /// Set used.
    pub fn set_used(&mut self, used: u64) -> Result<(), MeterError> {
        if used > self.total_bytes { return Err(MeterError::UsedOverTotal(used, self.total_bytes)); }
        self.used_bytes = used;
        Ok(())
    }

    /// Used percent (0..=100).
    pub fn used_pct(&self) -> u8 {
        if self.total_bytes == 0 { return 0; }
        ((self.used_bytes * 100) / self.total_bytes) as u8
    }

    /// Zone.
    pub fn zone(&self) -> Zone {
        let pct = self.used_pct();
        if pct >= self.critical_pct { Zone::Critical }
        else if pct >= self.warn_pct { Zone::Warn }
        else { Zone::Normal }
    }

    /// Render 'A.B GB / X.Y GB (PP%)'.
    pub fn render_display(&self) -> String {
        let used = format_bytes(self.used_bytes);
        let total = format_bytes(self.total_bytes);
        format!("{used} / {total} ({}%)", self.used_pct())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MeterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MeterError::SchemaMismatch);
        }
        if self.total_bytes == 0 { return Err(MeterError::TotalZero); }
        if self.warn_pct >= self.critical_pct { return Err(MeterError::BadThresholds(self.warn_pct, self.critical_pct)); }
        if self.critical_pct > 100 { return Err(MeterError::CriticalOver100(self.critical_pct)); }
        if self.used_bytes > self.total_bytes {
            return Err(MeterError::UsedOverTotal(self.used_bytes, self.total_bytes));
        }
        Ok(())
    }
}

fn format_bytes(b: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = 1024 * KB;
    const GB: u64 = 1024 * MB;
    const TB: u64 = 1024 * GB;
    if b >= TB { format!("{:.1} TB", b as f64 / TB as f64) }
    else if b >= GB { format!("{:.1} GB", b as f64 / GB as f64) }
    else if b >= MB { format!("{:.1} MB", b as f64 / MB as f64) }
    else if b >= KB { format!("{:.1} KB", b as f64 / KB as f64) }
    else { format!("{b} B") }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn total_zero_rejected() {
        assert!(matches!(MemoryMeter::new(0, 70, 90).unwrap_err(), MeterError::TotalZero));
    }

    #[test]
    fn bad_thresholds_rejected() {
        assert!(matches!(MemoryMeter::new(1024, 90, 70).unwrap_err(), MeterError::BadThresholds(_, _)));
    }

    #[test]
    fn critical_over_100_rejected() {
        assert!(matches!(MemoryMeter::new(1024, 70, 150).unwrap_err(), MeterError::CriticalOver100(150)));
    }

    #[test]
    fn used_pct_correct() {
        let mut m = MemoryMeter::new(1000, 70, 90).unwrap();
        m.set_used(250).unwrap();
        assert_eq!(m.used_pct(), 25);
    }

    #[test]
    fn zone_thresholds() {
        let mut m = MemoryMeter::new(1000, 70, 90).unwrap();
        m.set_used(500).unwrap();
        assert_eq!(m.zone(), Zone::Normal);
        m.set_used(800).unwrap();
        assert_eq!(m.zone(), Zone::Warn);
        m.set_used(950).unwrap();
        assert_eq!(m.zone(), Zone::Critical);
    }

    #[test]
    fn used_over_total_rejected() {
        let mut m = MemoryMeter::new(1000, 70, 90).unwrap();
        assert!(matches!(m.set_used(2000).unwrap_err(), MeterError::UsedOverTotal(_, _)));
    }

    #[test]
    fn format_kb() {
        assert_eq!(format_bytes(1024), "1.0 KB");
    }

    #[test]
    fn format_mb() {
        assert_eq!(format_bytes(2 * 1024 * 1024), "2.0 MB");
    }

    #[test]
    fn format_gb() {
        assert_eq!(format_bytes(3 * 1024 * 1024 * 1024), "3.0 GB");
    }

    #[test]
    fn render_display() {
        let mut m = MemoryMeter::new(1000 * 1024 * 1024 * 1024, 70, 90).unwrap();
        m.set_used(250 * 1024 * 1024 * 1024).unwrap();
        let d = m.render_display();
        assert!(d.contains("GB"));
        assert!(d.contains("25%"));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = MemoryMeter::new(1000, 70, 90).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), MeterError::SchemaMismatch));
    }

    #[test]
    fn meter_serde_roundtrip() {
        let mut m = MemoryMeter::new(1000, 70, 90).unwrap();
        m.set_used(250).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: MemoryMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
