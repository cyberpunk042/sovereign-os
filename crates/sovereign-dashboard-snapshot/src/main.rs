//! `sovereign-dashboard-snapshot` CLI — the runnable end of the cockpit composite.
//!
//! The library composes three cockpit sub-states — `BannerState` (top bar),
//! `ContextPanel` (sidebar), and `ToastTray` (notifications) — into one
//! serializable [`DashboardSnapshot`] envelope, with a `build(...)` constructor
//! and a `validate()` contract that re-checks all three sub-states plus the
//! envelope's own schema version and capture timestamp. But nothing *ran* it, so
//! "is this exported snapshot well-formed?" was unanswerable at the command line.
//! This binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — build a small, realistic example snapshot through the
//!     real `DashboardSnapshot::build(...)` API, print a human-readable summary
//!     plus its `validate()` verdict, and echo the snapshot as JSON so it can be
//!     piped straight back into `--validate`.
//!   * `--validate FILE` — load a `DashboardSnapshot` from JSON, run `validate()`,
//!     report OK / the `SnapshotError`, and exit non-zero on read/parse/validate
//!     failure.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_cockpit_banner_state::{BannerSeverity, BannerState};
use sovereign_cockpit_context_panel::ContextPanel;
use sovereign_cockpit_toast_tray::{ToastTray, build as build_toast};
use sovereign_dashboard_snapshot::DashboardSnapshot;
use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_hardware_thermal_policy::ThermalVerdict;
use sovereign_profile_bundles::BundleName;

/// The capture timestamp used for the built-in example snapshot.
const EXAMPLE_CAPTURED_AT: &str = "2026-07-12T09:30:00Z";

/// Build a small but realistic example snapshot through the real
/// [`DashboardSnapshot::build`] API — mid-incident on a live sovereign bundle:
/// live writes armed (Execute), a GPU running warm, two open alerts, and two
/// toasts (one informational, one warning).
///
/// This is not a hand-assembled struct literal: each sub-state is produced by
/// its own crate's constructor, so the example exercises the same composition
/// path an operator's daemon would.
fn example_snapshot() -> DashboardSnapshot {
    let banner = BannerState::build(
        ExecutionMode::Execute,
        BundleName::Sovereign,
        ThermalVerdict::Warm,
        2,
        EXAMPLE_CAPTURED_AT,
    );

    let context = ContextPanel::new(
        BundleName::Sovereign,
        ExecutionMode::Execute,
        "sovereign-os",
        "main",
        "th-42",
        EXAMPLE_CAPTURED_AT,
    );

    let mut toasts = ToastTray::new();
    toasts
        .post(build_toast(
            "boot-01",
            BannerSeverity::Notice,
            "First boot complete",
            "Bare-metal hardware setup finished.",
            30,
            EXAMPLE_CAPTURED_AT,
        ))
        .expect("example notice toast is well-formed");
    toasts
        .post(build_toast(
            "thermal-01",
            BannerSeverity::Warn,
            "GPU warm",
            "GPU crossed the warn threshold (72 C).",
            0,
            EXAMPLE_CAPTURED_AT,
        ))
        .expect("example warn toast is well-formed");

    DashboardSnapshot::build(banner, context, toasts, EXAMPLE_CAPTURED_AT)
}

/// A human-readable summary of a snapshot: envelope metadata plus a one-line
/// digest of each of the three sub-states.
fn summary(snap: &DashboardSnapshot) -> String {
    let b = &snap.banner;
    let c = &snap.context;
    let t = &snap.toasts;
    let conversation = if c.conversation_id.is_empty() {
        "(none)".to_string()
    } else {
        c.conversation_id.clone()
    };
    format!(
        "DashboardSnapshot (schema {schema})\n\
         \x20 captured_at : {captured}\n\
         \x20 banner      : mode={mode:?} bundle={bundle:?} thermal={thermal:?} \
open_alerts={alerts} severity={severity:?}\n\
         \x20 context     : conversation={conversation} workspace={workspace:?} branch={branch:?}\n\
         \x20 toasts      : {total} in-tray, {live} live\n",
        schema = snap.schema_version,
        captured = snap.captured_at,
        mode = b.mode,
        bundle = b.bundle,
        thermal = b.worst_thermal,
        alerts = b.open_alerts,
        severity = b.severity,
        conversation = conversation,
        workspace = c.workspace_label,
        branch = c.branch_id,
        total = t.toasts.len(),
        live = t.live_count(),
    )
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-dashboard-snapshot — point-in-time cockpit composite\n\n\
     Composes BannerState (top bar) + ContextPanel (sidebar) + ToastTray\n\
     (notifications) into one serializable snapshot with a validate() contract.\n\n\
     USAGE:\n\
     \x20   sovereign-dashboard-snapshot                 build an example snapshot, summarize + validate\n\
     \x20   sovereign-dashboard-snapshot --validate FILE validate a DashboardSnapshot JSON file\n\
     \x20   sovereign-dashboard-snapshot --help          print this help and exit\n\n\
     With no arguments, an example snapshot is built through the real build()\n\
     API, summarized, validated, and echoed as JSON (pipe it into --validate).\n\
     --validate FILE loads a DashboardSnapshot object from JSON, runs validate()\n\
     (schema version, captured_at, and all three sub-states), and exits non-zero\n\
     if the file cannot be read, is not a DashboardSnapshot, or fails validation.\n"
        .to_string()
}

