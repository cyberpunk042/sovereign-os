//! `sovereign-network-zerotrust` CLI — the runnable end of master spec §8.
//!
//! The library encodes the asymmetric Zero-Trust NIC layout (mgmt Intel 2.5GbE
//! VLAN 100 carries the default route; data Marvell 10GbE VLAN 200 MUST NOT) and
//! a `validate()` that flags a default route on the data plane as a critical
//! egress breach. But nothing *ran* it, so "is this observed/proposed NIC set
//! compliant?" was unanswerable at the command line. This binary is that
//! runnable end: it emits the canonical policy and decides allow/deny for a NIC
//! set — real work, no live enforcement or bridge required.
//!
//! Modes:
//!   * default (no args) — print the canonical §8 NIC policy as a human-readable
//!     reference (the two NICs + the Zero-Trust egress invariant).
//!   * `--emit` — print the canonical NIC set as JSON (the policy, machine-readable).
//!   * `--check FILE` — load a `Nic` object or a JSON array of them, run
//!     `validate()`, report every Zero-Trust violation (marking the critical
//!     data-plane egress breach), and exit non-zero if the set is non-compliant.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_network_zerotrust::{
    Nic, NicRole, SCHEMA_VERSION, ZeroTrustViolation, canonical_nics, validate,
};

/// The stable kebab-case label for a NIC role — identical to how [`NicRole`]
/// serializes to JSON (kept honest by the `labels_match_serde` test).
fn role_label(role: NicRole) -> &'static str {
    match role {
        NicRole::Mgmt => "mgmt",
        NicRole::Data => "data",
    }
}

/// The stable kebab-case label for a violation — identical to how
/// [`ZeroTrustViolation`] serializes to JSON (kept honest by `labels_match_serde`).
fn violation_label(v: ZeroTrustViolation) -> &'static str {
    match v {
        ZeroTrustViolation::DataNicHasDefaultRoute => "data-nic-has-default-route",
        ZeroTrustViolation::NoDefaultRoute => "no-default-route",
        ZeroTrustViolation::MultipleDefaultRoutes => "multiple-default-routes",
    }
}

/// A one-line human description of what each violation means.
fn violation_description(v: ZeroTrustViolation) -> &'static str {
    match v {
        ZeroTrustViolation::DataNicHasDefaultRoute => {
            "the data plane carries the default route — a WAN egress path off the bulk \
             model/storage plane (master spec §8: the Marvell data NIC MUST NOT carry it)"
        }
        ZeroTrustViolation::NoDefaultRoute => {
            "no NIC carries the default route — the station has no WAN path at all"
        }
        ZeroTrustViolation::MultipleDefaultRoutes => {
            "more than one NIC carries the default route — ambiguous egress"
        }
    }
}

/// Render a link speed held in deci-gigabit units as GbE (25 -> "2.5 GbE").
fn speed_label(decigbps: u16) -> String {
    format!("{}.{} GbE", decigbps / 10, decigbps % 10)
}

/// A single reference line describing one canonical NIC.
fn nic_line(nic: &Nic) -> String {
    let mtu = match nic.mtu {
        Some(m) => format!("MTU {m}"),
        None => "MTU default".to_string(),
    };
    format!(
        "{:<5} VLAN {:<4} {:<9} default-route={:<5} {}",
        role_label(nic.role),
        nic.vlan,
        speed_label(nic.speed_decigbps),
        nic.default_gateway,
        mtu,
    )
}

/// The human-readable reference: the canonical §8 NIC policy and its invariant.
fn reference_text() -> String {
    let mut s = format!(
        "Master spec §8 asymmetric Zero-Trust NIC layout (schema {SCHEMA_VERSION}).\n\n\
         Canonical NICs (source of truth: profiles/sain-01.yaml hardware.network, R401):\n"
    );
    for nic in &canonical_nics() {
        s.push_str(&format!("  {}\n", nic_line(nic)));
    }
    s.push_str(
        "\nInvariant: exactly one NIC carries the default route, and it MUST be the mgmt\n\
         NIC. A default route on the data NIC is a Zero-Trust egress breach (critical).\n\
         Run `--check FILE` to validate an observed/proposed NIC set against this.\n",
    );
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-network-zerotrust — master spec §8 asymmetric Zero-Trust NICs\n\n\
     The workstation has two NICs with deliberately asymmetric trust: the mgmt NIC\n\
     carries the only default route (the WAN path); the data NIC MUST NOT — the bulk\n\
     model/storage plane has no outbound WAN access by design.\n\n\
     USAGE:\n\
     \x20   sovereign-network-zerotrust                 print the canonical §8 NIC policy (reference)\n\
     \x20   sovereign-network-zerotrust --emit          print the canonical NIC set as JSON\n\
     \x20   sovereign-network-zerotrust --check FILE     validate a NIC set (JSON) against the invariant\n\
     \x20   sovereign-network-zerotrust --help           print this help and exit\n\n\
     --check FILE loads a single Nic object or a JSON array of them, runs validate(),\n\
     reports every Zero-Trust violation (marking the critical data-plane egress\n\
     breach), and exits non-zero if the NIC set is non-compliant (deny).\n"
        .to_string()
}

/// The outcome of checking one NIC set.
struct CheckReport {
    /// How many NICs were in the set.
    nic_count: usize,
    /// Every Zero-Trust violation found (empty = compliant).
    violations: Vec<ZeroTrustViolation>,
}

