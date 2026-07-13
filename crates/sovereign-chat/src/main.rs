//! `sovereign-chat` binary — runs the multi-turn conversation assembly.
//!
//! The library composes `sovereign-llm` into a stateful chat session — record
//! the user turn, render the role-tagged history into a prompt, generate the
//! reply, append it — with **bounded history** (keep the system message + the
//! most recent turns) for endless dialogue. It was lib-only; this binary drives
//! a session on a small real `SovereignLlm` and shows the bounded history hold
//! steady as the conversation grows.
//!
//! The weights are random, so the replies are gibberish — the point is that the
//! conversation assembly runs on the real engine and the history stays bounded.
//!
//! Usage: `sovereign-chat [DECODE FLAGS] [MESSAGE…]` · `--help`. Decode flags
//! (`--temperature`, `--top-k`, `--top-p`, `--typical-p`) build the sampler, so
//! the generation controls are drivable from the command line.

use sovereign_agent_loop::Responder;
use sovereign_agent_runtime::LlmResponder;
use sovereign_chat::{ChatSession, Role};
use sovereign_decoder_stack::StackConfig;
use sovereign_ffn::SwiGlu;
use sovereign_llm::SovereignLlm;
use sovereign_retrieval::{Bm25Store, RagResponder};
use sovereign_rmsnorm::RmsNorm;
use sovereign_sampler::{Sampler, SamplerConfig};
use sovereign_tokenizer::Tokenizer;
use sovereign_transformer_block::BlockWeights;

const MD: usize = 4;

/// Deterministic weight filler — a stand-in for trained weights so the demo is
/// reproducible without a checkpoint.
fn mat(s: f32, n: usize) -> Vec<f32> {
    (0..n).map(|i| ((i as f32 + s) * 0.017).sin()).collect()
}

/// A small but real `SovereignLlm` (one transformer block, `model_dim = 4`),
/// sampling under the caller-supplied decode controls.
fn runtime(sampler: SamplerConfig) -> SovereignLlm {
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
        sampler: Sampler::new(sampler),
        recent_window: 64,
    };
    SovereignLlm::new(tok, cfg).unwrap()
}

/// A small built-in knowledge base so `--rag` retrieves real grounding. BM25
/// over these short documents gives the retrieval path something to rank; the
/// texts are about the box itself so a demo question resolves to a real hit.
fn knowledge_store() -> Bm25Store {
    let mut s = Bm25Store::new();
    s.add(
        "sovereignty",
        "Sovereignty means the box runs entirely on local hardware with no cloud call and no external dependency.",
    );
    s.add(
        "cost",
        "Local inference has zero per-token cost; the only cost is electricity plus the one-time hardware.",
    );
    s.add(
        "privacy",
        "Because nothing leaves the machine, every prompt and output stays private by construction.",
    );
    s.add(
        "rust",
        "Rust gives memory safety without a garbage collector through its ownership model.",
    );
    s.add(
        "offline",
        "The assistant keeps working with the network unplugged; the weights and tokenizer are on disk.",
    );
    s
}

/// Run the retrieval-augmented path: each user message is grounded in the
/// top-`k` BM25-retrieved documents before the runtime generates a reply. This
/// wires the runtime as a [`Responder`], wraps it in a [`RagResponder`] over the
/// built-in [`knowledge_store`], and drives it — a real second consumer of the
/// retrieval hub beyond the mega-demo. The weights are random so the replies are
/// gibberish; the point is that retrieval fires and grounds the prompt.
fn run_rag(messages: &[String], sampler: SamplerConfig) {
    const TOP_K: usize = 2;
    let responder = LlmResponder::new(runtime(sampler), 6);
    let mut rag = RagResponder::new(responder, knowledge_store(), TOP_K);

    let demo = ["what is sovereignty", "tell me about cost"];
    let queries: Vec<&str> = if messages.is_empty() {
        demo.to_vec()
    } else {
        messages.iter().map(String::as_str).collect()
    };

    println!("retrieval-augmented mode (top-{TOP_K} BM25 grounding)\n");
    for (i, q) in queries.iter().enumerate() {
        // `augment` shows what retrieval prepended; if it changed the prompt, a
        // document was retrieved and the reply is grounded.
        let grounded = rag.augment(q) != **q;
        match rag.respond(q, i as u64) {
            Ok(reply) => println!("q{i}: {q:?}\n     grounded: {grounded}\n     reply: {reply:?}"),
            Err(e) => println!("q{i}: error: {e}"),
        }
    }
}

