//! `sovereign-cgroup-systemd` — M045 cgroup v2 + systemd resource governance.
//!
//! Per M045 + E0428 + M00747-M00750 + dump 13564-13594. Eight OS
//! primitives form the peace-machine substrate.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine verbatim per E0428 dump 13594.
pub const DOCTRINE_PEACE_MACHINE_SUBSTRATE: &str = "This is not incidental. This is the peace-machine substrate";

/// 8 OS primitives per E0428 dump 13568-13586.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum OsPrimitive {
    /// cgroup v2 resource control (1).
    Cgroupv2,
    /// systemd lifecycle: service-boundaries / slices / scopes (2).
    Systemd,
    /// PSI pressure sensing CPU-memory-IO (3).
    Psi,
    /// eBPF + LSM observation possible-enforcement (4).
    Ebpf,
    /// AppArmor mandatory access boundaries (5).
    AppArmor,
    /// namespaces isolation (6).
    Namespaces,
    /// ZFS rollback durable memory (7).
    Zfs,
    /// LUKS-TPM-FIDO2 identity sealed storage (8).
    LuksTpmFido2,
}

impl OsPrimitive {
    /// Canonical 1..8.
    pub fn position(self) -> u8 {
        match self {
            OsPrimitive::Cgroupv2 => 1,
            OsPrimitive::Systemd => 2,
            OsPrimitive::Psi => 3,
            OsPrimitive::Ebpf => 4,
            OsPrimitive::AppArmor => 5,
            OsPrimitive::Namespaces => 6,
            OsPrimitive::Zfs => 7,
            OsPrimitive::LuksTpmFido2 => 8,
        }
    }
    /// Domain (governance / observability / isolation / identity).
    pub fn domain(self) -> &'static str {
        match self {
            OsPrimitive::Cgroupv2 | OsPrimitive::Systemd => "governance",
            OsPrimitive::Psi | OsPrimitive::Ebpf => "observability",
            OsPrimitive::AppArmor | OsPrimitive::Namespaces | OsPrimitive::Zfs => "isolation",
            OsPrimitive::LuksTpmFido2 => "identity",
        }
    }
}

/// Per-primitive availability state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PrimitiveState {
    /// Active and configured.
    Available,
    /// Compiled into kernel but disabled.
    Disabled,
    /// Missing from kernel build.
    Missing,
}

/// One primitive record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PrimitiveRecord {
    /// Primitive.
    pub primitive: OsPrimitive,
    /// State.
    pub state: PrimitiveState,
    /// Domain (governance / observability / isolation / identity).
    pub domain: String,
}

/// 8-primitive snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PrimitiveSnapshot {
    /// Schema version.
    pub schema_version: String,
    /// Doctrine surface — MUST equal [`DOCTRINE_PEACE_MACHINE_SUBSTRATE`].
    pub doctrine: String,
    /// 8 primitives (exactly 8).
    pub primitives: Vec<PrimitiveRecord>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PrimitiveError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Doctrine tampered.
    #[error("doctrine tampered")]
    DoctrineTampered,
    /// Count != 8.
    #[error("primitive count {0} != 8")]
    CountInvalid(usize),
    /// Missing primitive.
    #[error("required primitive missing: {0:?}")]
    PrimitiveMissing(OsPrimitive),
    /// Duplicate primitive.
    #[error("duplicate primitive: {0:?}")]
    DuplicatePrimitive(OsPrimitive),
    /// Domain mismatch.
    #[error("domain mismatch for {primitive:?}: declared {declared}, canonical {canonical}")]
    DomainMismatch {
        /// Primitive.
        primitive: OsPrimitive,
        /// Declared.
        declared: String,
        /// Canonical.
        canonical: String,
    },
}

