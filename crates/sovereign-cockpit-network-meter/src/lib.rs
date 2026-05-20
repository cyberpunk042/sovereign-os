//! `sovereign-cockpit-network-meter` — RX/TX throughput gauge.
//!
//! Stores last cumulative rx/tx + timestamp. Each new sample
//! computes a rate (bytes/sec) using the delta. render_display
//! formats with auto-unit (B/KB/MB/GB per second).
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
pub struct NetworkMeter {
    /// Schema version.
    pub schema_version: String,
    /// Last cumulative rx bytes.
    pub last_rx_bytes: u64,
    /// Last cumulative tx bytes.
    pub last_tx_bytes: u64,
    /// Last sample ms (0 = never).
    pub last_sample_ms: u64,
    /// Computed rx bytes/sec.
    pub rx_bps: u64,
    /// Computed tx bytes/sec.
    pub tx_bps: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum NetError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bytes counter went backward (interface reset).
    #[error("rx/tx counter went backward (interface reset?)")]
    CounterReset,
}

impl NetworkMeter {
    /// New (no samples).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            last_rx_bytes: 0,
            last_tx_bytes: 0,
            last_sample_ms: 0,
            rx_bps: 0,
            tx_bps: 0,
        }
    }

    /// Submit a new cumulative sample. Returns Err on counter reset.
    pub fn sample(&mut self, rx_bytes: u64, tx_bytes: u64, now_ms: u64) -> Result<(), NetError> {
        if self.last_sample_ms == 0 {
            // First sample — record only.
            self.last_rx_bytes = rx_bytes;
            self.last_tx_bytes = tx_bytes;
            self.last_sample_ms = now_ms;
            self.rx_bps = 0;
            self.tx_bps = 0;
            return Ok(());
        }
        let dt_ms = now_ms.saturating_sub(self.last_sample_ms);
        if dt_ms == 0 { return Ok(()); }
        if rx_bytes < self.last_rx_bytes || tx_bytes < self.last_tx_bytes {
            return Err(NetError::CounterReset);
        }
        let drx = rx_bytes - self.last_rx_bytes;
        let dtx = tx_bytes - self.last_tx_bytes;
        self.rx_bps = (drx * 1000) / dt_ms;
        self.tx_bps = (dtx * 1000) / dt_ms;
        self.last_rx_bytes = rx_bytes;
        self.last_tx_bytes = tx_bytes;
        self.last_sample_ms = now_ms;
        Ok(())
    }

    /// 'A KB/s ↓ / B KB/s ↑' display.
    pub fn render_display(&self) -> String {
        format!("{} ↓ / {} ↑", format_bps(self.rx_bps), format_bps(self.tx_bps))
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), NetError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(NetError::SchemaMismatch);
        }
        Ok(())
    }
}

fn format_bps(b: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = 1024 * KB;
    const GB: u64 = 1024 * MB;
    if b >= GB { format!("{:.1} GB/s", b as f64 / GB as f64) }
    else if b >= MB { format!("{:.1} MB/s", b as f64 / MB as f64) }
    else if b >= KB { format!("{:.1} KB/s", b as f64 / KB as f64) }
    else { format!("{b} B/s") }
}

impl Default for NetworkMeter {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_sample_records_only() {
        let mut m = NetworkMeter::new();
        m.sample(1000, 500, 100).unwrap();
        assert_eq!(m.rx_bps, 0);
        assert_eq!(m.tx_bps, 0);
        assert_eq!(m.last_rx_bytes, 1000);
    }

    #[test]
    fn second_sample_computes_rate() {
        let mut m = NetworkMeter::new();
        m.sample(0, 0, 1000).unwrap();
        m.sample(1024, 2048, 2000).unwrap();
        // 1 second elapsed.
        assert_eq!(m.rx_bps, 1024);
        assert_eq!(m.tx_bps, 2048);
    }

    #[test]
    fn counter_reset_rejected() {
        let mut m = NetworkMeter::new();
        m.sample(1000, 500, 1000).unwrap();
        assert!(matches!(m.sample(500, 500, 2000).unwrap_err(), NetError::CounterReset));
    }

    #[test]
    fn zero_dt_ignored() {
        let mut m = NetworkMeter::new();
        m.sample(0, 0, 1000).unwrap();
        m.sample(1024, 1024, 1000).unwrap();
        // dt = 0; rate unchanged.
        assert_eq!(m.rx_bps, 0);
    }

    #[test]
    fn format_bps_kb() {
        assert_eq!(format_bps(2048), "2.0 KB/s");
    }

    #[test]
    fn format_bps_mb() {
        assert_eq!(format_bps(2 * 1024 * 1024), "2.0 MB/s");
    }

    #[test]
    fn format_bps_bytes() {
        assert_eq!(format_bps(500), "500 B/s");
    }

    #[test]
    fn render_display_contains_arrows() {
        let m = NetworkMeter::new();
        let d = m.render_display();
        assert!(d.contains('↓'));
        assert!(d.contains('↑'));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = NetworkMeter::new();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), NetError::SchemaMismatch));
    }

    #[test]
    fn meter_serde_roundtrip() {
        let mut m = NetworkMeter::new();
        m.sample(0, 0, 1000).unwrap();
        m.sample(1024, 1024, 2000).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: NetworkMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
