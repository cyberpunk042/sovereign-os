//! `sovereign-worker-fleet` CLI — the runnable end of M00212 / F-2026-083.
//!
//! The library aggregates many worker status words into one *fleet* picture:
//! the worst pressure on each axis, how many workers are erroring or flagged,
//! and a single [`FleetVerdict`]. But nothing *ran* it, so "given this fleet of
//! workers, what is its verdict — is the cluster saturated?" was unanswerable at
//! the command line. This binary is that runnable end: the read-only fleet
//! health check a scheduler or cockpit would consult.
//!
//! Modes:
//!   * default (no args) — print the fleet model: the four pressure axes, the
//!     [`FleetVerdict`] taxonomy, and the default thresholds. A human-readable
//!     reference of what the aggregation decides.
//!   * `--check FILE` — load a fleet from JSON (a bare array of worker status
//!     words, or an object `{ "workers": [...], "thresholds": {...} }`), run
//!     [`summarise`], print the fleet summary + verdict, and exit non-zero if
//!     the fleet is `Saturated` (or the file cannot be read/parsed).
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::Deserialize;
use sovereign_worker_fleet::{FleetSummary, FleetThresholds, FleetVerdict, summarise};
use sovereign_worker_status_word::WorkerStatusWord;

/// Every fleet verdict, worst-first — the taxonomy the reference enumerates and
/// the check reports. Kept exhaustive by the `verdicts_are_exhaustive` test.
const VERDICTS: [FleetVerdict; 4] = [
    FleetVerdict::Empty,
    FleetVerdict::Healthy,
    FleetVerdict::Elevated,
    FleetVerdict::Saturated,
];

/// The stable kebab-case label for a verdict — identical to how [`FleetVerdict`]
/// serializes to JSON (kept honest by the `verdict_label_matches_serde` test).
fn verdict_label(verdict: FleetVerdict) -> &'static str {
    match verdict {
        FleetVerdict::Empty => "empty",
        FleetVerdict::Healthy => "healthy",
        FleetVerdict::Elevated => "elevated",
        FleetVerdict::Saturated => "saturated",
    }
}

/// A one-line description of what each verdict means for the fleet.
fn verdict_description(verdict: FleetVerdict) -> &'static str {
    match verdict {
        FleetVerdict::Empty => "no workers in the fleet",
        FleetVerdict::Healthy => "every pressure axis below the elevated threshold",
        FleetVerdict::Elevated => "an axis crossed the elevated threshold — busy but coping",
        FleetVerdict::Saturated => {
            "an axis crossed the saturated threshold, or a worker is erroring"
        }
    }
}

/// Whether a verdict is a health-check *failure* (a non-zero process exit).
/// Only a saturated fleet fails; empty/healthy/elevated are acceptable states.
fn verdict_is_failure(verdict: FleetVerdict) -> bool {
    matches!(verdict, FleetVerdict::Saturated)
}

/// The human-readable reference: the four pressure axes, the verdict taxonomy,
/// and the default thresholds.
fn reference_text() -> String {
    let th = FleetThresholds::default();
    let mut s = String::from(
        "The worker fleet model (M00212 / F-2026-083): a read-only aggregation over\n\
         many worker status words into one fleet verdict.\n\n\
         Worst-of-fleet pressure axes (each a 0..=255 byte, max taken across workers):\n\
         \x20   load bucket, memory pressure, thermal pressure, queue depth\n\n\
         Fleet verdicts (worst pressure across the fleet decides):\n",
    );
    for (i, verdict) in VERDICTS.into_iter().enumerate() {
        s.push_str(&format!(
            "  {}. {:<12} {}\n",
            i + 1,
            verdict_label(verdict),
            verdict_description(verdict),
        ));
    }
    s.push_str(&format!(
        "\nDefault thresholds (on the 0..=255 byte scale):\n\
         \x20   elevated  >= {} (~{}%)\n\
         \x20   saturated >= {} (~{}%)\n",
        th.elevated,
        u16::from(th.elevated) * 100 / 255,
        th.saturated,
        u16::from(th.saturated) * 100 / 255,
    ));
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-worker-fleet — fleet health summary over worker status words (M00212)\n\n\
     Aggregates many workers' status words into the worst pressure on each axis,\n\
     error/flag counts, and one fleet verdict (empty / healthy / elevated / saturated).\n\n\
     USAGE:\n\
     \x20   sovereign-worker-fleet                  print the fleet model (reference)\n\
     \x20   sovereign-worker-fleet --check FILE      summarise a fleet from JSON\n\
     \x20   sovereign-worker-fleet --help            print this help and exit\n\n\
     --check FILE loads a fleet as JSON — either a bare array of worker status words,\n\
     or an object { \"workers\": [...], \"thresholds\": { \"elevated\": N, \"saturated\": N } }\n\
     with optional custom thresholds — runs the summary, prints the per-axis worst,\n\
     the error/flag counts, and the verdict, and exits non-zero if the fleet is\n\
     saturated (or the file cannot be read or parsed).\n"
        .to_string()
}

