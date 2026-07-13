//! `sovereign-hibernation` CLI — the runnable end of E0453 (Hibernated Thought).
//!
//! The library fixes the wait conditions an agent hibernates on and the record
//! the runtime saves to resume a branch later. But nothing *ran* it, so "is this
//! saved hibernation record actually resumable, and how does it wake?" was
//! unanswerable at the command line. This binary is that runnable end — a pure
//! config/validate tool over the saved record: it never touches CRIU or a live
//! checkpoint, it only reasons about the plan the library models.
//!
//! Modes:
//!   * default (no args) — print the hibernation model as a human-readable
//!     reference: the 6 wait conditions (with their wake class) and the 5 fields
//!     the runtime saves in a `HibernationRecord`.
//!   * `--check FILE` — load a `HibernationRecord` (or a JSON array of them),
//!     run the real `is_resumable()` validator on each, report OK / why it is not
//!     resumable, and classify each record's wake condition (external vs
//!     resource) via the real `is_externally_driven()` decision; exit non-zero if
//!     any record is not safely resumable.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_hibernation::{HibernationRecord, WaitCondition};

/// The stable kebab-case label for a wait condition — identical to how
/// [`WaitCondition`] serializes to JSON (kept honest by the
/// `condition_label_matches_serde` test).
fn condition_label(condition: WaitCondition) -> &'static str {
    match condition {
        WaitCondition::WaitingForUser => "waiting-for-user",
        WaitCondition::WaitingForLongTest => "waiting-for-long-test",
        WaitCondition::WaitingForDownload => "waiting-for-download",
        WaitCondition::WaitingForExternalEvent => "waiting-for-external-event",
        WaitCondition::LowPriorityBranch => "low-priority-branch",
        WaitCondition::MemoryPressure => "memory-pressure",
    }
}

/// A one-line human description of what each wait condition means.
fn condition_description(condition: WaitCondition) -> &'static str {
    match condition {
        WaitCondition::WaitingForUser => "waiting for the user (a human gate)",
        WaitCondition::WaitingForLongTest => "waiting for a long test to finish",
        WaitCondition::WaitingForDownload => "waiting for a download",
        WaitCondition::WaitingForExternalEvent => "waiting for an external event",
        WaitCondition::LowPriorityBranch => "a low-priority branch that can yield",
        WaitCondition::MemoryPressure => "memory pressure forced it to yield",
    }
}

/// How a wait condition wakes: externally-driven conditions wake on their outside
/// event; resource-driven ones resume when resources free up. This is the CLI's
/// name for the library's [`WaitCondition::is_externally_driven`] decision.
fn wake_class(condition: WaitCondition) -> &'static str {
    if condition.is_externally_driven() {
        "external"
    } else {
        "resource"
    }
}

/// The five fields a `HibernationRecord` saves, in declaration order, with a
/// one-line description of each.
const SAVED_FIELDS: [(&str, &str); 5] = [
    ("branch_summary", "a summary of the branch so far"),
    ("state_vector", "the compact state vector"),
    (
        "tool_futures",
        "identifiers of the tool futures left pending",
    ),
    ("context_refs", "the context (memory) references to restore"),
    (
        "next_wake_condition",
        "the condition whose resolution wakes this branch",
    ),
];

/// The human-readable reference: the 6 wait conditions and the 5 saved fields.
fn reference_text() -> String {
    let mut s = String::from(
        "Hibernated Thought (E0453): an agent hibernates on 1 of 6 wait conditions;\n\
         the runtime saves 5 fields to resume the branch later.\n\n\
         The 6 wait conditions:\n",
    );
    for (i, condition) in WaitCondition::ALL.into_iter().enumerate() {
        s.push_str(&format!(
            "  {}. {:<26} {:<10} {}\n",
            i + 1,
            condition_label(condition),
            format!("[{}]", wake_class(condition)),
            condition_description(condition),
        ));
    }
    s.push_str("\nThe 5 saved fields (a HibernationRecord):\n");
    for (i, (field, description)) in SAVED_FIELDS.into_iter().enumerate() {
        s.push_str(&format!("  {}. {:<20} {}\n", i + 1, field, description));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-hibernation — Hibernated Thought (E0453)\n\n\
     An agent hibernates on 1 of 6 wait conditions (waiting-for-user,\n\
     waiting-for-long-test, waiting-for-download, waiting-for-external-event,\n\
     low-priority-branch, memory-pressure); the runtime saves a 5-field record to\n\
     resume it later. This is a config/validate tool — it never runs CRIU.\n\n\
     USAGE:\n\
     \x20   sovereign-hibernation                 print the model (conditions + fields)\n\
     \x20   sovereign-hibernation --check FILE     validate HibernationRecord(s) from JSON\n\
     \x20   sovereign-hibernation --help           print this help and exit\n\n\
     --check FILE loads a single HibernationRecord object or a JSON array of them,\n\
     runs is_resumable() on each (a non-empty branch summary), classifies each\n\
     record's wake condition as external or resource-driven, and exits non-zero if\n\
     any record is not safely resumable.\n"
        .to_string()
}

/// The outcome of checking one record.
struct CheckOutcome {
    /// The record's `branch_summary` (the human identifier of the branch).
    summary: String,
    /// The condition whose resolution wakes the branch.
    condition: WaitCondition,
    /// Whether the record carries enough to resume safely (`is_resumable`).
    resumable: bool,
}

/// Accept either a single record object or a JSON array of them.
fn parse_records(json: &str) -> Result<Vec<HibernationRecord>, serde_json::Error> {
    match serde_json::from_str::<Vec<HibernationRecord>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single record object, surfacing that error.
        Err(_) => serde_json::from_str::<HibernationRecord>(json).map(|r| vec![r]),
    }
}

