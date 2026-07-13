//! `sovereign-harness-layers` CLI — the runnable end of M082 (E0788-E0794).
//!
//! The library fixes the 5-layer TDD test pyramid: each layer's number, its
//! virtualization needs (E0789), its CI trigger gating (every-PR / merge-or-label
//! / operator-local), the flake-retry policy (F06852), and — the piece this
//! binary exercises — the test-directory classification used for discovery
//! (E0791). But nothing *ran* it, so "which layer runs this test directory, and
//! is my test tree fully classified?" was unanswerable at the command line. This
//! binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — print the 5-layer pyramid as a human-readable
//!     reference: per-layer virtualization, CI trigger, whether it runs in CI,
//!     and flake retries, plus the recognized test-directory names.
//!   * `--check FILE` — load a JSON list of test-directory names (or a single
//!     name), run [`TestLayer::classify_dir`] on each, report the layer each maps
//!     to, and FAIL (exit non-zero) on any directory the taxonomy does not
//!     recognize — an unclassified directory is a real defect because no pyramid
//!     layer would ever run it.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_harness_layers::{
    CiTrigger, L5_RUNTIME_BUDGET_SECS, SCHEMA_VERSION, TestLayer, Virtualization,
};

/// The stable kebab-case label for a layer — identical to how [`TestLayer`]
/// serializes to JSON (kept honest by the `layer_label_matches_serde` test).
fn layer_label(layer: TestLayer) -> &'static str {
    match layer {
        TestLayer::SchemaLint => "schema-lint",
        TestLayer::Unit => "unit",
        TestLayer::StageAcceptance => "stage-acceptance",
        TestLayer::Integration => "integration",
        TestLayer::HardwareConformance => "hardware-conformance",
    }
}

/// The stable kebab-case label for a virtualization mechanism — identical to how
/// [`Virtualization`] serializes (kept honest by `virt_label_matches_serde`).
fn virt_label(virt: Virtualization) -> &'static str {
    match virt {
        Virtualization::None => "none",
        Virtualization::Chroot => "chroot",
        Virtualization::SystemdNspawn => "systemd-nspawn",
        Virtualization::QemuSystem => "qemu-system",
        Virtualization::QemuUser => "qemu-user",
        Virtualization::Hardware => "hardware",
    }
}

/// The stable kebab-case label for a CI trigger — identical to how [`CiTrigger`]
/// serializes (kept honest by `trigger_label_matches_serde`).
fn trigger_label(trigger: CiTrigger) -> &'static str {
    match trigger {
        CiTrigger::EveryPr => "every-pr",
        CiTrigger::MergeOrLabel => "merge-or-label",
        CiTrigger::OperatorLocalOnly => "operator-local-only",
    }
}

/// The comma-joined virtualization stack for a layer.
fn virt_stack(layer: TestLayer) -> String {
    layer
        .virtualization()
        .iter()
        .map(|v| virt_label(*v))
        .collect::<Vec<_>>()
        .join(", ")
}

/// The human-readable reference: the 5-layer pyramid and its gating.
fn reference_text() -> String {
    let mut s = format!(
        "The M082 5-layer TDD test pyramid (E0788) — sovereign-harness-layers, schema {SCHEMA_VERSION}.\n\
         Every module's tests climb these layers, base to apex; each layer has its own\n\
         virtualization stack (E0789) and CI trigger gating.\n\n"
    );
    for layer in TestLayer::ALL {
        s.push_str(&format!(
            "  L{}  {:<20} virt: {:<28} trigger: {:<20} ci: {:<3} retries: {}\n",
            layer.number(),
            layer_label(layer),
            virt_stack(layer),
            trigger_label(layer.trigger()),
            if layer.runs_in_ci() { "yes" } else { "no" },
            layer.flake_retries(),
        ));
    }
    s.push_str(&format!(
        "\nL5 (hardware-conformance) runtime budget: {L5_RUNTIME_BUDGET_SECS}s on operator hardware (F06887).\n\n",
    ));
    s.push_str(
        "Test directories recognized by discovery (E0791):\n\
         \x20 schema, lint      -> L1 (schema-lint)\n\
         \x20 unit              -> L2 (unit)\n\
         \x20 chroot, nspawn    -> L3 (stage-acceptance)\n\
         \x20 qemu              -> L4 (integration)\n\
         \x20 hardware          -> L5 (hardware-conformance)\n\
         Any other directory name is unrecognized and is run by no layer.\n",
    );
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-harness-layers — the M082 5-layer TDD test pyramid (E0788-E0794)\n\n\
     The pyramid, base to apex: L1 schema/lint, L2 unit, L3 stage-acceptance,\n\
     L4 integration, L5 hardware-conformance. Each layer has its own\n\
     virtualization stack and CI trigger gating.\n\n\
     USAGE:\n\
     \x20   sovereign-harness-layers                 print the 5-layer pyramid (reference)\n\
     \x20   sovereign-harness-layers --check FILE     classify test-directory names from JSON\n\
     \x20   sovereign-harness-layers --help           print this help and exit\n\n\
     --check FILE loads a JSON array of test-directory names (or a single name\n\
     string), maps each to its pyramid layer via classify_dir, and exits non-zero\n\
     if any directory is unrecognized (no layer would ever run it).\n"
        .to_string()
}

