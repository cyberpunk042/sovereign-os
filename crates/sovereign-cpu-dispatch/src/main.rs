//! `sovereign-cpu-dispatch` CLI — the runnable end of E0490 (CPU Feature Dispatch).
//!
//! The library fixes the four build dispatch paths (scalar baseline / AVX2 /
//! AVX-512 generic / Zen5 AVX-512), the CPU features that gate each, and the
//! runtime-CPUID selection [`select_best`] that picks the most capable path the
//! host actually supports. But nothing *ran* it: "given these CPU features,
//! which path does the host take?" was unanswerable at the command line, and
//! "does the selector agree with what we expect for this host?" had no gate.
//! This binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — print the 4 canonical dispatch paths (rank + label +
//!     feature requirement) as a human-readable reference: the dispatch table.
//!   * `--select FILE` — load a [`CpuFeatures`] object (or a JSON array of them),
//!     run [`select_best`] on each, and report the chosen path plus every path
//!     the host supports. Pure query, always succeeds.
//!   * `--check FILE` — load a `{ "features": …, "expect": "<path>" }` case (or a
//!     JSON array of them), run [`select_best`] on the real features, compare to
//!     the expected path, report OK / the mismatch, and exit non-zero if any
//!     case disagrees. The gate.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::Deserialize;
use sovereign_cpu_dispatch::{CpuFeatures, DispatchPath, select_best};

/// The stable kebab-case label for a path — identical to how [`DispatchPath`]
/// serializes to JSON (kept honest by the `path_label_matches_serde` test).
fn path_label(path: DispatchPath) -> &'static str {
    match path {
        DispatchPath::ScalarBaseline => "scalar-baseline",
        DispatchPath::Avx2 => "avx2",
        DispatchPath::Avx512Generic => "avx512-generic",
        DispatchPath::Zen5Avx512 => "zen5-avx512",
    }
}

/// A one-line human description of what CPU features each path requires.
fn path_requirement(path: DispatchPath) -> &'static str {
    match path {
        DispatchPath::ScalarBaseline => "runs on any x86-64 (no feature requirement)",
        DispatchPath::Avx2 => "requires AVX2",
        DispatchPath::Avx512Generic => "requires AVX-512 (foundation)",
        DispatchPath::Zen5Avx512 => "requires AVX-512 and AMD Zen5 (-march=znver5)",
    }
}

/// A compact one-line rendering of a host's CPU feature set.
fn features_label(f: &CpuFeatures) -> String {
    format!("avx2={} avx512={} zen5={}", f.avx2, f.avx512, f.zen5)
}

/// The paths a host supports, least → most capable, as kebab labels.
fn supported_labels(f: &CpuFeatures) -> String {
    DispatchPath::ALL
        .into_iter()
        .filter(|p| f.supports(*p))
        .map(path_label)
        .collect::<Vec<_>>()
        .join(", ")
}

/// The human-readable reference: the 4 dispatch paths, least → most capable.
fn reference_text() -> String {
    let mut s = String::from(
        "CPU feature dispatch (E0490): 4 build paths, runtime-CPUID selects the most capable.\n\n",
    );
    for path in DispatchPath::ALL {
        s.push_str(&format!(
            "  rank {}  {:<16} {}\n",
            path.rank(),
            path_label(path),
            path_requirement(path),
        ));
    }
    s.push_str(
        "\nselect_best() picks the highest-rank path the host supports; scalar-baseline\n\
         is always supported, so selection never fails.\n",
    );
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-cpu-dispatch — CPU feature dispatch (E0490)\n\n\
     Four build paths, least -> most capable: scalar-baseline, avx2,\n\
     avx512-generic, zen5-avx512. Runtime CPUID selects the most capable path\n\
     the host actually supports.\n\n\
     USAGE:\n\
     \x20   sovereign-cpu-dispatch                  print the 4 dispatch paths (reference)\n\
     \x20   sovereign-cpu-dispatch --select FILE     report select_best() for CpuFeatures\n\
     \x20   sovereign-cpu-dispatch --check FILE       assert select_best() == expected path\n\
     \x20   sovereign-cpu-dispatch --help             print this help and exit\n\n\
     CpuFeatures JSON: {\"avx2\":bool,\"avx512\":bool,\"zen5\":bool}\n\
     --select FILE loads one CpuFeatures object or a JSON array of them and reports\n\
     the chosen path plus every supported path.\n\
     --check FILE loads one {\"features\":CpuFeatures,\"expect\":\"<path>\"} case or a\n\
     JSON array of them, runs select_best() on the real features, and exits\n\
     non-zero if any selected path disagrees with the expected one.\n"
        .to_string()
}

/// Accept either a single `T` or a JSON array of `T`.
fn parse_one_or_many<T: for<'de> Deserialize<'de>>(
    json: &str,
) -> Result<Vec<T>, serde_json::Error> {
    match serde_json::from_str::<Vec<T>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single object, surfacing that error.
        Err(_) => serde_json::from_str::<T>(json).map(|d| vec![d]),
    }
}

