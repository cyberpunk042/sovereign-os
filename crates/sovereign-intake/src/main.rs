//! `sovereign-intake` CLI — the runnable end of E0549 (Step 1 Intake).
//!
//! The library fixes the first step of the task lifecycle: a request can arrive
//! from any of ten [`TaskSource`]s, and the gateway stamps six fields on every
//! [`IntakeRequest`] (request_id / trace_id / client_id / profile_hint /
//! privacy_context / budget_hint). It also fixes what a *malformed* intake is:
//! [`IntakeRequest::has_identity`] — a request the gateway MUST reject unless it
//! carries a non-empty request_id AND client_id. But nothing *ran* it, so "would
//! the gateway accept this intake?" was unanswerable at the command line. This
//! binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — print the reference: the 10 task sources, the 3
//!     privacy contexts, and the 6 fields the gateway stamps per request.
//!   * `--check FILE` — load an [`IntakeRequest`] (or a JSON array of them), run
//!     [`IntakeRequest::has_identity`] on each, report OK / MALFORMED, and exit
//!     non-zero if any lacks required identity (or the file cannot be parsed).
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_intake::{IntakeRequest, PrivacyContext, TaskSource};

/// The stable kebab-case label for a task source — identical to how
/// [`TaskSource`] serializes to JSON (kept honest by the
/// `source_label_matches_serde` test).
fn source_label(source: TaskSource) -> &'static str {
    match source {
        TaskSource::ClaudeCode => "claude-code",
        TaskSource::Cline => "cline",
        TaskSource::OpenCode => "open-code",
        TaskSource::LocalDashboard => "local-dashboard",
        TaskSource::Cli => "cli",
        TaskSource::Mcp => "mcp",
        TaskSource::Api => "api",
        TaskSource::ScheduledAutomation => "scheduled-automation",
        TaskSource::FileWatcher => "file-watcher",
        TaskSource::HumanVoiceText => "human-voice-text",
    }
}

/// A one-line human description of each task source.
fn source_description(source: TaskSource) -> &'static str {
    match source {
        TaskSource::ClaudeCode => "Claude Code",
        TaskSource::Cline => "Cline",
        TaskSource::OpenCode => "OpenCode",
        TaskSource::LocalDashboard => "the local cockpit dashboard",
        TaskSource::Cli => "the CLI",
        TaskSource::Mcp => "an MCP client",
        TaskSource::Api => "the HTTP API",
        TaskSource::ScheduledAutomation => "scheduled automation (timer/cron)",
        TaskSource::FileWatcher => "a file watcher",
        TaskSource::HumanVoiceText => "human voice/text (later)",
    }
}

/// The three privacy contexts a request can arrive under.
const PRIVACY_CONTEXTS: [PrivacyContext; 3] = [
    PrivacyContext::Public,
    PrivacyContext::Private,
    PrivacyContext::LocalOnly,
];

/// The stable kebab-case label for a privacy context — identical to how
/// [`PrivacyContext`] serializes to JSON (kept honest by the
/// `privacy_label_matches_serde` test).
fn privacy_label(ctx: PrivacyContext) -> &'static str {
    match ctx {
        PrivacyContext::Public => "public",
        PrivacyContext::Private => "private",
        PrivacyContext::LocalOnly => "local-only",
    }
}

/// A one-line human description of each privacy context.
fn privacy_description(ctx: PrivacyContext) -> &'static str {
    match ctx {
        PrivacyContext::Public => "no special handling",
        PrivacyContext::Private => "keep local; cloud allowed with care",
        PrivacyContext::LocalOnly => "never leaves the host",
    }
}

/// The six fields the gateway stamps on every intake, in the library's order.
const STAMPED_FIELDS: [(&str, &str); 6] = [
    ("request_id", "unique per request"),
    ("trace_id", "the E0112 trace this request opens"),
    ("client_id", "the originating client"),
    (
        "profile_hint",
        "a suggested operating profile (resolved later)",
    ),
    (
        "privacy_context",
        "public / private / local-only (refined by the E0473 policy fabric)",
    ),
    ("budget_hint", "a suggested spend ceiling in USD"),
];

/// The human-readable reference: the 10 sources, 3 privacy contexts, and the 6
/// fields the gateway stamps per request.
fn reference_text() -> String {
    let mut s = String::from(
        "Step 1 Intake (E0549): a task can arrive from any of 10 sources, and the\n\
         gateway stamps 6 fields on every request so the rest of the lifecycle has\n\
         a stable, typed handle from the very start.\n\n",
    );

    s.push_str("The 10 task sources:\n");
    for (i, source) in TaskSource::ALL.into_iter().enumerate() {
        s.push_str(&format!(
            "  {:>2}. {:<20} {}\n",
            i + 1,
            source_label(source),
            source_description(source),
        ));
    }

    s.push_str("\nThe 3 privacy contexts:\n");
    for ctx in PRIVACY_CONTEXTS {
        s.push_str(&format!(
            "  - {:<20} {}\n",
            privacy_label(ctx),
            privacy_description(ctx),
        ));
    }

    s.push_str("\nThe 6 fields the gateway stamps per request:\n");
    for (i, (name, desc)) in STAMPED_FIELDS.into_iter().enumerate() {
        s.push_str(&format!("  {}. {:<16} {}\n", i + 1, name, desc));
    }

    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-intake — Step 1 Intake of the task lifecycle (E0549)\n\n\
     A task can arrive from any of 10 sources; the gateway stamps 6 fields on\n\
     every request (request_id / trace_id / client_id / profile_hint /\n\
     privacy_context / budget_hint). An intake without a non-empty request_id\n\
     AND client_id is malformed and must be rejected.\n\n\
     USAGE:\n\
     \x20   sovereign-intake                 print the 10 sources & 6 stamped fields (reference)\n\
     \x20   sovereign-intake --check FILE     validate IntakeRequest(s) from JSON\n\
     \x20   sovereign-intake --help           print this help and exit\n\n\
     --check FILE loads a single IntakeRequest object or a JSON array of them,\n\
     runs has_identity() on each (non-empty request_id AND client_id), reports\n\
     each as OK or MALFORMED, and exits non-zero if any is malformed.\n"
        .to_string()
}

