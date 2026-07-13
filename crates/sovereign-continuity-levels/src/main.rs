//! `sovereign-continuity-levels` CLI — the runnable end of E0456.
//!
//! The library fixes the 8-level continuity ladder and the ownership boundary:
//! a cloud typically provides only the shallow levels (0–2), while the sovereign
//! station owns the deep ones (3–7). But nothing *ran* it, so "is this a real
//! level on the ladder, and who owns it?" was unanswerable at the command line.
//! This binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — print the 8-level ladder as a human-readable
//!     reference: each level's depth, kebab label, cloud/station ownership, and
//!     a one-line description. Depth and ownership are computed from the crate's
//!     own methods, never hardcoded.
//!   * `--check FILE` — load a single kebab-case level string or a JSON array of
//!     them, confirm each deserializes to a real [`ContinuityLevel`], report its
//!     depth and whether it is cloud-typical or station-owned; exit non-zero if
//!     the file cannot be read or any value is not a level on the ladder.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_continuity_levels::ContinuityLevel;

/// The stable kebab-case label for a level — identical to how
/// [`ContinuityLevel`] serializes to JSON (kept honest by the
/// `level_label_matches_serde` test).
fn level_label(level: ContinuityLevel) -> &'static str {
    match level {
        ContinuityLevel::StatelessApiCall => "stateless-api-call",
        ContinuityLevel::ConversationMemory => "conversation-memory",
        ContinuityLevel::WorkflowCheckpoint => "workflow-checkpoint",
        ContinuityLevel::FilesystemSnapshot => "filesystem-snapshot",
        ContinuityLevel::ProcessContainerCheckpoint => "process-container-checkpoint",
        ContinuityLevel::WarmModelKvContext => "warm-model-kv-context",
        ContinuityLevel::LearnedSkillProfilePolicy => "learned-skill-profile-policy",
        ContinuityLevel::UserSovereignLifeContinuity => "user-sovereign-life-continuity",
    }
}

/// A one-line human description of what each level of continuity provides.
fn level_description(level: ContinuityLevel) -> &'static str {
    match level {
        ContinuityLevel::StatelessApiCall => {
            "a single request with no memory of anything before it"
        }
        ContinuityLevel::ConversationMemory => {
            "memory that persists across the turns of one conversation"
        }
        ContinuityLevel::WorkflowCheckpoint => {
            "a resumable checkpoint within a multi-step workflow"
        }
        ContinuityLevel::FilesystemSnapshot => "a warm filesystem snapshot, restorable in place",
        ContinuityLevel::ProcessContainerCheckpoint => {
            "a live process / container checkpoint, resumable mid-flight"
        }
        ContinuityLevel::WarmModelKvContext => "a warm model with its KV context kept resident",
        ContinuityLevel::LearnedSkillProfilePolicy => {
            "a learned skill, profile, or policy carried forward"
        }
        ContinuityLevel::UserSovereignLifeContinuity => {
            "a continuous life of work the user fully owns"
        }
    }
}

/// The ownership tag for a level — decided by the crate's own methods, so the
/// reference can never drift from the E0456 boundary.
fn owner_label(level: ContinuityLevel) -> &'static str {
    if level.is_cloud_typical() {
        "cloud-typical"
    } else {
        "station-owned"
    }
}

