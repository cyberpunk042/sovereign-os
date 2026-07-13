//! `sovereign-network-boundary` CLI — the runnable end of E0124 / M00232.
//!
//! The library fixes the network boundary: network access is not binary. A
//! branch declares the *narrowest* network scope it needs as a [`ToolIntent`],
//! and the runtime grants it only if that scope sits within the profile the
//! operator/policy allows — the 5-rung [`NetworkProfile`] ladder. But nothing
//! *ran* it, so "is this branch's network intent within its allowance?" was
//! unanswerable at the command line. This binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — print the 5-rung profile ladder (label + reach rank +
//!     description) as a human-readable reference: the network boundary itself.
//!   * `--check FILE` — load a boundary policy (an `allowed` profile plus a list
//!     of `intents`, each `network_scope` + `reason`), decide ALLOW / DENY for
//!     each intent via `is_within_allowance()`, and exit non-zero if any intent
//!     escalates past the allowance.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::Deserialize;
use sovereign_network_boundary::{NetworkProfile, ToolIntent, is_within_allowance};

/// The stable kebab-case label for a profile — identical to how
/// [`NetworkProfile`] serializes to JSON (kept honest by the
/// `profile_label_matches_serde` test).
fn profile_label(profile: NetworkProfile) -> &'static str {
    match profile {
        NetworkProfile::Offline => "offline",
        NetworkProfile::PackageRegistries => "package-registries",
        NetworkProfile::DocsWeb => "docs-web",
        NetworkProfile::ArbitraryWeb => "arbitrary-web",
        NetworkProfile::AuthenticatedBrowserProfile => "authenticated-browser-profile",
    }
}

/// A one-line human description of the reach each profile grants.
fn profile_description(profile: NetworkProfile) -> &'static str {
    match profile {
        NetworkProfile::Offline => "no network at all",
        NetworkProfile::PackageRegistries => "package registries only (crates.io / PyPI / npm …)",
        NetworkProfile::DocsWeb => "read-only documentation web",
        NetworkProfile::ArbitraryWeb => "arbitrary web (any http(s) host)",
        NetworkProfile::AuthenticatedBrowserProfile => {
            "an authenticated browser profile (logged-in sessions)"
        }
    }
}

/// A boundary policy to evaluate: the operator/policy `allowed` profile plus the
/// per-branch `intents` requesting network scope. Deserialized from the
/// `--check FILE` JSON.
#[derive(Debug, Deserialize)]
struct BoundaryPolicy {
    /// The broadest network profile the operator/policy permits.
    allowed: NetworkProfile,
    /// The per-branch network intents to gate against `allowed`.
    intents: Vec<ToolIntent>,
}

/// The decision for one intent under the policy's allowance.
struct IntentOutcome {
    /// The intent that was evaluated.
    intent: ToolIntent,
    /// Whether the intent's scope sits within the allowance.
    allowed: bool,
}

