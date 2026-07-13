//! `sovereign-replay-export-bundle` CLI — the runnable end of the export envelope.
//!
//! The library packs a `ConversationThread` + `ReplayCursor` + `BookmarkSet`
//! into one `ExportBundle` so an operator can hand a live debug session to a
//! colleague, and cross-validates that the cursor and every bookmark reference
//! the bundled thread by id. But nothing *ran* it, so "is this exported bundle
//! internally consistent?" was unanswerable at the command line. This binary is
//! that runnable end.
//!
//! Modes:
//!   * default (no args) — build a small, real example `ExportBundle` via the
//!     library `build(...)` API, print a summary, and print the `validate()`
//!     verdict.
//!   * `--validate FILE` — load an `ExportBundle` from JSON, run `validate()`,
//!     print OK / the `ExportError`, and exit non-zero on failure.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_conversation_thread::{ConversationThread, Turn, TurnRole};
use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_replay_bookmark_set::{Bookmark, BookmarkSet, ColorTag};
use sovereign_replay_cursor::ReplayCursor;
use sovereign_replay_export_bundle::ExportBundle;

/// One conversation turn at a fixed timestamp on the `main` branch.
fn turn(role: TurnRole, tokens_in: u32, tokens_out: u32, text: &str) -> Turn {
    Turn {
        index: 0,
        role,
        tokens_in,
        tokens_out,
        provider: "local:rocm-4090".into(),
        started_at: "2026-05-19T03:00:00Z".into(),
        completed_at: "2026-05-19T03:00:01Z".into(),
        branch_id: "main".into(),
        text: text.into(),
    }
}

/// Build a small, internally-consistent example `ExportBundle` using the real
/// library `build(...)` API: a 4-turn debug thread, a replay cursor opened over
/// it, and two bookmarks that reference it by id.
fn example_bundle() -> ExportBundle {
    let mut thread = ConversationThread::new("th-demo-42", "2026-05-19T03:00:00Z");
    thread.append(turn(TurnRole::Operator, 42, 0, "why did the boot hang?"));
    thread.append(turn(TurnRole::Model, 0, 128, "checking the last snapshot…"));
    thread.append(turn(TurnRole::Tool, 0, 0, "zfs list -t snapshot"));
    thread.append(turn(
        TurnRole::Model,
        0,
        96,
        "the pre-upgrade snapshot is intact",
    ));

    // A real cursor via the real API: `open` copies the thread_id from the
    // thread, so cursor.thread_id will match on validate(). Replay mode is the
    // only mode `open` accepts, so this never fails for a fresh thread.
    let cursor = ReplayCursor::open(&thread, ExecutionMode::Replay)
        .expect("ReplayCursor::open accepts Replay mode");

    let mut bookmarks = BookmarkSet::new();
    bookmarks
        .add(
            Bookmark {
                label: "symptom".into(),
                thread_id: thread.thread_id.clone(),
                turn_index: 0,
                color: ColorTag::Red,
                note: "operator's original question".into(),
            },
            &thread,
        )
        .expect("in-range bookmark on turn 0");
    bookmarks
        .add(
            Bookmark {
                label: "root-cause".into(),
                thread_id: thread.thread_id.clone(),
                turn_index: 3,
                color: ColorTag::Green,
                note: "snapshot intact — safe rollback point".into(),
            },
            &thread,
        )
        .expect("in-range bookmark on turn 3");

    ExportBundle::build(
        thread,
        cursor,
        bookmarks,
        "2026-05-19T03:05:00Z",
        "op:MS003:demo-fingerprint",
    )
}

