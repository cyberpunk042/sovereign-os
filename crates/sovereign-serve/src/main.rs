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
//! Generation runs on the **real** engine: a small `SovereignLlm` (built once)
//! backs the `serve()` generate step, so the cost-aware path actually drives
//! the inference stack — a `$0` cache hit still short-circuits before the model
//! runs. The weights are random, so the text is gibberish; the point is that
//! the serving assembly and the model are wired together and run. With
//! `--stream`, each generated token is printed the instant the model emits it
//! (via the engine's streaming API) before the served result is recorded.
//! Usage: `sovereign-serve [--stream] [PROMPT…]` · `sovereign-serve --help`.

use sovereign_decoder_stack::{GenOptions, StackConfig};
use sovereign_ffn::SwiGlu;
use sovereign_llm::SovereignLlm;
use sovereign_rmsnorm::RmsNorm;
use sovereign_sampler::{Sampler, SamplerConfig};
use sovereign_serve::Server;
use sovereign_token_meter::Budget;
use sovereign_tokenizer::Tokenizer;
use sovereign_transformer_block::BlockWeights;

const MD: usize = 4;

/// Whitespace-word token counter — keeps the printed accounting readable and
/// deterministic (the engine's own tokenizer drives generation length).
fn words(s: &str) -> usize {
    s.split_whitespace().count()
}

/// Deterministic weight filler so the demo runs without a checkpoint.
fn mat(s: f32, n: usize) -> Vec<f32> {
    (0..n).map(|i| ((i as f32 + s) * 0.017).sin()).collect()
}

/// A small but real `SovereignLlm` (one transformer block, `model_dim = 4`).
fn runtime() -> SovereignLlm {
    let tok = Tokenizer::default();
    let vocab = tok.vocab_size();
    let block = BlockWeights {
        model_dim: MD,
        head_dim: MD,
        attn_norm: RmsNorm::new(MD),
        ffn_norm: RmsNorm::new(MD),
        w_q: mat(1.0, MD * MD),
        w_k: mat(2.0, MD * MD),
        w_v: mat(3.0, MD * MD),
        w_o: mat(4.0, MD * MD),
        ffn: SwiGlu::new(
            MD,
            MD,
            mat(5.0, MD * MD),
            mat(6.0, MD * MD),
            mat(7.0, MD * MD),
        )
        .unwrap(),
    };
    let cfg = StackConfig {
        vocab,
        model_dim: MD,
        embedding: mat(0.5, vocab * MD),
        blocks: vec![block],
        final_norm: RmsNorm::new(MD),
        head: mat(0.9, vocab * MD),
        sampler: Sampler::new(SamplerConfig::default()),
        recent_window: 64,
    };
    SovereignLlm::new(tok, cfg).unwrap()
}

const USAGE: &str = "\
sovereign-serve — the $0-aware serving assembly (cache -> complexity -> budget -> generate -> account)

