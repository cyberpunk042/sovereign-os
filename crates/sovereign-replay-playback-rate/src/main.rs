//! `sovereign-replay-playback-rate` CLI — the runnable end of the cockpit's
//! replay playback speed control.
//!
//! The library fixes 6 discrete operator-selectable rates (0.25x / 0.5x / 1x /
//! 2x / 4x / 8x) and the timing semantics: when advancing the replay cursor the
//! cockpit divides the wall-time interval between two turns by the rate's
//! multiplier. So at 8x the cursor advances in 1/8th of the recorded wall time;
//! at 0.25x it lingers 4x as long. The library models the rates and the walk
//! (faster / slower / reset), but nothing *ran* it — "how long does a 1000 ms
//! gap take at 4x?" and "is this persisted rate-state on-schema?" were
//! unanswerable at the command line. This binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — print the 6 canonical rates (label + speed +
//!     wall-time factor) as a human-readable reference. With `--interval MS`
//!     each line also shows the real advance interval for that wall gap.
//!   * `--rate NAME` — report one rate's multiplier, wall-time factor, and its
//!     faster/slower neighbours; with `--interval MS`, the advance interval too.
//!   * `--check FILE` — load a `PlaybackRateState` (or a JSON array of them),
//!     `validate()` each against the schema, report OK / the `PlaybackError`,
//!     and exit non-zero if any fail.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_replay_playback_rate::{
    PlaybackError, PlaybackRate, PlaybackRateState, SCHEMA_VERSION,
};

/// The stable kebab-case label for a rate — identical to how [`PlaybackRate`]
/// serializes to JSON (kept honest by the `rate_label_matches_serde` test).
fn rate_label(rate: PlaybackRate) -> &'static str {
    match rate {
        PlaybackRate::Quarter => "quarter",
        PlaybackRate::Half => "half",
        PlaybackRate::Normal => "normal",
        PlaybackRate::Double => "double",
        PlaybackRate::Quadruple => "quadruple",
        PlaybackRate::Octuple => "octuple",
    }
}

/// The human-facing speed label ("0.25x", "1x", "8x"), derived from the real
/// multiplier so it can never drift from it.
fn speed_label(rate: PlaybackRate) -> String {
    format!("{}x", rate.multiplier())
}

/// The wall-time factor: how much recorded wall time one cursor advance consumes
/// relative to real time. It is exactly `1 / multiplier` — the inverse of the
/// speed. At 8x an advance takes 0.125x wall time; at 0.25x it takes 4x.
fn wall_factor(rate: PlaybackRate) -> f64 {
    1.0 / f64::from(rate.multiplier())
}

/// The real advance interval for a `wall_ms` gap at this rate: the cockpit
/// divides the wall-time interval by the multiplier, so `wall_ms / multiplier`.
fn advance_interval_ms(rate: PlaybackRate, wall_ms: f64) -> f64 {
    wall_ms / f64::from(rate.multiplier())
}

/// The human-readable reference: the 6 rates every cockpit exposes. When
/// `interval` is `Some(ms)`, each line also carries the real advance interval
/// for that wall-time gap.
fn reference_text(interval: Option<f64>) -> String {
    let mut s = format!(
        "Cockpit replay playback rates (schema {SCHEMA_VERSION}): 6 discrete \
         operator-selectable speeds.\nThe replay cursor advances at \
         wall-interval / multiplier between turns.\n\n",
    );
    for (i, rate) in PlaybackRate::ALL.into_iter().enumerate() {
        let base = format!(
            "  {}. {:<10} {:<7} {:.3}x wall-time per advance",
            i + 1,
            rate_label(rate),
            speed_label(rate),
            wall_factor(rate),
        );
        match interval {
            Some(ms) => s.push_str(&format!(
                "{base}   advance {:.2} ms (from {:.2} ms wall gap)\n",
                advance_interval_ms(rate, ms),
                ms,
            )),
            None => {
                s.push_str(&base);
                s.push('\n');
            }
        }
    }
    s
}

/// A one-line description of a neighbour rate (or "—" at a bound).
fn neighbour(rate: Option<PlaybackRate>) -> String {
    match rate {
        Some(r) => format!("{} ({})", rate_label(r), speed_label(r)),
        None => "— (at bound)".to_string(),
    }
}

/// `--rate NAME`: report one rate's real properties.
fn rate_report(rate: PlaybackRate, interval: Option<f64>) -> String {
    let mut s = format!(
        "rate:         {}\n\
         speed:        {}\n\
         multiplier:   {}\n\
         wall factor:  {:.3}x wall-time per cursor advance\n\
         faster:       {}\n\
         slower:       {}\n",
        rate_label(rate),
        speed_label(rate),
        rate.multiplier(),
        wall_factor(rate),
        neighbour(rate.faster()),
        neighbour(rate.slower()),
    );
    if let Some(ms) = interval {
        s.push_str(&format!(
            "advance:      {:.2} ms (from {:.2} ms wall gap)\n",
            advance_interval_ms(rate, ms),
            ms,
        ));
    }
    s
}