/// The human-readable reference: the 8-level continuity ladder, shallow → deep.
fn reference_text() -> String {
    let mut s = String::from(
        "The 8-level continuity ladder (E0456), shallow → deep.\n\
         Cloud typically provides levels 0–2; the sovereign station owns 3–7.\n\n",
    );
    for level in ContinuityLevel::ALL {
        s.push_str(&format!(
            "  {}. {:<32} [{:<13}] {}\n",
            level.depth(),
            level_label(level),
            owner_label(level),
            level_description(level),
        ));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-continuity-levels — the 8-level continuity ladder (E0456)\n\n\
     Continuity has depth: from a stateless API call (Level 0) up to user-sovereign\n\
     life continuity (Level 7). A cloud typically provides levels 0–2; the sovereign\n\
     station owns 3–7.\n\n\
     USAGE:\n\
     \x20   sovereign-continuity-levels                print the 8-level ladder (reference)\n\
     \x20   sovereign-continuity-levels --check FILE    validate continuity level(s) from JSON\n\
     \x20   sovereign-continuity-levels --help          print this help and exit\n\n\
     --check FILE loads a single kebab-case level string or a JSON array of them,\n\
     confirms each is a real level on the ladder, reports its depth and whether it\n\
     is cloud-typical or station-owned, and exits non-zero if any are unrecognised.\n"
        .to_string()
}

/// Accept either a single level string or a JSON array of level strings.
fn parse_levels(json: &str) -> Result<Vec<ContinuityLevel>, serde_json::Error> {
    match serde_json::from_str::<Vec<ContinuityLevel>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single level string, surfacing that error.
        Err(_) => serde_json::from_str::<ContinuityLevel>(json).map(|l| vec![l]),
    }
}

/// `--check FILE`: read the file, confirm each value is a real level, print a
/// report of its computed properties, and return a process exit code (non-zero
/// on read/parse error).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let levels = match parse_levels(&json) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("error: {path} is not a continuity level (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if levels.is_empty() {
        println!("(no levels in {path})");
        return ExitCode::SUCCESS;
    }

    for level in &levels {
        println!(
            "OK   {:<32} depth {} [{}] — {}",
            level_label(*level),
            level.depth(),
            owner_label(*level),
            level_description(*level),
        );
    }
    ExitCode::SUCCESS
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
    fn reference_lists_all_eight_levels() {
        let t = reference_text();
        for l in ContinuityLevel::ALL {
            assert!(t.contains(level_label(l)), "reference missing {l:?}:\n{t}");
            assert!(
                t.contains(level_description(l)),
                "reference missing description for {l:?}:\n{t}"
            );
        }
        // Exactly eight lines that begin (after indent) with a digit — one per level.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(
            numbered,
            ContinuityLevel::ALL.len(),
            "expected 8 level lines"
        );
    }

    #[test]
    fn level_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for l in ContinuityLevel::ALL {
            let json = serde_json::to_string(&l).unwrap();
            assert_eq!(json, format!("\"{}\"", level_label(l)));
        }
    }

    #[test]
    fn owner_label_reflects_the_e0456_boundary() {
        // Ownership is decided by the crate's methods, and the partition is total.
        for l in ContinuityLevel::ALL {
            let expected = if l.is_cloud_typical() {
                "cloud-typical"
            } else {
                "station-owned"
            };
            assert_eq!(owner_label(l), expected, "{l:?}");
            assert_ne!(l.is_cloud_typical(), l.is_station_owned(), "{l:?}");
        }
        // The reference shows both sides of the boundary.
        let t = reference_text();
        assert!(t.contains("cloud-typical"));
        assert!(t.contains("station-owned"));
    }

    #[test]
    fn check_accepts_single_level() {
        let json = serde_json::to_string(&ContinuityLevel::FilesystemSnapshot).unwrap();
        let levels = parse_levels(&json).unwrap();
        assert_eq!(levels, vec![ContinuityLevel::FilesystemSnapshot]);
        // A deep level the cloud rarely provides.
        assert!(levels[0].is_station_owned());
    }

    #[test]
    fn check_accepts_array_of_levels() {
        let arr = vec![
            ContinuityLevel::StatelessApiCall,
            ContinuityLevel::WarmModelKvContext,
            ContinuityLevel::UserSovereignLifeContinuity,
        ];
        let json = serde_json::to_string(&arr).unwrap();
        let levels = parse_levels(&json).unwrap();
        assert_eq!(levels, arr);
    }

    #[test]
    fn check_rejects_values_that_are_not_levels() {
        // A plausible-but-fake level on nobody's ladder.
        assert!(parse_levels("\"teleportation\"").is_err());
        // Outright garbage.
        assert!(parse_levels("not json").is_err());
    }
}
