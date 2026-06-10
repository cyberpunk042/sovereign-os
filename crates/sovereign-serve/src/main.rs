//! `sovereign-serve` binary — runs the cost-aware serving assembly end-to-end.
//!
//! The library composes the cache / complexity / token-meter crates into one
//! `$0`-aware `serve()` call; this binary drives a small session through it so
//! the assembly actually *runs*, showing the cost-aware behaviour the crates
//! exist for:
//!
//! * a repeated request is a **cache hit** — `$0`, the model never runs;
//! * each request's **complexity tier** is estimated for routing;
//! * a request that would blow the **token budget** is refused *before*
//!   generating, not run and charged.
//!
//! The generator here is a deterministic stand-in for a model (it echoes the
//! prompt back, uppercased, padded/truncated to `max_new` "tokens") — the point
//! is the orchestration, not the text. Usage: `sovereign-serve` (runs the demo
//! session) · `sovereign-serve --help`.

use sovereign_serve::Server;
use sovereign_token_meter::Budget;

/// Whitespace-word token counter — the runtime supplies the real tokenizer; the
/// demo counts words so the accounting is readable and deterministic.
fn words(s: &str) -> usize {
    s.split_whitespace().count()
}

/// A deterministic stand-in for a model: echo the prompt's words back,
/// uppercased, padded/truncated to exactly `max_new` "tokens" (words).
fn demo_generate(prompt: &str, max_new: usize, _seed: u64) -> Result<String, String> {
    let mut out: Vec<String> = prompt.split_whitespace().map(str::to_uppercase).collect();
    out.resize(max_new.max(1), "…".to_string());
    Ok(out.join(" "))
}

const USAGE: &str = "\
sovereign-serve — the $0-aware serving assembly (cache -> complexity -> budget -> generate -> account)

USAGE:
    sovereign-serve                    run the built-in demo session, print, exit
    sovereign-serve PROMPT [PROMPT…]   serve each prompt (unlimited budget; a
                                       repeated prompt is a $0 cache hit)
    sovereign-serve --help             print this help and exit";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!("{USAGE}");
        return;
    }
    let prompts: Vec<&str> = args
        .iter()
        .filter(|a| !a.starts_with('-'))
        .map(String::as_str)
        .collect();

    if prompts.is_empty() {
        // Demo: a small total-token budget so the session shows a real refusal,
        // and a repeated prompt so it shows a $0 cache hit.
        let mut server = Server::with_budget(64, Budget::total(40));
        run_session(
            &mut server,
            &[
                ("hello there", 3, 1),
                ("explain raft consensus to me", 6, 2),
                ("hello there", 3, 1),
                ("generate a very long answer please", 50, 3),
            ],
        );
    } else {
        // Serve the operator's prompts on an unlimited budget; a repeated prompt
        // still resolves as a $0 cache hit.
        let mut server = Server::new(64);
        // Fixed seed so an identical prompt resolves as a $0 cache hit.
        let session: Vec<(&str, usize, u64)> = prompts.iter().map(|p| (*p, 16, 0u64)).collect();
        run_session(&mut server, &session);
    }
}

/// Serve each `(prompt, max_new, seed)` in order, printing the cost-aware
/// outcome per request and a usage summary at the end.
fn run_session(server: &mut Server, session: &[(&str, usize, u64)]) {
    let mut cache_hits = 0usize;
    let mut refused = 0usize;
    for &(prompt, max_new, seed) in session {
        match server.serve(prompt, max_new, seed, words, demo_generate) {
            Ok(r) => {
                if r.cache_hit {
                    cache_hits += 1;
                }
                println!(
                    "serve  ok   | cache_hit={:<5} tier={:?} in={} out={} | {prompt:?} -> {:?}",
                    r.cache_hit, r.tier, r.input_tokens, r.output_tokens, r.text
                );
            }
            Err(e) => {
                refused += 1;
                println!("serve  REFUSED | {prompt:?} (max_new={max_new}) -> {e}");
            }
        }
    }

    let usage = server.meter().usage();
    println!(
        "# session: {} request(s), {cache_hits} cache hit(s) ($0), {refused} refused",
        session.len()
    );
    println!(
        "# usage: input={} output={} total={} remaining={:?} | cache hit-rate={:.2}",
        usage.input_tokens,
        usage.output_tokens,
        usage.total(),
        server.meter().remaining_total(),
        server.cache_hit_rate(),
    );
}
