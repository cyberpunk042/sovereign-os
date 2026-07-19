//! Real-model **coherence harness** for GPT-OSS — the verification the whole
//! GPT-OSS decoder line (safetensors MXFP4 + attention biases/sinks + sliding
//! window + the GGUF path) is ultimately gated on but which no synthetic fixture
//! can stand in for: does a **real** gpt-oss checkpoint, loaded by this crate,
//! produce sane autoregressive logits on this box?
//!
//! It is **env-gated** so CI (which has no multi-GB checkpoint) compiles it and
//! skips at run time. Point it at a real GGUF and run it to close the gate:
//!
//! ```text
//! # a gpt-oss GGUF (e.g. from ggml-org/gpt-oss-20b-GGUF) — self-contained:
//! # k-quant experts we already dequant + the tokenizer in metadata, so no MXFP4.
//! export SOVEREIGN_GPT_OSS_GGUF=/path/to/gpt-oss-20b.gguf
//! cargo test -p sovereign-safetensors-loader --test gpt_oss_coherence -- --nocapture
//! ```
//!
//! Optional: `SOVEREIGN_GPT_OSS_PROMPT_IDS="1 2 3"` seeds the rollout with those
//! token ids (default: a single non-zero id). A gpt-oss GGUF is the tractable
//! real path — its experts are standard k-quants this crate already dequants
//! byte-exact and it carries its tokenizer in metadata, so no MXFP4 and no
//! separate vocab bridge is needed to smoke it.
//!
//! What it asserts (mechanical invariants a broken dequant/assembly would trip)
//! vs what it EMITS (the human-judged coherence signal — a real coherence verdict
//! is a human/reference-model call, so the harness produces the evidence, it does
//! not fabricate a threshold): every step's logits are finite, non-degenerate
//! (not all-equal), and the greedy argmax is a valid token id; the greedy id
//! rollout is printed for inspection, with a soft note if it collapses to a
//! single repeated token (a real degeneration signal, not a hard failure).
//!
//! The **safetensors** arm (`openai/gpt-oss-20b`) is a documented follow-up: that
//! release is multi-shard MXFP4, so it needs the loader's multi-shard/index
//! assembly before a real dir loads — the GGUF arm here is the coherence anchor.

use sovereign_safetensors_loader::{Precision, Sampler, load_gguf};

fn argmax(logits: &[f32]) -> usize {
    let mut best = 0usize;
    let mut best_v = f32::NEG_INFINITY;
    for (i, &v) in logits.iter().enumerate() {
        if v > best_v {
            best_v = v;
            best = i;
        }
    }
    best
}

#[test]
fn gpt_oss_gguf_real_model_is_coherent() {
    let path = match std::env::var("SOVEREIGN_GPT_OSS_GGUF") {
        Ok(p) if !p.trim().is_empty() => p,
        _ => {
            eprintln!(
                "SKIP gpt_oss_gguf_real_model_is_coherent: set SOVEREIGN_GPT_OSS_GGUF to a \
                 gpt-oss .gguf to run the real-model coherence check (see the runbook)."
            );
            return;
        }
    };
    let bytes = std::fs::read(&path).unwrap_or_else(|e| panic!("read {path}: {e}"));
    let mut model = load_gguf(&bytes, Precision::F32, Sampler::greedy())
        .unwrap_or_else(|e| panic!("load gpt-oss GGUF at {path}: {e:?}"));
    let vocab = model.vocab();
    assert!(vocab > 0, "vocab must be positive");

    // Seed the rollout (from the env, else a single non-zero id) then greedily
    // continue, asserting the mechanical invariants at every step.
    let seed_ids: Vec<usize> = std::env::var("SOVEREIGN_GPT_OSS_PROMPT_IDS")
        .ok()
        .map(|s| {
            s.split_whitespace()
                .filter_map(|t| t.parse::<usize>().ok())
                .filter(|&t| t < vocab)
                .collect()
        })
        .filter(|v: &Vec<usize>| !v.is_empty())
        .unwrap_or_else(|| vec![1 % vocab]);

    let assert_logits = |logits: &[f32], where_: &str| {
        assert_eq!(
            logits.len(),
            vocab,
            "{where_}: logits width must equal vocab"
        );
        assert!(
            logits.iter().all(|x| x.is_finite()),
            "{where_}: logits must be finite (a broken dequant/assembly yields NaN/inf)"
        );
        let (mn, mx) = logits
            .iter()
            .fold((f32::INFINITY, f32::NEG_INFINITY), |(a, b), &x| {
                (a.min(x), b.max(x))
            });
        assert!(
            mx > mn,
            "{where_}: logits must be non-degenerate (not all-equal), got min==max=={mn}"
        );
    };

    let mut rollout: Vec<usize> = Vec::new();
    let mut last = seed_ids[0];
    for (i, &t) in seed_ids.iter().enumerate() {
        let logits = model.forward(t).expect("forward on a seed id");
        assert_logits(&logits, &format!("seed[{i}]"));
        last = argmax(&logits);
        assert!(last < vocab, "argmax must be a valid token id");
    }
    rollout.push(last);
    for step in 0..24 {
        let logits = model.forward(last).expect("forward during rollout");
        assert_logits(&logits, &format!("rollout[{step}]"));
        last = argmax(&logits);
        assert!(last < vocab, "argmax must be a valid token id");
        rollout.push(last);
    }

    let distinct: std::collections::HashSet<usize> = rollout.iter().copied().collect();
    eprintln!(
        "gpt-oss GGUF coherence @ {path}\n  vocab={vocab} seed_ids={seed_ids:?}\n  \
         greedy_rollout={rollout:?}\n  distinct_tokens={}/{}",
        distinct.len(),
        rollout.len()
    );
    if distinct.len() == 1 {
        // Not a hard failure (a real model CAN loop on a degenerate seed), but the
        // signal a human wants to see when judging coherence.
        eprintln!(
            "  NOTE: the greedy rollout collapsed to a single repeated token — inspect \
             the checkpoint / seed before trusting coherence."
        );
    }
}
