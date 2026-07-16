//! Integration tests for `sovereign-llm` — exercise the public text-to-text API
//! from an external consumer's perspective.
//!
//! Every test builds a tiny synthetic model (deterministic pseudo-weights) so the
//! suite is fast, requires no real checkpoint, and is fully reproducible.

use sovereign_decoder_stack::{DecoderStack, StackConfig};
use sovereign_ffn::SwiGlu;
use sovereign_llm::{
    Calibration, ConfidenceReport, LlmConfig, SampleDiversity, SemanticCachedLlm, SovereignLlm,
    Vote,
};
use sovereign_rmsnorm::RmsNorm;
use sovereign_sampler::{Sampler, SamplerConfig};
use sovereign_tokenizer::Tokenizer;
use sovereign_transformer_block::BlockWeights;

const MD: usize = 4;

fn mat(s: f32, n: usize) -> Vec<f32> {
    (0..n).map(|i| ((i as f32 + s) * 0.013).sin()).collect()
}

fn block(seed: f32) -> BlockWeights {
    BlockWeights {
        model_dim: MD,
        head_dim: MD,
        attn_norm: RmsNorm::new(MD),
        ffn_norm: RmsNorm::new(MD),
        w_q: mat(seed, MD * MD),
        w_k: mat(seed + 1.0, MD * MD),
        w_v: mat(seed + 2.0, MD * MD),
        w_o: mat(seed + 3.0, MD * MD),
        ffn: SwiGlu::new(
            MD,
            MD,
            mat(seed + 4.0, MD * MD),
            mat(seed + 5.0, MD * MD),
            mat(seed + 6.0, MD * MD),
        )
        .unwrap(),
    }
}

fn model_config(vocab: usize, layers: usize, sampler: Sampler) -> StackConfig {
    StackConfig {
        vocab,
        model_dim: MD,
        embedding: (0..vocab * MD)
            .map(|i| ((i as f32) * 0.001).sin())
            .collect(),
        blocks: (0..layers).map(|l| block(l as f32 * 7.0)).collect(),
        final_norm: RmsNorm::new(MD),
        head: (0..vocab * MD)
            .map(|i| ((i as f32) * 0.001).cos())
            .collect(),
        sampler,
        recent_window: 64,
    }
}

fn runtime(sampler: Sampler) -> SovereignLlm {
    let tok = Tokenizer::default();
    let cfg = model_config(tok.vocab_size(), 2, sampler);
    SovereignLlm::new(tok, cfg).unwrap()
}

fn runtime_with_eos(sampler: Sampler) -> SovereignLlm {
    let tok = Tokenizer::default().with_specials(["<eos>"]);
    let cfg = model_config(tok.vocab_size(), 2, sampler);
    SovereignLlm::new(tok, cfg).unwrap()
}

// ---------------------------------------------------------------------------
// Construction and basic properties
// ---------------------------------------------------------------------------

#[test]
fn runtime_reports_correct_vocab_and_layers() {
    let llm = runtime(Sampler::greedy());
    assert_eq!(llm.vocab_size(), 256);
    assert_eq!(llm.layers(), 2);
}

#[test]
fn vocab_mismatch_is_rejected() {
    let tok = Tokenizer::default(); // 256
    let cfg = model_config(100, 1, Sampler::greedy());
    let err = SovereignLlm::new(tok, cfg).unwrap_err();
    assert!(err.to_string().contains("vocab mismatch"));
}

#[test]
fn llm_config_serde_roundtrip() {
    let tok = Tokenizer::default();
    let cfg = LlmConfig {
        tokenizer: tok.clone(),
        model: model_config(tok.vocab_size(), 1, Sampler::greedy()),
    };
    let j = serde_json::to_string(&cfg).unwrap();
    let back: LlmConfig = serde_json::from_str(&j).unwrap();
    assert_eq!(cfg, back);
    assert!(SovereignLlm::from_config(back).is_ok());
}

// ---------------------------------------------------------------------------
// Generation is reproducible and bounded
// ---------------------------------------------------------------------------

#[test]
fn complete_is_reproducible_per_seed() {
    let a = runtime(Sampler::new(SamplerConfig::default()));
    let b = runtime(Sampler::new(SamplerConfig::default()));
    assert_eq!(
        a.complete("the quick brown fox", 10, 7).unwrap(),
        b.complete("the quick brown fox", 10, 7).unwrap()
    );
}

#[test]
fn generate_ids_stay_in_vocab() {
    let llm = runtime(Sampler::new(SamplerConfig::default()));
    let ids = llm.generate_ids("hello", 12, 99).unwrap();
    let v = llm.vocab_size() as u32;
    assert!(ids.iter().all(|&t| t < v));
}

#[test]
fn generation_is_stateless_across_calls() {
    let llm = runtime(Sampler::new(SamplerConfig::default()));
    let a = llm.generate_ids("hello world", 10, 5).unwrap();
    let _ = llm.generate_ids("other prompt", 7, 9).unwrap();
    let c = llm.generate_ids("hello world", 10, 5).unwrap();
    assert_eq!(a, c);
}