/// The outcome of checking one persisted rate-state.
struct CheckOutcome {
    /// The state's rate label.
    label: &'static str,
    /// The state's speed label.
    speed: String,
    /// The schema-validation result.
    result: Result<(), PlaybackError>,
}

/// Accept either a single state object or a JSON array of them.
fn parse_states(json: &str) -> Result<Vec<PlaybackRateState>, serde_json::Error> {
    match serde_json::from_str::<Vec<PlaybackRateState>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single state object, surfacing that error.
        Err(_) => serde_json::from_str::<PlaybackRateState>(json).map(|s| vec![s]),
    }
}

/// Parse one-or-many states from JSON and `validate()` each.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let states = parse_states(json)?;
    Ok(states
        .into_iter()
        .map(|s| CheckOutcome {
            label: rate_label(s.rate),
            speed: speed_label(s.rate),
            result: s.validate(),
        })
        .collect())
}

/// `--check FILE`: read the file, validate the state(s), print a report, and
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
            eprintln!("error: {path} is not a PlaybackRateState (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no states in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let (label, speed) = (o.label, &o.speed);
        match &o.result {
            Ok(()) => println!("OK   {label} [{speed}] — on schema {SCHEMA_VERSION}"),
            Err(err) => {
                all_ok = false;
                println!("FAIL {label} [{speed}] — {err}");
            }
        }
    }

    if all_ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-replay-playback-rate — cockpit replay playback speed control\n\n\
     6 discrete rates: 0.25x / 0.5x / 1x (default) / 2x / 4x / 8x. The replay\n\
     cursor advances at wall-interval / multiplier between turns.\n\n\
     USAGE:\n\
     \x20   sovereign-replay-playback-rate                 print the 6 rates (reference)\n\
     \x20   sovereign-replay-playback-rate --rate NAME     report one rate's properties\n\
     \x20   sovereign-replay-playback-rate --check FILE    validate PlaybackRateState(s) (JSON)\n\
     \x20   sovereign-replay-playback-rate --interval MS   add advance intervals for an MS gap\n\
     \x20   sovereign-replay-playback-rate --help          print this help and exit\n\n\
     NAME is one of: quarter half normal double quadruple octuple.\n\
     --interval MS combines with the reference listing or with --rate NAME.\n\
     --check FILE loads a single PlaybackRateState object or a JSON array of them,\n\
     runs validate() on each, and exits non-zero if any is off-schema.\n"
        .to_string()
}

/// Parse a rate NAME via the crate's own serde form, so the accepted spellings
/// can never drift from the enum's kebab-case labels.
fn parse_rate(name: &str) -> Option<PlaybackRate> {
    serde_json::from_str::<PlaybackRate>(&format!("\"{name}\"")).ok()
}

