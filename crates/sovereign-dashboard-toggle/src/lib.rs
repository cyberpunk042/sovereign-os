//! `sovereign-dashboard-toggle` — per-dashboard visibility/toggle
//! infrastructure per M060 R10038 + R10129-R10132 + R10174 + R10198.
//!
//! Operator standing direction (verbatim, 2026-05-19):
//!
//! > "everything can be turned on and off and there are also a tons of
//! > modes and profiles"
//!
//! The toggle state is the authoritative source for which dashboards
//! the cockpit renders. Per M060 R10131 every change is MS003-signed;
//! per R10132 every change emits an M049 trace + OCSF Configuration
//! Change (class 5001) event. Per R10198 LAN exposure is default-off
//! and operator-toggled.
//!
//! The crate composes the 21-slot catalog from
//! `sovereign-dashboard-coverage`; you cannot toggle a slot that does
//! not appear there (no invention).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_dashboard_coverage::CoverageManifest;
use std::collections::BTreeMap;
use std::path::Path;
use thiserror::Error;

/// Schema version of the toggle config.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Canonical on-disk path per M060 R10130.
pub const TOGGLE_CONFIG_PATH: &str = "/etc/sovereign-os/dashboards.toml";

/// Per-slot toggle state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SlotState {
    /// Dashboard is visible to the operator.
    Enabled,
    /// Dashboard is hidden from the cockpit but the publisher endpoint stays live.
    Disabled,
    /// Dashboard is hidden AND its publisher is paused.
    Paused,
}

/// Network exposure level per R10198.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ExposureLevel {
    /// Loopback only (default per R10198).
    LoopbackOnly,
    /// LAN visible — operator-signed enablement required.
    Lan,
}

/// One config snapshot: per-slot state + global exposure + signature envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToggleConfig {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// Per-slot state keyed by canonical "D-NN" id.
    pub slots: BTreeMap<String, SlotState>,
    /// Global exposure level (default LoopbackOnly per R10198).
    pub exposure: ExposureLevel,
    /// ISO-8601 UTC of last operator-signed change.
    pub updated_at: String,
    /// MS003 signature over canonical-JSON (hex). Empty until first signed change.
    pub signature: String,
}

impl Default for ToggleConfig {
    fn default() -> Self {
        // Default: all 21 catalog slots Enabled, LoopbackOnly exposure.
        let manifest = CoverageManifest::canonical();
        let mut slots = BTreeMap::new();
        for e in &manifest.entries {
            slots.insert(e.slot.clone(), SlotState::Enabled);
        }
        Self {
            schema_version: SCHEMA_VERSION.into(),
            slots,
            exposure: ExposureLevel::LoopbackOnly,
            updated_at: "1970-01-01T00:00:00Z".into(),
            signature: String::new(),
        }
    }
}

/// Toggle errors.
#[derive(Debug, Error)]
pub enum ToggleError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Slot is not in the M060 catalog — refused per "no invention".
    #[error("slot not in M060 catalog: {0}")]
    SlotNotInCatalog(String),
    /// Default-off LAN exposure cannot be enabled without operator-signed change.
    #[error("LAN exposure refused without MS003 signature (R10198)")]
    LanExposureUnsigned,
    /// Disabling D-00 is refused — master surface is non-toggleable.
    #[error("D-00 master dashboard cannot be disabled (anchor surface)")]
    MasterDashboardLocked,
}

/// Single toggle-change event for the M049 + OCSF emission per R10132.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToggleChangeEvent {
    /// Slot id, e.g. "D-12".
    pub slot: String,
    /// Previous state.
    pub from: SlotState,
    /// New state.
    pub to: SlotState,
    /// ISO-8601 UTC timestamp.
    pub at: String,
    /// Operator MS003 fingerprint.
    pub actor: String,
    /// OCSF event class — always 5001 (Configuration Change) per R10132.
    pub ocsf_class: u32,
    /// M049 trace_id reference.
    pub trace_id: String,
}