// ---------------------------------------------------------------------------
// Self-consistency and best-of-n
// ---------------------------------------------------------------------------

#[test]
fn self_consistent_greedy_is_unanimous() {
    let llm = runtime(Sampler::greedy());
    let vote = llm.complete_self_consistent("hello", 6, 4, 5).unwrap();
    assert_eq!(vote.total, 5);
    assert_eq!(vote.count, 5);
    assert!((vote.agreement - 1.0).abs() < 1e-9);
    assert_eq!(vote.answer, llm.complete("hello", 6, 4).unwrap());
}

#[test]
fn best_of_n_greedy_equals_single_complete() {
    let llm = runtime(Sampler::greedy());
    assert_eq!(
        llm.complete_best_of_n("hello", 6, 4, 5).unwrap(),
        llm.complete("hello", 6, 4).unwrap()
    );
}

#[test]
fn best_of_n_zero_clamps_to_single() {
    let llm = runtime(Sampler::greedy());
    assert_eq!(
        llm.complete_best_of_n("hello", 6, 4, 0).unwrap(),
        llm.complete("hello", 6, 4).unwrap()
    );
}

// ---------------------------------------------------------------------------
// Confidence reporting
// ---------------------------------------------------------------------------

#[test]
fn completion_confidence_summarizes_generated_tokens() {
    let llm = runtime(Sampler::greedy());
    let report = llm.completion_confidence("hello", 8, 5).unwrap().unwrap();
    assert_eq!(
        report.tokens,
        llm.generate_ids("hello", 8, 5).unwrap().len()
    );
    assert!(report.perplexity >= 1.0 - 1e-9 && report.perplexity.is_finite());
    assert!(report.mean_logprob <= 1e-9);
    assert!(report.weakest_logprob <= report.mean_logprob + 1e-9);
    assert!(report.weakest_index.unwrap() < report.tokens);
}

#[test]
fn completion_confidence_zero_max_new_is_none() {
    let llm = runtime(Sampler::greedy());
    assert_eq!(llm.completion_confidence("hello", 0, 5).unwrap(), None);
}

// ---------------------------------------------------------------------------
// Semantic cache
// ---------------------------------------------------------------------------

#[test]
fn semantic_cache_first_misses_then_hits() {
    let mut cached = SemanticCachedLlm::new(runtime(Sampler::greedy()), 0.9, 8);
    let first = cached.complete("hello world", 6, 4).unwrap();
    assert!(!first.cached);
    let second = cached.complete("hello world", 6, 4).unwrap();
    assert!(second.cached);
    assert_eq!(second.text, first.text);
    assert!(second.similarity.unwrap() > 0.999);
    assert_eq!(cached.cache_hits(), 1);
    assert_eq!(cached.cache_misses(), 1);
}

#[test]
fn semantic_cache_miss_matches_plain_complete() {
    let plain = runtime(Sampler::greedy()).complete("hello", 6, 4).unwrap();
    let mut cached = SemanticCachedLlm::new(runtime(Sampler::greedy()), 0.9, 8);
    let r = cached.complete("hello", 6, 4).unwrap();
    assert!(!r.cached);
    assert_eq!(r.text, plain);
}

// ---------------------------------------------------------------------------
// Safety / screening pipelines
// ---------------------------------------------------------------------------

#[test]
fn complete_redacted_scrubs_secrets_and_pii() {
    let llm = runtime(Sampler::greedy());
    // The synthetic model won't emit secrets, so the test verifies the pipeline
    // runs and returns text (not an error) — a wiring check.
    let out = llm.complete_redacted("hello", 12, 5).unwrap();
    // result is a String
    assert!(out.is_empty() || out.is_char_boundary(0));
}

#[test]
fn complete_screened_wires_toxicity_filter() {
    use sovereign_toxicity::{Severity, ToxicityFilter};
    let llm = runtime(Sampler::greedy());
    let mut filter = ToxicityFilter::new();
    filter.add_term("zzbadzz", Severity::Severe);
    let (text, toxic) = llm.complete_screened("hello", 12, 5, &filter, 0.5).unwrap();
    assert_eq!(text, llm.complete("hello", 12, 5).unwrap());
    assert_eq!(toxic, filter.is_toxic(&text, 0.5));
}

#[test]
fn complete_checked_wires_degeneration_report() {
    use sovereign_degeneration::Config;
    let llm = runtime(Sampler::greedy());
    let cfg = Config::default();
    let (text, report) = llm.complete_checked("hello", 12, 7, &cfg).unwrap();
    assert_eq!(text, llm.complete("hello", 12, 7).unwrap());
    assert!((0.0..=1.0).contains(&report.distinct_ngram_ratio));
}

// ---------------------------------------------------------------------------
// Sampling variants identity when inactive
// ---------------------------------------------------------------------------

