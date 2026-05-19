//! `sovereign-cockpit-banner-state` — top-bar source of truth.
//!
//! 4-tuple the cockpit's always-visible banner consumes:
//! - `mode`           — current ExecutionMode
//! - `bundle`         — active profile BundleName
//! - `worst_thermal`  — hottest target's ThermalVerdict (worst-of-5)
//! - `open_alerts`    — count of unresolved alerts
//!
//! The daemon recomputes + signs this on every relevant state change.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_profile_bundles::BundleName;
use sovereign_hardware_thermal_policy::ThermalVerdict;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Banner severity rolled up for visual styling.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum BannerSeverity {
    /// All clear.
    Calm,
    /// Background condition (Warm thermal, Execute mode in private bundle, etc.).
    Notice,
    /// Active condition needing attention (Throttle, open alerts).
    Warn,
    /// Critical (Shutdown thermal, many open alerts).
    Critical,
}

/// Banner state envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BannerState {
    /// Schema version.
    pub schema_version: String,
    /// Active execution mode.
    pub mode: ExecutionMode,
    /// Active profile bundle.
    pub bundle: BundleName,
    /// Worst-of-5 thermal verdict across hardware.
    pub worst_thermal: ThermalVerdict,
    /// Count of unresolved alerts.
    pub open_alerts: u32,
    /// Computed severity (must match `compute_severity`).
    pub severity: BannerSeverity,
    /// ISO-8601 UTC of last update.
    pub updated_at: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BannerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Stored severity disagrees with computed.
    #[error("severity mismatch: stored={stored:?} computed={computed:?}")]
    SeverityMismatch {
        /// Stored.
        stored: BannerSeverity,
        /// Computed.
        computed: BannerSeverity,
    },
    /// updated_at empty.
    #[error("updated_at missing")]
    MissingTimestamp,
}

/// Compute banner severity from the live signals.
///
/// Rules (most severe wins):
/// - Shutdown thermal → Critical
/// - Open alerts > 5 → Critical
/// - Throttle thermal → Warn
/// - Open alerts ≥ 1 → Warn
/// - Warm thermal → Notice
/// - Execute mode → Notice (operator should know live writes are armed)
/// - Otherwise → Calm
pub fn compute_severity(mode: ExecutionMode, worst_thermal: ThermalVerdict, open_alerts: u32) -> BannerSeverity {
    if worst_thermal == ThermalVerdict::Shutdown { return BannerSeverity::Critical; }
    if open_alerts > 5 { return BannerSeverity::Critical; }
    if worst_thermal == ThermalVerdict::Throttle { return BannerSeverity::Warn; }
    if open_alerts >= 1 { return BannerSeverity::Warn; }
    if worst_thermal == ThermalVerdict::Warm { return BannerSeverity::Notice; }
    if mode == ExecutionMode::Execute { return BannerSeverity::Notice; }
    BannerSeverity::Calm
}

impl BannerState {
    /// Build a fresh banner state.
    pub fn build(
        mode: ExecutionMode,
        bundle: BundleName,
        worst_thermal: ThermalVerdict,
        open_alerts: u32,
        at: &str,
    ) -> Self {
        let severity = compute_severity(mode, worst_thermal, open_alerts);
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode, bundle, worst_thermal, open_alerts, severity,
            updated_at: at.into(),
        }
    }

    /// Validate stored severity matches the computed one + timestamp present.
    pub fn validate(&self) -> Result<(), BannerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BannerError::SchemaMismatch);
        }
        if self.updated_at.is_empty() {
            return Err(BannerError::MissingTimestamp);
        }
        let computed = compute_severity(self.mode, self.worst_thermal, self.open_alerts);
        if computed != self.severity {
            return Err(BannerError::SeverityMismatch { stored: self.severity, computed });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_validates() {
        let b = BannerState::build(ExecutionMode::Plan, BundleName::Careful, ThermalVerdict::Cool, 0, "t");
        b.validate().unwrap();
    }

    #[test]
    fn calm_when_quiet_and_planning() {
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Cool, 0), BannerSeverity::Calm);
    }

    #[test]
    fn execute_mode_promotes_to_notice() {
        assert_eq!(compute_severity(ExecutionMode::Execute, ThermalVerdict::Cool, 0), BannerSeverity::Notice);
    }

    #[test]
    fn warm_thermal_is_notice() {
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Warm, 0), BannerSeverity::Notice);
    }

    #[test]
    fn throttle_is_warn() {
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Throttle, 0), BannerSeverity::Warn);
    }

    #[test]
    fn alerts_one_to_five_is_warn() {
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Cool, 1), BannerSeverity::Warn);
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Cool, 5), BannerSeverity::Warn);
    }

    #[test]
    fn alerts_over_five_is_critical() {
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Cool, 6), BannerSeverity::Critical);
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Cool, 100), BannerSeverity::Critical);
    }

    #[test]
    fn shutdown_thermal_is_critical_even_with_no_alerts() {
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Shutdown, 0), BannerSeverity::Critical);
    }

    #[test]
    fn shutdown_outranks_warn_alerts() {
        assert_eq!(compute_severity(ExecutionMode::Plan, ThermalVerdict::Shutdown, 1), BannerSeverity::Critical);
    }

    #[test]
    fn severity_mismatch_caught() {
        let mut b = BannerState::build(ExecutionMode::Plan, BundleName::Careful, ThermalVerdict::Cool, 0, "t");
        b.severity = BannerSeverity::Critical; // wrong
        match b.validate().unwrap_err() {
            BannerError::SeverityMismatch { stored, computed } => {
                assert_eq!(stored, BannerSeverity::Critical);
                assert_eq!(computed, BannerSeverity::Calm);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = BannerState::build(ExecutionMode::Plan, BundleName::Careful, ThermalVerdict::Cool, 0, "t");
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), BannerError::SchemaMismatch));
    }

    #[test]
    fn missing_timestamp_caught() {
        let mut b = BannerState::build(ExecutionMode::Plan, BundleName::Careful, ThermalVerdict::Cool, 0, "t");
        b.updated_at = String::new();
        assert!(matches!(b.validate().unwrap_err(), BannerError::MissingTimestamp));
    }

    #[test]
    fn severity_serde_kebab() {
        assert_eq!(serde_json::to_string(&BannerSeverity::Calm).unwrap(), "\"calm\"");
        assert_eq!(serde_json::to_string(&BannerSeverity::Notice).unwrap(), "\"notice\"");
        assert_eq!(serde_json::to_string(&BannerSeverity::Warn).unwrap(), "\"warn\"");
        assert_eq!(serde_json::to_string(&BannerSeverity::Critical).unwrap(), "\"critical\"");
    }

    #[test]
    fn banner_serde_roundtrip() {
        let b = BannerState::build(ExecutionMode::Execute, BundleName::Fast, ThermalVerdict::Warm, 2, "2026-05-19T03:00:00Z");
        let j = serde_json::to_string(&b).unwrap();
        let back: BannerState = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
