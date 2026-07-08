//! `sovereign-base-os` — E0459 / M00800: the Base OS module.
//!
//! Debian 13 / Ubuntu 24 base: "reproducible enough to rebuild, but flexible
//! enough for NVIDIA reality." The OS base owns ten responsibilities and runs
//! in one of five config modes. This crate fixes both, plus the principle
//! "declarative where it protects continuity, imperative where hardware reality
//! demands adaptation."

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 10 base-OS responsibilities (M00800).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum OsResponsibility {
    /// Kernel.
    Kernel,
    /// Firmware.
    Firmware,
    /// NVIDIA drivers.
    NvidiaDrivers,
    /// AppArmor.
    AppArmor,
    /// cgroup v2.
    CgroupV2,
    /// systemd.
    Systemd,
    /// ZFS.
    Zfs,
    /// LUKS.
    Luks,
    /// Networking.
    Networking,
    /// VFIO / IOMMU.
    VfioIommu,
}

impl OsResponsibility {
    /// All 10 responsibilities.
    pub const ALL: [OsResponsibility; 10] = [
        OsResponsibility::Kernel,
        OsResponsibility::Firmware,
        OsResponsibility::NvidiaDrivers,
        OsResponsibility::AppArmor,
        OsResponsibility::CgroupV2,
        OsResponsibility::Systemd,
        OsResponsibility::Zfs,
        OsResponsibility::Luks,
        OsResponsibility::Networking,
        OsResponsibility::VfioIommu,
    ];

    /// Whether this responsibility is "hardware reality" — the imperative,
    /// adaptation-driven part (drivers / firmware / VFIO) vs the declarative,
    /// continuity-protecting part (the rest), per the E0459 principle.
    #[must_use]
    pub fn is_hardware_reality(self) -> bool {
        matches!(
            self,
            OsResponsibility::Firmware
                | OsResponsibility::NvidiaDrivers
                | OsResponsibility::VfioIommu
        )
    }
}

/// The 5 base-OS config modes (M00800).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum OsConfigMode {
    /// Stable — pinned, reproducible.
    Stable,
    /// AI-driver-latest — newest NVIDIA stack.
    AiDriverLatest,
    /// Secure — hardened.
    Secure,
    /// Developer — looser, for building.
    Developer,
    /// Offline — no network.
    Offline,
}

impl OsConfigMode {
    /// All 5 config modes.
    pub const ALL: [OsConfigMode; 5] = [
        OsConfigMode::Stable,
        OsConfigMode::AiDriverLatest,
        OsConfigMode::Secure,
        OsConfigMode::Developer,
        OsConfigMode::Offline,
    ];

    /// Whether the host has network in this mode. Only `Offline` cuts it.
    #[must_use]
    pub fn network_enabled(self) -> bool {
        self != OsConfigMode::Offline
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ten_responsibilities_five_modes() {
        assert_eq!(OsResponsibility::ALL.len(), 10);
        assert_eq!(OsConfigMode::ALL.len(), 5);
    }

    #[test]
    fn hardware_reality_responsibilities_are_the_imperative_three() {
        let hw = OsResponsibility::ALL
            .iter()
            .filter(|r| r.is_hardware_reality())
            .count();
        assert_eq!(hw, 3); // firmware / nvidia-drivers / vfio-iommu
        assert!(OsResponsibility::NvidiaDrivers.is_hardware_reality());
        assert!(!OsResponsibility::Zfs.is_hardware_reality());
    }

    #[test]
    fn only_offline_cuts_the_network() {
        assert!(!OsConfigMode::Offline.network_enabled());
        for m in OsConfigMode::ALL
            .into_iter()
            .filter(|m| *m != OsConfigMode::Offline)
        {
            assert!(m.network_enabled(), "{m:?}");
        }
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&OsConfigMode::AiDriverLatest).unwrap(),
            "\"ai-driver-latest\""
        );
        assert_eq!(
            serde_json::to_string(&OsResponsibility::VfioIommu).unwrap(),
            "\"vfio-iommu\""
        );
    }
}