/// Optional custom thresholds carried in the object form of a fleet file.
#[derive(Deserialize)]
struct ThresholdSpec {
    /// A pressure byte at or above this is "elevated".
    elevated: u8,
    /// A pressure byte at or above this is "saturated".
    saturated: u8,
}

/// The object form of a fleet file: workers plus optional thresholds.
#[derive(Deserialize)]
struct FleetObject {
    /// The workers' status words.
    workers: Vec<WorkerStatusWord>,
    /// Optional custom thresholds; absent means [`FleetThresholds::default`].
    #[serde(default)]
    thresholds: Option<ThresholdSpec>,
}

/// Parse a fleet from JSON: accept either a bare array of worker status words
/// (default thresholds) or an object with `workers` and optional `thresholds`.
fn parse_fleet(json: &str) -> Result<(Vec<WorkerStatusWord>, FleetThresholds), serde_json::Error> {
    if json.trim_start().starts_with('[') {
        let workers: Vec<WorkerStatusWord> = serde_json::from_str(json)?;
        Ok((workers, FleetThresholds::default()))
    } else {
        let obj: FleetObject = serde_json::from_str(json)?;
        let th = obj
            .thresholds
            .map_or_else(FleetThresholds::default, |t| FleetThresholds {
                elevated: t.elevated,
                saturated: t.saturated,
            });
        Ok((obj.workers, th))
    }
}

/// Parse a fleet from JSON and summarise it under the resolved thresholds.
fn evaluate(json: &str) -> Result<(FleetThresholds, FleetSummary), serde_json::Error> {
    let (workers, th) = parse_fleet(json)?;
    Ok((th, summarise(&workers, th)))
}

/// Render a summary + thresholds as the human-readable check report.
fn report_text(th: FleetThresholds, summary: &FleetSummary) -> String {
    format!(
        "fleet: {} worker(s)  [elevated >= {}, saturated >= {}]\n\
         \x20   max load           {}\n\
         \x20   max memory         {}\n\
         \x20   max thermal        {}\n\
         \x20   max queue          {}\n\
         \x20   workers in error   {}\n\
         \x20   workers flagged    {}\n\
         verdict: {}\n",
        summary.worker_count,
        th.elevated,
        th.saturated,
        summary.max_load,
        summary.max_memory_pressure,
        summary.max_thermal_pressure,
        summary.max_queue_depth,
        summary.workers_in_error,
        summary.workers_flagged,
        verdict_label(summary.verdict),
    )
}

