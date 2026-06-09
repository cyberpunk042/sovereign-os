//! `sovereign-network-zerotrust` — master spec §8 asymmetric Zero-Trust NICs.
//!
//! The workstation has two NICs with deliberately *asymmetric* trust:
//!
//! - **mgmt** — Intel i226-v 2.5GbE, VLAN 100 (Management/Telemetry),
//!   `10.0.100.50/24`, **carries the default route** (the only WAN path).
//! - **data** — Marvell AQC113C 10GbE, VLAN 200 (Model Ingestion/Storage),
//!   MTU 9000, `10.0.200.50/24`, and **MUST NOT carry the default route** —
//!   the high-bandwidth data plane has no outbound WAN access by design (master
//!   spec §8 ASCII topology). A default route on the data NIC is a Zero-Trust
//!   egress breach: it gives the bulk model/storage plane a path off-network.
//!
//! Source of truth (verified, not catalogue): `profiles/sain-01.yaml`
//! `hardware.network` (master spec §8.1 verbatim), pinned by
//! `tests/lint/test_network_vlan_verbatim.py` (R401). This crate encodes that
//! canonical layout and [`validate`]s an observed/proposed NIC set against the
//! invariant — flagging the data-plane default route as `Critical`.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A NIC's trust role (master spec §8).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum NicRole {
    /// Management / telemetry plane — carries the default route.
    Mgmt,
    /// Model-ingestion / storage data plane — no WAN egress.
    Data,
}

/// The security-relevant facts about one NIC.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Nic {
    /// Trust role.
    pub role: NicRole,
    /// VLAN id.
    pub vlan: u16,
    /// Link speed in deci-gigabit (25 = 2.5 GbE, 100 = 10 GbE) — integer so the
    /// type stays `Eq`/`Hash` while still representing 2.5.
    pub speed_decigbps: u16,
    /// Whether this NIC carries the default route (the WAN path).
    pub default_gateway: bool,
    /// MTU, if pinned (data plane uses jumbo frames, 9000).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mtu: Option<u32>,
}

/// The canonical §8.1 NIC layout from `profiles/sain-01.yaml`.
#[must_use]
pub fn canonical_nics() -> [Nic; 2] {
    [
        // mgmt — Intel 2.5GbE, VLAN 100, default route.
        Nic {
            role: NicRole::Mgmt,
            vlan: 100,
            speed_decigbps: 25,
            default_gateway: true,
            mtu: None,
        },
        // data — Marvell 10GbE, VLAN 200, jumbo, NO default route.
        Nic {
            role: NicRole::Data,
            vlan: 200,
            speed_decigbps: 100,
            default_gateway: false,
            mtu: Some(9000),
        },
    ]
}

/// A Zero-Trust segregation violation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ZeroTrustViolation {
    /// A `data`-role NIC carries the default route — the bulk data plane has a
    /// WAN egress path. The load-bearing breach (master spec §8: Marvell MUST
    /// NOT carry the default route).
    DataNicHasDefaultRoute,
    /// No NIC carries the default route — the station has no WAN path at all.
    NoDefaultRoute,
    /// More than one NIC carries the default route — ambiguous egress, and at
    /// least one is not the single intended mgmt path.
    MultipleDefaultRoutes,
}

impl ZeroTrustViolation {
    /// Whether this violation is security-critical (a real egress breach) vs a
    /// connectivity/config error.
    #[must_use]
    pub const fn is_critical(self) -> bool {
        matches!(self, ZeroTrustViolation::DataNicHasDefaultRoute)
    }
}

