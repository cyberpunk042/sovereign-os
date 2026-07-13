//! `sovereign-cgroup-systemd` CLI — the runnable end of M045 / E0428.
//!
//! The library models the 8 OS primitives that form the peace-machine substrate
//! (cgroup v2 / systemd / PSI / eBPF / AppArmor / namespaces / ZFS /
//! LUKS-TPM-FIDO2), with a `PrimitiveSnapshot` + `validate()` contract. But
//! nothing *ran* it, so "is this snapshot canonical, and how much of the
//! substrate is live?" was unanswerable at the command line. This binary is that
//! runnable end.
//!
//! Modes:
//!   * default (no args) — print the 8 canonical OS primitives (position +
//!     kebab label + domain) as a human-readable reference: the substrate itself.
//!   * `--check FILE` — load a `PrimitiveSnapshot` from JSON, run `validate()`
//!     (schema, doctrine, exactly-8, no duplicates, canonical domains), report OK
//!     or the `PrimitiveError`, print how many primitives are available, and exit
//!     non-zero if validation fails.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_cgroup_systemd::{OsPrimitive, PrimitiveError, PrimitiveSnapshot};

/// The 8 OS primitives in canonical position order (1..8) — the same order and
/// membership `PrimitiveSnapshot::empty_canonical()` produces (kept honest by the
/// `all_primitives_match_canonical_order` test).
const ALL_PRIMITIVES: [OsPrimitive; 8] = [
    OsPrimitive::Cgroupv2,
    OsPrimitive::Systemd,
    OsPrimitive::Psi,
    OsPrimitive::Ebpf,
    OsPrimitive::AppArmor,
    OsPrimitive::Namespaces,
    OsPrimitive::Zfs,
    OsPrimitive::LuksTpmFido2,
];

/// The stable kebab-case label for a primitive — identical to how [`OsPrimitive`]
/// serializes to JSON (kept honest by the `primitive_label_matches_serde` test).
fn primitive_label(primitive: OsPrimitive) -> &'static str {
    match primitive {
        OsPrimitive::Cgroupv2 => "cgroupv2",
        OsPrimitive::Systemd => "systemd",
        OsPrimitive::Psi => "psi",
        OsPrimitive::Ebpf => "ebpf",
        OsPrimitive::AppArmor => "app-armor",
        OsPrimitive::Namespaces => "namespaces",
        OsPrimitive::Zfs => "zfs",
        OsPrimitive::LuksTpmFido2 => "luks-tpm-fido2",
    }
}