impl PrimitiveSnapshot {
    /// Canonical empty snapshot.
    pub fn empty_canonical() -> Self {
        let primitives = [
            OsPrimitive::Cgroupv2, OsPrimitive::Systemd, OsPrimitive::Psi,
            OsPrimitive::Ebpf, OsPrimitive::AppArmor, OsPrimitive::Namespaces,
            OsPrimitive::Zfs, OsPrimitive::LuksTpmFido2,
        ].into_iter().map(|p| PrimitiveRecord {
            primitive: p,
            state: PrimitiveState::Missing,
            domain: p.domain().into(),
        }).collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_PEACE_MACHINE_SUBSTRATE.into(),
            primitives,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PrimitiveError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PrimitiveError::SchemaMismatch);
        }
        if self.doctrine != DOCTRINE_PEACE_MACHINE_SUBSTRATE {
            return Err(PrimitiveError::DoctrineTampered);
        }
        if self.primitives.len() != 8 {
            return Err(PrimitiveError::CountInvalid(self.primitives.len()));
        }
        let required = [
            OsPrimitive::Cgroupv2, OsPrimitive::Systemd, OsPrimitive::Psi,
            OsPrimitive::Ebpf, OsPrimitive::AppArmor, OsPrimitive::Namespaces,
            OsPrimitive::Zfs, OsPrimitive::LuksTpmFido2,
        ];
        for p in required {
            if !self.primitives.iter().any(|r| r.primitive == p) {
                return Err(PrimitiveError::PrimitiveMissing(p));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<OsPrimitive> = HashSet::new();
        for r in &self.primitives {
            if !seen.insert(r.primitive) {
                return Err(PrimitiveError::DuplicatePrimitive(r.primitive));
            }
            let canonical = r.primitive.domain();
            if r.domain != canonical {
                return Err(PrimitiveError::DomainMismatch {
                    primitive: r.primitive,
                    declared: r.domain.clone(),
                    canonical: canonical.into(),
                });
            }
        }
        Ok(())
    }

    /// Count available primitives.
    pub fn available_count(&self) -> usize {
        self.primitives.iter().filter(|r| r.state == PrimitiveState::Available).count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eight_primitives_positioned_1_to_8() {
        for (p, n) in [
            (OsPrimitive::Cgroupv2, 1), (OsPrimitive::Systemd, 2),
            (OsPrimitive::Psi, 3), (OsPrimitive::Ebpf, 4),
            (OsPrimitive::AppArmor, 5), (OsPrimitive::Namespaces, 6),
            (OsPrimitive::Zfs, 7), (OsPrimitive::LuksTpmFido2, 8),
        ] {
            assert_eq!(p.position(), n);
        }
    }

    #[test]
    fn domain_mapping() {
        assert_eq!(OsPrimitive::Cgroupv2.domain(), "governance");
        assert_eq!(OsPrimitive::Systemd.domain(), "governance");
        assert_eq!(OsPrimitive::Psi.domain(), "observability");
        assert_eq!(OsPrimitive::Ebpf.domain(), "observability");
        assert_eq!(OsPrimitive::AppArmor.domain(), "isolation");
        assert_eq!(OsPrimitive::Namespaces.domain(), "isolation");
        assert_eq!(OsPrimitive::Zfs.domain(), "isolation");
        assert_eq!(OsPrimitive::LuksTpmFido2.domain(), "identity");
    }

    #[test]
    fn empty_canonical_validates() {
        PrimitiveSnapshot::empty_canonical().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = PrimitiveSnapshot::empty_canonical();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), PrimitiveError::SchemaMismatch));
    }

    #[test]
    fn doctrine_tamper_caught() {
        let mut s = PrimitiveSnapshot::empty_canonical();
        s.doctrine = "wrong".into();
        assert!(matches!(s.validate().unwrap_err(), PrimitiveError::DoctrineTampered));
    }

    #[test]
    fn count_invalid_rejected() {
        let mut s = PrimitiveSnapshot::empty_canonical();
        s.primitives.pop();
        assert!(matches!(s.validate().unwrap_err(), PrimitiveError::CountInvalid(7)));
    }

    #[test]
    fn domain_mismatch_caught() {
        let mut s = PrimitiveSnapshot::empty_canonical();
        s.primitives[0].domain = "wrong".into();
        match s.validate().unwrap_err() {
            PrimitiveError::DomainMismatch { primitive, declared, canonical } => {
                assert_eq!(primitive, OsPrimitive::Cgroupv2);
                assert_eq!(declared, "wrong");
                assert_eq!(canonical, "governance");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn available_count_filters() {
        let mut s = PrimitiveSnapshot::empty_canonical();
        s.primitives[0].state = PrimitiveState::Available;
        s.primitives[1].state = PrimitiveState::Available;
        s.primitives[2].state = PrimitiveState::Disabled;
        assert_eq!(s.available_count(), 2);
    }

    #[test]
    fn doctrine_verbatim() {
        assert_eq!(DOCTRINE_PEACE_MACHINE_SUBSTRATE, "This is not incidental. This is the peace-machine substrate");
    }

    #[test]
    fn os_primitive_serde_kebab() {
        assert_eq!(serde_json::to_string(&OsPrimitive::Cgroupv2).unwrap(), "\"cgroupv2\"");
        assert_eq!(serde_json::to_string(&OsPrimitive::AppArmor).unwrap(), "\"app-armor\"");
        assert_eq!(serde_json::to_string(&OsPrimitive::LuksTpmFido2).unwrap(), "\"luks-tpm-fido2\"");
    }

    #[test]
    fn snapshot_serde_roundtrip() {
        let s = PrimitiveSnapshot::empty_canonical();
        let j = serde_json::to_string(&s).unwrap();
        let back: PrimitiveSnapshot = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
