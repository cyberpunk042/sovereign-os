//! `sovereign-inference-demo` — a runnable end-to-end demo of the stack.
//!
//! This binary assembles the real inference engine from its crates and runs
//! it: a byte-level BPE tokenizer in front of a mixed-precision decoder model
//! whose three layers are an f32 transformer block, a ternary quant block, and
//! an NVFP4 multi-head block — one residual stream across three precisions. It
//! then drives unconstrained and constrained generation and prints the whole
//! pipeline. The weights are deterministic pseudo-values (this demonstrates
//! that the engine *runs and composes*, not that it produces trained output).
//!
//! Run with: `cargo run -p sovereign-inference-demo`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use sovereign_beam_search::BeamSearch;
use sovereign_checkpoint::{load, save};
use sovereign_decoder_layer::{DecoderLayer, LayerStack};
use sovereign_decoder_stack::{DecoderStack, StackConfig};
use sovereign_ffn::SwiGlu;
use sovereign_linear::Precision;
use sovereign_llm::LlmConfig;
use sovereign_logit_mask::LogitMask;
use sovereign_mha_block::{MhaBlockWeights, MhaDecoderBlock};
use sovereign_perplexity::evaluate;
use sovereign_quant_block::{QuantBlockWeights, QuantDecoderBlock};
use sovereign_quant_llm::QuantLlm;
use sovereign_quant_model::QuantModel;
use sovereign_rmsnorm::RmsNorm;
use sovereign_sampler::{Sampler, SamplerConfig};
use sovereign_speculative::Speculative;
use sovereign_tokenizer::Tokenizer;
use sovereign_transformer_block::{BlockWeights, DecoderBlock};

const MODEL_DIM: usize = 8;

/// Deterministic pseudo-weights of length `n`.
fn weights(seed: f32, n: usize) -> Vec<f32> {
    (0..n)
        .map(|i| ((i as f32 + seed) * 0.013).sin() * 0.5)
        .collect()
}

/// An f32 transformer block (single head, model_dim wide).
fn f32_layer() -> DecoderBlock {
    let md = MODEL_DIM;
    DecoderBlock::new(BlockWeights {
        model_dim: md,
        head_dim: md,
        attn_norm: RmsNorm::new(md),
        ffn_norm: RmsNorm::new(md),
        w_q: weights(1.0, md * md),
        w_k: weights(2.0, md * md),
        w_v: weights(3.0, md * md),
        w_o: weights(4.0, md * md),
        ffn: SwiGlu::new(
            md,
            md,
            weights(5.0, md * md),
            weights(6.0, md * md),
            weights(7.0, md * md),
        )
        .expect("valid swiglu"),
    })
    .expect("valid f32 block")
}

/// A ternary (1.58-bit) quant block.
fn ternary_layer() -> QuantDecoderBlock {
    let md = MODEL_DIM;
    QuantDecoderBlock::from_weights(
        &QuantBlockWeights {
            model_dim: md,
            head_dim: md,
            hidden_dim: md,
            attn_norm: RmsNorm::new(md),
            ffn_norm: RmsNorm::new(md),
            w_q: weights(8.0, md * md),
            w_k: weights(9.0, md * md),
            w_v: weights(10.0, md * md),
            w_o: weights(11.0, md * md),
            w_gate: weights(12.0, md * md),
            w_up: weights(13.0, md * md),
            w_down: weights(14.0, md * md),
        },
        Precision::Ternary,
    )
    .expect("valid ternary block")
}

/// An NVFP4 multi-head (GQA) block: 4 query heads, 2 KV heads, head_dim 2.
fn nvfp4_mha_layer() -> MhaDecoderBlock {
    let md = MODEL_DIM;
    let (nq, nkv, hd) = (4, 2, 2);
    MhaDecoderBlock::from_weights(
        &MhaBlockWeights {
            model_dim: md,
            head_dim: hd,
            num_q_heads: nq,
            num_kv_heads: nkv,
            hidden_dim: md,
            attn_norm: RmsNorm::new(md),
            ffn_norm: RmsNorm::new(md),
            w_q: weights(15.0, nq * hd * md),
            w_k: weights(16.0, nkv * hd * md),
            w_v: weights(17.0, nkv * hd * md),
            w_o: weights(18.0, md * nq * hd),
            w_gate: weights(19.0, md * md),
            w_up: weights(20.0, md * md),
            w_down: weights(21.0, md * md),
        },
        Precision::Nvfp4,
    )
    .expect("valid nvfp4 mha block")
}