/// The human-readable reference: the 8 OS primitives, each with its canonical
/// position (1..8), kebab label, and domain.
fn reference_text() -> String {
    let mut s = String::from(
        "The 8 M045 OS primitives (E0428 / M00747-M00750) — the peace-machine substrate.\n\n",
    );
    for primitive in ALL_PRIMITIVES {
        s.push_str(&format!(
            "  {}. {:<16} {}\n",
            primitive.position(),
            primitive_label(primitive),
            primitive.domain(),
        ));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-cgroup-systemd — M045 cgroup v2 + systemd resource governance\n\n\
     The 8 OS primitives (E0428 / M00747-M00750) form the peace-machine substrate:\n\
     cgroup v2, systemd, PSI, eBPF, AppArmor, namespaces, ZFS, LUKS-TPM-FIDO2.\n\n\
     USAGE:\n\
     \x20   sovereign-cgroup-systemd                 print the 8 OS primitives (reference)\n\
     \x20   sovereign-cgroup-systemd --check FILE     validate a PrimitiveSnapshot from JSON\n\
     \x20   sovereign-cgroup-systemd --help           print this help and exit\n\n\
     --check FILE loads a PrimitiveSnapshot object, runs validate() (schema,\n\
     doctrine, exactly 8 primitives present, no duplicates, canonical domains),\n\
     reports OK or the PrimitiveError plus how many primitives are available, and\n\
     exits non-zero if validation fails.\n"
        .to_string()
}

/// The outcome of checking one snapshot.
struct CheckOutcome {
    /// The completeness/canonicity result from `validate()`.
    result: Result<(), PrimitiveError>,
    /// How many primitives report `Available`.
    available: usize,
    /// Total primitives declared in the snapshot.
    total: usize,
}

/// Parse a `PrimitiveSnapshot` from JSON and validate it, capturing the
/// available/total counts alongside the validation result.
fn check_json(json: &str) -> Result<CheckOutcome, serde_json::Error> {
    let snapshot: PrimitiveSnapshot = serde_json::from_str(json)?;
    Ok(CheckOutcome {
        result: snapshot.validate(),
        available: snapshot.available_count(),
        total: snapshot.primitives.len(),
    })
}

/// `--check FILE`: read the file, parse+validate the snapshot, print a report,
/// and return a process exit code (non-zero on read/parse error or invalid
/// snapshot).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let outcome = match check_json(&json) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("error: {path} is not a PrimitiveSnapshot: {e}");
            return ExitCode::FAILURE;
        }
    };

    let code = match &outcome.result {
        Ok(()) => {
            println!("OK   snapshot valid — 8 canonical OS primitives, no drift");
            ExitCode::SUCCESS
        }
        Err(err) => {
            println!("FAIL {err}");
            ExitCode::FAILURE
        }
    };
    println!(
        "available: {}/{} primitives active",
        outcome.available, outcome.total
    );
    code
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
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
    use sovereign_cgroup_systemd::PrimitiveState;

    #[test]
    fn all_primitives_match_canonical_order() {
        // The CLI's ALL_PRIMITIVES must not drift from the library's canonical
        // snapshot: same members, same order, positions 1..8.
        let canonical: Vec<OsPrimitive> = PrimitiveSnapshot::empty_canonical()
            .primitives
            .iter()
            .map(|r| r.primitive)
            .collect();
        assert_eq!(ALL_PRIMITIVES.to_vec(), canonical);
        for (i, p) in ALL_PRIMITIVES.into_iter().enumerate() {
            assert_eq!(p.position() as usize, i + 1);
        }
    }

    #[test]
    fn primitive_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for p in ALL_PRIMITIVES {
            let json = serde_json::to_string(&p).unwrap();
            assert_eq!(json, format!("\"{}\"", primitive_label(p)));
        }
    }

    #[test]
    fn reference_lists_all_eight_primitives() {
        let t = reference_text();
        for p in ALL_PRIMITIVES {
            assert!(
                t.contains(primitive_label(p)),
                "reference missing {p:?}:\n{t}"
            );
        }
        for domain in ["governance", "observability", "isolation", "identity"] {
            assert!(
                t.contains(domain),
                "reference missing domain {domain}:\n{t}"
            );
        }
        // Exactly eight numbered "  N. " entries — one per primitive, no more.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(numbered, ALL_PRIMITIVES.len(), "expected 8 primitive lines");
    }

    #[test]
    fn check_accepts_valid_canonical_snapshot() {
        let mut s = PrimitiveSnapshot::empty_canonical();
        s.primitives[0].state = PrimitiveState::Available;
        s.primitives[3].state = PrimitiveState::Available;
        let json = serde_json::to_string(&s).unwrap();
        let outcome = check_json(&json).unwrap();
        assert!(outcome.result.is_ok());
        assert_eq!(outcome.available, 2);
        assert_eq!(outcome.total, 8);
    }

    #[test]
    fn check_rejects_broken_snapshot() {
        // Drop a primitive: count falls to 7, validate() must reject it.
        let mut s = PrimitiveSnapshot::empty_canonical();
        s.primitives.pop();
        let json = serde_json::to_string(&s).unwrap();
        let outcome = check_json(&json).unwrap();
        assert!(matches!(
            outcome.result,
            Err(PrimitiveError::CountInvalid(7))
        ));
        assert_eq!(outcome.total, 7);
    }

    #[test]
    fn check_rejects_domain_tamper() {
        let mut s = PrimitiveSnapshot::empty_canonical();
        s.primitives[0].domain = "wrong".into();
        let json = serde_json::to_string(&s).unwrap();
        let outcome = check_json(&json).unwrap();
        assert!(matches!(
            outcome.result,
            Err(PrimitiveError::DomainMismatch { .. })
        ));
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }
}
