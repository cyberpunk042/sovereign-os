//! `sovereign-fs-boundary` CLI — the runnable end of E0123 / M00231.
//!
//! The library fixes the Filesystem Boundary: sandboxes never touch host files
//! directly — everything crosses through the explicit exchange directories under
//! `/ai-exchange` ([`ExchangeDir`]), and anything coming IN runs the host
//! import-validation pipeline ([`ImportStep`]) before it is trusted. But nothing
//! *ran* it, so "is this path allowed to cross the boundary?" was unanswerable at
//! the command line. This binary is that runnable end: a pure validate/emit tool
//! that needs no live sandbox.
//!
//! Modes:
//!   * default (no args) — print the boundary model: the 3 exchange directories
//!     with their absolute paths and the 6-step import pipeline. This is the rule
//!     set the decision function enforces.
//!   * `PATH...` — classify each path against the boundary and report whether it
//!     is ALLOWED to cross (and which exchange directory it maps to) or DENIED;
//!     exit non-zero if any path is denied.
//!   * `--check FILE` — load a boundary-query config from JSON (a path string, an
//!     object `{"path": …, "expect": …}`, or an array of either), classify each
//!     path, validate any stated `expect`, and exit non-zero on any failure.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::Deserialize;
use sovereign_fs_boundary::{ExchangeDir, ImportStep};

/// The stable kebab-case leaf label of an exchange directory — identical to how
/// [`ExchangeDir`] serializes to JSON (kept honest by the
/// `dir_leaf_matches_serde` test). This is also the ALLOWED verdict label.
fn dir_label(dir: ExchangeDir) -> &'static str {
    // `ExchangeDir::leaf()` already returns the kebab label; this indirection
    // keeps the CLI's vocabulary in one place and is proven equal by a test.
    dir.leaf()
}

/// The stable kebab-case label of an import-validation step — identical to how
/// [`ImportStep`] serializes to JSON (kept honest by the `step_label_matches_serde`
/// test).
fn step_label(step: ImportStep) -> &'static str {
    match step {
        ImportStep::Parse => "parse",
        ImportStep::Scan => "scan",
        ImportStep::Diff => "diff",
        ImportStep::PolicyCheck => "policy-check",
        ImportStep::OracleReview => "oracle-review",
        ImportStep::Commit => "commit",
    }
}

/// Why a path is refused passage across the boundary.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DenyReason {
    /// The path is relative; boundary paths are absolute under `/ai-exchange`.
    NotAbsolute,
    /// The path traverses above the filesystem root via `..`.
    Traversal,
    /// The path is not under `/ai-exchange` at all — a host file the sandbox may
    /// never touch directly.
    NotUnderExchangeRoot,
    /// The path is under `/ai-exchange` but not one of the three exchange leaves.
    UnknownExchangeLeaf,
}

impl DenyReason {
    /// A one-line human explanation.
    fn explain(self) -> &'static str {
        match self {
            DenyReason::NotAbsolute => {
                "path is not absolute — boundary paths are absolute under /ai-exchange"
            }
            DenyReason::Traversal => "path traverses above the filesystem root via `..`",
            DenyReason::NotUnderExchangeRoot => {
                "not under /ai-exchange — sandboxes never touch host files directly"
            }
            DenyReason::UnknownExchangeLeaf => {
                "under /ai-exchange but not one of inbox/outbox/artifacts"
            }
        }
    }
}

/// The boundary decision for one path.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Verdict {
    /// Allowed to cross — the path lives under this exchange directory.
    Allowed(ExchangeDir),
    /// Refused passage.
    Denied(DenyReason),
}

/// The coarse verdict label used for `expect` comparison: the exchange-dir leaf
/// for an allowed path, or `"denied"` for any denial.
fn verdict_label(v: Verdict) -> &'static str {
    match v {
        Verdict::Allowed(dir) => dir_label(dir),
        Verdict::Denied(_) => "denied",
    }
}

/// A human-readable rendering of a verdict, including the import-validation note
/// for inbound paths.
fn verdict_detail(v: Verdict) -> String {
    match v {
        Verdict::Allowed(ExchangeDir::Inbox) => {
            "ALLOWED [inbox] — inbound: must pass the 6-step import-validation pipeline".to_string()
        }
        Verdict::Allowed(dir) => format!("ALLOWED [{}]", dir_label(dir)),
        Verdict::Denied(reason) => format!("DENIED — {}", reason.explain()),
    }
}

