//! `sovereign-continuity-manager` CLI — the runnable end of M048 Module 8
//! (E0464 / M00810, dump 14706-14720).
//!
//! The library fixes the continuity discipline: 6 primitives, 8 lifecycle
//! states with a canonical position and a resumability flag, and — the real
//! contract — a transition graph plus a signed [`transition`] function that
//! rejects illegal or unsigned moves. But nothing *ran* it, so "is this
//! state move legal?" was unanswerable at the command line. This binary is
//! that runnable end.
//!
//! Modes:
//!   * default (no args) — print the canonical reference: the 8 states (with
//!     position + resumability), the 6 primitives, and the full allowed-move
//!     matrix derived live from [`is_allowed_transition`].
//!   * `--check FILE` — load a transition request (a single object or a JSON
//!     array of them), run the library's real [`transition`] on each, report
//!     OK / the [`ContinuityError`], and exit non-zero if any move is illegal
//!     or unsigned.
//!   * `--help` — usage.
//!
//! stdlib + crate types + `serde_json` only.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::Deserialize;
use sovereign_continuity_manager::{
    ContinuityError, ContinuityPrimitive, ContinuityState, SCHEMA_VERSION, SessionRecord,
    is_allowed_transition, transition,
};

/// All 8 states in canonical (position 1..8) order.
const ALL_STATES: [ContinuityState; 8] = [
    ContinuityState::Active,
    ContinuityState::Paused,
    ContinuityState::Hibernated,
    ContinuityState::Checkpointed,
    ContinuityState::Archived,
    ContinuityState::Quarantined,
    ContinuityState::Promoted,
    ContinuityState::RolledBack,
];

/// All 6 primitives (E0464 dump 14710 order).
const ALL_PRIMITIVES: [ContinuityPrimitive; 6] = [
    ContinuityPrimitive::ZfsSnapshots,
    ContinuityPrimitive::PodmanCriu,
    ContinuityPrimitive::WorkflowHibernation,
    ContinuityPrimitive::ContextCompaction,
    ContinuityPrimitive::WarmPools,
    ContinuityPrimitive::SessionResume,
];

/// The stable kebab-case label for a state — identical to how
/// [`ContinuityState`] serializes to JSON (kept honest by the
/// `state_label_matches_serde` test).
fn state_label(state: ContinuityState) -> &'static str {
    match state {
        ContinuityState::Active => "active",
        ContinuityState::Paused => "paused",
        ContinuityState::Hibernated => "hibernated",
        ContinuityState::Checkpointed => "checkpointed",
        ContinuityState::Archived => "archived",
        ContinuityState::Quarantined => "quarantined",
        ContinuityState::Promoted => "promoted",
        ContinuityState::RolledBack => "rolled-back",
    }
}

/// The stable kebab-case label for a primitive — identical to how
/// [`ContinuityPrimitive`] serializes to JSON (kept honest by the
/// `primitive_label_matches_serde` test).
fn primitive_label(primitive: ContinuityPrimitive) -> &'static str {
    match primitive {
        ContinuityPrimitive::ZfsSnapshots => "zfs-snapshots",
        ContinuityPrimitive::PodmanCriu => "podman-criu",
        ContinuityPrimitive::WorkflowHibernation => "workflow-hibernation",
        ContinuityPrimitive::ContextCompaction => "context-compaction",
        ContinuityPrimitive::WarmPools => "warm-pools",
        ContinuityPrimitive::SessionResume => "session-resume",
    }
}

/// The human-readable reference: the 8 states, the 6 primitives, and the full
/// allowed-transition matrix derived live from [`is_allowed_transition`].
fn reference_text() -> String {
    let mut s = format!(
        "Continuity Manager (M048 Module 8 / E0464 / M00810) — schema {SCHEMA_VERSION}\n\
         The continuity discipline: 8 lifecycle states, 6 primitives, one signed\n\
         transition graph.\n\n\
         8 STATES (position — label — resumable):\n",
    );
    for state in ALL_STATES {
        s.push_str(&format!(
            "  {}. {:<13} {}\n",
            state.position(),
            state_label(state),
            if state.is_resumable() {
                "resumable"
            } else {
                "not-resumable"
            },
        ));
    }

    s.push_str("\n6 PRIMITIVES:\n");
    for (i, primitive) in ALL_PRIMITIVES.into_iter().enumerate() {
        s.push_str(&format!("  {}. {}\n", i + 1, primitive_label(primitive)));
    }

    s.push_str("\nALLOWED TRANSITIONS (from → to, per is_allowed_transition):\n");
    for from in ALL_STATES {
        let targets: Vec<&str> = ALL_STATES
            .into_iter()
            .filter(|&to| is_allowed_transition(from, to))
            .map(state_label)
            .collect();
        let list = if targets.is_empty() {
            "(none)".to_string()
        } else {
            targets.join(", ")
        };
        s.push_str(&format!("  {:<13} → {}\n", state_label(from), list));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-continuity-manager — the continuity discipline (M048 / E0464 / M00810)\n\n\
     8 lifecycle states, 6 primitives, one signed transition graph.\n\n\
     USAGE:\n\
     \x20   sovereign-continuity-manager                 print states, primitives & transition matrix\n\
     \x20   sovereign-continuity-manager --check FILE     validate transition request(s) from JSON\n\
     \x20   sovereign-continuity-manager --help           print this help and exit\n\n\
     --check FILE loads a single transition request or a JSON array of them and\n\
     runs the library's transition() on each. A request is:\n\
     \x20   { \"from\": <state>, \"to\": <state>, \"signature\": <str>,\n\
     \x20     \"primitive\": <primitive|null>, \"at\": <iso-8601> }\n\
     states are kebab-case (active, paused, hibernated, checkpointed, archived,\n\
     quarantined, promoted, rolled-back). A move is rejected when the graph\n\
     forbids it or the signature is empty (MS003). Exits non-zero if any fail.\n"
        .to_string()
}

/// A transition request read from `--check` JSON: exactly the arguments the
/// library's [`transition`] function consumes, with `from` standing in for the
/// record's current state.
#[derive(Debug, Clone, Deserialize)]
struct TransitionRequest {
    /// The record's current state (the move's origin).
    from: ContinuityState,
    /// The desired target state.
    to: ContinuityState,
    /// The primitive applied by this move (audit trail); optional.
    #[serde(default)]
    primitive: Option<ContinuityPrimitive>,
    /// MS003 signature on the transition envelope; empty ⇒ rejected as unsigned.
    #[serde(default)]
    signature: String,
    /// ISO-8601 UTC timestamp recorded on the move; optional.
    #[serde(default)]
    at: String,
}

/// The outcome of checking one transition request.
struct CheckOutcome {
    /// The origin state.
    from: ContinuityState,
    /// The target state.
    to: ContinuityState,
    /// The result of running the real [`transition`] on the request.
    result: Result<(), ContinuityError>,
}

/// Accept either a single request object or a JSON array of them.
fn parse_requests(json: &str) -> Result<Vec<TransitionRequest>, serde_json::Error> {
    match serde_json::from_str::<Vec<TransitionRequest>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single request object, surfacing that error.
        Err(_) => serde_json::from_str::<TransitionRequest>(json).map(|r| vec![r]),
    }
}

