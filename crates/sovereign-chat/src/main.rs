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
//! Usage: `sovereign-chat` (runs the demo session) · `sovereign-chat --help`.

use sovereign_chat::{ChatSession, Role};
use sovereign_decoder_stack::StackConfig;
use sovereign_ffn::SwiGlu;
use sovereign_llm::SovereignLlm;
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
sovereign-chat — multi-turn conversation with bounded history on the real engine

USAGE:
    sovereign-chat                   run the demo session (4 turns, bounded), exit
    sovereign-chat MESSAGE [MESSAGE…] run your messages as turns (history bounded)
    sovereign-chat --help            print this help and exit";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!("{USAGE}");
        return;
    }

    // Bound retained history to 4 non-system messages (≈ 2 turns) so the prompt
    // stays small no matter how long the dialogue runs.
    const MAX_TURNS: usize = 4;
    let mut chat = ChatSession::new(runtime(), Some("You are a sovereign local assistant."), 6)
        .with_max_turns(MAX_TURNS);

    // Operator messages if given, else a built-in demo dialogue. Either way the
    // history-bounding (the assembly's point) operates on the real turns.
    let demo_turns = [
        "hello",
        "what can you do",
        "tell me about sovereignty",
        "and about cost",
    ];
    let user_turns: Vec<&str> = {
        let given: Vec<&str> = args
            .iter()
            .filter(|a| !a.starts_with('-'))
            .map(String::as_str)
            .collect();
        if given.is_empty() {
            demo_turns.to_vec()
        } else {
            given
        }
    };

    println!("system + bounded history (max {MAX_TURNS} non-system messages)\n");
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
