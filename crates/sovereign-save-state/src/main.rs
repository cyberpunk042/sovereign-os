//! `sovereign-save-state` CLI — the runnable end of E0451.
//!
//! The library fixes the five layers of a TRUE agent save-state (ZFS snapshot +
//! CRIU checkpoint + replay log + memory record + profile state) and the
//! completeness gate that keeps a partial capture from being mistaken for a true
//! one. But nothing *ran* it, so "is this captured save-state actually complete?"
//! was unanswerable at the command line. This binary is that runnable end — and
//! it does real work without the live persistence backend: it never touches ZFS
//! or CRIU, it checks the *record* of what was captured against the model's
//! invariants and the completeness gate.
//!
//! Modes:
//!   * default (no args) — print the 5 canonical save-state layers (label +
//!     description) as a human-readable reference: the save-state schema itself.
//!   * `--check FILE` — load a [`SaveState`] (or a JSON array of them), verify the
//!     serde round-trip and the model invariants, report whether each is a TRUE
//!     save-state or which layers are missing, and exit non-zero if any is
//!     incomplete or malformed.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_save_state::{SaveLayer, SaveState};

/// The stable kebab-case label for a layer — identical to how [`SaveLayer`]
/// serializes to JSON (kept honest by the `layer_label_matches_serde` test).
fn layer_label(layer: SaveLayer) -> &'static str {
    match layer {
        SaveLayer::ZfsSnapshot => "zfs-snapshot",
        SaveLayer::CriuCheckpoint => "criu-checkpoint",
        SaveLayer::ReplayLog => "replay-log",
        SaveLayer::MemoryRecord => "memory-record",
        SaveLayer::ProfileState => "profile-state",
    }
}

/// A one-line human description of what each layer contributes to the whole.
fn layer_description(layer: SaveLayer) -> &'static str {
    match layer {
        SaveLayer::ZfsSnapshot => "files + repo + caches + artifacts (filesystem truth)",
        SaveLayer::CriuCheckpoint => "running process / container state",
        SaveLayer::ReplayLog => "why the state exists",
        SaveLayer::MemoryRecord => "what was learned",
        SaveLayer::ProfileState => "what permissions and budgets apply",
    }
}

/// The human-readable reference: the 5 layers every TRUE save-state must hold.
fn reference_text() -> String {
    let mut s = String::from(
        "The 5-layer agent save-state (E0451): a TRUE save-state requires ALL 5 layers.\n\n",
    );
    for (i, layer) in SaveLayer::ALL.into_iter().enumerate() {
        s.push_str(&format!(
            "  {}. {:<16} {}\n",
            i + 1,
            layer_label(layer),
            layer_description(layer),
        ));
    }
    s.push_str("\nMissing any one layer -> restorable, but NOT a true agent save-state.\n");
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-save-state — the 5-layer agent save-state (E0451)\n\n\
     A TRUE agent save-state requires all 5 layers: a ZFS snapshot, a CRIU\n\
     checkpoint, the replay log, the memory record, and the profile state.\n\n\
     USAGE:\n\
     \x20   sovereign-save-state                 print the 5 save-state layers (reference)\n\
     \x20   sovereign-save-state --check FILE     validate SaveState(s) from JSON\n\
     \x20   sovereign-save-state --help           print this help and exit\n\n\
     --check FILE loads a single SaveState object or a JSON array of them,\n\
     verifies the serde round-trip and the model invariants, reports whether\n\
     each is a TRUE save-state (all 5 layers) or which layers are missing, and\n\
     exits non-zero if any is incomplete or malformed.\n"
        .to_string()
}

/// The outcome of checking one save-state record.
struct CheckOutcome {
    /// 1-based position of this record in the input (single object => 1).
    index: usize,
    /// Whether the serde round-trip is lossless (`state == deser(ser(state))`).
    roundtrip_ok: bool,
    /// Whether the model's internal invariants hold for this record.
    invariant_ok: bool,
    /// Whether this record is a TRUE save-state (all 5 layers captured).
    true_save_state: bool,
    /// The layers still missing for a true save-state (empty iff true).
    missing: Vec<SaveLayer>,
}

impl CheckOutcome {
    /// A record passes only if it round-trips, upholds the invariants, and is a
    /// complete (true) save-state — the completeness gate.
    fn passed(&self) -> bool {
        self.roundtrip_ok && self.invariant_ok && self.true_save_state
    }
}

/// The serde round-trip must be lossless: serializing a state and reading it
/// back must yield an equal state. This exercises the real `Serialize` /
/// `Deserialize` path on the crate's own types.
fn roundtrips(state: &SaveState) -> bool {
    match serde_json::to_string(state) {
        Ok(json) => matches!(serde_json::from_str::<SaveState>(&json), Ok(back) if &back == state),
        Err(_) => false,
    }
}

/// The model's cross-method invariants that must hold for every save-state:
///   * `has(l)` is true exactly for the layers NOT in `missing_layers()`;
///   * captured + missing layer counts sum to the full layer set;
///   * `is_true_save_state()` is true exactly when nothing is missing.
fn invariant_holds(state: &SaveState) -> bool {
    let missing = state.missing_layers();
    let has_matches_missing = SaveLayer::ALL
        .into_iter()
        .all(|l| state.has(l) != missing.contains(&l));
    let captured = SaveLayer::ALL.into_iter().filter(|l| state.has(*l)).count();
    let counts_sum = captured + missing.len() == SaveLayer::ALL.len();
    let gate_agrees = state.is_true_save_state() == missing.is_empty();
    has_matches_missing && counts_sum && gate_agrees
}