/// Accept either a single `Nic` object or a JSON array of them.
fn parse_nics(json: &str) -> Result<Vec<Nic>, serde_json::Error> {
    match serde_json::from_str::<Vec<Nic>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single Nic object, surfacing that error.
        Err(_) => serde_json::from_str::<Nic>(json).map(|n| vec![n]),
    }
}

/// Parse one-or-many NICs from JSON and validate the set as a whole.
fn check_json(json: &str) -> Result<CheckReport, serde_json::Error> {
    let nics = parse_nics(json)?;
    Ok(CheckReport {
        nic_count: nics.len(),
        violations: validate(&nics),
    })
}

/// `--check FILE`: read the file, validate the NIC set, print a report, and
/// return a process exit code (non-zero on read/parse error or any violation).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let report = match check_json(&json) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("error: {path} is not a Nic (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };

    let count = report.nic_count;
    if report.violations.is_empty() {
        println!("OK   {count} NIC(s) — ALLOW: Zero-Trust compliant (master spec §8)");
        return ExitCode::SUCCESS;
    }

    for v in &report.violations {
        let sev = if v.is_critical() {
            "CRITICAL"
        } else {
            "warning "
        };
        println!(
            "DENY [{sev}] {} — {}",
            violation_label(*v),
            violation_description(*v)
        );
    }
    println!(
        "FAIL {count} NIC(s) — {} Zero-Trust violation(s)",
        report.violations.len()
    );
    ExitCode::FAILURE
}

/// `--emit`: print the canonical NIC set as pretty JSON (the machine-readable policy).
fn run_emit() -> ExitCode {
    let nics = canonical_nics();
    match serde_json::to_string_pretty(&nics[..]) {
        Ok(j) => {
            println!("{j}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("error: cannot emit canonical policy: {e}");
            ExitCode::FAILURE
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    if args.iter().any(|a| a == "--emit") {
        return run_emit();
    }

    if let Some(i) = args.iter().position(|a| a == "--check") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --check requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_check(path);
    }

    if let Some(unknown) = args.iter().find(|a| a.starts_with('-')) {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    print!("{}", reference_text());
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A NIC with the given role and default-route flag; canonical VLAN/speed/MTU.
    fn nic(role: NicRole, default_gateway: bool) -> Nic {
        match role {
            NicRole::Mgmt => Nic {
                role,
                vlan: 100,
                speed_decigbps: 25,
                default_gateway,
                mtu: None,
            },
            NicRole::Data => Nic {
                role,
                vlan: 200,
                speed_decigbps: 100,
                default_gateway,
                mtu: Some(9000),
            },
        }
    }

    #[test]
    fn reference_mentions_both_roles_and_the_invariant() {
        let t = reference_text();
        assert!(t.contains("mgmt"), "reference missing mgmt NIC:\n{t}");
        assert!(t.contains("data"), "reference missing data NIC:\n{t}");
        assert!(
            t.contains("default route"),
            "reference missing invariant:\n{t}"
        );
        assert!(t.contains(SCHEMA_VERSION), "reference missing schema:\n{t}");
    }

    #[test]
    fn emit_json_roundtrips_and_canonical_is_compliant() {
        // What `--emit` prints must parse back and validate clean (ALLOW).
        let nics = canonical_nics();
        let json = serde_json::to_string(&nics[..]).unwrap();
        let report = check_json(&json).unwrap();
        assert_eq!(report.nic_count, 2);
        assert!(
            report.violations.is_empty(),
            "canonical policy must be Zero-Trust compliant, got {:?}",
            report.violations
        );
    }

    #[test]
    fn check_denies_data_plane_egress_breach_as_critical() {
        let breach = vec![nic(NicRole::Mgmt, false), nic(NicRole::Data, true)];
        let json = serde_json::to_string(&breach).unwrap();
        let report = check_json(&json).unwrap();
        assert!(
            report
                .violations
                .contains(&ZeroTrustViolation::DataNicHasDefaultRoute),
            "data-plane default route must be flagged"
        );
        assert!(
            report.violations.iter().any(|v| v.is_critical()),
            "the data-plane egress breach must be critical"
        );
    }

    #[test]
    fn check_accepts_single_nic_object() {
        // A lone mgmt NIC carrying the default route is compliant (one gw, on mgmt).
        let json = serde_json::to_string(&nic(NicRole::Mgmt, true)).unwrap();
        let report = check_json(&json).unwrap();
        assert_eq!(report.nic_count, 1);
        assert!(report.violations.is_empty());
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }

    #[test]
    fn labels_match_serde() {
        for role in [NicRole::Mgmt, NicRole::Data] {
            let json = serde_json::to_string(&role).unwrap();
            assert_eq!(json, format!("\"{}\"", role_label(role)));
        }
        for v in [
            ZeroTrustViolation::DataNicHasDefaultRoute,
            ZeroTrustViolation::NoDefaultRoute,
            ZeroTrustViolation::MultipleDefaultRoutes,
        ] {
            let json = serde_json::to_string(&v).unwrap();
            assert_eq!(json, format!("\"{}\"", violation_label(v)));
        }
    }

    #[test]
    fn speed_label_formats_decigbps() {
        assert_eq!(speed_label(25), "2.5 GbE");
        assert_eq!(speed_label(100), "10.0 GbE");
    }
}