/// Build the demo runtime: BPE tokenizer + mixed-precision 3-layer model.
fn build_runtime() -> QuantLlm {
    // a few merges so the tokenizer does real BPE, not just raw bytes
    let merges = [("t", "h"), ("th", "e"), ("e", " ")]
        .iter()
        .map(|(a, b)| (a.as_bytes().to_vec(), b.as_bytes().to_vec()))
        .collect();
    let tokenizer = Tokenizer::from_merges(merges);
    let vocab = tokenizer.vocab_size();

    let layers: Vec<Box<dyn DecoderLayer>> = vec![
        Box::new(f32_layer()),
        Box::new(ternary_layer()),
        Box::new(nvfp4_mha_layer()),
    ];
    let stack = LayerStack::new(layers).expect("non-empty stack");

    let model = QuantModel::new(
        vocab,
        MODEL_DIM,
        weights(0.5, vocab * MODEL_DIM),
        stack,
        RmsNorm::new(MODEL_DIM),
        weights(0.9, vocab * MODEL_DIM),
        Sampler::new(SamplerConfig {
            temperature: 0.8,
            top_k: Some(40),
            ..SamplerConfig::default()
        }),
    )
    .expect("vocab-consistent model");

    QuantLlm::new(tokenizer, model).expect("matching vocab")
}

/// Run the demonstration, returning the printed report (also used by a smoke
/// test).
fn run_demo() -> String {
    use std::fmt::Write as _;
    let mut out = String::new();
    let prompt = "the cat";
    let seed = 0xC0FFEE;

    let mut llm = build_runtime();
    let _ = writeln!(out, "=== sovereign quantized inference demo ===");
    let _ = writeln!(out, "tokenizer vocab : {}", llm.vocab_size());
    let _ = writeln!(
        out,
        "decoder layers  : {} (f32 | ternary | NVFP4-MHA)",
        llm.layers()
    );
    let _ = writeln!(out, "prompt          : {prompt:?}");

    let ids = llm.generate_ids(prompt, 12, seed).expect("generation");
    let text = llm.complete(prompt, 12, seed).expect("completion");
    let _ = writeln!(out, "generated ids   : {ids:?}");
    let _ = writeln!(out, "generated text  : {text:?}");

    // constrained: confine generation to the bytes for 'A'..='D'
    let mask = LogitMask::new().allow_only((b'A' as usize)..=(b'D' as usize));
    let constrained = llm
        .complete_constrained(prompt, 12, seed, &mask)
        .expect("constrained completion");
    let _ = writeln!(out, "constrained out : {constrained:?} (allow-list A..=D)");

    // determinism: same seed reproduces the same ids
    let mut llm2 = build_runtime();
    let again = llm2.generate_ids(prompt, 12, seed).expect("generation");
    let _ = writeln!(out, "reproducible    : {}", again == ids);

    out
}

/// Build a small f32 decoder-stack model (vocab 64, 1 block) for the
/// decoding-strategy and evaluation demonstrations.
fn build_f32_model(vocab: usize) -> StackConfig {
    let md = MODEL_DIM;
    let block = BlockWeights {
        model_dim: md,
        head_dim: md,
        attn_norm: RmsNorm::new(md),
        ffn_norm: RmsNorm::new(md),
        w_q: weights(1.0, md * md),
        w_k: weights(2.0, md * md),
        w_v: weights(3.0, md * md),
        w_o: weights(4.0, md * md),
        ffn: SwiGlu::new(
            md,
            md,
            weights(5.0, md * md),
            weights(6.0, md * md),
            weights(7.0, md * md),
        )
        .expect("valid swiglu"),
    };
    StackConfig {
        vocab,
        model_dim: md,
        embedding: weights(0.5, vocab * md),
        blocks: vec![block],
        final_norm: RmsNorm::new(md),
        head: weights(0.9, vocab * md),
        sampler: Sampler::new(SamplerConfig {
            temperature: 0.8,
            ..SamplerConfig::default()
        }),
        recent_window: 64,
    }
}

/// Demonstrate the f32 decoder-stack across all decoding strategies, perplexity
/// evaluation, and a checkpoint round-trip.
fn run_strategies_demo() -> String {
    use std::fmt::Write as _;
    let mut out = String::new();
    let vocab = 64usize;
    let prompt = [7usize, 11, 23];
    let cfg = build_f32_model(vocab);
    let model = DecoderStack::new(cfg.clone()).expect("valid model");

    let _ = writeln!(
        out,
        "\n=== decoding strategies (f32 decoder-stack, vocab {vocab}) ==="
    );

    // sampling
    let mut sampled = model.clone();
    let s = sampled.generate(&prompt, 8, 42).expect("sample");
    let _ = writeln!(out, "sampled         : {s:?}");

    // beam search (deterministic)
    let beam = BeamSearch::new(4, 8).search(&model, &prompt).expect("beam");
    let _ = writeln!(
        out,
        "beam (w=4)      : {:?} (logprob {:.3})",
        beam.tokens, beam.score
    );

    // speculative decoding (self-draft → lossless vs greedy target)
    let spec = Speculative::new(4, 8)
        .decode(&model, &model, &prompt)
        .expect("spec");
    let _ = writeln!(
        out,
        "speculative     : {:?} (accept {}/{} = {:.0}%)",
        spec.tokens,
        spec.accepted,
        spec.proposed,
        spec.acceptance_rate() * 100.0
    );

    // perplexity over a reference sequence
    let reference = [7usize, 11, 23, 5, 9, 2, 14];
    let ev = evaluate(&model, &reference).expect("perplexity");
    let _ = writeln!(
        out,
        "perplexity      : {:.3} (cross-entropy {:.3} nats over {} tokens)",
        ev.perplexity, ev.cross_entropy, ev.predicted
    );

    // checkpoint save + load round-trip
    let llm_cfg = LlmConfig {
        tokenizer: Tokenizer::default(),
        model: cfg,
    };
    let bytes = save(&llm_cfg);
    let restored = load(&bytes).expect("checkpoint loads");
    let _ = writeln!(
        out,
        "checkpoint      : {} bytes, round-trip ok = {}",
        bytes.len(),
        restored == llm_cfg
    );

    out
}