/// The outcome of classifying one test-directory name.
struct ClassifyOutcome {
    /// The directory name as given in the input.
    dir: String,
    /// The layer it maps to, or `None` if unrecognized.
    layer: Option<TestLayer>,
}

/// Accept either a single directory-name string or a JSON array of them.
fn parse_dirs(json: &str) -> Result<Vec<String>, serde_json::Error> {
    match serde_json::from_str::<Vec<String>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single string, surfacing that error.
        Err(_) => serde_json::from_str::<String>(json).map(|d| vec![d]),
    }
}

/// Parse directory names from JSON and classify each against the taxonomy.
fn check_json(json: &str) -> Result<Vec<ClassifyOutcome>, serde_json::Error> {
    let dirs = parse_dirs(json)?;
    Ok(dirs
        .into_iter()
        .map(|dir| ClassifyOutcome {
            layer: TestLayer::classify_dir(&dir),
            dir,
        })
        .collect())
}

/// `--check FILE`: read the file, classify each directory name, print a report,
/// and return a process exit code (non-zero on read/parse error or any
/// unrecognized directory).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let outcomes = match check_json(&json) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("error: {path} is not a test-directory name (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no test directories in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let dir = &o.dir;
        match o.layer {
            Some(layer) => println!(
                "OK   {dir} -> L{} ({}) [virt: {}, trigger: {}, ci: {}]",
                layer.number(),
                layer_label(layer),
                virt_stack(layer),
                trigger_label(layer.trigger()),
                if layer.runs_in_ci() { "yes" } else { "no" },
            ),
            None => {
                all_ok = false;
                println!("FAIL {dir} -> unrecognized test directory (no pyramid layer runs it)");
            }
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
    fn reference_lists_all_five_layers() {
        let t = reference_text();
        for layer in TestLayer::ALL {
            assert!(
                t.contains(layer_label(layer)),
                "reference missing {layer:?}:\n{t}"
            );
        }
        // Exactly five "  LN … retries: N" layer lines — one per layer, no more.
        // (Keyed on "retries:", which only the per-layer table rows carry.)
        let numbered = t.lines().filter(|l| l.contains("retries:")).count();
        assert_eq!(numbered, TestLayer::ALL.len(), "expected 5 layer lines");
        // The L5 runtime budget must be surfaced.
        assert!(t.contains(&L5_RUNTIME_BUDGET_SECS.to_string()));
    }

    #[test]
    fn layer_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for layer in TestLayer::ALL {
            let json = serde_json::to_string(&layer).unwrap();
            assert_eq!(json, format!("\"{}\"", layer_label(layer)));
        }
    }

    #[test]
    fn virt_label_matches_serde() {
        for v in [
            Virtualization::None,
            Virtualization::Chroot,
            Virtualization::SystemdNspawn,
            Virtualization::QemuSystem,
            Virtualization::QemuUser,
            Virtualization::Hardware,
        ] {
            let json = serde_json::to_string(&v).unwrap();
            assert_eq!(json, format!("\"{}\"", virt_label(v)));
        }
    }

    #[test]
    fn trigger_label_matches_serde() {
        for tr in [
            CiTrigger::EveryPr,
            CiTrigger::MergeOrLabel,
            CiTrigger::OperatorLocalOnly,
        ] {
            let json = serde_json::to_string(&tr).unwrap();
            assert_eq!(json, format!("\"{}\"", trigger_label(tr)));
        }
    }

    #[test]
    fn check_classifies_known_directories() {
        let json = r#"["schema", "lint", "unit", "chroot", "nspawn", "qemu", "hardware"]"#;
        let outcomes = check_json(json).unwrap();
        assert_eq!(outcomes.len(), 7);
        assert_eq!(outcomes[0].layer, Some(TestLayer::SchemaLint)); // schema
        assert_eq!(outcomes[1].layer, Some(TestLayer::SchemaLint)); // lint
        assert_eq!(outcomes[2].layer, Some(TestLayer::Unit));
        assert_eq!(outcomes[3].layer, Some(TestLayer::StageAcceptance)); // chroot
        assert_eq!(outcomes[4].layer, Some(TestLayer::StageAcceptance)); // nspawn
        assert_eq!(outcomes[5].layer, Some(TestLayer::Integration));
        assert_eq!(outcomes[6].layer, Some(TestLayer::HardwareConformance));
        assert!(outcomes.iter().all(|o| o.layer.is_some()));
    }

    #[test]
    fn check_flags_unrecognized_directory() {
        let outcomes = check_json(r#"["unit", "docs"]"#).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert_eq!(outcomes[0].layer, Some(TestLayer::Unit));
        assert_eq!(outcomes[1].dir, "docs");
        assert_eq!(outcomes[1].layer, None, "docs maps to no layer");
    }

    #[test]
    fn check_accepts_a_single_name_string() {
        let outcomes = check_json(r#""hardware""#).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].layer, Some(TestLayer::HardwareConformance));
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }
}