USAGE:
    sovereign-serve                    run the built-in demo session, print, exit
    sovereign-serve PROMPT [PROMPT…]   serve each prompt (unlimited budget; a
                                       repeated prompt is a $0 cache hit)
    sovereign-serve --stream PROMPT…   stream each generated token as it arrives
    sovereign-serve --no-repeat-ngram N PROMPT…  block repeated N-grams (unified path)
    sovereign-serve --semantic PROMPT… enable the semantic cache tier: a
                                       paraphrase of a served prompt is a $0 hit
    sovereign-serve --redact PROMPT…   scrub secrets + PII from each completion
                                       before it is cached/returned (egress gate)
    sovereign-serve --screen PROMPT…   refuse a completion flagged toxic by the
                                       built-in content filter (egress gate)
    sovereign-serve --regex RE PROMPT… constrain every completion to the regex RE
                                       (guaranteed-format output)
    sovereign-serve --help             print this help and exit";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!("{USAGE}");
        return;
    }
    let stream = args.iter().any(|a| a == "--stream");
    let semantic = args.iter().any(|a| a == "--semantic");
    let redact = args.iter().any(|a| a == "--redact");
    let screen = args.iter().any(|a| a == "--screen");
    // Built-in content filter, built once, used by the egress screen.
    let tox = sovereign_toxicity::ToxicityFilter::with_builtin();
    // `--no-repeat-ngram N` drives the unified composable generation path.
    let nrn_idx = args.iter().position(|a| a == "--no-repeat-ngram");
    let no_repeat: Option<usize> = nrn_idx
        .and_then(|i| args.get(i + 1))
        .and_then(|v| v.parse().ok());
    // `--regex RE` constrains every completion to the pattern RE.
    let regex_idx = args.iter().position(|a| a == "--regex");
    let regex: Option<String> = regex_idx.and_then(|i| args.get(i + 1)).cloned();
    // Exclude the values following value-taking flags from the prompt list.
    let mut skip: std::collections::HashSet<usize> = std::collections::HashSet::new();
    if no_repeat.is_some() {
        skip.insert(nrn_idx.unwrap() + 1);
    }
    if regex.is_some() {
        skip.insert(regex_idx.unwrap() + 1);
    }
    let prompts: Vec<&str> = args
        .iter()
        .enumerate()
        .filter(|(j, a)| !a.starts_with('-') && !skip.contains(j))
        .map(|(_, a)| a.as_str())
        .collect();

    // Build the engine once; its `complete` (immutable, reproducible per seed)
    // backs every generate step. `--no-repeat-ngram N` uses the unified
    // GenOptions path; `--stream` prints each token as the model emits it; the
    // decoded completion is returned for caching + accounting.
    let llm = runtime();
    let generate = |prompt: &str, max_new: usize, seed: u64| -> Result<String, String> {
        let text = if let Some(pattern) = regex.as_deref() {
            // Constrained decoding: the completion is forced to match `pattern`.
            llm.complete_regex(prompt, pattern, max_new, seed)
                .map_err(|e| e.to_string())?
        } else if let Some(n) = no_repeat {
            let opts = GenOptions::new(max_new).with_no_repeat_ngram(n);
            let ids = llm
                .generate_ids_with(prompt, seed, &opts, |_| {})
                .map_err(|e| e.to_string())?;
            llm.tokenizer().decode(&ids).unwrap_or_default()
        } else if stream {
            print!("  stream:");
            let ids = llm
                .generate_ids_streaming(prompt, max_new, seed, |id| {
                    print!(" {id}");
                    let _ = std::io::Write::flush(&mut std::io::stdout());
                })
                .map_err(|e| e.to_string())?;
            println!();
            llm.tokenizer().decode(&ids).unwrap_or_default()
        } else {
            llm.complete(prompt, max_new, seed)
                .map_err(|e| e.to_string())?
        };
        // Egress gate: scrub secrets then PII before the text is cached/returned.
        let text = if redact {
            sovereign_pii_redact::redact(&sovereign_secret_scan::redact(&text))
        } else {
            text
        };
        // Egress gate: refuse a completion the content filter flags as toxic.
        if screen && tox.is_toxic(&text, 0.5) {
            return Err("blocked: completion flagged toxic by content filter".to_string());
        }
        Ok(text)
    };

    if prompts.is_empty() {
        // Demo: a small total-token budget so the session shows a real refusal,
        // and a repeated prompt so it shows a $0 cache hit.
        let mut server = Server::with_budget(64, Budget::total(40));
        if semantic {
            server = server.with_semantic(64, 0.6);
        }
        run_session(
            &mut server,
            &[
                ("hello there", 3, 1),
                ("explain raft consensus to me", 6, 2),
                ("hello there", 3, 1),
                ("generate a very long answer please", 50, 3),
            ],
            generate,
        );
    } else {
        // Serve the operator's prompts on an unlimited budget; a repeated prompt
        // still resolves as a $0 cache hit.
        let mut server = Server::new(64);
        if semantic {
            server = server.with_semantic(64, 0.6);
        }
        // Fixed seed so an identical prompt resolves as a $0 cache hit.
        let session: Vec<(&str, usize, u64)> = prompts.iter().map(|p| (*p, 16, 0u64)).collect();
        run_session(&mut server, &session, generate);
    }
}

/// Serve each `(prompt, max_new, seed)` in order on the real engine `generate`,
/// printing the cost-aware outcome per request and a usage summary at the end.
fn run_session<G>(server: &mut Server, session: &[(&str, usize, u64)], mut generate: G)
where
    G: FnMut(&str, usize, u64) -> Result<String, String>,
{
    let mut cache_hits = 0usize;
    let mut semantic_hits = 0usize;
    let mut refused = 0usize;
    for &(prompt, max_new, seed) in session {
        match server.serve(prompt, max_new, seed, words, &mut generate) {
            Ok(r) => {
                if r.cache_hit {
                    cache_hits += 1;
                }
                if r.semantic_hit {
                    semantic_hits += 1;
                }
                let kind = if r.semantic_hit {
                    "semantic"
                } else if r.cache_hit {
                    "exact"
                } else {
                    "miss"
                };
                println!(
                    "serve  ok   | hit={kind:<8} tier={:?} in={} out={} | {prompt:?} -> {:?}",
                    r.tier, r.input_tokens, r.output_tokens, r.text
                );
            }
            Err(e) => {
                refused += 1;
                println!("serve  REFUSED | {prompt:?} (max_new={max_new}) -> {e}");
            }
        }
    }

    let usage = server.meter().usage();
    let exact_hits = cache_hits - semantic_hits;
    println!(
        "# session: {} request(s), {cache_hits} cache hit(s) ($0) [{exact_hits} exact, {semantic_hits} semantic], {refused} refused",
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
