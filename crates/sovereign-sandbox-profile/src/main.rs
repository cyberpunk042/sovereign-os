//! `sovereign-sandbox-profile` CLI — the runnable end of E0461 / M00804.
//!
//! The library fixes the sandbox-fabric's 8 named profiles, each constraining
//! one of four dimensions (filesystem / network / gpu / isolation), plus the
//! `grants_gpu` property. But nothing *ran* it, so "what are the profiles?" and
//! "is this selection of profiles coherent?" were unanswerable at the command
//! line. This binary is that runnable end — a reference + validator that needs
//! no live sandbox: it works purely off the crate's model.
//!
//! Modes:
//!   * default (no args) — print the 8 canonical profiles grouped by the
//!     dimension each constrains, with the real `grants_gpu` property marked.
//!   * `--check FILE` — load a sandbox config (a JSON array of profile names,
//!     or a single profile name), resolve it per dimension, and validate that
//!     no dimension is constrained by two different profiles; exit non-zero on
//!     a conflict (or on a read/parse error).
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_sandbox_profile::{SandboxDimension, SandboxProfile};

/// The four dimensions, in canonical order.
const DIMENSIONS: [SandboxDimension; 4] = [
    SandboxDimension::Filesystem,
    SandboxDimension::Network,
    SandboxDimension::Gpu,
    SandboxDimension::Isolation,
];

/// The stable kebab/serde label for a profile — identical to how
/// [`SandboxProfile`] serializes to JSON (kept honest by the
/// `profile_label_matches_serde` test). This is exactly the spelling a config
/// file must use to name the profile.
fn profile_label(profile: SandboxProfile) -> &'static str {
    match profile {
        SandboxProfile::ReadOnlyRepo => "read-only-repo",
        SandboxProfile::WriteWorkspace => "write-workspace",
        SandboxProfile::NetworkDenied => "network-denied",
        SandboxProfile::NetworkDocsOnly => "network-docs-only",
        SandboxProfile::GpuScout => "gpu-scout",
        SandboxProfile::NoGpu => "no-gpu",
        SandboxProfile::VmIsolated => "vm-isolated",
        SandboxProfile::Vfio4090 => "vfio4090",
    }
}

/// The stable serde label for a dimension (kept honest by the
/// `dimension_label_matches_serde` test).
fn dimension_label(dimension: SandboxDimension) -> &'static str {
    match dimension {
        SandboxDimension::Filesystem => "filesystem",
        SandboxDimension::Network => "network",
        SandboxDimension::Gpu => "gpu",
        SandboxDimension::Isolation => "isolation",
    }
}

/// A one-line human description of what each profile permits or denies — taken
/// from the library's own doc comments on the [`SandboxProfile`] variants.
fn profile_description(profile: SandboxProfile) -> &'static str {
    match profile {
        SandboxProfile::ReadOnlyRepo => "read-only repo mount",
        SandboxProfile::WriteWorkspace => "writable workspace",
        SandboxProfile::NetworkDenied => "no network",
        SandboxProfile::NetworkDocsOnly => "network limited to documentation",
        SandboxProfile::GpuScout => "4090 scout GPU access",
        SandboxProfile::NoGpu => "no GPU",
        SandboxProfile::VmIsolated => "VM-isolated",
        SandboxProfile::Vfio4090 => "VFIO-passthrough of the 4090",
    }
}

/// The profiles that constrain `dimension`, in `SandboxProfile::ALL` order.
fn profiles_in(dimension: SandboxDimension) -> Vec<SandboxProfile> {
    SandboxProfile::ALL
        .into_iter()
        .filter(|p| p.dimension() == dimension)
        .collect()
}