/// A human-readable one-block summary of a bundle.
fn summary(bundle: &ExportBundle) -> String {
    let mut s = String::new();
    s.push_str(&format!("schema_version : {}\n", bundle.schema_version));
    s.push_str(&format!("thread_id      : {}\n", bundle.thread.thread_id));
    s.push_str(&format!("turns          : {}\n", bundle.thread.turns.len()));
    s.push_str(&format!(
        "tokens         : {} in / {} out\n",
        bundle.thread.total_tokens_in(),
        bundle.thread.total_tokens_out()
    ));
    s.push_str(&format!(
        "cursor         : next_index {} of {} (state {:?})\n",
        bundle.cursor.next_index, bundle.cursor.total_turns, bundle.cursor.state
    ));
    s.push_str(&format!(
        "bookmarks      : {}\n",
        bundle.bookmarks.bookmarks.len()
    ));
    for b in &bundle.bookmarks.bookmarks {
        s.push_str(&format!(
            "  - {} @turn {} ({:?})\n",
            b.label, b.turn_index, b.color
        ));
    }
    s.push_str(&format!("exported_at    : {}\n", bundle.exported_at));
    s.push_str(&format!("exported_by    : {}\n", bundle.exported_by));
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-replay-export-bundle — exportable replay session envelope\n\n\
     Packs a ConversationThread + ReplayCursor + BookmarkSet into one bundle so a\n\
     live debug session can be handed to a colleague, and cross-validates that the\n\
     cursor and every bookmark reference the bundled thread by id.\n\n\
     USAGE:\n\
     \x20   sovereign-replay-export-bundle                  build an example bundle, print summary + verdict\n\
     \x20   sovereign-replay-export-bundle --validate FILE  validate an ExportBundle loaded from JSON\n\
     \x20   sovereign-replay-export-bundle --help           print this help and exit\n\n\
     --validate FILE loads one ExportBundle object from JSON, runs validate()\n\
     (schema version, non-empty exported_at / exported_by, and that the cursor +\n\
     every bookmark reference the bundled thread), and exits non-zero if it fails.\n"
        .to_string()
}

/// Default mode: build the example bundle, print a summary + `validate()` verdict.
fn run_default() -> ExitCode {
    let bundle = example_bundle();
    print!("{}", summary(&bundle));
    match bundle.validate() {
        Ok(()) => {
            println!("\nvalidate       : OK — cursor + all bookmarks reference the bundled thread");
            ExitCode::SUCCESS
        }
        Err(e) => {
            println!("\nvalidate       : FAIL — {e}");
            ExitCode::FAILURE
        }
    }
}

/// `--validate FILE`: read the file, parse an `ExportBundle`, run `validate()`,
/// print OK / the error, and return a non-zero exit code on any failure.
fn run_validate(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let bundle: ExportBundle = match serde_json::from_str(&json) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {path} is not an ExportBundle: {e}");
            return ExitCode::FAILURE;
        }
    };
    match bundle.validate() {
        Ok(()) => {
            println!("OK   {path} — bundle is internally consistent");
            ExitCode::SUCCESS
        }
        Err(e) => {
            println!("FAIL {path} — {e}");
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

    run_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn example_bundle_validates() {
        // The built example must satisfy the library's cross-validation.
        example_bundle().validate().unwrap();
    }

    #[test]
    fn example_bundle_survives_json_round_trip() {
        // Serialize → deserialize → re-validate, matching how `--validate FILE` loads.
        let bundle = example_bundle();
        let json = serde_json::to_string(&bundle).unwrap();
        let back: ExportBundle = serde_json::from_str(&json).unwrap();
        back.validate().unwrap();
        assert_eq!(bundle, back);
    }

    #[test]
    fn tampered_cursor_thread_id_is_rejected() {
        // A bundle whose cursor points at a different thread must fail validate().
        let mut bundle = example_bundle();
        bundle.cursor.thread_id = "th-someone-elses".into();
        assert!(bundle.validate().is_err());
    }

    #[test]
    fn tampered_bookmark_thread_id_is_rejected() {
        let mut bundle = example_bundle();
        bundle.bookmarks.bookmarks[0].thread_id = "th-someone-elses".into();
        assert!(bundle.validate().is_err());
    }

    #[test]
    fn summary_mentions_thread_and_every_bookmark() {
        let bundle = example_bundle();
        let s = summary(&bundle);
        assert!(s.contains(&bundle.thread.thread_id));
        for b in &bundle.bookmarks.bookmarks {
            assert!(s.contains(&b.label), "summary missing bookmark {}", b.label);
        }
    }

    #[test]
    fn help_text_lists_all_modes() {
        let h = help_text();
        assert!(h.contains("--validate"));
        assert!(h.contains("--help"));
    }
}