/// Pull an optional `--interval MS` value out of the args, validating it is a
/// finite, non-negative number. Returns `Ok(None)` when absent.
fn interval_arg(args: &[String]) -> Result<Option<f64>, String> {
    let Some(i) = args.iter().position(|a| a == "--interval") else {
        return Ok(None);
    };
    let Some(raw) = args.get(i + 1) else {
        return Err("--interval requires an MS argument".to_string());
    };
    match raw.parse::<f64>() {
        Ok(ms) if ms.is_finite() && ms >= 0.0 => Ok(Some(ms)),
        _ => Err(format!(
            "--interval MS must be a non-negative number, got '{raw}'"
        )),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    let interval = match interval_arg(&args) {
        Ok(v) => v,
        Err(msg) => {
            eprintln!("error: {msg}\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        }
    };

    if let Some(i) = args.iter().position(|a| a == "--check") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --check requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_check(path);
    }

    if let Some(i) = args.iter().position(|a| a == "--rate") {
        let Some(name) = args.get(i + 1) else {
            eprintln!("error: --rate requires a NAME argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        let Some(rate) = parse_rate(name) else {
            eprintln!(
                "error: unknown rate '{name}' — expected one of: quarter half normal double quadruple octuple\n"
            );
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        print!("{}", rate_report(rate, interval));
        return ExitCode::SUCCESS;
    }

    // Reject unknown flags, but let --interval's own value through.
    let interval_val = args
        .iter()
        .position(|a| a == "--interval")
        .and_then(|i| args.get(i + 1).cloned());
    if let Some(unknown) = args.iter().find(|a| {
        a.starts_with('-') && a.as_str() != "--interval" && Some((*a).clone()) != interval_val
    }) {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    print!("{}", reference_text(interval));
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reference_lists_all_six_rates() {
        let t = reference_text(None);
        for r in PlaybackRate::ALL {
            assert!(t.contains(rate_label(r)), "reference missing {r:?}:\n{t}");
            assert!(
                t.contains(&speed_label(r)),
                "reference missing speed for {r:?}:\n{t}"
            );
        }
        // Exactly six numbered "  N. " entries — one per rate, no more.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(numbered, PlaybackRate::ALL.len(), "expected 6 rate lines");
    }

    #[test]
    fn rate_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for r in PlaybackRate::ALL {
            let json = serde_json::to_string(&r).unwrap();
            assert_eq!(json, format!("\"{}\"", rate_label(r)));
        }
    }

    #[test]
    fn speed_label_is_clean() {
        assert_eq!(speed_label(PlaybackRate::Quarter), "0.25x");
        assert_eq!(speed_label(PlaybackRate::Half), "0.5x");
        assert_eq!(speed_label(PlaybackRate::Normal), "1x");
        assert_eq!(speed_label(PlaybackRate::Octuple), "8x");
    }

    #[test]
    fn advance_interval_divides_by_multiplier() {
        // 1000 ms wall gap: 0.25x lingers to 4000 ms, 8x compresses to 125 ms,
        // 1x is unchanged.
        assert!((advance_interval_ms(PlaybackRate::Quarter, 1000.0) - 4000.0).abs() < 1e-6);
        assert!((advance_interval_ms(PlaybackRate::Normal, 1000.0) - 1000.0).abs() < 1e-6);
        assert!((advance_interval_ms(PlaybackRate::Octuple, 1000.0) - 125.0).abs() < 1e-6);
    }

    #[test]
    fn wall_factor_is_inverse_of_multiplier() {
        for r in PlaybackRate::ALL {
            let product = wall_factor(r) * f64::from(r.multiplier());
            assert!((product - 1.0).abs() < 1e-6, "{r:?}: factor*mult != 1");
        }
    }

    #[test]
    fn parse_rate_roundtrips_and_rejects_garbage() {
        for r in PlaybackRate::ALL {
            assert_eq!(parse_rate(rate_label(r)), Some(r));
        }
        assert_eq!(parse_rate("triple"), None);
        assert_eq!(parse_rate("2x"), None);
        assert_eq!(parse_rate(""), None);
    }

    #[test]
    fn rate_report_shows_neighbours_and_advance() {
        let t = rate_report(PlaybackRate::Double, Some(1000.0));
        assert!(t.contains("double"));
        assert!(t.contains("quadruple (4x)")); // faster neighbour
        assert!(t.contains("normal (1x)")); // slower neighbour
        assert!(t.contains("500.00 ms")); // 1000 / 2
    }

    #[test]
    fn rate_report_marks_bounds() {
        let fastest = rate_report(PlaybackRate::Octuple, None);
        assert!(fastest.contains("faster:       — (at bound)"));
        let slowest = rate_report(PlaybackRate::Quarter, None);
        assert!(slowest.contains("slower:       — (at bound)"));
    }

    #[test]
    fn check_accepts_valid_default_state() {
        let json = serde_json::to_string(&PlaybackRateState::default_state()).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].label, "normal");
        assert!(outcomes[0].result.is_ok());
    }

    #[test]
    fn check_rejects_schema_drift() {
        let json = r#"{"schema_version":"9.9.9","rate":"double"}"#;
        let outcomes = check_json(json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].label, "double");
        assert!(matches!(
            outcomes[0].result,
            Err(PlaybackError::SchemaMismatch)
        ));
    }

    #[test]
    fn check_parses_array_of_states() {
        let arr = vec![
            PlaybackRateState::default_state(),
            PlaybackRateState {
                schema_version: SCHEMA_VERSION.to_string(),
                rate: PlaybackRate::Octuple,
            },
        ];
        let json = serde_json::to_string(&arr).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert_eq!(outcomes[1].label, "octuple");
        assert!(outcomes.iter().all(|o| o.result.is_ok()));
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }

    #[test]
    fn interval_arg_parses_and_validates() {
        assert_eq!(
            interval_arg(&["--interval".into(), "250".into()]).unwrap(),
            Some(250.0)
        );
        assert_eq!(
            interval_arg(&["--rate".into(), "normal".into()]).unwrap(),
            None
        );
        assert!(interval_arg(&["--interval".into(), "-5".into()]).is_err());
        assert!(interval_arg(&["--interval".into(), "abc".into()]).is_err());
        assert!(interval_arg(&["--interval".into()]).is_err());
    }
}
