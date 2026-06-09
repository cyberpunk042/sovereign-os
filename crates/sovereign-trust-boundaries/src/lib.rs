//! `sovereign-trust-boundaries` — M014: isolation and trust boundaries.
//!
//! The station is partitioned into four trust zones of decreasing privilege,
//! and tools are graded on a four-tier sandbox ladder (A→D) of increasing
//! danger. The load-bearing rule: a tool may only run in a zone whose
//! containment meets or exceeds the tier's requirement, so an untrusted
//! binary (tier D) can never execute on the host control plane (zone 0).

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The four trust zones (E0118 / M00216–M00219), zone 0 most privileged.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TrustZone {
    /// Zone 0 — Host Control Plane (scheduler / policy / replay / ZFS / observability).
    Host,
    /// Zone 1 — Oracle Plane (main inference, trusted-but-not-omnipotent).
    Oracle,
    /// Zone 2 — Scout/Sandbox Plane (draft models, experimental agents, risky code).
    ScoutSandbox,
    /// Zone 3 — Disposable Tool Sandboxes (microVM/container-per-task).
    Disposable,
}

impl TrustZone {
    /// All four zones, most-privileged first.
    pub const ALL: [TrustZone; 4] = [
        TrustZone::Host,
        TrustZone::Oracle,
        TrustZone::ScoutSandbox,
        TrustZone::Disposable,
    ];

    /// Containment rank — higher = stronger isolation / lower privilege.
    /// (Host=0 … Disposable=3.)
    #[must_use]
    pub fn containment(self) -> u8 {
        match self {
            TrustZone::Host => 0,
            TrustZone::Oracle => 1,
            TrustZone::ScoutSandbox => 2,
            TrustZone::Disposable => 3,
        }
    }
}

/// The four-tier tool sandbox ladder (E0122 / M00227–M00230), A→D increasing danger.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ToolTier {
    /// A — deterministic host tools (rg, parsers, formatters, read-only queries).
    A,
    /// B — controlled host tools (tests, builds, package managers, file edits).
    B,
    /// C — VM tools (risky dependency installs, unknown scripts, browser actions).
    C,
    /// D — disposable microVM (untrusted binaries, unknown archives, hostile inputs).
    D,
}

impl ToolTier {
    /// All four tiers, least-dangerous first.
    pub const ALL: [ToolTier; 4] = [ToolTier::A, ToolTier::B, ToolTier::C, ToolTier::D];

    /// Danger rank — higher = more dangerous / stronger sandbox required.
    #[must_use]
    pub fn rank(self) -> u8 {
        match self {
            ToolTier::A => 0,
            ToolTier::B => 1,
            ToolTier::C => 2,
            ToolTier::D => 3,
        }
    }

    /// The *minimum* trust zone this tier may run in. A/B may run on the host
    /// planes; C needs at least the Scout/Sandbox VM; D needs a disposable
    /// per-task sandbox.
    #[must_use]
    pub fn min_zone(self) -> TrustZone {
        match self {
            ToolTier::A => TrustZone::Host,
            ToolTier::B => TrustZone::Oracle,
            ToolTier::C => TrustZone::ScoutSandbox,
            ToolTier::D => TrustZone::Disposable,
        }
    }
}

/// Whether running a `tier` tool in `zone` is permitted: the zone's containment
/// must meet or exceed the tier's minimum. This is the rule that keeps an
/// untrusted binary off the host.
#[must_use]
pub fn is_placement_safe(tier: ToolTier, zone: TrustZone) -> bool {
    zone.containment() >= tier.min_zone().containment()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn four_zones_four_tiers() {
        assert_eq!(TrustZone::ALL.len(), 4);
        assert_eq!(ToolTier::ALL.len(), 4);
    }

    #[test]
    fn containment_and_danger_increase_together() {
        assert!(TrustZone::Disposable.containment() > TrustZone::Host.containment());
        assert!(ToolTier::D.rank() > ToolTier::A.rank());
        // each tier's min zone gets stronger up the ladder.
        assert!(ToolTier::D.min_zone().containment() > ToolTier::C.min_zone().containment());
        assert!(ToolTier::C.min_zone().containment() > ToolTier::B.min_zone().containment());
    }

    #[test]
    fn untrusted_binary_cannot_run_on_host() {
        // Tier D (hostile inputs) on Zone 0 (host control plane) is forbidden.
        assert!(!is_placement_safe(ToolTier::D, TrustZone::Host));
        assert!(!is_placement_safe(ToolTier::D, TrustZone::Oracle));
        assert!(!is_placement_safe(ToolTier::D, TrustZone::ScoutSandbox));
        // Only the disposable sandbox is adequate.
        assert!(is_placement_safe(ToolTier::D, TrustZone::Disposable));
    }

    #[test]
    fn deterministic_host_tools_run_anywhere() {
        // Tier A is safe in every zone (a stronger zone is always allowed).
        for z in TrustZone::ALL {
            assert!(is_placement_safe(ToolTier::A, z), "{z:?}");
        }
    }

    #[test]
    fn vm_tools_need_at_least_the_scout_vm() {
        assert!(!is_placement_safe(ToolTier::C, TrustZone::Host));
        assert!(!is_placement_safe(ToolTier::C, TrustZone::Oracle));
        assert!(is_placement_safe(ToolTier::C, TrustZone::ScoutSandbox));
        assert!(is_placement_safe(ToolTier::C, TrustZone::Disposable));
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&TrustZone::ScoutSandbox).unwrap(),
            "\"scout-sandbox\""
        );
        assert_eq!(serde_json::to_string(&ToolTier::D).unwrap(), "\"d\"");
    }
}
