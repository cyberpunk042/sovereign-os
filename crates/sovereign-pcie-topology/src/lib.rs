//! `sovereign-pcie-topology` — M003: ProArt X870E-Creator PCIe discipline.
//!
//! The board exposes dual PCIe 5.0 x8/x8 to the CPU plus M.2 slots, but some
//! slots **share lanes**: populating `PCIEX16_2` and `M.2_2` together starves
//! one of them (E0027, the "lane-sharing trap"). This crate fixes the slot map,
//! the recommended layout (E0028), and a validator that catches a lane-sharing
//! conflict before it silently halves a GPU's bandwidth.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// A physical slot on the ProArt X870E-Creator (M00031).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PcieSlot {
    /// PCIEX16_1 — primary x16 (CPU, Gen 5).
    X16_1,
    /// PCIEX16_2 — secondary (CPU, Gen 5) — shares lanes with M.2_2.
    X16_2,
    /// M.2_1 — CPU Gen 5 x4.
    M2_1,
    /// M.2_2 — shares lanes with PCIEX16_2.
    M2_2,
    /// M.2_3 — chipset.
    M2_3,
    /// M.2_4 — chipset.
    M2_4,
}

/// A slot's electrical spec.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct SlotSpec {
    /// The slot.
    pub slot: PcieSlot,
    /// Maximum electrical lane width when not contended.
    pub max_lanes: u8,
    /// PCIe generation.
    pub pcie_gen: u8,
    /// If populating this slot contends with another, which one (E0027).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub shares_with: Option<PcieSlot>,
}

/// The 6-slot map (M00031). `PCIEX16_2` and `M.2_2` are mutually lane-sharing.
#[must_use]
pub fn slot_map() -> [SlotSpec; 6] {
    [
        SlotSpec { slot: PcieSlot::X16_1, max_lanes: 16, pcie_gen: 5, shares_with: None },
        SlotSpec { slot: PcieSlot::X16_2, max_lanes: 8, pcie_gen: 5, shares_with: Some(PcieSlot::M2_2) },
        SlotSpec { slot: PcieSlot::M2_1, max_lanes: 4, pcie_gen: 5, shares_with: None },
        SlotSpec { slot: PcieSlot::M2_2, max_lanes: 4, pcie_gen: 5, shares_with: Some(PcieSlot::X16_2) },
        SlotSpec { slot: PcieSlot::M2_3, max_lanes: 4, pcie_gen: 4, shares_with: None },
        SlotSpec { slot: PcieSlot::M2_4, max_lanes: 4, pcie_gen: 4, shares_with: None },
    ]
}

/// One placement: a device in a slot.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Placement {
    /// The slot used.
    pub slot: PcieSlot,
    /// What's plugged in (e.g. `"blackwell-oracle"`, `"nvme-zfs-0"`).
    pub device: String,
}

/// The recommended layout (E0028): Blackwell x8 + 3090 x8 + M.2_1 x4 + chipset
/// NVMe — deliberately leaving `M.2_2` empty so the secondary GPU keeps its x8.
#[must_use]
pub fn recommended_layout() -> Vec<Placement> {
    vec![
        Placement { slot: PcieSlot::X16_1, device: "blackwell-oracle".into() },
        Placement { slot: PcieSlot::X16_2, device: "rocm-3090".into() },
        Placement { slot: PcieSlot::M2_1, device: "nvme-zfs-0".into() },
        Placement { slot: PcieSlot::M2_3, device: "nvme-chipset".into() },
    ]
}

/// Why a population is invalid.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PcieError {
    /// Two mutually lane-sharing slots are both populated (E0027).
    LaneSharingConflict(PcieSlot, PcieSlot),
    /// The same slot was populated twice.
    DuplicateSlot(PcieSlot),
}

impl std::fmt::Display for PcieError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PcieError::LaneSharingConflict(a, b) => {
                write!(f, "{a:?} and {b:?} share lanes; populating both starves one (E0027)")
            }
            PcieError::DuplicateSlot(s) => write!(f, "slot {s:?} populated more than once"),
        }
    }
}

impl std::error::Error for PcieError {}

/// Validate a set of placements against the lane-sharing rules.
pub fn validate(placements: &[Placement]) -> Result<(), PcieError> {
    use std::collections::HashSet;
    let map = slot_map();
    let mut seen: HashSet<PcieSlot> = HashSet::new();
    for p in placements {
        if !seen.insert(p.slot) {
            return Err(PcieError::DuplicateSlot(p.slot));
        }
    }
    for p in placements {
        if let Some(spec) = map.iter().find(|s| s.slot == p.slot)
            && let Some(other) = spec.shares_with
            && seen.contains(&other)
        {
            return Err(PcieError::LaneSharingConflict(p.slot, other));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn place(slot: PcieSlot, device: &str) -> Placement {
        Placement { slot, device: device.into() }
    }

    #[test]
    fn slot_map_marks_the_lane_sharing_pair() {
        let map = slot_map();
        let x16_2 = map.iter().find(|s| s.slot == PcieSlot::X16_2).unwrap();
        let m2_2 = map.iter().find(|s| s.slot == PcieSlot::M2_2).unwrap();
        assert_eq!(x16_2.shares_with, Some(PcieSlot::M2_2));
        assert_eq!(m2_2.shares_with, Some(PcieSlot::X16_2));
    }

    #[test]
    fn recommended_layout_is_conflict_free() {
        // It deliberately leaves M.2_2 empty so the secondary GPU keeps x8.
        validate(&recommended_layout()).unwrap();
        assert!(
            !recommended_layout().iter().any(|p| p.slot == PcieSlot::M2_2),
            "M.2_2 left empty to protect PCIEX16_2"
        );
    }

    #[test]
    fn lane_sharing_trap_is_detected() {
        let bad = vec![
            place(PcieSlot::X16_2, "rocm-3090"),
            place(PcieSlot::M2_2, "nvme-extra"), // the trap
        ];
        // X16_2 is iterated first, so it's the one whose share-conflict trips.
        assert_eq!(
            validate(&bad),
            Err(PcieError::LaneSharingConflict(PcieSlot::X16_2, PcieSlot::M2_2))
        );
    }

    #[test]
    fn either_slot_alone_is_fine() {
        validate(&[place(PcieSlot::X16_2, "gpu")]).unwrap();
        validate(&[place(PcieSlot::M2_2, "nvme")]).unwrap();
    }

    #[test]
    fn duplicate_slot_is_rejected() {
        let dup = vec![place(PcieSlot::M2_1, "a"), place(PcieSlot::M2_1, "b")];
        assert_eq!(validate(&dup), Err(PcieError::DuplicateSlot(PcieSlot::M2_1)));
    }

    #[test]
    fn slot_serializes_kebab() {
        assert_eq!(serde_json::to_string(&PcieSlot::X16_1).unwrap(), "\"x16-1\"");
        assert_eq!(serde_json::to_string(&PcieSlot::M2_2).unwrap(), "\"m2-2\"");
    }
}