/// The human-readable reference: the 5-rung network-profile ladder.
fn reference_text() -> String {
    let mut s = String::from(
        "The network boundary (E0124 / M00232): a branch is granted the network only if its\n\
         narrowest declared scope sits within the operator/policy allowance.\n\n\
         The 5-rung network-profile ladder (ascending reach):\n\n",
    );
    for profile in NetworkProfile::ALL {
        let rank = profile.rank();
        let label = profile_label(profile);
        let description = profile_description(profile);
        s.push_str(&format!("  {rank}. {label:<31} {description}\n"));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-network-boundary — the network boundary (E0124 / M00232)\n\n\
     Network access is not binary. A branch declares the narrowest network scope\n\
     it needs (a ToolIntent: network_scope + reason), and the runtime grants it\n\
     only if that scope sits within the profile the operator/policy allows — the\n\
     5-rung ladder offline < package-registries < docs-web < arbitrary-web <\n\
     authenticated-browser-profile.\n\n\
     USAGE:\n\
     \x20   sovereign-network-boundary                print the 5-rung profile ladder (reference)\n\
     \x20   sovereign-network-boundary --check FILE    evaluate a boundary policy from JSON\n\
     \x20   sovereign-network-boundary --help          print this help and exit\n\n\
     --check FILE loads a boundary policy — an \"allowed\" profile plus a list of\n\
     \"intents\" (each network_scope + reason) — decides ALLOW / DENY for each\n\
     intent via is_within_allowance(), and exits non-zero if any intent escalates\n\
     past the allowance.\n"
        .to_string()
}

/// Parse a boundary policy from the `--check` JSON.
fn parse_policy(json: &str) -> Result<BoundaryPolicy, serde_json::Error> {
    serde_json::from_str(json)
}

/// Decide ALLOW / DENY for every intent in the policy against its allowance.
fn evaluate(policy: BoundaryPolicy) -> Vec<IntentOutcome> {
    let allowed = policy.allowed;
    policy
        .intents
        .into_iter()
        .map(|intent| IntentOutcome {
            allowed: is_within_allowance(&intent, allowed),
            intent,
        })
        .collect()
}

/// `--check FILE`: read the file, evaluate the policy, print a report, and
/// return a process exit code (non-zero on read/parse error or any denied
/// intent).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let policy = match parse_policy(&json) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {path} is not a boundary policy (allowed + intents): {e}");
            return ExitCode::FAILURE;
        }
    };

    let allowance_label = profile_label(policy.allowed);
    let allowance_rank = policy.allowed.rank();
    let outcomes = evaluate(policy);
    if outcomes.is_empty() {
        println!("(no intents in {path}) — allowance {allowance_label} (rank {allowance_rank})");
        return ExitCode::SUCCESS;
    }
    println!("allowance: {allowance_label} (rank {allowance_rank})");

    let mut all_ok = true;
    for o in &outcomes {
        let scope = profile_label(o.intent.network_scope);
        let scope_rank = o.intent.network_scope.rank();
        let reason = &o.intent.reason;
        if o.allowed {
            println!(
                "ALLOW {scope} (rank {scope_rank}) <= {allowance_label} (rank {allowance_rank}) — {reason}"
            );
        } else {
            all_ok = false;
            println!(
                "DENY  {scope} (rank {scope_rank}) > {allowance_label} (rank {allowance_rank}) — {reason}"
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
    fn reference_lists_all_five_profiles() {
        let t = reference_text();
        for p in NetworkProfile::ALL {
            assert!(
                t.contains(profile_label(p)),
                "reference missing {p:?}:\n{t}"
            );
            assert!(
                t.contains(profile_description(p)),
                "reference missing description for {p:?}:\n{t}"
            );
        }
        // Exactly five numbered "  N. " entries — one per profile, no more.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(
            numbered,
            NetworkProfile::ALL.len(),
            "expected 5 profile lines"
        );
    }

    #[test]
    fn profile_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for p in NetworkProfile::ALL {
            let json = serde_json::to_string(&p).unwrap();
            assert_eq!(json, format!("\"{}\"", profile_label(p)));
        }
    }

    #[test]
    fn check_allows_intents_within_allowance() {
        let json = r#"{
            "allowed": "arbitrary-web",
            "intents": [
                {"network_scope": "docs-web", "reason": "read rust docs"},
                {"network_scope": "arbitrary-web", "reason": "fetch a blog"},
                {"network_scope": "offline", "reason": "pure compute"}
            ]
        }"#;
        let outcomes = evaluate(parse_policy(json).unwrap());
        assert_eq!(outcomes.len(), 3);
        assert!(outcomes.iter().all(|o| o.allowed));
    }

    #[test]
    fn check_denies_intent_that_escalates_past_allowance() {
        let json = r#"{
            "allowed": "docs-web",
            "intents": [
                {"network_scope": "docs-web", "reason": "read rust docs"},
                {"network_scope": "authenticated-browser-profile", "reason": "log in somewhere"}
            ]
        }"#;
        let outcomes = evaluate(parse_policy(json).unwrap());
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes[0].allowed, "docs-web is within docs-web");
        assert!(
            !outcomes[1].allowed,
            "authenticated-browser-profile must be denied under docs-web"
        );
    }

    #[test]
    fn offline_allowance_denies_every_networked_intent() {
        let json = r#"{
            "allowed": "offline",
            "intents": [
                {"network_scope": "package-registries", "reason": "cargo fetch"}
            ]
        }"#;
        let outcomes = evaluate(parse_policy(json).unwrap());
        assert!(!outcomes[0].allowed);
    }

    #[test]
    fn parse_reports_invalid_json_as_error() {
        assert!(parse_policy("not json").is_err());
        // Missing the required `intents` field is also an error.
        assert!(parse_policy(r#"{"allowed": "offline"}"#).is_err());
    }
}