/// The outcome of checking one intake request.
struct CheckOutcome {
    /// The request's `request_id` (as received — may be blank/whitespace).
    request_id: String,
    /// The source the request claims to have arrived from.
    source: TaskSource,
    /// Whether the request carries the required identity (`has_identity()`).
    has_identity: bool,
}

/// Accept either a single intake request object or a JSON array of them.
fn parse_requests(json: &str) -> Result<Vec<IntakeRequest>, serde_json::Error> {
    match serde_json::from_str::<Vec<IntakeRequest>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single request object, surfacing that error.
        Err(_) => serde_json::from_str::<IntakeRequest>(json).map(|r| vec![r]),
    }
}

/// Parse one-or-many intake requests from JSON and check each for identity.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let requests = parse_requests(json)?;
    Ok(requests
        .into_iter()
        .map(|r| CheckOutcome {
            has_identity: r.has_identity(),
            request_id: r.request_id,
            source: r.source,
        })
        .collect())
}

/// `--check FILE`: read the file, check the request(s), print a report, and
/// return a process exit code (non-zero on read/parse error or any malformed
/// intake).
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
            eprintln!("error: {path} is not an IntakeRequest (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no intake requests in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let src = source_label(o.source);
        // Show the request_id, but make blank/whitespace ids visible.
        let id = if o.request_id.trim().is_empty() {
            "(blank)"
        } else {
            &o.request_id
        };
        if o.has_identity {
            println!("OK        [{src}] request_id={id} — required identity present");
        } else {
            all_ok = false;
            println!(
                "MALFORMED [{src}] request_id={id} — missing identity (need non-empty request_id AND client_id)"
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
    use sovereign_trace_context::TraceId;

    /// A well-formed intake request carrying required identity.
    fn valid(source: TaskSource, request_id: &str, client_id: &str) -> IntakeRequest {
        IntakeRequest::new(
            source,
            request_id,
            TraceId(0xfeed),
            client_id,
            PrivacyContext::Private,
        )
    }

    #[test]
    fn source_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for s in TaskSource::ALL {
            let json = serde_json::to_string(&s).unwrap();
            assert_eq!(json, format!("\"{}\"", source_label(s)));
        }
    }

    #[test]
    fn privacy_label_matches_serde() {
        for ctx in PRIVACY_CONTEXTS {
            let json = serde_json::to_string(&ctx).unwrap();
            assert_eq!(json, format!("\"{}\"", privacy_label(ctx)));
        }
    }

    #[test]
    fn reference_lists_all_ten_sources_and_six_fields() {
        let t = reference_text();
        for s in TaskSource::ALL {
            assert!(t.contains(source_label(s)), "reference missing {s:?}:\n{t}");
        }
        for ctx in PRIVACY_CONTEXTS {
            assert!(t.contains(privacy_label(ctx)), "reference missing {ctx:?}");
        }
        for (name, _) in STAMPED_FIELDS {
            assert!(t.contains(name), "reference missing field {name}");
        }
        // Exactly ten numbered source lines.
        let numbered = t
            .lines()
            .filter(|l| {
                let l = l.trim_start();
                l.starts_with(|c: char| c.is_ascii_digit()) && l.contains(". ")
            })
            .count();
        // 10 sources + 6 fields = 16 numbered lines.
        assert_eq!(numbered, TaskSource::ALL.len() + STAMPED_FIELDS.len());
    }

    #[test]
    fn check_accepts_well_formed_request() {
        let json =
            serde_json::to_string(&valid(TaskSource::ClaudeCode, "req-1", "client-a")).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].request_id, "req-1");
        assert_eq!(outcomes[0].source, TaskSource::ClaudeCode);
        assert!(outcomes[0].has_identity);
    }

    #[test]
    fn check_rejects_blank_request_id() {
        // Whitespace request_id — has_identity() must be false.
        let json = serde_json::to_string(&valid(TaskSource::Api, "  ", "client-a")).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(!outcomes[0].has_identity);
    }

    #[test]
    fn check_rejects_empty_client_id() {
        let json = serde_json::to_string(&valid(TaskSource::Cli, "req-2", "")).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert!(!outcomes[0].has_identity);
    }

    #[test]
    fn check_parses_array_of_mixed_validity() {
        let arr = vec![
            valid(TaskSource::FileWatcher, "req-a", "watcher"),
            valid(TaskSource::Mcp, "", "mcp-client"),
        ];
        let json = serde_json::to_string(&arr).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes[0].has_identity);
        assert!(!outcomes[1].has_identity);
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }

    #[test]
    fn help_text_mentions_all_modes() {
        let h = help_text();
        assert!(h.contains("--check"));
        assert!(h.contains("--help"));
        assert!(h.contains("has_identity"));
    }
}