/// Lexically split an absolute path into its real components, resolving `.` and
/// `..`. Returns a [`DenyReason`] when the path is not absolute or `..` escapes
/// above the root — both of which are boundary denials in their own right.
fn normalize(path: &str) -> Result<Vec<&str>, DenyReason> {
    if !path.starts_with('/') {
        return Err(DenyReason::NotAbsolute);
    }
    let mut out: Vec<&str> = Vec::new();
    for comp in path.split('/') {
        match comp {
            // empty (leading `/` or `//`) and `.` contribute nothing
            "" | "." => {}
            ".." => {
                if out.pop().is_none() {
                    return Err(DenyReason::Traversal);
                }
            }
            other => out.push(other),
        }
    }
    Ok(out)
}

/// The boundary decision function: decide whether `path` may cross the boundary.
///
/// A path is ALLOWED iff, after lexical normalization, it lives under one of the
/// three exchange directories (`/ai-exchange/{inbox,outbox,artifacts}`). Anything
/// else is DENIED — host files, unknown exchange leaves, relative paths, and `..`
/// traversal above the root.
fn classify(path: &str) -> Verdict {
    let comps = match normalize(path) {
        Ok(c) => c,
        Err(reason) => return Verdict::Denied(reason),
    };
    match comps.split_first() {
        // "/" itself, or anything not rooted at ai-exchange.
        None => Verdict::Denied(DenyReason::NotUnderExchangeRoot),
        Some((&"ai-exchange", rest)) => match rest.first() {
            // exactly "/ai-exchange" — the root has no crossing point of its own.
            None => Verdict::Denied(DenyReason::UnknownExchangeLeaf),
            Some(leaf) => match ExchangeDir::ALL.into_iter().find(|d| d.leaf() == *leaf) {
                Some(dir) => Verdict::Allowed(dir),
                None => Verdict::Denied(DenyReason::UnknownExchangeLeaf),
            },
        },
        Some(_) => Verdict::Denied(DenyReason::NotUnderExchangeRoot),
    }
}