/// Demonstrate the agentic stack: a RAG-grounded, tool-equipped agent running
/// on the real LLM runtime, end to end.
fn run_agent_demo() -> String {
    use sovereign_agent_loop::AgentLoop;
    use sovereign_agent_runtime::LlmResponder;
    use sovereign_embed::EmbedStore;
    use sovereign_retrieval::RagResponder;
    use sovereign_tool_dispatch::ToolRegistry;
    use std::fmt::Write as _;

    let mut out = String::new();
    let _ = writeln!(
        out,
        "\n=== agentic stack (RAG + tools + ReAct on the real runtime) ==="
    );

    // a tiny f32 runtime over the byte vocab
    let tok = Tokenizer::default();
    let vocab = tok.vocab_size();
    let cfg = build_f32_model(vocab);
    let llm = sovereign_llm::SovereignLlm::new(tok, cfg).expect("runtime");

    // knowledge to ground answers (embedding-backed semantic retrieval)
    let mut docs = EmbedStore::new();
    docs.add(
        "rust",
        "rust ownership gives memory safety without a garbage collector",
    );
    docs.add("cook", "pasta with tomato sauce and basil");

    // a tool the agent could call
    let mut tools = ToolRegistry::new();
    tools.register("upper", |a| a.to_uppercase());

    // compose: runtime -> RAG (grounds the prompt) -> agent loop (tools + ReAct)
    let responder = LlmResponder::new(llm, 6);
    let rag = RagResponder::new(responder, docs, 1);
    let mut agent = AgentLoop::new(rag, tools, 3);

    let res = agent
        .run("rust memory safety", 0xABCDEF)
        .expect("agent run");
    let _ = writeln!(out, "tools available : {:?}", agent.tool_names());
    let _ = writeln!(out, "agent steps     : {}", res.steps.len());
    let _ = writeln!(out, "completed       : {}", res.completed);
    let _ = writeln!(
        out,
        "answer (len {})  : {:?}",
        res.answer.as_deref().unwrap_or("").chars().count(),
        res.answer.as_deref().unwrap_or("")
    );
    out
}

fn main() {
    if std::env::args().any(|a| a == "--help" || a == "-h") {
        println!(
            "sovereign-inference-demo — quantized-inference + decoding-strategies + agentic demos\n\n\
             USAGE:\n\
             \x20   sovereign-inference-demo        run the demos, print, exit\n\
             \x20   sovereign-inference-demo --help print this help and exit"
        );
        return;
    }
    print!("{}", run_demo());
    print!("{}", run_strategies_demo());
    print!("{}", run_agent_demo());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn demo_runs_end_to_end() {
        let report = run_demo();
        assert!(report.contains("sovereign quantized inference demo"));
        assert!(report.contains("decoder layers  : 3"));
        // reproducibility line must report true
        assert!(report.contains("reproducible    : true"), "{report}");
    }

    #[test]
    fn constrained_demo_output_is_confined() {
        let mut llm = build_runtime();
        let mask = LogitMask::new().allow_only((b'A' as usize)..=(b'D' as usize));
        let text = llm.complete_constrained("the cat", 12, 1, &mask).unwrap();
        assert!(text.chars().all(|c| ('A'..='D').contains(&c)), "{text:?}");
    }

    #[test]
    fn strategies_demo_runs_and_reports_each_strategy() {
        let report = run_strategies_demo();
        assert!(report.contains("sampled"));
        assert!(report.contains("beam (w=4)"));
        assert!(report.contains("speculative"));
        assert!(report.contains("perplexity"));
        assert!(report.contains("round-trip ok = true"), "{report}");
    }

    #[test]
    fn agent_demo_runs_the_full_stack() {
        let report = run_agent_demo();
        assert!(report.contains("agentic stack"));
        assert!(report.contains("tools available : [\"upper\"]"));
        assert!(report.contains("completed       : true"));
    }

    #[test]
    fn speculative_in_demo_is_lossless_vs_beam_width_one() {
        // self-draft speculative == greedy target == beam width 1, on the demo model.
        let cfg = build_f32_model(64);
        let model = DecoderStack::new(cfg).unwrap();
        let prompt = [7usize, 11, 23];
        let spec = Speculative::new(4, 8)
            .decode(&model, &model, &prompt)
            .unwrap();
        let beam1 = BeamSearch::new(1, 8).search(&model, &prompt).unwrap();
        assert_eq!(spec.tokens, beam1.tokens);
    }
}