/// Parse a single `DashboardSnapshot` from JSON.
fn load_snapshot(json: &str) -> Result<DashboardSnapshot, serde_json::Error> {
    serde_json::from_str(json)
}

/// `--validate FILE`: read the file, parse it as a `DashboardSnapshot`, run
/// `validate()`, print a verdict, and return a process exit code (non-zero on
/// read/parse error or a validation failure).
fn run_validate(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let snap = match load_snapshot(&json) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("error: {path} is not a DashboardSnapshot: {e}");
            return ExitCode::FAILURE;
        }
    };
    match snap.validate() {
        Ok(()) => {
            println!("OK   {path} — snapshot is valid");
            ExitCode::SUCCESS
        }
        Err(err) => {
            println!("FAIL {path} — {err}");
            ExitCode::FAILURE
        }
    }
}

/// Default mode: build the example, summarize it, print the `validate()` verdict,
/// and echo the snapshot as JSON. Returns non-zero only in the (contract-broken)
/// case where the freshly built example fails to validate.
fn run_example() -> ExitCode {
    let snap = example_snapshot();
    print!("{}", summary(&snap));

    let verdict = snap.validate();
    match &verdict {
        Ok(()) => println!("validate(): OK"),
        Err(err) => println!("validate(): FAIL — {err}"),
    }

    match serde_json::to_string_pretty(&snap) {
        Ok(json) => println!("\n--- snapshot JSON (pipe into --validate) ---\n{json}"),
        Err(e) => eprintln!("error: could not serialize example snapshot: {e}"),
    }

    if verdict.is_ok() {
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

    if let Some(i) = args.iter().position(|a| a == "--validate") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --validate requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_validate(path);
    }

    if let Some(unknown) = args.iter().find(|a| a.starts_with('-')) {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    run_example()
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_dashboard_snapshot::SCHEMA_VERSION;

    #[test]
    fn example_is_built_and_valid() {
        let snap = example_snapshot();
        // Built through the real API, so the schema version is the crate's.
        assert_eq!(snap.schema_version, SCHEMA_VERSION);
        assert_eq!(snap.toasts.toasts.len(), 2);
        snap.validate().expect("example snapshot must validate");
    }

    #[test]
    fn summary_mentions_each_sub_state() {
        let snap = example_snapshot();
        let s = summary(&snap);
        assert!(s.contains("banner"), "summary missing banner:\n{s}");
        assert!(s.contains("context"), "summary missing context:\n{s}");
        assert!(s.contains("toasts"), "summary missing toasts:\n{s}");
        assert!(s.contains(EXAMPLE_CAPTURED_AT), "summary missing timestamp");
    }

    #[test]
    fn load_snapshot_roundtrips_the_example() {
        let snap = example_snapshot();
        let json = serde_json::to_string(&snap).unwrap();
        let back = load_snapshot(&json).unwrap();
        assert_eq!(snap, back);
        back.validate().unwrap();
    }

    #[test]
    fn load_snapshot_rejects_non_snapshot_json() {
        assert!(load_snapshot("not json").is_err());
        assert!(load_snapshot("{}").is_err());
    }

    #[test]
    fn tampered_snapshot_fails_validation() {
        let mut snap = example_snapshot();
        snap.schema_version = "9.9.9".into();
        let json = serde_json::to_string(&snap).unwrap();
        let back = load_snapshot(&json).unwrap();
        assert!(back.validate().is_err(), "schema drift must be rejected");
    }
}