/// Run all checks against one save-state record.
fn check_state(index: usize, state: &SaveState) -> CheckOutcome {
    CheckOutcome {
        index,
        roundtrip_ok: roundtrips(state),
        invariant_ok: invariant_holds(state),
        true_save_state: state.is_true_save_state(),
        missing: state.missing_layers(),
    }
}

/// Accept either a single save-state object or a JSON array of them.
fn parse_states(json: &str) -> Result<Vec<SaveState>, serde_json::Error> {
    match serde_json::from_str::<Vec<SaveState>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single save-state object, surfacing that error.
        Err(_) => serde_json::from_str::<SaveState>(json).map(|s| vec![s]),
    }
}

/// Parse one-or-many save-states from JSON and check each.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let states = parse_states(json)?;
    Ok(states
        .iter()
        .enumerate()
        .map(|(i, s)| check_state(i + 1, s))
        .collect())
}

/// Format the missing layers as a comma-separated list of their labels.
fn missing_labels(missing: &[SaveLayer]) -> String {
    missing
        .iter()
        .map(|l| layer_label(*l))
        .collect::<Vec<_>>()
        .join(", ")
}

/// `--check FILE`: read the file, check the save-state(s), print a report, and
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
            eprintln!("error: {path} is not a SaveState (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no save-states in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        all_ok &= o.passed();
        let n = o.index;
        if !o.roundtrip_ok {
            println!("FAIL #{n} — serde round-trip is lossy");
        } else if !o.invariant_ok {
            println!("FAIL #{n} — model invariants violated");
        } else if o.true_save_state {
            println!("OK   #{n} — TRUE save-state (all 5 layers captured)");
        } else {
            println!(
                "FAIL #{n} — INCOMPLETE: missing {} layer(s): {}",
                o.missing.len(),
                missing_labels(&o.missing),
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

    /// A save-state with exactly the given layers captured.
    fn state_with(layers: &[SaveLayer]) -> SaveState {
        let mut s = SaveState::new();
        for l in layers {
            s.capture(*l);
        }
        s
    }

    /// A complete (true) save-state — all 5 layers captured.
    fn complete() -> SaveState {
        state_with(&SaveLayer::ALL)
    }

    #[test]
    fn reference_lists_all_five_layers() {
        let t = reference_text();
        for l in SaveLayer::ALL {
            assert!(t.contains(layer_label(l)), "reference missing {l:?}:\n{t}");
            assert!(
                t.contains(layer_description(l)),
                "reference missing description for {l:?}:\n{t}"
            );
        }
        // Exactly five numbered "  N. " entries — one per layer, no more.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(numbered, SaveLayer::ALL.len(), "expected 5 layer lines");
    }

    #[test]
    fn layer_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for l in SaveLayer::ALL {
            let json = serde_json::to_string(&l).unwrap();
            assert_eq!(json, format!("\"{}\"", layer_label(l)));
        }
    }

    #[test]
    fn check_accepts_true_save_state() {
        let json = serde_json::to_string(&complete()).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(outcomes[0].passed());
        assert!(outcomes[0].true_save_state);
        assert!(outcomes[0].missing.is_empty());
    }

    #[test]
    fn check_rejects_zfs_plus_criu_alone() {
        // The classic partial: files + process, but no replay/memory/profile.
        let s = state_with(&[SaveLayer::ZfsSnapshot, SaveLayer::CriuCheckpoint]);
        let json = serde_json::to_string(&s).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(
            !outcomes[0].passed(),
            "incomplete state must not pass the gate"
        );
        assert!(!outcomes[0].true_save_state);
        assert!(outcomes[0].roundtrip_ok && outcomes[0].invariant_ok);
        for wanted in [
            SaveLayer::ReplayLog,
            SaveLayer::MemoryRecord,
            SaveLayer::ProfileState,
        ] {
            assert!(outcomes[0].missing.contains(&wanted));
        }
    }

    #[test]
    fn check_parses_array_mixed() {
        let arr = vec![complete(), state_with(&[SaveLayer::ProfileState])];
        let json = serde_json::to_string(&arr).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes[0].passed());
        assert!(!outcomes[1].passed());
        assert_eq!(outcomes[1].missing.len(), 4);
    }

    #[test]
    fn roundtrip_and_invariants_hold_for_all_shapes() {
        for state in [
            SaveState::new(),
            state_with(&[SaveLayer::ZfsSnapshot]),
            state_with(&[SaveLayer::ZfsSnapshot, SaveLayer::CriuCheckpoint]),
            complete(),
        ] {
            assert!(roundtrips(&state), "round-trip failed for {state:?}");
            assert!(invariant_holds(&state), "invariant failed for {state:?}");
        }
    }

    #[test]
    fn empty_object_is_rejected_as_error() {
        // `captured` is a required field: an empty object is malformed JSON model.
        assert!(check_json("{}").is_err());
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }
}
