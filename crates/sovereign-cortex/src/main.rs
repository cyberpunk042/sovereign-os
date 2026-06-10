//! `sovereign-cortex` binary — runs the cortex pipeline.
//!
//! Usage:
//!
//! ```text
//! sovereign-cortex                 # run the built-in demo scenarios
//! sovereign-cortex request.json    # run one request from a JSON file
//! sovereign-cortex '{"axes":…}'    # run one request from an inline JSON arg
//! sovereign-cortex --explain       # print the plain-language rationale on stdout
//! sovereign-cortex --search        # demo the iterative search mode (refine to commit)
//! sovereign-cortex --help          # print usage and exit
//! ```
//!
//! By default each decision is printed to stdout as pretty JSON; with
//! `--explain` the operator-facing plain-language rationale (M015 human-gate)
//! is printed on stdout instead. A one-line trace of every tick goes to stderr.
//! Exit code is `1` if any request was refused, `2` if the JSON could not be
//! parsed.

use sovereign_cortex::verify::F_CLOUD_SPILL;
use sovereign_cortex::{
    BranchExpander, Cortex, CortexRequest, demo_requests, seed_memory, verify_session,
};
use sovereign_symbolic_plan::{SafetyProperty, facts};
use sovereign_value_plane::{BranchAssessment, IntelligenceTier, RewardVector};

/// A demo expander that converges: each round it proposes one fully-strong
/// candidate, so an uncertain seed is refined to a committable branch. (A real
/// expander samples/refines from the model; this stands in for that.)
struct ConvergingExpander;
impl BranchExpander for ConvergingExpander {
    fn expand(&self, _best: &BranchAssessment, _round: u32) -> Vec<RewardVector> {
        vec![strong_reward()]
    }
}

/// An uncertain starting reward (the seed the search refines from).
fn uncertain_reward() -> RewardVector {
    RewardVector {
        correctness: 0.7,
        evidence: 0.6,
        schema_validity: 1.0,
        tool_success: 1.0,
        test_success: 1.0,
        risk: 0.1,
        latency: 0.2,
        cost: 0.2,
        novelty: 0.4,
        user_preference: 0.6,
        cache_reuse: 0.5,
        confidence_calibration: 0.2,
    }
}

/// A fully-strong reward the expander converges toward.
fn strong_reward() -> RewardVector {
    RewardVector {
        correctness: 1.0,
        evidence: 1.0,
        schema_validity: 1.0,
        tool_success: 1.0,
        test_success: 1.0,
        risk: 0.0,
        latency: 0.0,
        cost: 0.0,
        novelty: 1.0,
        user_preference: 1.0,
        cache_reuse: 1.0,
        confidence_calibration: 0.99,
    }
}

/// Run the iterative-search demo (M035): refine an uncertain seed round by round
/// until it commits or the tier's budget is spent. Prints the outcome to stdout.
fn run_search_demo(request: &CortexRequest) {
    let cortex = Cortex::with_memory(seed_memory());
    let seed = vec![uncertain_reward()];
    match cortex.search(
        request,
        &seed,
        IntelligenceTier::Deliberate,
        &ConvergingExpander,
    ) {
        Ok(out) => {
            println!("# iterative search (tier=deliberate)");
            println!("{}", out.summary);
            println!(
                "rounds={} committed={} final_score={:?}",
                out.rounds,
                out.committed,
                out.final_best.as_ref().map(|b| b.step_score),
            );
            for (round, branch) in out.history.iter().enumerate() {
                println!(
                    "  round {round}: score={:.3} uncertainty={:.3} action={:?}",
                    branch.step_score, branch.uncertainty, branch.suggested_next_action
                );
            }
        }
        Err(e) => {
            eprintln!("search error: {e}");
            std::process::exit(1);
        }
    }
}

const USAGE: &str = "\
sovereign-cortex — runs the cortex decision pipeline

USAGE:
    sovereign-cortex                 run the built-in demo scenarios
    sovereign-cortex request.json    run one request (or a JSON array) from a file
    sovereign-cortex '{\"axes\":…}'    run one request from an inline JSON arg
    sovereign-cortex --explain       print the plain-language rationale on stdout
    sovereign-cortex --search        demo the iterative search mode (refine to commit)
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

    // Iterative-search demo on the first request, then exit.
    if args.iter().any(|a| a == "--search") {
        match requests.first() {
            Some(r) => run_search_demo(r),
            None => eprintln!("no request available for --search"),
        }
        return;
    }

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
