//! `chromofold` — the diagnostic + CPU-search CLI for the ChromoFold surface (SDD-400).
//!
//! - `info`     — print the [`sovereign_chromofold::CapabilityDescriptor`] as JSON.
//! - `selftest` — the offline, no-GPU functional round-trip (descriptor +
//!   a known-answer FM-index check).
//! - `count` / `locate` / `predict` — run the **CPU-native FM-index**
//!   (provenance-B, [`FmIndex`]) over a `--corpus <file>` of whitespace/comma-
//!   separated token ids, querying `--pattern`/`--context` (same format). No GPU,
//!   no native library — the working compressed-domain search on the command line.
//!
//! Precursor + companion to the `sovereign-osctl chromofold` verb (SDD-400 step 5).

use std::process::ExitCode;

use sovereign_chromofold::{Availability, CapabilityDescriptor, FmIndex, availability, descriptor};

fn print_info() {
    let d = descriptor();
    match serde_json::to_string_pretty(&d) {
        Ok(json) => println!("{json}"),
        // never fabricate output — surface the failure honestly
        Err(e) => eprintln!("chromofold: could not serialize descriptor: {e}"),
    }
}

/// Offline, no-GPU self-test: the descriptor round-trips, and the CPU-native
/// FM-index (provenance-B) returns the correct count/locate for a known stream —
/// a real functional check, no GPU, no fabrication.
fn selftest() -> Result<(), String> {
    let d = descriptor();
    let json =
        serde_json::to_string(&d).map_err(|e| format!("descriptor serialize failed: {e}"))?;
    let back: CapabilityDescriptor =
        serde_json::from_str(&json).map_err(|e| format!("descriptor round-trip failed: {e}"))?;
    if back != d {
        return Err("descriptor did not survive a serde round-trip".to_string());
    }
    // provenance-B functional check against a known answer ("abracadabra").
    let text: Vec<u32> = "abracadabra".bytes().map(u32::from).collect();
    let idx = FmIndex::build(&text);
    let a = b'a' as u32;
    if idx.count(&[a]) != 5 {
        return Err(format!(
            "FM-index count('a') = {}, expected 5",
            idx.count(&[a])
        ));
    }
    let abra: Vec<u32> = "abra".bytes().map(u32::from).collect();
    if idx.locate(&abra) != vec![0, 7] {
        return Err(format!(
            "FM-index locate('abra') = {:?}, expected [0, 7]",
            idx.locate(&abra)
        ));
    }
    Ok(())
}

/// Parse whitespace/comma-separated non-negative integers into token ids.
fn parse_tokens(s: &str) -> Result<Vec<u32>, String> {
    s.split(|c: char| c.is_whitespace() || c == ',')
        .filter(|t| !t.is_empty())
        .map(|t| {
            t.parse::<u32>()
                .map_err(|_| format!("not a u32 token id: {t:?}"))
        })
        .collect()
}

/// `--key value` lookup over the argument tail (returns the value after `key`).
fn flag<'a>(args: &'a [String], key: &str) -> Option<&'a str> {
    args.iter()
        .position(|a| a == key)
        .and_then(|i| args.get(i + 1))
        .map(String::as_str)
}

/// Run a CPU FM-index query subcommand. `kind` ∈ count|locate|predict.
fn cmd_search(kind: &str, args: &[String]) -> Result<(), String> {
    let json = args.iter().any(|a| a == "--json");
    let corpus_path = flag(args, "--corpus")
        .ok_or_else(|| format!("chromofold {kind}: --corpus <file> is required"))?;
    let query_key = if kind == "predict" {
        "--context"
    } else {
        "--pattern"
    };
    let query_raw = flag(args, query_key)
        .ok_or_else(|| format!("chromofold {kind}: {query_key} \"<token ids>\" is required"))?;

    let corpus_text = std::fs::read_to_string(corpus_path)
        .map_err(|e| format!("cannot read corpus {corpus_path}: {e}"))?;
    let corpus = parse_tokens(&corpus_text).map_err(|e| format!("corpus: {e}"))?;
    let query = parse_tokens(query_raw).map_err(|e| format!("{query_key}: {e}"))?;

    let idx = FmIndex::build(&corpus);
    match kind {
        "count" => {
            let n = idx.count(&query);
            if json {
                println!("{}", serde_json::json!({ "count": n }));
            } else {
                println!("{n}");
            }
        }
        "locate" => {
            let pos = idx.locate(&query);
            if json {
                println!("{}", serde_json::json!({ "positions": pos }));
            } else if pos.is_empty() {
                println!("(no occurrences)");
            } else {
                println!(
                    "{}",
                    pos.iter()
                        .map(ToString::to_string)
                        .collect::<Vec<_>>()
                        .join(" ")
                );
            }
        }
        "predict" => {
            let preds = idx.predict(&query);
            if json {
                println!("{}", serde_json::json!({ "predictions": preds }));
            } else if preds.is_empty() {
                println!("(no continuation)");
            } else {
                for (tok, p) in preds {
                    println!("{tok}\t{p:.4}");
                }
            }
        }
        _ => unreachable!(),
    }
    Ok(())
}

