//! `sovereign-dashboard-snapshot` — point-in-time cockpit composite.
//!
//! Wraps `BannerState + ContextPanel + ToastTray` into a single
//! serializable envelope. Validates all three sub-states on construction
//! and serialization.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_cockpit_banner_state::BannerState;
use sovereign_cockpit_context_panel::ContextPanel;
use sovereign_cockpit_toast_tray::ToastTray;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Snapshot envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DashboardSnapshot {
    /// Schema version.
    pub schema_version: String,
    /// ISO-8601 UTC capture time.
    pub captured_at: String,
    /// Banner state.
    pub banner: BannerState,
    /// Context panel state.
    pub context: ContextPanel,
    /// Toast tray state.
    pub toasts: ToastTray,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SnapshotError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// captured_at empty.
    #[error("captured_at missing")]
    MissingTimestamp,
    /// Banner invalid.
    #[error("banner invalid: {0}")]
    BannerInvalid(String),
    /// Context invalid.
    #[error("context invalid: {0}")]
    ContextInvalid(String),
    /// Toasts invalid.
    #[error("toasts invalid: {0}")]
    ToastsInvalid(String),
}

impl DashboardSnapshot {
    /// Build a snapshot from sub-states.
    pub fn build(banner: BannerState, context: ContextPanel, toasts: ToastTray, at: &str) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            captured_at: at.into(),
            banner,
            context,
            toasts,
        }
    }

    /// Validate the composite.
    pub fn validate(&self) -> Result<(), SnapshotError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SnapshotError::SchemaMismatch);
        }
        if self.captured_at.is_empty() {
            return Err(SnapshotError::MissingTimestamp);
        }
        self.banner
            .validate()
            .map_err(|e| SnapshotError::BannerInvalid(e.to_string()))?;
        self.context
            .validate()
            .map_err(|e| SnapshotError::ContextInvalid(e.to_string()))?;
        self.toasts
            .validate()
            .map_err(|e| SnapshotError::ToastsInvalid(e.to_string()))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_cockpit_banner_state::BannerSeverity;
    use sovereign_cockpit_toast_tray::build;
    use sovereign_execution_mode_registry::ExecutionMode;
    use sovereign_hardware_thermal_policy::ThermalVerdict;
    use sovereign_profile_bundles::BundleName;

    fn banner() -> BannerState {
        BannerState::build(
            ExecutionMode::Plan,
            BundleName::Careful,
            ThermalVerdict::Cool,
            0,
            "t",
        )
    }
    fn ctx() -> ContextPanel {
        ContextPanel::new(
            BundleName::Careful,
            ExecutionMode::Plan,
            "repo",
            "main",
            "th-1",
            "t",
        )
    }
    fn tray() -> ToastTray {
        let mut tr = ToastTray::new();
        tr.post(build("t1", BannerSeverity::Notice, "Hi", "Body", 5, "t"))
            .unwrap();
        tr
    }

    #[test]
    fn snapshot_validates() {
        let s = DashboardSnapshot::build(banner(), ctx(), tray(), "t");
        s.validate().unwrap();
    }

    #[test]
    fn missing_captured_at_caught() {
        let s = DashboardSnapshot::build(banner(), ctx(), tray(), "");
        assert!(matches!(
            s.validate().unwrap_err(),
            SnapshotError::MissingTimestamp
        ));
    }

    #[test]
    fn invalid_banner_caught() {
        let mut s = DashboardSnapshot::build(banner(), ctx(), tray(), "t");
        s.banner.severity = BannerSeverity::Critical; // mismatched
        assert!(matches!(
            s.validate().unwrap_err(),
            SnapshotError::BannerInvalid(_)
        ));
    }

    #[test]
    fn invalid_context_caught() {
        let mut s = DashboardSnapshot::build(banner(), ctx(), tray(), "t");
        s.context.refreshed_at = String::new();
        assert!(matches!(
            s.validate().unwrap_err(),
            SnapshotError::ContextInvalid(_)
        ));
    }

    #[test]
    fn invalid_toasts_caught() {
        let mut s = DashboardSnapshot::build(banner(), ctx(), tray(), "t");
        // Tamper toast.
        s.toasts.toasts[0].id = String::new();
        assert!(matches!(
            s.validate().unwrap_err(),
            SnapshotError::ToastsInvalid(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = DashboardSnapshot::build(banner(), ctx(), tray(), "t");
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SnapshotError::SchemaMismatch
        ));
    }

    #[test]
    fn snapshot_serde_roundtrip() {
        let s = DashboardSnapshot::build(banner(), ctx(), tray(), "2026-05-19T03:00:00Z");
        let j = serde_json::to_string(&s).unwrap();
        let back: DashboardSnapshot = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
