//! `sovereign-zfs-commit-gate` CLI — the runnable end of M040 / M00678.
//!
//! The library models the 4-stage ZFS commit gate every agent write passes
//! through (snapshot → apply → test → commit-or-rollback) and encodes the
//! standing rule that a commit is permitted only when the test stage scores
//! `>= 80`; otherwise the gate rolls back to the pre-commit snapshot. But
//! nothing *ran* that gate, so "would this gate permit the commit?" and "is
//! this recorded cycle a legal outcome of the gate?" were unanswerable at the
//! command line. This binary is that runnable end — a real
//! decision/validation tool that needs no live ZFS host, because the decision
//! lives entirely in the [`GateCycle`] state and its `validate()` / `finalize()`
//! functions.
//!
//! Modes:
//!   * default (no args) — print the 4 canonical stages and the gate rules as a
//!     human-readable reference: the commit gate itself.
//!   * `--check FILE` — load a `GateCycle` (or a JSON array of them), run the
//!     real `validate()` and `finalize()` gate functions, and print the gate's
//!     verdict for each: whether a commit is permitted (ALLOW), denied
//!     (DENY — rollback required or already rolled back), the record is
//!     malformed (FAIL), or the record claims a commit the gate would never
//!     permit (VIOLATION). Exits non-zero if any record is anything but ALLOW.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_zfs_commit_gate::{Disposition, GateCycle, GateError, GateStage, SCHEMA_VERSION};

/// The stable kebab-case label for a stage — identical to how [`GateStage`]
/// serializes to JSON (kept honest by the `stage_label_matches_serde` test).
fn stage_label(stage: GateStage) -> &'static str {
    match stage {
        GateStage::Snapshot => "snapshot",
        GateStage::Apply => "apply",
        GateStage::Test => "test",
        GateStage::CommitOrRollback => "commit-or-rollback",
    }
}

/// A one-line human description of what each stage does.
fn stage_description(stage: GateStage) -> &'static str {
    match stage {
        GateStage::Snapshot => "take a pre-commit ZFS snapshot",
        GateStage::Apply => "apply the patch (atomic write)",
        GateStage::Test => "run the eval-gate (produces test_score 0..=100)",
        GateStage::CommitOrRollback => "commit iff test_score >= 80, else roll back",
    }
}

/// The stable kebab-case label for a disposition — identical to how
/// [`Disposition`] serializes to JSON (kept honest by
/// `disposition_label_matches_serde`).
fn disposition_label(disposition: Disposition) -> &'static str {
    match disposition {
        Disposition::Committed => "committed",
        Disposition::RolledBack => "rolled-back",
        Disposition::InFlight => "in-flight",
    }
}

/// The 4 stages in canonical order, built by walking the real `next()` chain
/// from `Snapshot` — so this list can never drift from the library's model.
fn all_stages() -> Vec<GateStage> {
    let mut stages = vec![GateStage::Snapshot];
    while let Some(next) = stages.last().expect("non-empty").next() {
        stages.push(next);
    }
    stages
}

/// The human-readable reference: the 4 stages and the gate rules.
fn reference_text() -> String {
    let mut s = format!(
        "The M040 ZFS commit gate (schema {SCHEMA_VERSION}): every agent write to a ZFS dataset\n\
         passes through 4 stages. A commit is permitted only when the test stage scores >= 80;\n\
         otherwise the gate rolls back to the pre-commit snapshot.\n\n",
    );
    for stage in all_stages() {
        s.push_str(&format!(
            "  {}. {:<18} {}\n",
            stage.position(),
            stage_label(stage),
            stage_description(stage),
        ));
    }
    s.push_str(
        "\nGate rules:\n\
         \x20 * stages advance 1 -> 2 -> 3 -> 4 with no skips  (GateCycle::advance)\n\
         \x20 * snapshot_id must contain '@' and no field may be empty  (GateCycle::validate)\n\
         \x20 * a commit requires test_score >= 80  (GateCycle::finalize)\n\
         \x20 * a rollback is always permitted, regardless of score\n",
    );
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-zfs-commit-gate — the M040 4-stage ZFS commit gate (M00678)\n\n\
     Every agent write passes through 4 stages: snapshot, apply, test, and\n\
     commit-or-rollback. A commit is permitted only when test_score >= 80.\n\n\
     USAGE:\n\
     \x20   sovereign-zfs-commit-gate                 print the 4 stages and gate rules (reference)\n\
     \x20   sovereign-zfs-commit-gate --check FILE     run the gate on GateCycle(s) from JSON\n\
     \x20   sovereign-zfs-commit-gate --help           print this help and exit\n\n\
     --check FILE loads a single GateCycle object or a JSON array of them, runs the\n\
     real validate() and finalize() gate functions, and prints the gate's verdict:\n\
     \x20   ALLOW      a commit is permitted (committed & legal, or in-flight & eligible)\n\
     \x20   DENY       a commit is not permitted (rollback required, or already rolled back)\n\
     \x20   FAIL       the record is malformed (validate() rejected it)\n\
     \x20   VIOLATION  the record claims a commit the gate would never permit (test_score < 80)\n\n\
     Exits non-zero unless every record is ALLOW.\n"
        .to_string()
}