impl ToggleConfig {
    /// Validate config invariants.
    pub fn validate(&self) -> Result<(), ToggleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToggleError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        // Reject any slot not in the M060 catalog.
        let catalog = CoverageManifest::canonical();
        let known: std::collections::HashSet<&str> =
            catalog.entries.iter().map(|e| e.slot.as_str()).collect();
        for slot in self.slots.keys() {
            if !known.contains(slot.as_str()) {
                return Err(ToggleError::SlotNotInCatalog(slot.clone()));
            }
        }
        // D-00 master dashboard must never be Disabled or Paused (anchor surface).
        if let Some(state) = self.slots.get("D-00") {
            if *state != SlotState::Enabled {
                return Err(ToggleError::MasterDashboardLocked);
            }
        }
        // LAN exposure refused when signature empty per R10198.
        if self.exposure == ExposureLevel::Lan && self.signature.is_empty() {
            return Err(ToggleError::LanExposureUnsigned);
        }
        Ok(())
    }

    /// Return the slot's state, or Enabled if not in the config (lenient default).
    pub fn state(&self, slot: &str) -> SlotState {
        self.slots.get(slot).copied().unwrap_or(SlotState::Enabled)
    }

    /// True when the dashboard renders in the cockpit.
    pub fn is_visible(&self, slot: &str) -> bool {
        self.state(slot) == SlotState::Enabled
    }

    /// Apply a state change. Returns the event that should be emitted
    /// via M049 + OCSF class 5001 per R10132.
    pub fn apply_change(
        &mut self,
        slot: &str,
        new_state: SlotState,
        actor: &str,
        trace_id: &str,
        at: &str,
    ) -> Result<ToggleChangeEvent, ToggleError> {
        // Catalog presence check.
        let catalog = CoverageManifest::canonical();
        let known: std::collections::HashSet<&str> =
            catalog.entries.iter().map(|e| e.slot.as_str()).collect();
        if !known.contains(slot) {
            return Err(ToggleError::SlotNotInCatalog(slot.into()));
        }
        // D-00 anchor protection.
        if slot == "D-00" && new_state != SlotState::Enabled {
            return Err(ToggleError::MasterDashboardLocked);
        }
        let from = self.state(slot);
        self.slots.insert(slot.into(), new_state);
        self.updated_at = at.into();
        Ok(ToggleChangeEvent {
            slot: slot.into(),
            from,
            to: new_state,
            at: at.into(),
            actor: actor.into(),
            ocsf_class: 5001,
            trace_id: trace_id.into(),
        })
    }

    /// Count of slots in each state.
    pub fn state_counts(&self) -> (u32, u32, u32) {
        let mut e = 0u32;
        let mut d = 0u32;
        let mut p = 0u32;
        for &s in self.slots.values() {
            match s {
                SlotState::Enabled => e += 1,
                SlotState::Disabled => d += 1,
                SlotState::Paused => p += 1,
            }
        }
        (e, d, p)
    }

    /// Serialise to TOML-friendly canonical form. (Pure-JSON encoding;
    /// the daemon-side reader translates to/from TOML on disk.)
    pub fn to_canonical_json(&self) -> Result<String, ToggleError> {
        serde_json::to_string_pretty(self).map_err(|e| ToggleError::SchemaMismatch {
            expected: SCHEMA_VERSION.into(),
            actual: format!("serialize: {e}"),
        })
    }

    /// Path-helper: canonical on-disk path per R10130.
    pub fn canonical_path() -> &'static Path {
        Path::new(TOGGLE_CONFIG_PATH)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates_with_21_enabled_slots() {
        let c = ToggleConfig::default();
        c.validate().unwrap();
        let (e, d, p) = c.state_counts();
        assert_eq!(e, 21);
        assert_eq!(d, 0);
        assert_eq!(p, 0);
    }

    #[test]
    fn default_exposure_is_loopback_only() {
        // Per R10198 — operator must sign to expose on LAN
        assert_eq!(ToggleConfig::default().exposure, ExposureLevel::LoopbackOnly);
    }

    #[test]
    fn lan_exposure_unsigned_refused() {
        let mut c = ToggleConfig::default();
        c.exposure = ExposureLevel::Lan;
        // signature still empty → refused
        assert!(matches!(c.validate().unwrap_err(), ToggleError::LanExposureUnsigned));
    }

    #[test]
    fn lan_exposure_with_signature_accepted() {
        let mut c = ToggleConfig::default();
        c.exposure = ExposureLevel::Lan;
        c.signature = "deadbeef".into();
        c.validate().unwrap();
    }

    #[test]
    fn unknown_slot_refused() {
        let mut c = ToggleConfig::default();
        c.slots.insert("D-99".into(), SlotState::Disabled);
        assert!(matches!(
            c.validate().unwrap_err(),
            ToggleError::SlotNotInCatalog(s) if s == "D-99"
        ));
    }

    #[test]
    fn d00_anchor_cannot_be_disabled() {
        let mut c = ToggleConfig::default();
        c.slots.insert("D-00".into(), SlotState::Disabled);
        assert!(matches!(c.validate().unwrap_err(), ToggleError::MasterDashboardLocked));
        // also blocks via apply_change
        let mut c2 = ToggleConfig::default();
        assert!(matches!(
            c2.apply_change("D-00", SlotState::Disabled, "op", "t", "2026-05-19T00:00:00Z").unwrap_err(),
            ToggleError::MasterDashboardLocked
        ));
    }

    #[test]
    fn apply_change_emits_ocsf_5001_event() {
        let mut c = ToggleConfig::default();
        let ev = c
            .apply_change(
                "D-12",
                SlotState::Disabled,
                "operator-fp",
                "trace-x",
                "2026-05-19T03:30:00Z",
            )
            .unwrap();
        assert_eq!(ev.slot, "D-12");
        assert_eq!(ev.from, SlotState::Enabled);
        assert_eq!(ev.to, SlotState::Disabled);
        assert_eq!(ev.actor, "operator-fp");
        assert_eq!(ev.ocsf_class, 5001);
        assert_eq!(ev.trace_id, "trace-x");
        assert_eq!(c.state("D-12"), SlotState::Disabled);
        assert!(!c.is_visible("D-12"));
        assert_eq!(c.updated_at, "2026-05-19T03:30:00Z");
    }

    #[test]
    fn apply_change_to_unknown_slot_refused() {
        let mut c = ToggleConfig::default();
        let err = c.apply_change("D-99", SlotState::Disabled, "op", "t", "ts").unwrap_err();
        assert!(matches!(err, ToggleError::SlotNotInCatalog(_)));
    }

    #[test]
    fn state_counts_track_transitions() {
        let mut c = ToggleConfig::default();
        c.apply_change("D-12", SlotState::Disabled, "op", "t", "ts").unwrap();
        c.apply_change("D-13", SlotState::Disabled, "op", "t", "ts").unwrap();
        c.apply_change("D-14", SlotState::Paused, "op", "t", "ts").unwrap();
        let (e, d, p) = c.state_counts();
        assert_eq!(e, 18);
        assert_eq!(d, 2);
        assert_eq!(p, 1);
    }

    #[test]
    fn state_for_unknown_slot_defaults_enabled() {
        let c = ToggleConfig::default();
        assert_eq!(c.state("D-XX-not-in-catalog"), SlotState::Enabled);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ToggleConfig::default();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), ToggleError::SchemaMismatch { .. }));
    }

    #[test]
    fn canonical_json_roundtrip_preserves_state() {
        let mut original = ToggleConfig::default();
        original
            .apply_change("D-15", SlotState::Disabled, "op-x", "trace-1", "2026-05-19T04:00:00Z")
            .unwrap();
        let j = original.to_canonical_json().unwrap();
        let back: ToggleConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(original, back);
        assert_eq!(back.state("D-15"), SlotState::Disabled);
    }

    #[test]
    fn canonical_path_matches_r10130() {
        assert_eq!(
            ToggleConfig::canonical_path().to_str().unwrap(),
            "/etc/sovereign-os/dashboards.toml"
        );
    }

    #[test]
    fn slot_state_serde_uses_kebab_case() {
        assert_eq!(serde_json::to_string(&SlotState::Paused).unwrap(), "\"paused\"");
        assert_eq!(serde_json::to_string(&SlotState::Disabled).unwrap(), "\"disabled\"");
    }

    #[test]
    fn exposure_serde_uses_kebab_case() {
        assert_eq!(
            serde_json::to_string(&ExposureLevel::LoopbackOnly).unwrap(),
            "\"loopback-only\""
        );
        assert_eq!(serde_json::to_string(&ExposureLevel::Lan).unwrap(), "\"lan\"");
    }
}