/// The human-readable reference: the 8 profiles grouped by their dimension,
/// with the real `grants_gpu` property surfaced.
fn reference_text() -> String {
    let mut s = String::from(
        "The sandbox-fabric profiles (E0461 / M00804): 8 profiles, grouped by the\n\
         dimension each constrains. A trailing mark shows which profiles expose a GPU.\n\n",
    );
    for dim in DIMENSIONS {
        s.push_str(dimension_label(dim));
        s.push('\n');
        for p in profiles_in(dim) {
            let gpu = if p.grants_gpu() { "  [grants GPU]" } else { "" };
            s.push_str(&format!(
                "  {:<18} {}{}\n",
                profile_label(p),
                profile_description(p),
                gpu,
            ));
        }
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-sandbox-profile — the sandbox-fabric profiles (E0461 / M00804)\n\n\
     8 profiles, two per dimension: filesystem (read-only-repo / write-workspace),\n\
     network (network-denied / network-docs-only), gpu (gpu-scout / no-gpu),\n\
     isolation (vm-isolated / vfio4090).\n\n\
     USAGE:\n\
     \x20   sovereign-sandbox-profile                print the 8 profiles (reference)\n\
     \x20   sovereign-sandbox-profile --check FILE   validate a sandbox config from JSON\n\
     \x20   sovereign-sandbox-profile --help         print this help and exit\n\n\
     --check FILE loads a sandbox config — a JSON array of profile names (e.g.\n\
     [\"read-only-repo\",\"network-denied\",\"no-gpu\"]) or a single profile name —\n\
     resolves it per dimension, and fails (non-zero exit) if any one dimension is\n\
     constrained by two different profiles (an incoherent selection).\n"
        .to_string()
}

/// Why a sandbox config is incoherent.
#[derive(Debug, PartialEq, Eq)]
enum ConfigError {
    /// Two different profiles constrain the same dimension.
    Conflict {
        /// The over-constrained dimension.
        dimension: SandboxDimension,
        /// The first profile naming that dimension.
        first: SandboxProfile,
        /// The second, conflicting, profile.
        second: SandboxProfile,
    },
}

impl std::fmt::Display for ConfigError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConfigError::Conflict {
                dimension,
                first,
                second,
            } => write!(
                f,
                "the {} dimension is constrained by two profiles: {} and {}",
                dimension_label(*dimension),
                profile_label(*first),
                profile_label(*second),
            ),
        }
    }
}

/// Accept either a JSON array of profile names or a single profile name.
fn parse_config(json: &str) -> Result<Vec<SandboxProfile>, serde_json::Error> {
    match serde_json::from_str::<Vec<SandboxProfile>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single profile name, surfacing that error.
        Err(_) => serde_json::from_str::<SandboxProfile>(json).map(|p| vec![p]),
    }
}

/// Validate a resolved config: at most one *distinct* profile per dimension.
/// Repeating the same profile is idempotent and allowed; selecting two rival
/// profiles for one dimension (e.g. `network-denied` + `network-docs-only`) is
/// the incoherence this rejects.
fn validate_config(profiles: &[SandboxProfile]) -> Result<(), ConfigError> {
    for (i, &p) in profiles.iter().enumerate() {
        for &q in &profiles[i + 1..] {
            if p != q && p.dimension() == q.dimension() {
                return Err(ConfigError::Conflict {
                    dimension: p.dimension(),
                    first: p,
                    second: q,
                });
            }
        }
    }
    Ok(())
}

/// Render the per-dimension resolution of a config as human-readable lines.
fn resolution_text(profiles: &[SandboxProfile]) -> String {
    let mut s = String::new();
    for dim in DIMENSIONS {
        let mut selected: Vec<SandboxProfile> = profiles
            .iter()
            .copied()
            .filter(|p| p.dimension() == dim)
            .collect();
        selected.dedup();
        let label = dimension_label(dim);
        if selected.is_empty() {
            s.push_str(&format!("  {label:<11} (unconstrained — fabric default)\n"));
        } else {
            let names: Vec<&str> = selected.into_iter().map(profile_label).collect();
            s.push_str(&format!("  {:<11} {}\n", label, names.join(" + ")));
        }
    }
    s
}

