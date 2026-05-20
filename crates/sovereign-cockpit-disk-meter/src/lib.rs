//! `sovereign-cockpit-disk-meter` — per-mount disk gauge.
//!
//! Tracks N mountpoints with (mount, used_bytes, total_bytes).
//! Per-mount zone + overall worst zone for the global indicator.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Zone (mirror of memory-meter).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Ord, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Zone {
    /// Normal.
    Normal,
    /// Warn.
    Warn,
    /// Critical.
    Critical,
}

/// One mountpoint.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Mount {
    /// Mount path / label.
    pub mount: String,
    /// Used bytes.
    pub used_bytes: u64,
    /// Total bytes.
    pub total_bytes: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DiskMeter {
    /// Schema version.
    pub schema_version: String,
    /// Mounts.
    pub mounts: Vec<Mount>,
    /// Warn pct.
    pub warn_pct: u8,
    /// Critical pct.
    pub critical_pct: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DiskError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty mount.
    #[error("mount path empty")]
    EmptyMount,
    /// Total zero.
    #[error("mount {0} total_bytes zero")]
    TotalZero(String),
    /// Used > total.
    #[error("mount {mount} used {used} > total {total}")]
    UsedOverTotal {
        /// mount.
        mount: String,
        /// used.
        used: u64,
        /// total.
        total: u64,
    },
    /// Duplicate.
    #[error("duplicate mount: {0}")]
    DuplicateMount(String),
    /// Bad thresholds.
    #[error("warn {0} >= critical {1}")]
    BadThresholds(u8, u8),
    /// Critical over 100.
    #[error("critical_pct {0} > 100")]
    CriticalOver100(u8),
}

impl DiskMeter {
    /// New.
    pub fn new(warn_pct: u8, critical_pct: u8) -> Result<Self, DiskError> {
        if warn_pct >= critical_pct { return Err(DiskError::BadThresholds(warn_pct, critical_pct)); }
        if critical_pct > 100 { return Err(DiskError::CriticalOver100(critical_pct)); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            mounts: Vec::new(),
            warn_pct, critical_pct,
        })
    }

    /// Register a mount.
    pub fn register(&mut self, m: Mount) -> Result<(), DiskError> {
        if m.mount.is_empty() { return Err(DiskError::EmptyMount); }
        if m.total_bytes == 0 { return Err(DiskError::TotalZero(m.mount)); }
        if m.used_bytes > m.total_bytes {
            return Err(DiskError::UsedOverTotal { mount: m.mount, used: m.used_bytes, total: m.total_bytes });
        }
        if self.mounts.iter().any(|x| x.mount == m.mount) {
            return Err(DiskError::DuplicateMount(m.mount));
        }
        self.mounts.push(m);
        Ok(())
    }

    /// Update existing.
    pub fn update(&mut self, mount: &str, used_bytes: u64) -> Result<(), DiskError> {
        let m = self.mounts.iter_mut().find(|x| x.mount == mount)
            .ok_or_else(|| DiskError::DuplicateMount(mount.into()))?;
        if used_bytes > m.total_bytes {
            return Err(DiskError::UsedOverTotal { mount: mount.into(), used: used_bytes, total: m.total_bytes });
        }
        m.used_bytes = used_bytes;
        Ok(())
    }

    /// Per-mount used pct.
    pub fn used_pct(&self, mount: &str) -> Option<u8> {
        self.mounts.iter().find(|x| x.mount == mount).map(|m| {
            if m.total_bytes == 0 { 0 } else { ((m.used_bytes * 100) / m.total_bytes) as u8 }
        })
    }

    /// Per-mount zone.
    pub fn zone_of(&self, mount: &str) -> Option<Zone> {
        self.used_pct(mount).map(|pct| {
            if pct >= self.critical_pct { Zone::Critical }
            else if pct >= self.warn_pct { Zone::Warn }
            else { Zone::Normal }
        })
    }

    /// Worst zone across all mounts.
    pub fn worst_zone(&self) -> Zone {
        self.mounts.iter()
            .filter_map(|m| self.zone_of(&m.mount))
            .max()
            .unwrap_or(Zone::Normal)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DiskError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DiskError::SchemaMismatch);
        }
        if self.warn_pct >= self.critical_pct {
            return Err(DiskError::BadThresholds(self.warn_pct, self.critical_pct));
        }
        if self.critical_pct > 100 { return Err(DiskError::CriticalOver100(self.critical_pct)); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for m in &self.mounts {
            if m.mount.is_empty() { return Err(DiskError::EmptyMount); }
            if m.total_bytes == 0 { return Err(DiskError::TotalZero(m.mount.clone())); }
            if m.used_bytes > m.total_bytes {
                return Err(DiskError::UsedOverTotal {
                    mount: m.mount.clone(),
                    used: m.used_bytes,
                    total: m.total_bytes,
                });
            }
            if !seen.insert(m.mount.as_str()) {
                return Err(DiskError::DuplicateMount(m.mount.clone()));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mount(name: &str, used: u64, total: u64) -> Mount {
        Mount { mount: name.into(), used_bytes: used, total_bytes: total }
    }

    #[test]
    fn bad_thresholds_rejected() {
        assert!(matches!(DiskMeter::new(90, 70).unwrap_err(), DiskError::BadThresholds(_, _)));
    }

    #[test]
    fn register_and_zone() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        d.register(mount("/", 50, 100)).unwrap();
        assert_eq!(d.zone_of("/"), Some(Zone::Normal));
    }

    #[test]
    fn duplicate_rejected() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        d.register(mount("/", 50, 100)).unwrap();
        assert!(matches!(d.register(mount("/", 60, 100)).unwrap_err(), DiskError::DuplicateMount(_)));
    }

    #[test]
    fn used_over_total_rejected() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        assert!(matches!(d.register(mount("/", 200, 100)).unwrap_err(), DiskError::UsedOverTotal { .. }));
    }

    #[test]
    fn worst_zone() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        d.register(mount("/", 50, 100)).unwrap();
        d.register(mount("/var", 95, 100)).unwrap();
        assert_eq!(d.worst_zone(), Zone::Critical);
    }

    #[test]
    fn update_changes_used() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        d.register(mount("/", 0, 100)).unwrap();
        d.update("/", 80).unwrap();
        assert_eq!(d.used_pct("/"), Some(80));
        assert_eq!(d.zone_of("/"), Some(Zone::Warn));
    }

    #[test]
    fn empty_mount_rejected() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        assert!(matches!(d.register(mount("", 0, 100)).unwrap_err(), DiskError::EmptyMount));
    }

    #[test]
    fn total_zero_rejected() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        assert!(matches!(d.register(mount("/", 0, 0)).unwrap_err(), DiskError::TotalZero(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        d.schema_version = "9.9.9".into();
        assert!(matches!(d.validate().unwrap_err(), DiskError::SchemaMismatch));
    }

    #[test]
    fn meter_serde_roundtrip() {
        let mut d = DiskMeter::new(70, 90).unwrap();
        d.register(mount("/", 50, 100)).unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: DiskMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