/// The commit-gate's decision on one [`GateCycle`] record, computed only from
/// the library's real `validate()` / `finalize()` functions.
enum GateVerdict {
    /// `validate()` rejected the record — it is not a well-formed gate cycle.
    Malformed(GateError),
    /// The record's disposition is `committed`, but the gate would never permit
    /// it (test_score < 80): a gate violation / tampered record.
    IllegalCommit(GateError),
    /// A commit is permitted for this record.
    CommitAllowed,
    /// A commit is not permitted; the gate requires (or already enacted) a
    /// rollback. Carries the human-readable reason.
    CommitDenied(String),
}

impl GateVerdict {
    /// Whether the gate permits the commit (the only clean-pass outcome).
    fn permits_commit(&self) -> bool {
        matches!(self, GateVerdict::CommitAllowed)
    }

    /// The short label printed at the head of each report line.
    fn label(&self) -> &'static str {
        match self {
            GateVerdict::CommitAllowed => "ALLOW",
            GateVerdict::CommitDenied(_) => "DENY",
            GateVerdict::Malformed(_) => "FAIL",
            GateVerdict::IllegalCommit(_) => "VIOLATION",
        }
    }
}

/// Decide the gate's verdict for one cycle using only the real gate functions:
/// `validate()` for structural invariants, and a `finalize(Committed)` probe on
/// a clone to apply the real test-score commit rule without mutating the input.
fn decide(cycle: &GateCycle) -> GateVerdict {
    if let Err(e) = cycle.validate() {
        return GateVerdict::Malformed(e);
    }
    // The real commit rule lives in finalize(): probe it on a clone so we read
    // the gate's own answer to "may this cycle commit?" rather than restating it.
    let mut probe = cycle.clone();
    let commit_check = probe.finalize(Disposition::Committed);
    match cycle.disposition {
        Disposition::Committed => match commit_check {
            Ok(()) => GateVerdict::CommitAllowed,
            Err(e) => GateVerdict::IllegalCommit(e),
        },
        Disposition::InFlight => match commit_check {
            Ok(()) => GateVerdict::CommitAllowed,
            Err(_) => GateVerdict::CommitDenied(format!(
                "in-flight, test_score {} < 80 — commit blocked, rollback required",
                cycle.test_score
            )),
        },
        Disposition::RolledBack => GateVerdict::CommitDenied(
            "disposition rolled-back — gate denied the commit".to_string(),
        ),
    }
}

/// A cycle paired with the gate's verdict on it.
struct CheckOutcome {
    /// The input cycle (for reporting its context).
    cycle: GateCycle,
    /// The gate's decision.
    verdict: GateVerdict,
}

/// Accept either a single cycle object or a JSON array of them.
fn parse_cycles(json: &str) -> Result<Vec<GateCycle>, serde_json::Error> {
    match serde_json::from_str::<Vec<GateCycle>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single cycle object, surfacing that error.
        Err(_) => serde_json::from_str::<GateCycle>(json).map(|c| vec![c]),
    }
}

/// Parse one-or-many cycles from JSON and run the gate on each.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let cycles = parse_cycles(json)?;
    Ok(cycles
        .into_iter()
        .map(|cycle| CheckOutcome {
            verdict: decide(&cycle),
            cycle,
        })
        .collect())
}

/// A compact one-line description of the cycle's ZFS context.
fn cycle_context(cycle: &GateCycle) -> String {
    format!(
        "{} @ {} stage={} disposition={}",
        cycle.dataset,
        cycle.snapshot_id,
        stage_label(cycle.stage),
        disposition_label(cycle.disposition),
    )
}