/// `--check FILE`: read the file, summarise the fleet, print the report, and
/// return a process exit code (non-zero on read/parse error, or if saturated).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let (th, summary) = match evaluate(&json) {
        Ok(pair) => pair,
        Err(e) => {
            eprintln!(
                "error: {path} is not a fleet (array of status words, or {{workers, thresholds}}): {e}"
            );
            return ExitCode::FAILURE;
        }
    };

    print!("{}", report_text(th, &summary));
    if verdict_is_failure(summary.verdict) {
        eprintln!("FAIL: fleet is saturated");
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
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

    /// A worker status word with the given pressures (health/policy left zero).
    fn worker(load: u8, mem: u8, thermal: u8, queue: u8, error: u8, flags: u8) -> WorkerStatusWord {
        WorkerStatusWord {
            load_bucket: load,
            memory_pressure: mem,
            thermal_pressure: thermal,
            queue_depth: queue,
            error_state: error,
            health: 0,
            policy_mode: 0,
            flags,
        }
    }

    #[test]
    fn verdicts_are_exhaustive() {
        // If a variant is added to FleetVerdict, this const array (and the
        // reference it feeds) must be updated too.
        assert_eq!(VERDICTS.len(), 4);
    }

    #[test]
    fn verdict_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for v in VERDICTS {
            let json = serde_json::to_string(&v).unwrap();
            assert_eq!(json, format!("\"{}\"", verdict_label(v)));
        }
    }

    #[test]
    fn reference_lists_all_verdicts() {
        let t = reference_text();
        for v in VERDICTS {
            assert!(
                t.contains(verdict_label(v)),
                "reference missing {v:?}:\n{t}"
            );
            assert!(
                t.contains(verdict_description(v)),
                "reference missing description for {v:?}:\n{t}"
            );
        }
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(numbered, VERDICTS.len(), "expected one line per verdict");
    }

    #[test]
    fn bare_array_uses_default_thresholds_and_summarises() {
        let json = serde_json::to_string(&vec![
            worker(10, 20, 30, 5, 0, 0),
            worker(50, 40, 10, 8, 0, 0b0001),
        ])
        .unwrap();
        let (th, summary) = evaluate(&json).unwrap();
        assert_eq!(th.elevated, FleetThresholds::default().elevated);
        assert_eq!(summary.worker_count, 2);
        assert_eq!(summary.max_load, 50);
        assert_eq!(summary.workers_flagged, 1);
        assert_eq!(summary.verdict, FleetVerdict::Healthy);
        assert!(!verdict_is_failure(summary.verdict));
    }

    #[test]
    fn object_form_honours_custom_thresholds() {
        // A worker at 100 across the board: healthy under defaults, but with a
        // low elevated threshold of 90 it becomes Elevated.
        let json = r#"{
            "workers": [{"load_bucket":100,"memory_pressure":100,"thermal_pressure":100,
                         "queue_depth":100,"error_state":0,"health":0,"policy_mode":0,"flags":0}],
            "thresholds": { "elevated": 90, "saturated": 200 }
        }"#;
        let (th, summary) = evaluate(json).unwrap();
        assert_eq!(th.elevated, 90);
        assert_eq!(th.saturated, 200);
        assert_eq!(summary.verdict, FleetVerdict::Elevated);
        assert!(!verdict_is_failure(summary.verdict));
    }

    #[test]
    fn saturated_fleet_is_a_failure() {
        // One worker over the saturated default (224) → Saturated → check fails.
        let json = serde_json::to_string(&vec![worker(240, 0, 0, 0, 0, 0)]).unwrap();
        let (_, summary) = evaluate(&json).unwrap();
        assert_eq!(summary.verdict, FleetVerdict::Saturated);
        assert!(verdict_is_failure(summary.verdict));
    }

    #[test]
    fn erroring_worker_saturates_and_fails() {
        // Low pressure everywhere, but a worker reports an error → Saturated.
        let json = serde_json::to_string(&vec![worker(5, 5, 5, 5, 9, 0)]).unwrap();
        let (_, summary) = evaluate(&json).unwrap();
        assert_eq!(summary.workers_in_error, 1);
        assert!(verdict_is_failure(summary.verdict));
    }

    #[test]
    fn empty_array_is_empty_verdict_and_passes() {
        let (_, summary) = evaluate("[]").unwrap();
        assert_eq!(summary.verdict, FleetVerdict::Empty);
        assert_eq!(summary.worker_count, 0);
        assert!(!verdict_is_failure(summary.verdict));
    }

    #[test]
    fn invalid_json_is_an_error() {
        assert!(evaluate("not json").is_err());
        assert!(evaluate("{\"workers\": 3}").is_err());
    }

    #[test]
    fn report_shows_axes_and_verdict() {
        let json = serde_json::to_string(&vec![worker(70, 90, 30, 5, 0, 0)]).unwrap();
        let (th, summary) = evaluate(&json).unwrap();
        let r = report_text(th, &summary);
        assert!(r.contains("max memory         90"), "report:\n{r}");
        assert!(r.contains("verdict: healthy"), "report:\n{r}");
    }
}
