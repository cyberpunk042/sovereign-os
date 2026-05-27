//! `sovereign-trinity` — M066 Trinity Framework Genesis.
//!
//! Per M066 + dump 936-987:
//!
//! > "The Pulse (Vector Core) / The Weaver (Sandboxed Fabric) / The
//! > Auditor (Immutable Gatekeeper)" (dump 953-978 verbatim)
//!
//! **Project boundary** per E0645 + operator standing direction
//! ("Respect the projects"):
//!
//! - **Pulse + Weaver implementations live in sovereign-os runtime.**
//! - **Auditor IMPLEMENTATION lives in selfdef MS044 (guardian-core).**
//!   This crate carries the typed-mirror surface for Pulse/Weaver +
//!   the Auditor reference (no implementation).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Verbatim Trinity genesis quote per dump 953-978.
pub const TRINITY_GENESIS: &str =
    "The Pulse (Vector Core) / The Weaver (Sandboxed Fabric) / The Auditor (Immutable Gatekeeper)";

/// The three Trinity roles per E0640-E0642.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TrinityRole {
    /// The Pulse — Vector Core (MASM + Wasm primitives, AVX-512, bit-plane transposition).
    Pulse,
    /// The Weaver — Sandboxed Fabric (Wasm + Podman+VFIO multi-agent orchestration).
    Weaver,
    /// The Auditor — Immutable Gatekeeper (Tetragon eBPF; implementation in selfdef MS044).
    Auditor,
}

impl TrinityRole {
    /// Substrate that this role manifests on physically.
    pub fn substrate(self) -> &'static str {
        match self {
            TrinityRole::Pulse => "ryzen-9-9900x-avx512",
            TrinityRole::Weaver => "podman-vfio-3090-blackwell",
            TrinityRole::Auditor => "tetragon-ebpf",
        }
    }
    /// Which repo owns the implementation.
    pub fn implementation_repo(self) -> &'static str {
        match self {
            TrinityRole::Pulse => "sovereign-os",
            TrinityRole::Weaver => "sovereign-os",
            // Project boundary per E0645 — Auditor IMPLEMENTATION is selfdef MS044.
            TrinityRole::Auditor => "selfdef",
        }
    }
}

/// Per-role status snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RoleStatus {
    /// Role.
    pub role: TrinityRole,
    /// Whether the role is currently bound to a running implementation.
    pub bound: bool,
    /// Substrate identifier (matches role.substrate() in canonical case).
    pub substrate: String,
    /// Operator-readable state (e.g. "warm", "cold", "draining").
    pub state: String,
    /// ISO-8601 UTC timestamp of last heartbeat.
    pub last_heartbeat_at: String,
}

/// Top-level Trinity manifest envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TrinityManifest {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// Verbatim genesis quote.
    pub genesis: String,
    /// All 3 role statuses (Pulse + Weaver + Auditor; MUST be exactly 3).
    pub roles: Vec<RoleStatus>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TrinityError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Genesis quote tampered.
    #[error("trinity genesis quote tampered (project-boundary doctrine)")]
    GenesisTampered,
    /// Role count != exactly 3.
    #[error("role count {0} != 3 canonical roles")]
    RoleCountInvalid(usize),
    /// One of the 3 roles missing.
    #[error("required role missing: {0:?}")]
    RoleMissing(TrinityRole),
    /// Duplicate role.
    #[error("duplicate role: {0:?}")]
    DuplicateRole(TrinityRole),
}