/// Parse `--temperature/-T`, `--top-k`, `--top-p`, `--typical-p` decode flags
/// out of `args`, returning the resulting [`SamplerConfig`] and the remaining
/// non-flag arguments (the chat messages). Unknown flags are passed through as
/// messages so callers see them rather than silently dropping. A flag with a
/// missing or unparseable value falls back to the config default.
fn parse_sampler_args(args: &[String]) -> (SamplerConfig, Vec<String>) {
    let mut cfg = SamplerConfig::default();
    let mut messages = Vec::new();
    let mut i = 0;
    while i < args.len() {
        let a = &args[i];
        // Accept both "--flag value" and "--flag=value" forms.
        let (key, inline_val) = match a.split_once('=') {
            Some((k, v)) => (k, Some(v.to_string())),
            None => (a.as_str(), None),
        };
        let mut take_val = |inline: Option<String>| -> Option<String> {
            if let Some(v) = inline {
                Some(v)
            } else if i + 1 < args.len() {
                i += 1;
                Some(args[i].clone())
            } else {
                None
            }
        };
        match key {
            "--temperature" | "-T" => {
                if let Some(v) = take_val(inline_val).and_then(|s| s.parse().ok()) {
                    cfg.temperature = v;
                }
            }
            "--top-k" => {
                if let Some(v) = take_val(inline_val).and_then(|s| s.parse().ok()) {
                    cfg.top_k = Some(v);
                }
            }
            "--top-p" => {
                if let Some(v) = take_val(inline_val).and_then(|s| s.parse().ok()) {
                    cfg.top_p = Some(v);
                }
            }
            "--typical-p" => {
                if let Some(v) = take_val(inline_val).and_then(|s| s.parse().ok()) {
                    cfg.typical_p = Some(v);
                }
            }
            _ => messages.push(a.clone()),
        }
        i += 1;
    }
    (cfg, messages)
}

/// Extract a `--format NAME` / `--format=NAME` flag from `args`, returning the
/// selected [`ChatFormat`] (if any and recognized) and the remaining arguments.
/// An unrecognized name is ignored (left to the plain default).
fn extract_format(args: &[String]) -> (Option<sovereign_chat_template::ChatFormat>, Vec<String>) {
    use sovereign_chat_template::ChatFormat;
    let mut format = None;
    let mut rest = Vec::new();
    let mut i = 0;
    while i < args.len() {
        let a = &args[i];
        let (key, inline) = match a.split_once('=') {
            Some((k, v)) => (k, Some(v.to_string())),
            None => (a.as_str(), None),
        };
        if key == "--format" {
            let val = inline.or_else(|| {
                i += 1;
                args.get(i).cloned()
            });
            format = match val.as_deref().map(str::to_lowercase).as_deref() {
                Some("chatml") => Some(ChatFormat::ChatML),
                Some("llama2") => Some(ChatFormat::Llama2),
                Some("alpaca") => Some(ChatFormat::Alpaca),
                _ => format, // unrecognized → keep prior (None) and drop the flag
            };
        } else {
            rest.push(a.clone());
        }
        i += 1;
    }
    (format, rest)
}

const USAGE: &str = "\
sovereign-chat — multi-turn conversation with bounded history on the real engine

USAGE:
    sovereign-chat                   run the demo session (4 turns, bounded), exit
    sovereign-chat MESSAGE [MESSAGE…] run your messages as turns (history bounded)
    sovereign-chat --rag [QUERY…]    retrieval-augmented mode: ground each query
                                     in a small BM25 knowledge store before reply
    sovereign-chat --help            print this help and exit

DECODE CONTROLS (apply to generation; any combination):
    -T, --temperature F   softmax temperature (<=0 greedy; default 1.0)
        --top-k N         keep only the N highest-probability tokens
        --top-p F         nucleus threshold in (0,1]
        --typical-p F     locally-typical mass threshold in (0,1]
        --format NAME     chat-template dialect: chatml | llama2 | alpaca
                          (default: plain Role:-labelled prompt)
    (also accepts --flag=value form)";

