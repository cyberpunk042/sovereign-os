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

use sovereign_decoder_layer::{DecoderLayer, LayerStack};
use sovereign_ffn::SwiGlu;
use sovereign_linear::Precision;
use sovereign_logit_mask::LogitMask;
use sovereign_mha_block::{MhaBlockWeights, MhaDecoderBlock};
use sovereign_quant_block::{QuantBlockWeights, QuantDecoderBlock};
use sovereign_quant_llm::QuantLlm;
use sovereign_quant_model::QuantModel;
use sovereign_rmsnorm::RmsNorm;
use sovereign_sampler::{Sampler, SamplerConfig};
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

fn main() {
    print!("{}", run_demo());
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
}