/// `--check FILE`: read the file, run the gate on the cycle(s), print a report,
/// and return a process exit code (non-zero on read/parse error, or if any
/// record is anything other than ALLOW).
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
            eprintln!("error: {path} is not a GateCycle (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no cycles in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_allow = true;
    for o in &outcomes {
        let label = o.verdict.label();
        let ctx = cycle_context(&o.cycle);
        let detail = match &o.verdict {
            GateVerdict::CommitAllowed => {
                format!("commit permitted (test_score {} >= 80)", o.cycle.test_score)
            }
            GateVerdict::CommitDenied(reason) => reason.clone(),
            GateVerdict::Malformed(e) => format!("malformed: {e}"),
            GateVerdict::IllegalCommit(e) => format!("illegal commit: {e}"),
        };
        if !o.verdict.permits_commit() {
            all_allow = false;
        }
        println!("{label:<9} {ctx} — {detail}");
    }

    if all_allow {
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

    /// A well-formed cycle with the given score and disposition.
    fn cycle(test_score: u8, disposition: Disposition) -> GateCycle {
        GateCycle {
            schema_version: SCHEMA_VERSION.into(),
            dataset: "rpool/sovereign-os".into(),
            snapshot_id: "rpool/sovereign-os@pre-2026-05-19T03:00".into(),
            stage: GateStage::Test,
            disposition,
            test_score,
            signature: "ms003-sig".into(),
        }
    }

    #[test]
    fn stage_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for stage in all_stages() {
            let json = serde_json::to_string(&stage).unwrap();
            assert_eq!(json, format!("\"{}\"", stage_label(stage)));
        }
    }

    #[test]
    fn disposition_label_matches_serde() {
        for d in [
            Disposition::Committed,
            Disposition::RolledBack,
            Disposition::InFlight,
        ] {
            let json = serde_json::to_string(&d).unwrap();
            assert_eq!(json, format!("\"{}\"", disposition_label(d)));
        }
    }

    #[test]
    fn reference_lists_all_four_stages_in_order() {
        let t = reference_text();
        for stage in all_stages() {
            assert!(
                t.contains(stage_label(stage)),
                "reference missing {stage:?}"
            );
            assert!(
                t.contains(stage_description(stage)),
                "reference missing description for {stage:?}"
            );
        }
        // Exactly four numbered "  N. " entries — one per stage, no more.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(numbered, all_stages().len(), "expected 4 stage lines");
    }

    #[test]
    fn committed_with_passing_score_is_allowed() {
        let v = decide(&cycle(85, Disposition::Committed));
        assert!(v.permits_commit());
        assert_eq!(v.label(), "ALLOW");
    }

    #[test]
    fn committed_with_failing_score_is_a_violation() {
        // A record asserting a commit the gate would never permit.
        let v = decide(&cycle(70, Disposition::Committed));
        assert!(!v.permits_commit());
        assert!(matches!(
            v,
            GateVerdict::IllegalCommit(GateError::TestGateFailed(70))
        ));
    }

    #[test]
    fn in_flight_eligible_is_allowed() {
        let v = decide(&cycle(80, Disposition::InFlight));
        assert!(v.permits_commit());
    }

    #[test]
    fn in_flight_below_gate_is_denied() {
        let v = decide(&cycle(79, Disposition::InFlight));
        assert!(!v.permits_commit());
        assert!(matches!(v, GateVerdict::CommitDenied(_)));
        assert_eq!(v.label(), "DENY");
    }

    #[test]
    fn rolled_back_is_denied_but_not_a_violation() {
        // A legitimate rollback is the gate working correctly, yet a commit was
        // not permitted, so it is a DENY (non-zero), never a VIOLATION.
        let v = decide(&cycle(10, Disposition::RolledBack));
        assert!(!v.permits_commit());
        assert!(matches!(v, GateVerdict::CommitDenied(_)));
    }

    #[test]
    fn malformed_record_fails() {
        let mut c = cycle(90, Disposition::Committed);
        c.snapshot_id = "no-at-separator".into();
        let v = decide(&c);
        assert!(!v.permits_commit());
        assert!(matches!(v, GateVerdict::Malformed(_)));
        assert_eq!(v.label(), "FAIL");
    }

    #[test]
    fn check_json_parses_single_object() {
        let json = serde_json::to_string(&cycle(85, Disposition::Committed)).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(outcomes[0].verdict.permits_commit());
    }

    #[test]
    fn check_json_parses_array_mixed() {
        let arr = vec![
            cycle(85, Disposition::Committed),
            cycle(70, Disposition::Committed),
        ];
        let json = serde_json::to_string(&arr).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes[0].verdict.permits_commit());
        assert!(!outcomes[1].verdict.permits_commit());
    }

    #[test]
    fn check_json_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }

    #[test]
    fn decide_does_not_mutate_input() {
        // The finalize() probe runs on a clone, never the caller's cycle.
        let c = cycle(90, Disposition::InFlight);
        let _ = decide(&c);
        assert_eq!(c.disposition, Disposition::InFlight);
    }
}
