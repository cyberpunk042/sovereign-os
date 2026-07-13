//! `sovereign-pcie-topology` — M003: ProArt X870E-Creator PCIe discipline.
//!
//! The board exposes dual PCIe 5.0 x8/x8 to the CPU plus M.2 slots, but some
//! slots **share lanes**: populating two lane-sharing slots together starves
//! one of them (E0027, the "lane-sharing trap"). This crate fixes the slot map,
//! the recommended layout (E0028), and a validator that catches a lane-sharing
//! conflict before it silently halves a GPU's bandwidth.
//!
//! # Source agreement — this map matches the applied profile; the board-advisor diverges
//!
//! The lane-sharing pair `PCIEX16_2 ↔ M.2_2` here is a **physical board fact**
//! (electrical, independent of what is plugged in) and remains correct. Under
//! SDD-993 (operator hardware change 2026-07-13) the SAIN-01 runs **two internal
//! cards** — RTX PRO 6000 (`PCIEX16_1`) + RTX 5090 (`PCIEX16_2`) at **x8/x8** —
//! so `M.2_2` (which shares lanes with `PCIEX16_2`, the 5090's slot) **MUST stay
//! empty** or the 5090 drops to x4. The RTX 4090 moved OFF an internal slot onto
//! an **OcuLink eGPU** fed by an OcuLink-to-M.2 adapter in a **chipset M.2 slot**
//! (`M.2_3`/`M.2_4`), NOT `M.2_2`. `profiles/sain-01.yaml`
//! `hardware.motherboard.pcie_constraints` declares the `m2_2_empty` blocker,
//! pinned by `tests/schema/test_profile_schema_conformance.py` and
//! `tests/lint/test_sain01_profile_verbatim.py`.
//!
//! The one DIVERGENT source is `scripts/hardware/board-advisor-x870e-creator.py`,
//! which models three PCIe slots (PCIE_1/2/3) with `PCIE_3 ↔ M.2_3` under
//! x4/x4/x4/x4 bifurcation. Since the *applied, tested profile* — not an
//! advisory script — is this project's authority, this crate's `PCIEX16_2 ↔
//! M.2_2` model is correct; the board-advisor is the one to reconcile (its slot
//! identities should be checked against the board manual + brought in line with
//! the profile). (Corrects an earlier note here that wrongly treated the
//! board-advisor as authoritative.)

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
        SlotSpec {
            slot: PcieSlot::X16_1,
            max_lanes: 16,
            pcie_gen: 5,
            shares_with: None,
        },
        SlotSpec {
            slot: PcieSlot::X16_2,
            max_lanes: 8,
            pcie_gen: 5,
            shares_with: Some(PcieSlot::M2_2),
        },
        SlotSpec {
            slot: PcieSlot::M2_1,
            max_lanes: 4,
            pcie_gen: 5,
            shares_with: None,
        },
        SlotSpec {
            slot: PcieSlot::M2_2,
            max_lanes: 4,
            pcie_gen: 5,
            shares_with: Some(PcieSlot::X16_2),
        },
        SlotSpec {
            slot: PcieSlot::M2_3,
            max_lanes: 4,
            pcie_gen: 4,
            shares_with: None,
        },
        SlotSpec {
            slot: PcieSlot::M2_4,
            max_lanes: 4,
            pcie_gen: 4,
            shares_with: None,
        },
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

/// The recommended layout (E0028, SDD-993): TWO internal cards — RTX PRO 6000
/// (`PCIEX16_1`) + RTX 5090 (`PCIEX16_2`) at x8/x8 — with `M.2_2` LEFT EMPTY
/// (it shares lanes with `PCIEX16_2`, so populating it would drop the 5090 to
/// x4). NVMe on `M.2_1` + `M.2_3`; the OcuLink 4090 eGPU adapter on the chipset
/// `M.2_4`. Conflict-free: the only lane-sharing pair (`PCIEX16_2` ↔ `M.2_2`)
/// never has both members populated.
#[must_use]
pub fn recommended_layout() -> Vec<Placement> {
    vec![
        Placement {
            slot: PcieSlot::X16_1,
            device: "rtx-pro-6000-primary".into(),
        },
        Placement {
            slot: PcieSlot::X16_2,
            device: "rtx-5090-secondary".into(),
        },
        Placement {
            slot: PcieSlot::M2_1,
            device: "nvme-zfs-0".into(),
        },
        Placement {
            slot: PcieSlot::M2_3,
            device: "nvme-zfs-1".into(),
        },
        Placement {
            slot: PcieSlot::M2_4,
            device: "oculink-4090-egpu".into(),
        },
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
                write!(
                    f,
                    "{a:?} and {b:?} share lanes; populating both starves one (E0027)"
                )
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
        Placement {
            slot,
            device: device.into(),
        }
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
        // SDD-993: two internal cards (PRO 6000 in X16_1 + RTX 5090 in X16_2) at
        // x8/x8; M.2_2 MUST stay empty (it shares lanes with X16_2/the 5090).
        // Conflict-free because the lane-sharing pair never both-populated.
        validate(&recommended_layout()).unwrap();
        let layout = recommended_layout();
        assert!(
            layout.iter().any(|p| p.slot == PcieSlot::X16_2),
            "PCIEX16_2 carries the RTX 5090 secondary (x8)"
        );
        assert!(
            !layout.iter().any(|p| p.slot == PcieSlot::M2_2),
            "M.2_2 must stay empty (shares lanes with PCIEX16_2 / the 5090)"
        );
    }

    #[test]
    fn lane_sharing_trap_is_detected() {
        let bad = vec![
            place(PcieSlot::X16_2, "rocm-4090"),
            place(PcieSlot::M2_2, "nvme-extra"), // the trap
        ];
        // X16_2 is iterated first, so it's the one whose share-conflict trips.
        assert_eq!(
            validate(&bad),
            Err(PcieError::LaneSharingConflict(
                PcieSlot::X16_2,
                PcieSlot::M2_2
            ))
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
        assert_eq!(
            validate(&dup),
            Err(PcieError::DuplicateSlot(PcieSlot::M2_1))
        );
    }

    #[test]
    fn slot_serializes_kebab() {
        assert_eq!(
            serde_json::to_string(&PcieSlot::X16_1).unwrap(),
            "\"x16-1\""
        );
        assert_eq!(serde_json::to_string(&PcieSlot::M2_2).unwrap(), "\"m2-2\"");
    }
}
