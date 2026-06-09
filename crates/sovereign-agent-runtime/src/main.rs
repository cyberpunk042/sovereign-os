//! `sovereign-agent-runtime` binary — runs the agent assembly end-to-end.
//!
//! The library bridges the real quantized inference engine (`sovereign-llm`)
//! into the ReAct control loop (`sovereign-agent-loop`) via an `LlmResponder`,
//! but was lib-only — the running agent never actually ran. This binary drives
//! it two ways:
//!
//! 1. **Real runtime** — a small `SovereignLlm` drives the loop, proving the
//!    inference stack + agentic layer compose into one running agent. (The
//!    weights are random, so the model emits no tool call and the loop finishes
//!    in one step with a gibberish answer — the point is that the real engine
//!    drives the control flow end to end.)
//! 2. **Scripted ReAct** — a deterministic responder that emits a tool call,
//!    illustrating what the loop *does*: generate → dispatch a tool → feed the
//!    observation back → reach a final answer.
//!
//! Usage: `sovereign-agent-runtime` (runs both) · `sovereign-agent-runtime --help`.

use sovereign_agent_loop::{AgentLoop, ScriptedResponder};
use sovereign_agent_runtime::LlmResponder;
use sovereign_decoder_stack::StackConfig;
use sovereign_ffn::SwiGlu;
use sovereign_llm::SovereignLlm;
use sovereign_rmsnorm::RmsNorm;
use sovereign_sampler::{Sampler, SamplerConfig};
use sovereign_tokenizer::Tokenizer;
use sovereign_tool_dispatch::ToolRegistry;
use sovereign_transformer_block::BlockWeights;

const MD: usize = 4;

/// Deterministic weight filler (a smooth function of the index) — a stand-in
/// for trained weights so the demo is reproducible without a checkpoint.
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

/// A tool registry the agent can call: `echo` returns its argument, `upper`
/// upper-cases it.
fn tools() -> ToolRegistry {
    let mut t = ToolRegistry::new();
    t.register("echo", |a| a.to_string());
    t.register("upper", |a| a.to_uppercase());
    t
}

const USAGE: &str = "\
sovereign-agent-runtime — a tool-using ReAct agent on the real quantized inference engine

USAGE:
    sovereign-agent-runtime         run the real-runtime + scripted demos, exit
    sovereign-agent-runtime --help  print this help and exit";

fn main() {
    if std::env::args().any(|a| a == "--help" || a == "-h") {
        println!("{USAGE}");
        return;
    }

    // 1. The real inference engine drives the agent loop.
    println!("== real runtime (sovereign-llm drives the ReAct loop) ==");
    let mut real = AgentLoop::new(LlmResponder::new(runtime(), 6), tools(), 4);
    println!("tools: {:?}", real.tool_names());
    match real.run("hello", 0) {
        Ok(res) => {
            println!(
                "completed={} steps={} answer={:?}",
                res.completed,
                res.steps.len(),
                res.answer
            );
            println!(
                "(random-init weights → no tool call; this proves the inference stack drives the loop end-to-end)"
            );
        }
        Err(e) => println!("error: {e}"),
    }

    // 2. A scripted run that actually exercises the tool loop.
    println!(
        "\n== scripted ReAct (illustrating the generate → tool → observation → answer loop) =="
    );
    let script = ScriptedResponder::new([
        "I'll make it loud. [[tool:upper|sovereign]]",
        "The answer is SOVEREIGN.",
    ]);
    let mut scripted = AgentLoop::new(script, tools(), 4);
    match scripted.run("make 'sovereign' loud", 0) {
        Ok(res) => {
            for (i, step) in res.steps.iter().enumerate() {
                match &step.tool {
                    Some(o) => println!(
                        "step {i}: reply={:?} → tool {}({:?}) = {:?}",
                        step.reply, o.call.name, o.call.args, o.result
                    ),
                    None => println!("step {i}: final answer = {:?}", step.reply),
                }
            }
            println!("completed={} answer={:?}", res.completed, res.answer);
        }
        Err(e) => println!("error: {e}"),
    }
}
