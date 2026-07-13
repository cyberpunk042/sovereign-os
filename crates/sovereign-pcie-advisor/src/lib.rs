//! `sovereign-pcie-advisor` — the runnable consumer of `sovereign-pcie-topology`.
//!
//! The ProArt X870E-Creator shares PCIe lanes between `PCIEX16_2` and `M.2_2`:
//! populating both silently starves one, halving a GPU's bandwidth (E0027, the
//! "lane-sharing trap"). `sovereign-pcie-topology` fixes the slot map, the
//! recommended layout (E0028), and a validator — but nothing ran it. This crate is
//! that runnable end: it renders the recommended layout (and *why*) and validates a
//! proposed one, so the trap is caught before hardware is populated, not after a
//! benchmark comes back mysteriously halved.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use sovereign_pcie_topology::{PcieError, Placement, recommended_layout, slot_map, validate};

/// Re-export: validate a proposed population against the lane-sharing rules.
///
/// # Errors
/// [`PcieError::LaneSharingConflict`] if two lane-sharing slots are both populated,
/// or [`PcieError::DuplicateSlot`] if a slot is populated twice.
pub fn check(placements: &[Placement]) -> Result<(), PcieError> {
    validate(placements)
}

/// A human-readable advisory: the slot map (marking lane-sharing pairs), the
/// recommended layout, and the result of validating it (it must pass).
#[must_use]
pub fn recommended_advisory() -> String {
    let mut s = String::from("ProArt X870E-Creator PCIe layout advisory (E0027/E0028)\n\n");
    s.push_str("Slots (lane-sharing pairs starve each other if both populated):\n");
    for spec in slot_map() {
        match spec.shares_with {
            Some(other) => {
                s.push_str(&format!("  {:?} — shares lanes with {other:?}\n", spec.slot))
            }
            None => s.push_str(&format!("  {:?}\n", spec.slot)),
        }
    }
    let layout = recommended_layout();
    s.push_str("\nRecommended layout (E0028 — leaves M.2_2 empty to keep x8/x8):\n");
    for p in &layout {
        s.push_str(&format!("  {:?} ← {}\n", p.slot, p.device));
    }
    match validate(&layout) {
        Ok(()) => s.push_str("\nvalidates: OK (no lane-sharing conflict)\n"),
        // The recommended layout is validator-clean by construction; surface any
        // regression loudly rather than claiming OK.
        Err(e) => s.push_str(&format!("\nvalidates: FAILED — {e}\n")),
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_pcie_topology::PcieSlot;

    #[test]
    fn advisory_shows_the_recommended_layout_and_validates() {
        let a = recommended_advisory();
        assert!(a.contains("blackwell-oracle") && a.contains("rocm-4090"), "layout: {a}");
        assert!(a.contains("shares lanes with"), "must flag a lane-sharing pair: {a}");
        assert!(a.contains("validates: OK"), "recommended layout must validate: {a}");
    }

    #[test]
    fn check_catches_the_lane_sharing_trap() {
        // populating both lane-sharing slots (X16_2 + M.2_2) is the E0027 trap
        let trap = vec![
            Placement { slot: PcieSlot::X16_2, device: "rocm-4090".into() },
            Placement { slot: PcieSlot::M2_2, device: "nvme-extra".into() },
        ];
        assert!(
            matches!(check(&trap), Err(PcieError::LaneSharingConflict(..))),
            "the lane-sharing trap must be rejected"
        );
        // the recommended layout is accepted
        assert!(check(&recommended_layout()).is_ok());
    }
}