/// Validate a NIC set against the §8 Zero-Trust invariant: exactly one NIC
/// carries the default route, and it must be the `mgmt` NIC. Returns every
/// violation found (empty = compliant). The data-plane default route is always
/// reported even when other route problems coexist, because it is the
/// security-critical one.
#[must_use]
pub fn validate(nics: &[Nic]) -> Vec<ZeroTrustViolation> {
    let mut out = Vec::new();
    let gw_count = nics.iter().filter(|n| n.default_gateway).count();
    let data_has_gw = nics
        .iter()
        .any(|n| n.role == NicRole::Data && n.default_gateway);

    if data_has_gw {
        out.push(ZeroTrustViolation::DataNicHasDefaultRoute);
    }
    if gw_count == 0 {
        out.push(ZeroTrustViolation::NoDefaultRoute);
    } else if gw_count > 1 {
        out.push(ZeroTrustViolation::MultipleDefaultRoutes);
    }
    out
}

/// Whether a NIC set is Zero-Trust compliant (no violations).
#[must_use]
pub fn is_compliant(nics: &[Nic]) -> bool {
    validate(nics).is_empty()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_layout_is_compliant() {
        assert!(is_compliant(&canonical_nics()));
    }

    #[test]
    fn canon_matches_profile_section_8_1() {
        let nics = canonical_nics();
        let mgmt = nics.iter().find(|n| n.role == NicRole::Mgmt).unwrap();
        assert_eq!(mgmt.vlan, 100);
        assert_eq!(mgmt.speed_decigbps, 25); // 2.5 GbE
        assert!(mgmt.default_gateway);

        let data = nics.iter().find(|n| n.role == NicRole::Data).unwrap();
        assert_eq!(data.vlan, 200);
        assert_eq!(data.speed_decigbps, 100); // 10 GbE
        assert!(
            !data.default_gateway,
            "data NIC MUST NOT carry the default route"
        );
        assert_eq!(data.mtu, Some(9000));
    }

    #[test]
    fn data_nic_default_route_is_a_critical_breach() {
        let nics = vec![
            Nic {
                role: NicRole::Mgmt,
                vlan: 100,
                speed_decigbps: 25,
                default_gateway: false,
                mtu: None,
            },
            // The breach: data plane carries the default route.
            Nic {
                role: NicRole::Data,
                vlan: 200,
                speed_decigbps: 100,
                default_gateway: true,
                mtu: Some(9000),
            },
        ];
        let v = validate(&nics);
        assert!(v.contains(&ZeroTrustViolation::DataNicHasDefaultRoute));
        assert!(ZeroTrustViolation::DataNicHasDefaultRoute.is_critical());
    }

    #[test]
    fn no_default_route_is_flagged_but_not_critical() {
        let nics = vec![
            Nic {
                role: NicRole::Mgmt,
                vlan: 100,
                speed_decigbps: 25,
                default_gateway: false,
                mtu: None,
            },
            Nic {
                role: NicRole::Data,
                vlan: 200,
                speed_decigbps: 100,
                default_gateway: false,
                mtu: Some(9000),
            },
        ];
        let v = validate(&nics);
        assert_eq!(v, vec![ZeroTrustViolation::NoDefaultRoute]);
        assert!(!ZeroTrustViolation::NoDefaultRoute.is_critical());
    }

    #[test]
    fn both_carrying_default_route_reports_breach_and_ambiguity() {
        let nics = vec![
            Nic {
                role: NicRole::Mgmt,
                vlan: 100,
                speed_decigbps: 25,
                default_gateway: true,
                mtu: None,
            },
            Nic {
                role: NicRole::Data,
                vlan: 200,
                speed_decigbps: 100,
                default_gateway: true,
                mtu: Some(9000),
            },
        ];
        let v = validate(&nics);
        assert!(
            v.contains(&ZeroTrustViolation::DataNicHasDefaultRoute),
            "data breach"
        );
        assert!(
            v.contains(&ZeroTrustViolation::MultipleDefaultRoutes),
            "ambiguous egress"
        );
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(serde_json::to_string(&NicRole::Data).unwrap(), "\"data\"");
        assert_eq!(
            serde_json::to_string(&ZeroTrustViolation::DataNicHasDefaultRoute).unwrap(),
            "\"data-nic-has-default-route\""
        );
    }
}