impl TrinityManifest {
    /// Construct an unbound canonical manifest with all 3 roles unbound.
    pub fn empty_canonical() -> Self {
        let now = "2026-05-19T00:00:00Z";
        let roles = vec![
            RoleStatus {
                role: TrinityRole::Pulse,
                bound: false,
                substrate: TrinityRole::Pulse.substrate().into(),
                state: "cold".into(),
                last_heartbeat_at: now.into(),
            },
            RoleStatus {
                role: TrinityRole::Weaver,
                bound: false,
                substrate: TrinityRole::Weaver.substrate().into(),
                state: "cold".into(),
                last_heartbeat_at: now.into(),
            },
            RoleStatus {
                role: TrinityRole::Auditor,
                bound: false,
                substrate: TrinityRole::Auditor.substrate().into(),
                state: "cold".into(),
                last_heartbeat_at: now.into(),
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            genesis: TRINITY_GENESIS.into(),
            roles,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), TrinityError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TrinityError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.genesis != TRINITY_GENESIS {
            return Err(TrinityError::GenesisTampered);
        }
        if self.roles.len() != 3 {
            return Err(TrinityError::RoleCountInvalid(self.roles.len()));
        }
        for r in [
            TrinityRole::Pulse,
            TrinityRole::Weaver,
            TrinityRole::Auditor,
        ] {
            if !self.roles.iter().any(|rs| rs.role == r) {
                return Err(TrinityError::RoleMissing(r));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<TrinityRole> = HashSet::new();
        for rs in &self.roles {
            if !seen.insert(rs.role) {
                return Err(TrinityError::DuplicateRole(rs.role));
            }
        }
        Ok(())
    }

    /// Lookup by role.
    pub fn status_of(&self, role: TrinityRole) -> Option<&RoleStatus> {
        self.roles.iter().find(|rs| rs.role == role)
    }

    /// Bind a role to its running implementation.
    pub fn bind(&mut self, role: TrinityRole, state: &str, heartbeat_at: &str) {
        if let Some(rs) = self.roles.iter_mut().find(|rs| rs.role == role) {
            rs.bound = true;
            rs.state = state.into();
            rs.last_heartbeat_at = heartbeat_at.into();
        }
    }

    /// Count of bound roles.
    pub fn bound_count(&self) -> usize {
        self.roles.iter().filter(|rs| rs.bound).count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_canonical_validates() {
        TrinityManifest::empty_canonical().validate().unwrap();
    }

    #[test]
    fn three_roles_present() {
        let m = TrinityManifest::empty_canonical();
        assert!(m.status_of(TrinityRole::Pulse).is_some());
        assert!(m.status_of(TrinityRole::Weaver).is_some());
        assert!(m.status_of(TrinityRole::Auditor).is_some());
    }

    #[test]
    fn substrate_mapping_per_doctrine() {
        assert_eq!(TrinityRole::Pulse.substrate(), "ryzen-9-9900x-avx512");
        assert_eq!(
            TrinityRole::Weaver.substrate(),
            "podman-vfio-3090-blackwell"
        );
        assert_eq!(TrinityRole::Auditor.substrate(), "tetragon-ebpf");
    }

    #[test]
    fn project_boundary_implementation_repo() {
        // Per E0645 + "Respect the projects":
        assert_eq!(TrinityRole::Pulse.implementation_repo(), "sovereign-os");
        assert_eq!(TrinityRole::Weaver.implementation_repo(), "sovereign-os");
        assert_eq!(TrinityRole::Auditor.implementation_repo(), "selfdef");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = TrinityManifest::empty_canonical();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            TrinityError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn genesis_tamper_caught() {
        let mut m = TrinityManifest::empty_canonical();
        m.genesis = "Two roles only".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            TrinityError::GenesisTampered
        ));
    }

    #[test]
    fn role_count_invalid_caught() {
        let mut m = TrinityManifest::empty_canonical();
        m.roles.pop();
        assert!(matches!(
            m.validate().unwrap_err(),
            TrinityError::RoleCountInvalid(2)
        ));
    }

    #[test]
    fn missing_role_caught_when_replaced() {
        let mut m = TrinityManifest::empty_canonical();
        // Replace Pulse with second Weaver — count stays 3 but Pulse missing.
        m.roles[0] = RoleStatus {
            role: TrinityRole::Weaver,
            bound: false,
            substrate: "dup".into(),
            state: "cold".into(),
            last_heartbeat_at: "2026-05-19T00:00:00Z".into(),
        };
        let err = m.validate().unwrap_err();
        assert!(matches!(
            err,
            TrinityError::RoleMissing(TrinityRole::Pulse)
                | TrinityError::DuplicateRole(TrinityRole::Weaver)
        ));
    }

    #[test]
    fn bind_lifecycle() {
        let mut m = TrinityManifest::empty_canonical();
        assert_eq!(m.bound_count(), 0);
        m.bind(TrinityRole::Pulse, "warm", "2026-05-19T03:00:00Z");
        assert_eq!(m.bound_count(), 1);
        let pulse = m.status_of(TrinityRole::Pulse).unwrap();
        assert!(pulse.bound);
        assert_eq!(pulse.state, "warm");
        m.bind(TrinityRole::Weaver, "warm", "2026-05-19T03:00:00Z");
        m.bind(TrinityRole::Auditor, "warm", "2026-05-19T03:00:00Z");
        assert_eq!(m.bound_count(), 3);
        m.validate().unwrap();
    }

    #[test]
    fn genesis_verbatim_constant() {
        assert_eq!(
            TRINITY_GENESIS,
            "The Pulse (Vector Core) / The Weaver (Sandboxed Fabric) / The Auditor (Immutable Gatekeeper)"
        );
    }

    #[test]
    fn role_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&TrinityRole::Pulse).unwrap(),
            "\"pulse\""
        );
        assert_eq!(
            serde_json::to_string(&TrinityRole::Weaver).unwrap(),
            "\"weaver\""
        );
        assert_eq!(
            serde_json::to_string(&TrinityRole::Auditor).unwrap(),
            "\"auditor\""
        );
    }

    #[test]
    fn manifest_serde_roundtrip() {
        let mut m = TrinityManifest::empty_canonical();
        m.bind(TrinityRole::Pulse, "warm", "2026-05-19T03:00:00Z");
        let j = serde_json::to_string(&m).unwrap();
        let back: TrinityManifest = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