/// Parse one-or-many requests from JSON and run the library's [`transition`] on
/// each, capturing the real result (Ok or the [`ContinuityError`]).
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let requests = parse_requests(json)?;
    Ok(requests
        .into_iter()
        .map(|req| {
            let mut rec = SessionRecord {
                session_id: "continuity-check".to_string(),
                state: req.from,
                last_primitive: None,
                last_transition_at: String::new(),
                signature: String::new(),
            };
            let result = transition(&mut rec, req.to, req.primitive, &req.signature, &req.at);
            CheckOutcome {
                from: req.from,
                to: req.to,
                result,
            }
        })
        .collect())
}

/// `--check FILE`: read the file, run each transition, print a report, and
/// return a process exit code (non-zero on read/parse error or any illegal or
/// unsigned move).
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
            eprintln!("error: {path} is not a transition request (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no transition requests in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let from = state_label(o.from);
        let to = state_label(o.to);
        match &o.result {
            Ok(()) => println!("OK   {from} → {to}"),
            Err(err) => {
                all_ok = false;
                println!("FAIL {from} → {to} — {err}");
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
    fn reference_lists_all_states_and_primitives() {
        let t = reference_text();
        for s in ALL_STATES {
            assert!(
                t.contains(state_label(s)),
                "reference missing state {s:?}:\n{t}"
            );
        }
        for p in ALL_PRIMITIVES {
            assert!(
                t.contains(primitive_label(p)),
                "reference missing primitive {p:?}:\n{t}"
            );
        }
        // Positions 1..8 must all appear, one numbered state line each.
        for pos in 1..=8u8 {
            assert!(t.contains(&format!("  {pos}. ")), "missing position {pos}");
        }
    }

    #[test]
    fn state_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for s in ALL_STATES {
            let json = serde_json::to_string(&s).unwrap();
            assert_eq!(json, format!("\"{}\"", state_label(s)));
        }
    }

    #[test]
    fn primitive_label_matches_serde() {
        for p in ALL_PRIMITIVES {
            let json = serde_json::to_string(&p).unwrap();
            assert_eq!(json, format!("\"{}\"", primitive_label(p)));
        }
    }

    #[test]
    fn check_accepts_legal_signed_move() {
        let json = r#"{"from":"active","to":"hibernated","signature":"ms003","primitive":"podman-criu","at":"2026-05-19T00:00:00Z"}"#;
        let outcomes = check_json(json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].from, ContinuityState::Active);
        assert_eq!(outcomes[0].to, ContinuityState::Hibernated);
        assert!(outcomes[0].result.is_ok());
    }

    #[test]
    fn check_rejects_illegal_move() {
        // Promoted → Quarantined must route through Active first.
        let json = r#"{"from":"promoted","to":"quarantined","signature":"ms003"}"#;
        let outcomes = check_json(json).unwrap();
        assert!(matches!(
            outcomes[0].result,
            Err(ContinuityError::InvalidTransition { .. })
        ));
    }

    #[test]
    fn check_rejects_unsigned_move() {
        // Legal graph move, but no signature ⇒ MS003 rejection.
        let json = r#"{"from":"active","to":"paused"}"#;
        let outcomes = check_json(json).unwrap();
        assert!(matches!(outcomes[0].result, Err(ContinuityError::Unsigned)));
    }

    #[test]
    fn check_parses_array_of_requests() {
        let json = r#"[
            {"from":"active","to":"paused","signature":"s"},
            {"from":"promoted","to":"quarantined","signature":"s"}
        ]"#;
        let outcomes = check_json(json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes[0].result.is_ok());
        assert!(outcomes[1].result.is_err());
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }

    #[test]
    fn help_mentions_check_and_states() {
        let h = help_text();
        assert!(h.contains("--check"));
        assert!(h.contains("rolled-back"));
    }
}