/// Parse one-or-many records from JSON and validate each.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let records = parse_records(json)?;
    Ok(records
        .into_iter()
        .map(|r| CheckOutcome {
            resumable: r.is_resumable(),
            condition: r.next_wake_condition,
            summary: r.branch_summary,
        })
        .collect())
}

/// The branch identifier to show for a record: its summary, or `<blank>` when the
/// summary is empty/whitespace (which is exactly why it is not resumable).
fn display_summary(summary: &str) -> String {
    if summary.trim().is_empty() {
        "<blank>".to_string()
    } else {
        format!("\"{summary}\"")
    }
}

/// `--check FILE`: read the file, validate the record(s), print a report, and
/// return a process exit code (non-zero on read/parse error or any failure).
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
            eprintln!("error: {path} is not a HibernationRecord (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no records in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let who = display_summary(&o.summary);
        let wakes = condition_label(o.condition);
        let class = wake_class(o.condition);
        if o.resumable {
            println!("OK   {who} — resumable; wakes on {wakes} [{class}]");
        } else {
            all_ok = false;
            println!(
                "FAIL {who} — not resumable (empty branch summary); wakes on {wakes} [{class}]"
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
    fn reference_lists_all_six_conditions_and_five_fields() {
        let t = reference_text();
        for c in WaitCondition::ALL {
            assert!(
                t.contains(condition_label(c)),
                "reference missing {c:?}:\n{t}"
            );
            assert!(
                t.contains(condition_description(c)),
                "reference missing description for {c:?}:\n{t}"
            );
        }
        for (field, description) in SAVED_FIELDS {
            assert!(t.contains(field), "reference missing field {field}:\n{t}");
            assert!(
                t.contains(description),
                "reference missing description for {field}:\n{t}"
            );
        }
        // Exactly six numbered condition lines carrying a kebab label.
        let condition_lines = t
            .lines()
            .filter(|l| {
                WaitCondition::ALL
                    .iter()
                    .any(|c| l.contains(condition_label(*c)))
            })
            .count();
        assert_eq!(condition_lines, WaitCondition::ALL.len());
    }

    #[test]
    fn condition_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for c in WaitCondition::ALL {
            let json = serde_json::to_string(&c).unwrap();
            assert_eq!(json, format!("\"{}\"", condition_label(c)));
        }
    }

    #[test]
    fn wake_class_matches_decision() {
        for c in WaitCondition::ALL {
            let expected = if c.is_externally_driven() {
                "external"
            } else {
                "resource"
            };
            assert_eq!(wake_class(c), expected);
        }
        assert_eq!(wake_class(WaitCondition::WaitingForUser), "external");
        assert_eq!(wake_class(WaitCondition::MemoryPressure), "resource");
    }

    #[test]
    fn check_accepts_resumable_record() {
        let mut r =
            HibernationRecord::new("drafting parser fix", WaitCondition::WaitingForLongTest);
        r.tool_futures.push("pytest-run-7".into());
        let json = serde_json::to_string(&r).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].summary, "drafting parser fix");
        assert_eq!(outcomes[0].condition, WaitCondition::WaitingForLongTest);
        assert!(outcomes[0].resumable);
    }

    #[test]
    fn check_rejects_blank_summary() {
        // A record with a whitespace-only summary is not safely resumable.
        let r = HibernationRecord::new("   ", WaitCondition::MemoryPressure);
        let json = serde_json::to_string(&r).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(!outcomes[0].resumable);
    }

    #[test]
    fn check_parses_array_of_records() {
        let arr = vec![
            HibernationRecord::new("b1", WaitCondition::WaitingForUser),
            HibernationRecord::new("", WaitCondition::LowPriorityBranch),
        ];
        let json = serde_json::to_string(&arr).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes[0].resumable);
        assert!(!outcomes[1].resumable);
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }

    #[test]
    fn display_summary_marks_blank() {
        assert_eq!(display_summary("   "), "<blank>");
        assert_eq!(display_summary("hi"), "\"hi\"");
    }
}