/// Parse a `--key <usize>` flag with a default.
fn parse_usize(args: &[String], key: &str, default: usize) -> Result<usize, String> {
    match flag(args, key) {
        None => Ok(default),
        Some(v) => v
            .parse::<usize>()
            .map_err(|_| format!("{key}: not a usize: {v:?}")),
    }
}

/// Prompt-lookup speculative-decoding draft over a corpus (FmIndex::propose_draft).
fn cmd_draft(args: &[String]) -> Result<(), String> {
    let json = args.iter().any(|a| a == "--json");
    let corpus_path = flag(args, "--corpus")
        .ok_or_else(|| "chromofold draft: --corpus <file> is required".to_string())?;
    let max_ngram = parse_usize(args, "--max-ngram", 3)?;
    let min_ngram = parse_usize(args, "--min-ngram", 1)?;
    let max_draft = parse_usize(args, "--max-draft", 8)?;
    let corpus_text = std::fs::read_to_string(corpus_path)
        .map_err(|e| format!("cannot read corpus {corpus_path}: {e}"))?;
    let corpus = parse_tokens(&corpus_text).map_err(|e| format!("corpus: {e}"))?;
    let draft = FmIndex::build(&corpus).propose_draft(max_ngram, min_ngram, max_draft);
    if json {
        println!("{}", serde_json::json!({ "draft": draft }));
    } else if draft.is_empty() {
        println!("(no draft)");
    } else {
        println!(
            "{}",
            draft
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join(" ")
        );
    }
    Ok(())
}

/// Span recovery: the longest suffix of `--query` present in the corpus.
fn cmd_span(args: &[String]) -> Result<(), String> {
    let json = args.iter().any(|a| a == "--json");
    let corpus_path = flag(args, "--corpus")
        .ok_or_else(|| "chromofold span: --corpus <file> is required".to_string())?;
    let query_raw = flag(args, "--query")
        .ok_or_else(|| "chromofold span: --query \"<ids>\" is required".to_string())?;
    let corpus_text = std::fs::read_to_string(corpus_path)
        .map_err(|e| format!("cannot read corpus {corpus_path}: {e}"))?;
    let corpus = parse_tokens(&corpus_text).map_err(|e| format!("corpus: {e}"))?;
    let query = parse_tokens(query_raw).map_err(|e| format!("--query: {e}"))?;
    let (len, positions) = FmIndex::build(&corpus).longest_matching_span(&query);
    if json {
        println!(
            "{}",
            serde_json::json!({ "span_len": len, "positions": positions })
        );
    } else {
        println!(
            "span_len={len} positions={}",
            positions
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join(",")
        );
    }
    Ok(())
}

fn usage() {
    eprintln!(
        "chromofold — ChromoFold CPU search + diagnostics (SDD-400)\n\
         usage:\n  \
           chromofold info [--json]\n  \
           chromofold selftest\n  \
           chromofold count   --corpus <file> --pattern \"<ids>\" [--json]\n  \
           chromofold locate  --corpus <file> --pattern \"<ids>\" [--json]\n  \
           chromofold predict --corpus <file> --context \"<ids>\" [--json]\n  \
           chromofold draft   --corpus <file> [--max-ngram 3] [--min-ngram 1] [--max-draft 8] [--json]\n  \
           chromofold span    --corpus <file> --query \"<ids>\" [--json]\n\
         corpus/pattern/context/query: whitespace- or comma-separated u32 token ids.\n\
         draft: the prompt-lookup speculative-decoding draft (a drop-in for sovereign-ngram-speculative).\n\
         span:  the longest suffix of --query already in the corpus (prompt-cache span recovery)."
    );
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cmd = args.first().map(String::as_str).unwrap_or("info");
    let tail = if args.is_empty() { &[][..] } else { &args[1..] };
    match cmd {
        "info" => {
            print_info();
            ExitCode::SUCCESS
        }
        "selftest" => match selftest() {
            Ok(()) => {
                let note = match availability() {
                    Availability::Linked => "engine linked",
                    Availability::Unavailable => {
                        "honest-degrade (GPU engine not linked; CPU FM-index active)"
                    }
                };
                println!("chromofold selftest: PASS — {note}");
                ExitCode::SUCCESS
            }
            Err(why) => {
                eprintln!("chromofold selftest: FAIL — {why}");
                ExitCode::FAILURE
            }
        },
        "count" | "locate" | "predict" => match cmd_search(cmd, tail) {
            Ok(()) => ExitCode::SUCCESS,
            Err(why) => {
                eprintln!("chromofold: {why}");
                ExitCode::FAILURE
            }
        },
        "draft" => match cmd_draft(tail) {
            Ok(()) => ExitCode::SUCCESS,
            Err(why) => {
                eprintln!("chromofold: {why}");
                ExitCode::FAILURE
            }
        },
        "span" => match cmd_span(tail) {
            Ok(()) => ExitCode::SUCCESS,
            Err(why) => {
                eprintln!("chromofold: {why}");
                ExitCode::FAILURE
            }
        },
        "help" | "-h" | "--help" => {
            usage();
            ExitCode::SUCCESS
        }
        other => {
            eprintln!("chromofold: unknown command {other:?}");
            usage();
            ExitCode::FAILURE
        }
    }
}
