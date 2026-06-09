//! `sovereign-cortex` binary — runs the cortex pipeline.
//!
//! Usage:
//!
//! ```text
//! sovereign-cortex                 # run the built-in demo scenarios
//! sovereign-cortex request.json    # run one request from a JSON file
//! sovereign-cortex '{"axes":…}'    # run one request from an inline JSON arg
//! sovereign-cortex --explain       # print the plain-language rationale on stdout
//! sovereign-cortex --help          # print usage and exit
//! ```
//!
//! By default each decision is printed to stdout as pretty JSON; with
//! `--explain` the operator-facing plain-language rationale (M015 human-gate)
//! is printed on stdout instead. A one-line trace of every tick goes to stderr.
//! Exit code is `1` if any request was refused, `2` if the JSON could not be
//! parsed.

use sovereign_cortex::verify::F_CLOUD_SPILL;
use sovereign_cortex::{Cortex, CortexRequest, demo_requests, seed_memory, verify_session};
use sovereign_symbolic_plan::{SafetyProperty, facts};

const USAGE: &str = "\
sovereign-cortex — runs the cortex decision pipeline

USAGE:
    sovereign-cortex                 run the built-in demo scenarios
    sovereign-cortex request.json    run one request (or a JSON array) from a file
    sovereign-cortex '{\"axes\":…}'    run one request from an inline JSON arg
    sovereign-cortex --explain       print the plain-language rationale on stdout
    sovereign-cortex --help          print this help and exit";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!("{USAGE}");
        return;
    }
    let explain_mode = args.iter().any(|a| a == "--explain");

    let requests: Vec<CortexRequest> = match args.iter().find(|a| !a.starts_with('-')) {
        Some(arg) => {
            // Treat the arg as a file path, falling back to inline JSON. The
            // payload may be a single request OR a JSON array (a session).
            let raw = std::fs::read_to_string(arg).unwrap_or_else(|_| arg.clone());
            if let Ok(batch) = serde_json::from_str::<Vec<CortexRequest>>(&raw) {
                batch
            } else {
                match serde_json::from_str::<CortexRequest>(&raw) {
                    Ok(r) => vec![r],
                    Err(e) => {
                        eprintln!("error: could not parse request JSON: {e}");
                        std::process::exit(2);
                    }
                }
            }
        }
        None => {
            let demos = demo_requests();
            eprintln!(
                "# no request given — running {} demo scenario(s) as a session",
                demos.len()
            );
            demos
        }
    };

    // Run the whole input as one learning session: each committed decision is
    // admitted to memory, so later requests in the session decide better.
    let mut cortex = Cortex::with_memory(seed_memory());
    let (decisions, report) = cortex.run_session(&requests);

    for (i, decision) in decisions.iter().enumerate() {
        if explain_mode {
            // Operator-facing plain-language rationale (M015 human-gate) as the
            // primary, pipeable output.
            println!("# decision {i}");
            println!("{}", decision.explain());
            println!();
        } else {
            println!(
                "{}",
                serde_json::to_string_pretty(decision).expect("a CortexDecision always serializes")
            );
        }
        eprintln!("[{i}] {}", decision.summary);
        if !explain_mode {
            // Also trace the rationale to stderr in JSON mode.
            for line in decision.explain().lines() {
                eprintln!("[{i}]   {line}");
            }
        }
    }
    eprintln!(
        "# session: {}/{} committed, {} learned, {} refused",
        report.committed, report.total, report.learned, report.refused
    );

    // Formally verify the session's decisions (AgentVerify-style): a private
    // workstation must never spill work to the cloud.
    let safety = [SafetyProperty::Never(facts(&[F_CLOUD_SPILL]))];
    let safe = verify_session(&decisions, &safety);
    eprintln!(
        "# safety: never-cloud-spill = {}",
        if safe { "HOLDS" } else { "VIOLATED" }
    );

    // Non-zero exit if any request was refused or a safety property failed.
    std::process::exit(if report.refused > 0 || !safe { 1 } else { 0 });
}