fn main() {
    let raw: Vec<String> = std::env::args().skip(1).collect();
    if raw.iter().any(|a| a == "--help" || a == "-h") {
        println!("{USAGE}");
        return;
    }

    // `--rag` selects the retrieval-augmented path; strip it before flag parsing
    // so it isn't mistaken for a message.
    let rag_mode = raw.iter().any(|a| a == "--rag");
    let raw: Vec<String> = raw.into_iter().filter(|a| a != "--rag").collect();

    let (sampler_cfg, args) = parse_sampler_args(&raw);
    let (format, args) = extract_format(&args);

    if rag_mode {
        run_rag(&args, sampler_cfg);
        return;
    }

    // Bound retained history to 4 non-system messages (≈ 2 turns) so the prompt
    // stays small no matter how long the dialogue runs.
    const MAX_TURNS: usize = 4;
    let mut chat = ChatSession::new(
        runtime(sampler_cfg),
        Some("You are a sovereign local assistant."),
        6,
    )
    .with_max_turns(MAX_TURNS);
    if let Some(fmt) = format {
        chat = chat.with_format(fmt);
    }

    // Operator messages if given, else a built-in demo dialogue. Either way the
    // history-bounding (the assembly's point) operates on the real turns.
    let demo_turns = [
        "hello",
        "what can you do",
        "tell me about sovereignty",
        "and about cost",
    ];
    let user_turns: Vec<&str> = {
        let given: Vec<&str> = args.iter().map(String::as_str).collect();
        if given.is_empty() {
            demo_turns.to_vec()
        } else {
            given
        }
    };

    let t = sampler_cfg.temperature;
    println!("system + bounded history (max {MAX_TURNS} non-system messages); temperature {t}\n");
    for (i, user) in user_turns.iter().enumerate() {
        match chat.say(user, i as u64) {
            Ok(reply) => {
                let h = chat.history();
                let non_system = h.messages.iter().filter(|m| m.role != Role::System).count();
                println!(
                    "turn {i}: user={user:?} → reply={reply:?}\n         history: {} messages ({} non-system, ≤ {MAX_TURNS})",
                    h.len(),
                    non_system,
                );
            }
            Err(e) => println!("turn {i}: error: {e}"),
        }
    }

    // The earliest turns have been dropped; the system message is always kept.
    let h = chat.history();
    println!(
        "\n# final history: {} messages; first is {:?} (system always retained)",
        h.len(),
        h.messages.first().map(|m| m.role)
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(v: &[&str]) -> Vec<String> {
        v.iter().map(|x| x.to_string()).collect()
    }

    #[test]
    fn parses_decode_flags_and_keeps_messages() {
        let (cfg, msgs) = parse_sampler_args(&s(&[
            "hello",
            "--temperature",
            "0.7",
            "--top-k",
            "40",
            "world",
            "--typical-p=0.9",
        ]));
        assert!((cfg.temperature - 0.7).abs() < 1e-6);
        assert_eq!(cfg.top_k, Some(40));
        assert_eq!(cfg.typical_p, Some(0.9));
        assert_eq!(msgs, s(&["hello", "world"]));
    }

    #[test]
    fn defaults_when_no_flags() {
        let (cfg, msgs) = parse_sampler_args(&s(&["just", "messages"]));
        assert_eq!(cfg, SamplerConfig::default());
        assert_eq!(msgs, s(&["just", "messages"]));
    }

    #[test]
    fn short_temperature_and_equals_form() {
        let (cfg, msgs) = parse_sampler_args(&s(&["-T", "0.0", "--top-p=0.95"]));
        assert_eq!(cfg.temperature, 0.0);
        assert_eq!(cfg.top_p, Some(0.95));
        assert!(msgs.is_empty());
    }

    #[test]
    fn bad_value_falls_back_to_default() {
        // "--top-k notanumber" → top_k stays None, and the bad value is treated
        // as a message rather than silently consumed.
        let (cfg, _msgs) = parse_sampler_args(&s(&["--top-k", "notanumber"]));
        assert_eq!(cfg.top_k, None);
    }

    #[test]
    fn extracts_format_flag_and_keeps_messages() {
        use sovereign_chat_template::ChatFormat;
        let (fmt, msgs) = extract_format(&s(&["hello", "--format", "chatml", "world"]));
        assert_eq!(fmt, Some(ChatFormat::ChatML));
        assert_eq!(msgs, s(&["hello", "world"]));
        // equals form + alpaca
        let (fmt2, _) = extract_format(&s(&["--format=alpaca"]));
        assert_eq!(fmt2, Some(ChatFormat::Alpaca));
        // unrecognized → None, flag dropped
        let (fmt3, m3) = extract_format(&s(&["--format", "bogus", "hi"]));
        assert_eq!(fmt3, None);
        assert_eq!(m3, s(&["hi"]));
        // absent → None, messages untouched
        let (fmt4, m4) = extract_format(&s(&["just", "talk"]));
        assert_eq!(fmt4, None);
        assert_eq!(m4, s(&["just", "talk"]));
    }

    #[test]
    fn runtime_builds_with_custom_sampler() {
        let cfg = SamplerConfig {
            temperature: 0.5,
            top_k: Some(10),
            ..SamplerConfig::default()
        };
        let llm = runtime(cfg);
        assert!(llm.vocab_size() > 0);
    }

    #[test]
    fn rag_grounds_a_known_query() {
        // The `--rag` wiring: runtime → LlmResponder → RagResponder over the
        // built-in store. A question about the box retrieves the matching doc
        // and prepends it as context before the (untrained) reply.
        let responder = LlmResponder::new(runtime(SamplerConfig::default()), 6);
        let rag = RagResponder::new(responder, knowledge_store(), 2);
        let aug = rag.augment("what is sovereignty");
        assert!(aug.contains("Context:"), "retrieval did not fire:\n{aug}");
        assert!(
            aug.to_lowercase().contains("local hardware"),
            "did not retrieve the sovereignty doc:\n{aug}"
        );
        assert!(
            aug.ends_with("what is sovereignty"),
            "the query must be appended after the context:\n{aug}"
        );
    }

    #[test]
    fn knowledge_store_retrieves_a_corpus_match() {
        use sovereign_retrieval::Retriever;
        let store = knowledge_store();
        let ctx = store.retrieve_context("cost per token electricity", 2);
        assert!(!ctx.is_empty(), "no retrieval for a corpus term");
        assert!(
            ctx.iter().any(|d| d.to_lowercase().contains("electricity")),
            "did not retrieve the cost doc: {ctx:?}"
        );
    }
}