/// `--check FILE`: read the file, parse + resolve + validate the config, print a
/// report, and return a process exit code (non-zero on read/parse error or a
/// conflicting selection).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let profiles = match parse_config(&json) {
        Ok(p) => p,
        Err(e) => {
            eprintln!(
                "error: {path} is not a sandbox config (array of profile names, or one name): {e}"
            );
            return ExitCode::FAILURE;
        }
    };

    println!("config: {} profile(s) selected", profiles.len());
    print!("{}", resolution_text(&profiles));
    let grants = profiles.iter().any(|p| p.grants_gpu());
    println!("grants GPU: {}", if grants { "yes" } else { "no" });

    match validate_config(&profiles) {
        Ok(()) => {
            println!("OK — coherent: no dimension constrained by two profiles");
            ExitCode::SUCCESS
        }
        Err(err) => {
            println!("FAIL — {err}");
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

    #[test]
    fn profile_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form —
        // config files name profiles by exactly this spelling.
        for p in SandboxProfile::ALL {
            let json = serde_json::to_string(&p).unwrap();
            assert_eq!(json, format!("\"{}\"", profile_label(p)));
        }
    }

    #[test]
    fn dimension_label_matches_serde() {
        for dim in DIMENSIONS {
            let json = serde_json::to_string(&dim).unwrap();
            assert_eq!(json, format!("\"{}\"", dimension_label(dim)));
        }
    }

    #[test]
    fn reference_lists_all_eight_profiles() {
        let t = reference_text();
        for p in SandboxProfile::ALL {
            assert!(
                t.contains(profile_label(p)),
                "reference missing {p:?}:\n{t}"
            );
            assert!(
                t.contains(profile_description(p)),
                "reference missing description for {p:?}:\n{t}"
            );
        }
        for dim in DIMENSIONS {
            assert!(
                t.contains(dimension_label(dim)),
                "reference missing {dim:?}"
            );
        }
        // The `[grants GPU]` mark appears exactly for the two GPU-granting profiles.
        let marks = t.matches("[grants GPU]").count();
        let expected = SandboxProfile::ALL
            .iter()
            .filter(|p| p.grants_gpu())
            .count();
        assert_eq!(marks, expected, "one GPU mark per grants_gpu profile");
        assert_eq!(expected, 2);
    }

    #[test]
    fn parse_accepts_array_and_single() {
        let arr = parse_config("[\"read-only-repo\",\"no-gpu\"]").unwrap();
        assert_eq!(
            arr,
            vec![SandboxProfile::ReadOnlyRepo, SandboxProfile::NoGpu]
        );
        let one = parse_config("\"gpu-scout\"").unwrap();
        assert_eq!(one, vec![SandboxProfile::GpuScout]);
    }

    #[test]
    fn validate_accepts_one_profile_per_dimension() {
        let cfg = [
            SandboxProfile::ReadOnlyRepo,
            SandboxProfile::NetworkDenied,
            SandboxProfile::NoGpu,
            SandboxProfile::VmIsolated,
        ];
        assert_eq!(validate_config(&cfg), Ok(()));
    }

    #[test]
    fn validate_allows_repeated_same_profile() {
        let cfg = [SandboxProfile::GpuScout, SandboxProfile::GpuScout];
        assert_eq!(validate_config(&cfg), Ok(()));
    }

    #[test]
    fn validate_rejects_two_profiles_one_dimension() {
        let cfg = [
            SandboxProfile::NetworkDenied,
            SandboxProfile::NetworkDocsOnly,
        ];
        assert_eq!(
            validate_config(&cfg),
            Err(ConfigError::Conflict {
                dimension: SandboxDimension::Network,
                first: SandboxProfile::NetworkDenied,
                second: SandboxProfile::NetworkDocsOnly,
            })
        );
    }

    #[test]
    fn resolution_marks_unconstrained_dimensions() {
        // Only the filesystem dimension is named; the other three are defaults.
        let t = resolution_text(&[SandboxProfile::ReadOnlyRepo]);
        assert!(t.contains("read-only-repo"));
        assert_eq!(t.matches("unconstrained").count(), 3);
    }

    #[test]
    fn parse_reports_invalid_json_as_error() {
        assert!(parse_config("not json").is_err());
        assert!(parse_config("\"no-such-profile\"").is_err());
    }
}