/// `--select FILE`: report the dispatch decision for each host's features.
fn run_select(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let features: Vec<CpuFeatures> = match parse_one_or_many(&json) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("error: {path} is not a CpuFeatures (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if features.is_empty() {
        println!("(no feature sets in {path})");
        return ExitCode::SUCCESS;
    }
    for f in &features {
        let chosen = select_best(f);
        println!(
            "{} -> {} (supports: {})",
            features_label(f),
            path_label(chosen),
            supported_labels(f),
        );
    }
    ExitCode::SUCCESS
}

/// One `--check` case: real features, and the path we assert `select_best` picks.
#[derive(Debug, Deserialize)]
struct CheckCase {
    /// The host CPU features to feed the selector.
    features: CpuFeatures,
    /// The path the selector is expected to choose.
    expect: DispatchPath,
}

/// `--check FILE`: assert `select_best(features) == expect` for each case; exit
/// non-zero on read/parse error or any mismatch.
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let cases: Vec<CheckCase> = match parse_one_or_many(&json) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("error: {path} is not a check case (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if cases.is_empty() {
        println!("(no check cases in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for case in &cases {
        let chosen = select_best(&case.features);
        let feats = features_label(&case.features);
        if chosen == case.expect {
            println!("OK   {feats} -> {} (as expected)", path_label(chosen));
        } else {
            all_ok = false;
            println!(
                "FAIL {feats} -> expected {}, select_best chose {}",
                path_label(case.expect),
                path_label(chosen),
            );
        }
    }

    if all_ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    if let Some(i) = args.iter().position(|a| a == "--select") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --select requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_select(path);
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
    fn path_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for p in DispatchPath::ALL {
            let json = serde_json::to_string(&p).unwrap();
            assert_eq!(json, format!("\"{}\"", path_label(p)));
        }
    }

    #[test]
    fn reference_lists_all_four_paths_ranked() {
        let t = reference_text();
        for p in DispatchPath::ALL {
            assert!(t.contains(path_label(p)), "reference missing {p:?}:\n{t}");
            assert!(
                t.contains(path_requirement(p)),
                "reference missing requirement for {p:?}:\n{t}"
            );
        }
        // Exactly four "rank N" lines — one per path, no more.
        let ranked = t
            .lines()
            .filter(|l| l.trim_start().starts_with("rank "))
            .count();
        assert_eq!(
            ranked,
            DispatchPath::ALL.len(),
            "expected 4 ranked path lines"
        );
    }

    #[test]
    fn select_parses_single_and_array() {
        let one = CpuFeatures {
            avx2: true,
            avx512: false,
            zen5: false,
        };
        let json = serde_json::to_string(&one).unwrap();
        let v: Vec<CpuFeatures> = parse_one_or_many(&json).unwrap();
        assert_eq!(v.len(), 1);
        assert_eq!(select_best(&v[0]), DispatchPath::Avx2);

        let arr = vec![one, CpuFeatures::default()];
        let json = serde_json::to_string(&arr).unwrap();
        let v: Vec<CpuFeatures> = parse_one_or_many(&json).unwrap();
        assert_eq!(v.len(), 2);
        assert_eq!(select_best(&v[1]), DispatchPath::ScalarBaseline);
    }

    #[test]
    fn check_case_matching_expectation_passes() {
        // Operator's Zen5: expect the zen5 path, and get it.
        let json = r#"{"features":{"avx2":true,"avx512":true,"zen5":true},"expect":"zen5-avx512"}"#;
        let cases: Vec<CheckCase> = parse_one_or_many(json).unwrap();
        assert_eq!(cases.len(), 1);
        assert_eq!(select_best(&cases[0].features), cases[0].expect);
    }

    #[test]
    fn check_case_mismatch_is_detectable() {
        // Intel AVX-512 (no zen5) can never reach zen5-avx512 — a wrong expectation.
        let json =
            r#"{"features":{"avx2":true,"avx512":true,"zen5":false},"expect":"zen5-avx512"}"#;
        let cases: Vec<CheckCase> = parse_one_or_many(json).unwrap();
        let chosen = select_best(&cases[0].features);
        assert_ne!(chosen, cases[0].expect);
        assert_eq!(chosen, DispatchPath::Avx512Generic);
    }

    #[test]
    fn supported_labels_lists_baseline_and_all_reachable() {
        let none = CpuFeatures::default();
        assert_eq!(supported_labels(&none), "scalar-baseline");
        let zen5 = CpuFeatures {
            avx2: true,
            avx512: true,
            zen5: true,
        };
        assert_eq!(
            supported_labels(&zen5),
            "scalar-baseline, avx2, avx512-generic, zen5-avx512"
        );
    }

    #[test]
    fn parse_rejects_invalid_json() {
        assert!(parse_one_or_many::<CpuFeatures>("not json").is_err());
    }
}