/// The human-readable reference: the boundary rules the decision function
/// enforces — the exchange directories and the import pipeline.
fn reference_text() -> String {
    let mut s = String::from(
        "The Filesystem Boundary (E0123 / M00231).\n\n\
         Sandboxes never touch host files directly. Everything crosses through the\n\
         explicit exchange directories under /ai-exchange, and anything coming IN is\n\
         run through the host import-validation pipeline before it is trusted.\n\n\
         Exchange directories — a path is ALLOWED to cross iff it lives under one of\n\
         these; every other path is DENIED:\n",
    );
    for (i, dir) in ExchangeDir::ALL.into_iter().enumerate() {
        s.push_str(&format!(
            "  {}. {:<9} {}\n",
            i + 1,
            dir_label(dir),
            dir.path()
        ));
    }
    s.push_str(
        "\nHost import-validation pipeline (applied to inbound /ai-exchange/inbox files):\n",
    );
    for step in ImportStep::ALL {
        let cond = if step.is_conditional() {
            "   (conditional — only if the earlier steps flag it)"
        } else {
            ""
        };
        s.push_str(&format!(
            "  {}. {}{}\n",
            step.position(),
            step_label(step),
            cond
        ));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-fs-boundary — the Filesystem Boundary decision tool (E0123 / M00231)\n\n\
     Sandboxes never touch host files directly: everything crosses through the\n\
     exchange directories /ai-exchange/{inbox,outbox,artifacts}, and inbound files\n\
     run a 6-step import-validation pipeline.\n\n\
     USAGE:\n\
     \x20   sovereign-fs-boundary                 print the boundary model (reference)\n\
     \x20   sovereign-fs-boundary PATH...         classify each path (allowed / denied)\n\
     \x20   sovereign-fs-boundary --check FILE     validate a boundary-query config from JSON\n\
     \x20   sovereign-fs-boundary --help           print this help and exit\n\n\
     PATH... classifies each path against the boundary and exits non-zero if any\n\
     path is DENIED.\n\n\
     --check FILE loads a JSON query config — a path string, an object\n\
     {\"path\": \"…\", \"expect\": \"inbox|outbox|artifacts|denied\"}, or an array of\n\
     either. Each path is classified; when \"expect\" is present it is validated\n\
     against the decision, and the tool exits non-zero on any failure.\n"
        .to_string()
}

/// One query in a `--check` config: a bare path, or a path with an expectation.
#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
enum QueryInput {
    /// A bare path string to classify.
    Path(String),
    /// A path with an optional expected verdict label.
    Spec {
        /// The path to classify.
        path: String,
        /// The expected verdict label (`inbox`/`outbox`/`artifacts`/`denied`).
        #[serde(default)]
        expect: Option<String>,
    },
}

impl QueryInput {
    /// Split into `(path, expected verdict label)`.
    fn into_parts(self) -> (String, Option<String>) {
        match self {
            QueryInput::Path(path) => (path, None),
            QueryInput::Spec { path, expect } => (path, expect),
        }
    }
}

/// The outcome of checking one path.
struct CheckOutcome {
    /// The path that was classified.
    path: String,
    /// The boundary decision.
    verdict: Verdict,
    /// The stated expectation, if any.
    expect: Option<String>,
    /// Whether the outcome passed: matches `expect` when given, otherwise the
    /// path must be allowed to cross.
    pass: bool,
}

/// Classify a path and score it against an optional expectation.
fn evaluate(path: String, expect: Option<String>) -> CheckOutcome {
    let verdict = classify(&path);
    let pass = match &expect {
        Some(e) => verdict_label(verdict) == e.as_str(),
        None => matches!(verdict, Verdict::Allowed(_)),
    };
    CheckOutcome {
        path,
        verdict,
        expect,
        pass,
    }
}

/// Accept a single query or a JSON array of them (mirrors the descriptor parser
/// in `sovereign-module-facets`).
fn parse_queries(json: &str) -> Result<Vec<QueryInput>, serde_json::Error> {
    match serde_json::from_str::<Vec<QueryInput>>(json) {
        Ok(v) => Ok(v),
        Err(_) => serde_json::from_str::<QueryInput>(json).map(|q| vec![q]),
    }
}

/// Parse a `--check` config from JSON and evaluate each query.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let queries = parse_queries(json)?;
    Ok(queries
        .into_iter()
        .map(|q| {
            let (path, expect) = q.into_parts();
            evaluate(path, expect)
        })
        .collect())
}

/// Print a report for a set of outcomes and return the process exit code.
fn report(outcomes: &[CheckOutcome]) -> ExitCode {
    if outcomes.is_empty() {
        println!("(no paths to check)");
        return ExitCode::SUCCESS;
    }
    let mut all_pass = true;
    for o in outcomes {
        if !o.pass {
            all_pass = false;
        }
        let prefix = if o.pass { "OK  " } else { "FAIL" };
        let detail = verdict_detail(o.verdict);
        match &o.expect {
            Some(e) => println!("{prefix} {} → {detail} (expected: {e})", o.path),
            None => println!("{prefix} {} → {detail}", o.path),
        }
    }
    if all_pass {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

/// `PATH...`: classify each path given on the command line.
fn run_query(paths: &[String]) -> ExitCode {
    let outcomes: Vec<CheckOutcome> = paths.iter().map(|p| evaluate(p.clone(), None)).collect();
    report(&outcomes)
}

/// `--check FILE`: read the file, evaluate the queries, print the report, and
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
            eprintln!("error: {path} is not a boundary-query config (path/object/array): {e}");
            return ExitCode::FAILURE;
        }
    };
    report(&outcomes)
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

    if !args.is_empty() {
        return run_query(&args);
    }

    print!("{}", reference_text());
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dir_leaf_matches_serde() {
        // The ALLOWED verdict labels must not drift from the enum's JSON form.
        for dir in ExchangeDir::ALL {
            let json = serde_json::to_string(&dir).unwrap();
            assert_eq!(json, format!("\"{}\"", dir_label(dir)));
        }
    }

    #[test]
    fn step_label_matches_serde() {
        for step in ImportStep::ALL {
            let json = serde_json::to_string(&step).unwrap();
            assert_eq!(json, format!("\"{}\"", step_label(step)));
        }
    }

    #[test]
    fn allows_each_exchange_directory() {
        assert_eq!(
            classify("/ai-exchange/inbox/patch.json"),
            Verdict::Allowed(ExchangeDir::Inbox)
        );
        assert_eq!(
            classify("/ai-exchange/outbox/report.txt"),
            Verdict::Allowed(ExchangeDir::Outbox)
        );
        assert_eq!(
            classify("/ai-exchange/artifacts/build/out.img"),
            Verdict::Allowed(ExchangeDir::Artifacts)
        );
        // the directory itself (no file under it) still maps to its dir
        assert_eq!(
            classify("/ai-exchange/inbox"),
            Verdict::Allowed(ExchangeDir::Inbox)
        );
    }

    #[test]
    fn denies_host_file() {
        assert_eq!(
            classify("/etc/passwd"),
            Verdict::Denied(DenyReason::NotUnderExchangeRoot)
        );
        assert_eq!(
            classify("/"),
            Verdict::Denied(DenyReason::NotUnderExchangeRoot)
        );
    }

    #[test]
    fn denies_unknown_exchange_leaf() {
        assert_eq!(
            classify("/ai-exchange/tmp/x"),
            Verdict::Denied(DenyReason::UnknownExchangeLeaf)
        );
        assert_eq!(
            classify("/ai-exchange"),
            Verdict::Denied(DenyReason::UnknownExchangeLeaf)
        );
    }

    #[test]
    fn denies_relative_path() {
        assert_eq!(
            classify("ai-exchange/inbox/x"),
            Verdict::Denied(DenyReason::NotAbsolute)
        );
    }

    #[test]
    fn dotdot_that_escapes_the_boundary_is_denied() {
        // resolves to /etc/passwd — outside the boundary entirely.
        assert_eq!(
            classify("/ai-exchange/inbox/../../etc/passwd"),
            Verdict::Denied(DenyReason::NotUnderExchangeRoot)
        );
        // traversal above the root itself.
        assert_eq!(classify("/../etc"), Verdict::Denied(DenyReason::Traversal));
    }

    #[test]
    fn dotdot_that_stays_inside_is_allowed() {
        assert_eq!(
            classify("/ai-exchange/outbox/../inbox/file"),
            Verdict::Allowed(ExchangeDir::Inbox)
        );
    }

    #[test]
    fn inbox_detail_mentions_import_pipeline() {
        let detail = verdict_detail(Verdict::Allowed(ExchangeDir::Inbox));
        assert!(detail.contains("import-validation"), "got: {detail}");
    }

    #[test]
    fn reference_lists_all_dirs_and_steps() {
        let t = reference_text();
        for dir in ExchangeDir::ALL {
            assert!(
                t.contains(dir_label(dir)),
                "reference missing {dir:?}:\n{t}"
            );
            assert!(
                t.contains(&dir.path()),
                "reference missing path for {dir:?}"
            );
        }
        for step in ImportStep::ALL {
            assert!(t.contains(step_label(step)), "reference missing {step:?}");
        }
    }

    #[test]
    fn check_accepts_array_with_expectations() {
        let json = r#"[
            {"path": "/ai-exchange/inbox/a", "expect": "inbox"},
            {"path": "/etc/shadow", "expect": "denied"},
            "/ai-exchange/artifacts/b"
        ]"#;
        let outcomes = check_json(json).unwrap();
        assert_eq!(outcomes.len(), 3);
        assert!(outcomes.iter().all(|o| o.pass), "all should pass");
    }

    #[test]
    fn check_fails_on_expectation_mismatch() {
        let json = r#"{"path": "/etc/passwd", "expect": "inbox"}"#;
        let outcomes = check_json(json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(!outcomes[0].pass);
        assert_eq!(
            outcomes[0].verdict,
            Verdict::Denied(DenyReason::NotUnderExchangeRoot)
        );
    }

    #[test]
    fn check_without_expect_fails_denied_path() {
        // A bare path in the config is expected to be allowed to cross.
        let outcomes = check_json(r#""/etc/passwd""#).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(!outcomes[0].pass);

        let outcomes = check_json(r#""/ai-exchange/outbox/ok""#).unwrap();
        assert!(outcomes[0].pass);
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }
}
