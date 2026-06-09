//! `sovereign-cortex` binary — runs the cortex pipeline.
//!
//! Usage:
//!
//! ```text
//! sovereign-cortex                 # run the built-in demo scenarios
//! sovereign-cortex request.json    # run one request from a JSON file
//! sovereign-cortex '{"axes":…}'    # run one request from an inline JSON arg
//! ```
//!
//! Each decision is printed to stdout as pretty JSON; a one-line trace of
//! every tick goes to stderr. Exit code is `1` if any request was refused,
//! `2` if the supplied JSON could not be parsed.

use sovereign_cortex::{Cortex, CortexRequest, demo_requests, seed_memory};

fn main() {
    let cortex = Cortex::with_memory(seed_memory());
    let args: Vec<String> = std::env::args().collect();

    let requests: Vec<CortexRequest> = match args.get(1) {
        Some(arg) => {
            // Treat the arg as a file path, falling back to inline JSON.
            let raw = std::fs::read_to_string(arg).unwrap_or_else(|_| arg.clone());
            match serde_json::from_str::<CortexRequest>(&raw) {
                Ok(r) => vec![r],
                Err(e) => {
                    eprintln!("error: could not parse request JSON: {e}");
                    std::process::exit(2);
                }
            }
        }
        None => {
            let demos = demo_requests();
            eprintln!(
                "# no request given — running {} demo scenario(s)",
                demos.len()
            );
            demos
        }
    };

    let mut exit = 0;
    for (i, request) in requests.iter().enumerate() {
        // Full loop: decide (tick) then ratify through the Trinity gate.
        match cortex.act(request) {
            Ok((decision, cycle)) => {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&decision)
                        .expect("a CortexDecision always serializes")
                );
                eprintln!("[{i}] {}", decision.summary);
                eprintln!(
                    "[{i}] trinity: {:?} (committed={}) — {} stage(s)",
                    cycle.stage,
                    cycle.committed(),
                    cycle.reports.len()
                );
            }
            Err(e) => {
                eprintln!("[{i}] cortex refused: {e}");
                exit = 1;
            }
        }
    }
    std::process::exit(exit);
}