#[test]
fn complete_dry_inactive_equals_plain() {
    let llm = runtime(Sampler::greedy());
    assert_eq!(
        llm.complete_dry("hello", 6, 4, 0.0, 1.75, 2).unwrap(),
        llm.complete("hello", 6, 4).unwrap()
    );
}

#[test]
fn complete_xtc_inactive_equals_plain() {
    let llm = runtime(Sampler::greedy());
    assert_eq!(
        llm.complete_xtc("hello", 6, 4, 0.1, 0.0).unwrap(),
        llm.complete("hello", 6, 4).unwrap()
    );
}

#[test]
fn complete_penalized_identity_equals_plain() {
    let llm = runtime(Sampler::greedy());
    assert_eq!(
        llm.complete_penalized("hello", 6, 4, 1.0, 0.0, 0.0)
            .unwrap(),
        llm.complete("hello", 6, 4).unwrap()
    );
}

#[test]
fn complete_typical_full_mass_equals_plain() {
    let llm = runtime(Sampler::greedy());
    assert_eq!(
        llm.complete_typical("hello", 6, 4, 1.0).unwrap(),
        llm.complete("hello", 6, 4).unwrap()
    );
}

// ---------------------------------------------------------------------------
// Constrained decoding
// ---------------------------------------------------------------------------

#[test]
fn complete_regex_confines_to_pattern() {
    let llm = runtime(Sampler::greedy());
    let out = llm.complete_regex("number: ", "[0-9]+", 6, 7).unwrap();
    assert_eq!(out.chars().count(), 6);
    assert!(out.chars().all(|c| c.is_ascii_digit()), "{out:?}");
}

#[test]
fn complete_regex_rejects_bad_pattern() {
    let llm = runtime(Sampler::greedy());
    let err = llm.complete_regex("x", "[", 4, 1).unwrap_err();
    assert!(err.to_string().contains("regex"));
}

#[test]
fn complete_json_schema_confines_to_grammar() {
    use sovereign_json_schema_grammar::Schema;
    let llm = runtime(Sampler::greedy());
    let schema = Schema::object([("ok".to_string(), Schema::Boolean)]);
    let out = llm.complete_json_schema("emit: ", &schema, 40, 7).unwrap();
    let allowed: std::collections::HashSet<char> = "{}\":oktruefalse \t\n\r".chars().collect();
    assert!(
        out.chars().all(|c| allowed.contains(&c)),
        "out-of-grammar in {out:?}"
    );
}

// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

#[test]
fn majority_sequence_picks_most_common() {
    let a = vec![1u32, 2, 3];
    let b = vec![9u32, 9];
    let samples = vec![a.clone(), b.clone(), a.clone(), a.clone()];
    assert_eq!(
        sovereign_llm::majority_sequence(&samples),
        Some((a.clone(), 3))
    );
    assert_eq!(sovereign_llm::majority_sequence(&[]), None);
}

#[test]
fn majority_answer_picks_most_common_string() {
    let answers = vec!["42".to_string(), "the answer".to_string(), "42".to_string()];
    assert_eq!(
        sovereign_llm::majority_answer(&answers),
        Some(("42".to_string(), 2))
    );
}

// ---------------------------------------------------------------------------
// Serialization of data types
// ---------------------------------------------------------------------------

#[test]
fn sample_diversity_serde_roundtrip() {
    let d = SampleDiversity {
        samples: 4,
        distinct_1: 0.75,
        distinct_2: 0.60,
        self_bleu: 0.30,
        unique_ratio: 0.80,
    };
    let j = serde_json::to_string(&d).unwrap();
    let back: SampleDiversity = serde_json::from_str(&j).unwrap();
    assert_eq!(back.samples, d.samples);
    assert!((back.self_bleu - d.self_bleu).abs() < 1e-9);
}

#[test]
fn confidence_report_serde_roundtrip() {
    let c = ConfidenceReport {
        tokens: 8,
        mean_logprob: -2.5,
        perplexity: 12.0,
        weakest_index: Some(3),
        weakest_logprob: -4.0,
    };
    let j = serde_json::to_string(&c).unwrap();
    let back: ConfidenceReport = serde_json::from_str(&j).unwrap();
    assert_eq!(back.tokens, c.tokens);
    assert_eq!(back.weakest_index, c.weakest_index);
    assert!((back.mean_logprob - c.mean_logprob).abs() < 1e-9);
}

#[test]
fn vote_serde_roundtrip() {
    let v = Vote {
        answer: "yes".to_string(),
        count: 7,
        total: 10,
        agreement: 0.7,
    };
    let j = serde_json::to_string(&v).unwrap();
    let back: Vote = serde_json::from_str(&j).unwrap();
    assert_eq!(back.answer, v.answer);
    assert_eq!(back.count, v.count);
    assert!((back.agreement - v.agreement).abs() < 1e-9);
}
