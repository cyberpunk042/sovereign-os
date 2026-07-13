//! `sovereign-mode-transition-log` — the runnable end of the append-only
//! ExecutionMode transition record.
//!
//! The library defines the log (`from, to, reason, actor, at, trace_id` per
//! entry) and its validator, but nothing ran it, so "is this transition log
//! well-formed?" was unanswerable from a shell. This binary is that runnable
//! end.
//!
//! Default (no args): build a small example `TransitionLog` with the real
//! `record` API — demonstrating the append-only record — then print each entry
//! and the `validate()` verdict.
//!
//! `--validate FILE` (alias `--check FILE`): load a `TransitionLog` from JSON,
//! run `validate()`, print OK or the `TransitionError`, exiting non-zero on
//! failure.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_mode_transition_log::{TransitionLog, TransitionReason};

const HELP: &str = "\
sovereign-mode-transition-log — append-only ExecutionMode transition record

USAGE:
    sovereign-mode-transition-log                  build an example log, print its entries + validate() verdict
    sovereign-mode-transition-log --validate FILE  load a TransitionLog from JSON and validate it (non-zero on error)
    sovereign-mode-transition-log --check FILE     alias for --validate
    sovereign-mode-transition-log --help           print this help and exit";

/// Build a small illustrative append-only log using the real `record` API.
///
/// Two legal transitions (`Plan → DryRun`, then `DryRun → Execute`), each with
/// a distinct actor signature, monotonic timestamp, and trace_id.
fn example_log() -> TransitionLog {
    let mut log = TransitionLog::new();
    log.record(
        ExecutionMode::Plan,
        ExecutionMode::DryRun,
        TransitionReason::OperatorChose,
        "op:demo",
        "2026-07-08T09:00:00Z",
        "trace-demo-1",
    )
    .expect("example Plan→DryRun transition is legal");
    log.record(
        ExecutionMode::DryRun,
        ExecutionMode::Execute,
        TransitionReason::PromoteToLive,
        "op:demo",
        "2026-07-08T09:05:00Z",
        "trace-demo-2",
    )
    .expect("example DryRun→Execute transition is legal");
    log
}

/// Human-readable rendering: one line per entry, then the `validate()` verdict.
fn render_summary(log: &TransitionLog) -> String {
    let mut s = format!(
        "TransitionLog (schema {}, {} entries):\n",
        log.schema_version,
        log.entries.len()
    );
    for (i, e) in log.entries.iter().enumerate() {
        s.push_str(&format!(
            "  {i}. {:?} → {:?}  reason={:?}  actor={}  at={}  trace_id={}\n",
            e.from, e.to, e.reason, e.actor, e.at, e.trace_id
        ));
    }
    match log.validate() {
        Ok(()) => s.push_str("validate(): OK\n"),
        Err(err) => s.push_str(&format!("validate(): FAILED — {err}\n")),
    }
    s
}

/// Load a `TransitionLog` from a JSON file and validate it.
///
/// Returns the verdict message and whether it passed — I/O errors, JSON parse
/// errors, and validation errors all count as failure.
fn validate_file(path: &str) -> (String, bool) {
    let raw = match std::fs::read_to_string(path) {
        Ok(r) => r,
        Err(e) => return (format!("cannot read {path}: {e}"), false),
    };
    let log: TransitionLog = match serde_json::from_str(&raw) {
        Ok(l) => l,
        Err(e) => {
            return (
                format!("cannot parse {path} as TransitionLog JSON: {e}"),
                false,
            );
        }
    };
    match log.validate() {
        Ok(()) => (
            format!("OK — {path}: {} entries, log validates", log.entries.len()),
            true,
        ),
        Err(err) => (format!("INVALID — {path}: {err}"), false),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!("{HELP}");
        return ExitCode::SUCCESS;
    }

    if let Some(path) = args
        .iter()
        .position(|a| a == "--validate" || a == "--check")
        .and_then(|i| args.get(i + 1))
    {
        let (msg, ok) = validate_file(path);
        println!("{msg}");
        return if ok {
            ExitCode::SUCCESS
        } else {
            ExitCode::FAILURE
        };
    }

    print!("{}", render_summary(&example_log()));
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn example_log_records_two_entries_and_validates() {
        let log = example_log();
        assert_eq!(log.entries.len(), 2);
        log.validate().expect("example log must validate");
        assert_eq!(log.current_mode(), Some(ExecutionMode::Execute));
    }

    #[test]
    fn render_summary_reports_ok_for_wellformed_log() {
        let out = render_summary(&example_log());
        assert!(out.contains("validate(): OK"), "summary was:\n{out}");
        assert!(out.contains("Plan"), "summary was:\n{out}");
        assert!(out.contains("Execute"), "summary was:\n{out}");
    }

    #[test]
    fn validate_file_accepts_wellformed_json() {
        let json = serde_json::to_string(&example_log()).unwrap();
        let path = std::env::temp_dir().join(format!("mtl-ok-{}.json", std::process::id()));
        std::fs::write(&path, json).unwrap();
        let (msg, ok) = validate_file(path.to_str().unwrap());
        assert!(ok, "expected valid, got: {msg}");
        assert!(msg.starts_with("OK"), "msg: {msg}");
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn validate_file_rejects_malformed_log() {
        // A no-op transition (from == to) is valid JSON but fails validate().
        let bad = r#"{"schema_version":"1.0.0","entries":[{"from":"plan","to":"plan","reason":"operator-chose","actor":"op","at":"2026-07-08T09:00:00Z","trace_id":"tr"}]}"#;
        let path = std::env::temp_dir().join(format!("mtl-bad-{}.json", std::process::id()));
        std::fs::write(&path, bad).unwrap();
        let (msg, ok) = validate_file(path.to_str().unwrap());
        assert!(!ok, "expected invalid, got: {msg}");
        assert!(msg.starts_with("INVALID"), "msg: {msg}");
        let _ = std::fs::remove_file(&path);
    }
}
