//! `sovereign-llm` — the end-to-end text-to-text runtime.
//!
//! Every other crate in the inference arc does one stage; this is the one that
//! makes the whole thing *runnable from text*. It binds a byte-level BPE
//! [`Tokenizer`] to a [`DecoderStack`] so a caller can go straight from a
//! prompt string to generated text:
//!
//! ```text
//!   ids        = tokenizer.encode(prompt)
//!   new_ids    = model.generate(ids, max_new, seed)
//!   completion = tokenizer.decode(new_ids)
//! ```
//!
//! The one invariant that ties the two halves together — the model's
//! vocabulary must equal the tokenizer's — is checked at construction, so a
//! mismatched pair can never silently emit out-of-range ids. Because both the
//! tokenizer and the model are deterministic, a completion is fully
//! reproducible for a given seed, which is what lets the sovereign runtime log
//! and replay a generation exactly.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_decoder_stack::{DecoderStack, GenOptions, StackConfig, StackError};
use sovereign_logit_mask::LogitMask;
use sovereign_sampler::Mirostat;
use sovereign_tokenizer::Tokenizer;
use thiserror::Error;

/// The majority-vote result of [`SovereignLlm::complete_self_consistent`],
/// re-exported from [`sovereign-self-consistency`](sovereign_self_consistency).
pub use sovereign_self_consistency::Vote;

/// The result of [`SovereignLlm::calibrate`]: the fitted temperature and the
/// expected calibration error before and after applying it.
#[derive(Debug, Clone, PartialEq)]
pub struct Calibration {
    /// The temperature `T` that best calibrates the model's confidence (`>1`
    /// softens over-confidence, `<1` sharpens under-confidence; never changes the
    /// argmax).
    pub temperature: f64,
    /// Expected calibration error at `T = 1` (the raw model).
    pub ece_before: f64,
    /// Expected calibration error after dividing logits by the fitted `T`.
    pub ece_after: f64,
    /// Number of teacher-forced next-token predictions scored.
    pub samples: usize,
}

/// Schema version of the LLM runtime surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running the runtime.
#[derive(Debug, Error, PartialEq)]
pub enum LlmError {
    /// The model's vocabulary size did not match the tokenizer's.
    #[error("vocab mismatch: tokenizer has {tokenizer}, model has {model}")]
    VocabMismatch {
        /// Tokenizer vocabulary size.
        tokenizer: usize,
        /// Model vocabulary size.
        model: usize,
    },
    /// The prompt encoded to zero tokens (cannot prime the model).
    #[error("prompt encoded to no tokens")]
    EmptyPrompt,
    /// A model/stack error bubbled up.
    #[error("model: {0}")]
    Stack(#[from] StackError),
    /// Scoring the prompt for compression failed.
    #[error("scoring: {0}")]
    Perplexity(#[from] sovereign_perplexity::PerplexityError),
    /// The constraint pattern for constrained decoding was invalid.
    #[error("regex: {0}")]
    Regex(String),
    /// A self-consistency vote failed (zero samples, or all draws errored).
    #[error("self-consistency: {0}")]
    SelfConsistency(String),
}

/// The serializable definition of a runtime: a tokenizer + a model config.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LlmConfig {
    /// The byte-level BPE tokenizer.
    pub tokenizer: Tokenizer,
    /// The decoder-only model configuration.
    pub model: StackConfig,
}

/// Diversity metrics over a best-of-n sample set (see
/// [`SovereignLlm::sample_diversity`]). All ratios are in `[0, 1]`; lower
/// distinct-n / unique-ratio and higher Self-BLEU mean *less* diverse (more
/// collapse).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SampleDiversity {
    /// Number of samples measured.
    pub samples: usize,
    /// distinct-1 (distinct unigrams / total unigrams across all samples).
    pub distinct_1: f64,
    /// distinct-2 (distinct bigrams / total bigrams across all samples).
    pub distinct_2: f64,
    /// Mean Self-BLEU (each sample vs the others; high = samples resemble each
    /// other).
    pub self_bleu: f64,
    /// Fraction of samples that are exactly-distinct strings.
    pub unique_ratio: f64,
}

/// Confidence / uncertainty over a generated completion (see
/// [`SovereignLlm::completion_confidence`]). Built from the model's own
/// per-token log-probabilities for the tokens it generated.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ConfidenceReport {
    /// Number of generated tokens scored.
    pub tokens: usize,
    /// Mean per-token log-probability (nats; closer to 0 = more confident).
    pub mean_logprob: f64,
    /// Perplexity over the generated tokens (`≥ 1`; lower = more confident).
    pub perplexity: f64,
    /// Index (within the completion) of the least-confident token, if any.
    pub weakest_index: Option<usize>,
    /// The log-probability of that least-confident token.
    pub weakest_logprob: f64,
}

/// A runnable text-to-text LLM: tokenizer + stacked decoder model.
#[derive(Debug, Clone)]
pub struct SovereignLlm {
    tokenizer: Tokenizer,
    model: DecoderStack,
}

impl SovereignLlm {
    /// Build a runtime, checking that the model's vocab matches the tokenizer.
    pub fn new(tokenizer: Tokenizer, config: StackConfig) -> Result<Self, LlmError> {
        if config.vocab != tokenizer.vocab_size() {
            return Err(LlmError::VocabMismatch {
                tokenizer: tokenizer.vocab_size(),
                model: config.vocab,
            });
        }
        let model = DecoderStack::new(config)?;
        Ok(Self { tokenizer, model })
    }

    /// Build from a serializable [`LlmConfig`].
    pub fn from_config(config: LlmConfig) -> Result<Self, LlmError> {
        Self::new(config.tokenizer, config.model)
    }

    /// The shared vocabulary size.
    pub fn vocab_size(&self) -> usize {
        self.tokenizer.vocab_size()
    }

    /// Number of decoder layers.
    pub fn layers(&self) -> usize {
        self.model.layers()
    }

    /// Borrow the tokenizer.
    pub fn tokenizer(&self) -> &Tokenizer {
        &self.tokenizer
    }

    /// Complete `prompt`, returning **only** the newly generated text.
    /// Reproducible for a given `seed`. Stateless: each call decodes from a
    /// fresh clone of the model, so repeated calls never contaminate each
    /// other (which is what lets a chat/agent loop reuse one runtime).
    pub fn complete(&self, prompt: &str, max_new: usize, seed: u64) -> Result<String, LlmError> {
        let generated = self.generate_ids(prompt, max_new, seed)?;
        // ids come straight from the model's own vocab, so decode never fails.
        Ok(self.tokenizer.decode(&generated).unwrap_or_default())
    }

    /// Complete `prompt` using **DRY** (Don't Repeat Yourself) sampling to
    /// suppress repetition loops: each step penalizes candidates by how long a
    /// previously-generated sequence they would extend (exponential in match
    /// length, scaled by `multiplier`/`base` past `allowed_length`), so a long
    /// verbatim loop becomes exponentially hard to continue while legitimate reuse
    /// is barely touched — unlike a flat penalty or a hard n-gram ban. Composes
    /// DRY with this runtime's configured sampler. Reproducible per `seed`.
    pub fn complete_dry(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        multiplier: f32,
        base: f32,
        allowed_length: usize,
    ) -> Result<String, LlmError> {
        let dry = sovereign_dry_sampler::DrySampler::new(multiplier, base, allowed_length);
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids = model.generate_dry(&prompt_ids, max_new, seed, &dry)?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Complete `prompt` using **XTC** (Exclude Top Choices) sampling: when the
    /// model is confident about several tokens, the most-probable ones are
    /// dropped (above `threshold`, with per-step `probability`) so a
    /// lower-but-plausible token can win — more creative output than the base
    /// sampler without the incoherence of high temperature, and a no-op when only
    /// one token is confident. Composes XTC with this runtime's configured
    /// sampler. Reproducible per `seed`.
    pub fn complete_xtc(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        threshold: f32,
        probability: f32,
    ) -> Result<String, LlmError> {
        let xtc = sovereign_xtc_sampler::XtcSampler::new(threshold, probability);
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids = model.generate_xtc(&prompt_ids, max_new, seed, &xtc)?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Complete `prompt` applying **repetition / frequency / presence penalties**
    /// (`sovereign-repetition-penalty`) to the logits each step: `repetition`
    /// scales down any already-seen token (CTRL-style; `1.0` = off), `frequency`
    /// subtracts proportionally to a token's prior count, and `presence` subtracts
    /// a flat amount for any prior appearance (`0.0` = off) — the classic trio for
    /// discouraging loops and over-used tokens. The penalty history is the prompt
    /// plus the tokens generated in this call. Identity penalties reduce to the
    /// base sampler. Reproducible per `seed`.
    pub fn complete_penalized(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        repetition: f32,
        frequency: f32,
        presence: f32,
    ) -> Result<String, LlmError> {
        let penalties = sovereign_repetition_penalty::Penalties {
            repetition,
            frequency,
            presence,
        };
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids = model.generate_penalized(&prompt_ids, max_new, seed, &penalties)?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Complete `prompt` using **locally-typical sampling** at cumulative `mass`
    /// (`sovereign-typical-sampling`): each step keeps only the tokens whose
    /// surprisal is nearest the distribution's entropy (the typical set) and masks
    /// the rest before sampling — trimming both the blandest and the most
    /// incoherent candidates for more human-reading output. A `mass` of `1.0`
    /// keeps everything (reduces to the base sampler). Reproducible per `seed`.
    pub fn complete_typical(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mass: f64,
    ) -> Result<String, LlmError> {
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids = model.generate_typical(&prompt_ids, max_new, seed, mass)?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Complete `prompt` **`samples` times** (seeds `base_seed..base_seed+samples`)
    /// and return the **majority answer** with its agreement fraction
    /// (`sovereign-self-consistency`). Drawing several independent completions and
    /// voting is the self-consistency trick: for a task with one right answer,
    /// the majority across samples is more reliable than any single greedy decode,
    /// and the returned `agreement` is a cheap confidence signal. With a
    /// deterministic (e.g. greedy) sampler all samples coincide (agreement `1.0`);
    /// a temperature sampler produces the spread the vote is meant to resolve.
    /// Reproducible per `base_seed`.
    pub fn complete_self_consistent(
        &self,
        prompt: &str,
        max_new: usize,
        base_seed: u64,
        samples: usize,
    ) -> Result<Vote, LlmError> {
        sovereign_self_consistency::SelfConsistency::new(samples)
            .run(base_seed, |seed| {
                self.complete(prompt, max_new, seed)
                    .map_err(|e| e.to_string())
            })
            .map_err(|e| LlmError::SelfConsistency(e.to_string()))
    }

    /// Complete `prompt` **`n` times** (seeds `base_seed..base_seed+n`) and return
    /// the single completion the model is **most confident** in — the one with the
    /// highest mean per-token log-probability (`completion_confidence`), picked
    /// with [`sovereign-best-of-n`](sovereign_best_of_n). Best-of-`n` sampling
    /// trades compute for quality: draw several candidates and keep the one the
    /// model scores highest, rather than committing to a single stochastic decode.
    /// `n` is clamped to at least 1 (so `n = 0` reduces to a single completion at
    /// `base_seed`); ties go to the earliest seed. Reproducible per `base_seed`.
    pub fn complete_best_of_n(
        &self,
        prompt: &str,
        max_new: usize,
        base_seed: u64,
        n: usize,
    ) -> Result<String, LlmError> {
        let n = n.max(1);
        let mut candidates: Vec<(String, f64)> = Vec::with_capacity(n);
        for i in 0..n {
            // wrapping_add for consistency with generate_ids_n's diverse-seed
            // loop — a large base_seed must not debug-panic on overflow.
            let seed = base_seed.wrapping_add(i as u64);
            let text = self.complete(prompt, max_new, seed)?;
            // score each candidate by the model's own mean log-prob over the
            // generated tokens (higher = more confident); an empty generation
            // scores worst so it can never win.
            let score = self
                .completion_confidence(prompt, max_new, seed)?
                .map(|c| c.mean_logprob)
                .unwrap_or(f64::NEG_INFINITY);
            candidates.push((text, score));
        }
        Ok(sovereign_best_of_n::best(&candidates).expect("n >= 1 → non-empty"))
    }

    /// **Temperature-scaling calibration** of the model's next-token confidence
    /// over a `reference` sequence (`sovereign-confidence-calibration`). Teacher-
    /// forcing the model along the reference gives, at each position, a predicted
    /// distribution whose *label* is the actual next token; `fit_temperature`
    /// learns the single scalar `T` (logits ÷ `T`) that best calibrates those
    /// predictions, and the **expected calibration error** is reported before
    /// (`T = 1`) and after — how far the model's stated confidence sits from its
    /// accuracy, and how much a one-parameter fix closes the gap. Returns `None`
    /// for a reference under two tokens. Deterministic (reproducible).
    pub fn calibrate(&self, reference: &str, bins: usize) -> Result<Option<Calibration>, LlmError> {
        let toks: Vec<usize> = self
            .tokenizer
            .encode(reference)
            .iter()
            .map(|&i| i as usize)
            .collect();
        if toks.len() < 2 {
            return Ok(None);
        }
        // teacher-force: the logits after feeding toks[..=i] predict toks[i+1].
        let mut model = self.model.clone();
        let mut logits_list: Vec<Vec<f64>> = Vec::with_capacity(toks.len() - 1);
        let mut labels: Vec<usize> = Vec::with_capacity(toks.len() - 1);
        let mut logits = model.forward(toks[0])?;
        for &next in &toks[1..] {
            logits_list.push(logits.iter().map(|&l| l as f64).collect());
            labels.push(next);
            logits = model.forward(next)?;
        }
        let temperature = sovereign_confidence_calibration::fit_temperature(&logits_list, &labels);
        let ece_at = |temp: f64| {
            let mut confidences = Vec::with_capacity(labels.len());
            let mut correct = Vec::with_capacity(labels.len());
            for (lg, &label) in logits_list.iter().zip(&labels) {
                let probs = sovereign_confidence_calibration::softmax_t(lg, temp);
                // argmax of the (temperature-scaled) distribution.
                let mut arg = 0usize;
                let mut max_p = f64::NEG_INFINITY;
                for (i, &p) in probs.iter().enumerate() {
                    if p > max_p {
                        max_p = p;
                        arg = i;
                    }
                }
                confidences.push(max_p);
                correct.push(arg == label);
            }
            sovereign_confidence_calibration::expected_calibration_error(
                &confidences,
                &correct,
                bins.max(1),
            )
        };
        Ok(Some(Calibration {
            temperature,
            ece_before: ece_at(1.0),
            ece_after: ece_at(temperature),
            samples: labels.len(),
        }))
    }

    /// Complete `prompt` after **fitting it to a context budget**: if the prompt
    /// exceeds `max_context` tokens it is trimmed to the most recent `max_context`
    /// (`sovereign-context-budget`, keeping the tail — the text nearest where
    /// generation continues) before completing. A long prompt that would overflow
    /// the model's effective context window is bounded instead of silently
    /// degrading. A prompt that already fits is completed unchanged. Reproducible
    /// per `seed`.
    pub fn complete_within_context(
        &self,
        prompt: &str,
        max_context: usize,
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let trimmed = sovereign_context_budget::trim(
            &self.tokenizer,
            prompt,
            max_context,
            sovereign_context_budget::Keep::Tail,
        );
        self.complete(&trimmed, max_new, seed)
    }

    /// Complete `prompt` with **token healing** at the prompt/completion seam.
    /// Whole-prompt tokenization fixes the last token to whatever split the
    /// tokenizer chose at the cut — often *not* the split the model would pick
    /// (handed `http`, it can't emit the single token `https`). Healing
    /// (`sovereign-token-healing`) trims that trailing token, keeps its surface as
    /// a prefix constraint, and forces the **first** generated token to be
    /// consistent with the prefix (re-choose/extend the boundary) via the dynamic
    /// mask — so the model picks the natural boundary. Returns the continuation
    /// beyond the original prompt (the re-formed boundary prefix is stripped).
    /// Falls back to plain [`complete`](Self::complete) when there is nothing to
    /// heal (single-token or empty prompt). Reproducible per `seed`.
    pub fn complete_healed(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let prompt_ids = self.tokenizer.encode(prompt);
        let vocab: Vec<String> = (0..self.tokenizer.vocab_size())
            .map(|id| self.tokenizer.decode(&[id as u32]).unwrap_or_default())
            .collect();
        let healer = sovereign_token_healing::TokenHealer::new(vocab);
        let healed = healer.heal(&prompt_ids);
        // Can't heal a single-token / empty prompt (trimming leaves nothing to
        // prime the model) — fall back to a normal completion.
        if healed.trimmed.is_empty() || healed.prefix.is_empty() {
            return self.complete(prompt, max_new, seed);
        }
        let allowed: Vec<usize> = healer
            .allowed_continuations(&healed.prefix)
            .into_iter()
            .map(|t| t as usize)
            .collect();
        let trimmed: Vec<usize> = healed.trimmed.iter().map(|&i| i as usize).collect();
        let mut model = self.model.clone();
        let gen_ids = model.generate_dynamic_mask(&trimmed, max_new, seed, |generated| {
            if generated.is_empty() {
                // First step: only boundary-consistent tokens are allowed.
                LogitMask::new().allow_only(allowed.iter().copied())
            } else {
                LogitMask::new()
            }
        })?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        let text = self.tokenizer.decode(&out_ids).unwrap_or_default();
        // The re-formed boundary reconstructs the trimmed surface; strip it so the
        // result continues the original prompt rather than repeating its tail.
        Ok(text
            .strip_prefix(&healed.prefix)
            .unwrap_or(&text)
            .to_string())
    }

    /// **Constrained decoding**: generate a completion for `prompt` that is forced
    /// to match the regular expression `pattern`. At every step the live
    /// constraint (`sovereign-regex-constrain` over `sovereign-regex-nfa`) builds a
    /// [`LogitMask`] allowing only the tokens that keep the pattern *satisfiable*,
    /// so the model can never emit a string the pattern rejects — the basis of
    /// guaranteed-format output (digits-only, dates, enums, JSON shapes). Drives
    /// the decoder's [`generate_dynamic_mask`](sovereign_decoder_stack::DecoderStack::generate_dynamic_mask)
    /// loop on a fresh model clone (stateless). Returns the generated text;
    /// reproducible per `seed`. Errors if `pattern` is not a valid regex.
    pub fn complete_regex(
        &self,
        prompt: &str,
        pattern: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let constraint = sovereign_regex_constrain::RegexConstraint::new(pattern)
            .map_err(|e| LlmError::Regex(e.to_string()))?;
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        // Per-token vocab strings (each id decoded on its own).
        let vocab: Vec<String> = (0..self.tokenizer.vocab_size())
            .map(|id| self.tokenizer.decode(&[id as u32]).unwrap_or_default())
            .collect();
        let vocab_refs: Vec<&str> = vocab.iter().map(String::as_str).collect();
        let mut model = self.model.clone();
        let gen_ids = model.generate_dynamic_mask(&prompt_ids, max_new, seed, |generated| {
            let so_far: Vec<u32> = generated.iter().map(|&i| i as u32).collect();
            let text = self.tokenizer.decode(&so_far).unwrap_or_default();
            constraint.mask(&text, &vocab_refs)
        })?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// **Grammar-constrained decoding to a JSON Schema**: generate a completion
    /// that is guaranteed to be a JSON value conforming to `schema`. The schema is
    /// compiled to a grammar (`sovereign-json-schema-grammar`); at each step
    /// `sovereign-token-grammar-mask` reports exactly which tokens keep a valid
    /// parse reachable (the rest are masked), and generation **stops** the moment
    /// the emitted text is a complete sentence of the grammar — so the output is
    /// always well-formed and conforming, never truncated mid-structure. The
    /// strongest form of structured / tool-call output. Drives the decoder's
    /// stoppable dynamic-mask loop on a fresh model clone; reproducible per `seed`.
    pub fn complete_json_schema(
        &self,
        prompt: &str,
        schema: &sovereign_json_schema_grammar::Schema,
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let grammar = sovereign_json_schema_grammar::compile(schema);
        let vocab: Vec<String> = (0..self.tokenizer.vocab_size())
            .map(|id| self.tokenizer.decode(&[id as u32]).unwrap_or_default())
            .collect();
        let tgm = sovereign_token_grammar_mask::TokenGrammarMask::new(grammar, vocab);
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids =
            model.generate_dynamic_mask_until(&prompt_ids, max_new, seed, |generated| {
                let so_far: Vec<u32> = generated.iter().map(|&i| i as u32).collect();
                let prefix = self.tokenizer.decode(&so_far).unwrap_or_default();
                let mask = tgm.mask(&prefix);
                // Stop once the output is a complete sentence of the grammar, or if no
                // token can keep the parse valid (avoids sampling from an all-masked set).
                if mask.eos {
                    return None;
                }
                let allowed = mask.allowed_ids();
                if allowed.is_empty() {
                    return None;
                }
                Some(LogitMask::new().allow_only(allowed))
            })?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Constrain a completion to a JSON schema **and** a set of static policy
    /// planes at once (SDD-501 / M00117): the grammar plane — recomputed per
    /// position via [`sovereign_token_grammar_mask::TokenGrammarMask`] — is
    /// AND-combined with `policy_planes` (each a per-vocabulary allow-mask: a
    /// safety denylist, a tool/schema allow-list) through the real
    /// `token_law_combine` kernel every step, so the model is confined by the
    /// grammar **and** every policy simultaneously. Stops when the grammar is
    /// complete, when no token keeps the parse valid, or when the intersection
    /// is empty (every grammar-legal token is policy-banned). Reproducible per
    /// `seed`. This is the multi-plane composition the single grammar path
    /// ([`complete_json_schema`](Self::complete_json_schema)) does not do — one
    /// running model, several composed token-law planes.
    pub fn complete_json_schema_with_laws(
        &self,
        prompt: &str,
        schema: &sovereign_json_schema_grammar::Schema,
        policy_planes: &[&[u64]],
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let grammar = sovereign_json_schema_grammar::compile(schema);
        let vocab_size = self.tokenizer.vocab_size();
        let vocab: Vec<String> = (0..vocab_size)
            .map(|id| self.tokenizer.decode(&[id as u32]).unwrap_or_default())
            .collect();
        let tgm = sovereign_token_grammar_mask::TokenGrammarMask::new(grammar, vocab);
        let mut planes = sovereign_token_law_mask::TokenLawPlanes::new(vocab_size);
        for p in policy_planes {
            planes = planes.with_plane(p.to_vec());
        }
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids =
            model.generate_dynamic_token_law_until(&prompt_ids, max_new, seed, |generated| {
                let so_far: Vec<u32> = generated.iter().map(|&i| i as u32).collect();
                let prefix = self.tokenizer.decode(&so_far).unwrap_or_default();
                let mask = tgm.mask(&prefix);
                if mask.eos {
                    return None;
                }
                let allowed = mask.allowed_ids();
                if allowed.is_empty() {
                    return None;
                }
                let combined = planes.combine_with(&allowed);
                // Empty intersection — every grammar-legal token is policy-banned;
                // stop rather than sample from an all-masked logit row.
                if combined.iter().all(|w| *w == 0) {
                    return None;
                }
                Some(combined)
            })?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Constrain a completion to a **regular expression** *and* a set of static
    /// policy planes at once (SDD-503 / M00117). The regex plane — the token ids
    /// that keep the pattern satisfiable, recomputed per position via
    /// [`sovereign_regex_constrain::RegexConstraint::allowed_token_ids`] — is
    /// AND-combined with `policy_planes` (each a per-vocabulary allow-mask) through
    /// the real `token_law_combine` kernel every step. This is the regex sibling
    /// of [`complete_json_schema_with_laws`](Self::complete_json_schema_with_laws):
    /// a **real constraint source** feeding a token-law plane, not a hand-built
    /// bitset (SDD-500 Q4 / SDD-501's tracked non-goal). A tool-name allow-list is
    /// just a `(name_a|name_b|…)` alternation pattern. Stops when no token keeps
    /// the pattern satisfiable or the intersection with policy is empty.
    /// Reproducible per `seed`; errors if `pattern` is not a valid regex.
    pub fn complete_regex_with_laws(
        &self,
        prompt: &str,
        pattern: &str,
        policy_planes: &[&[u64]],
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let constraint = sovereign_regex_constrain::RegexConstraint::new(pattern)
            .map_err(|e| LlmError::Regex(e.to_string()))?;
        let vocab_size = self.tokenizer.vocab_size();
        let vocab: Vec<String> = (0..vocab_size)
            .map(|id| self.tokenizer.decode(&[id as u32]).unwrap_or_default())
            .collect();
        let vocab_refs: Vec<&str> = vocab.iter().map(String::as_str).collect();
        let mut planes = sovereign_token_law_mask::TokenLawPlanes::new(vocab_size);
        for p in policy_planes {
            planes = planes.with_plane(p.to_vec());
        }
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids =
            model.generate_dynamic_token_law_until(&prompt_ids, max_new, seed, |generated| {
                let so_far: Vec<u32> = generated.iter().map(|&i| i as u32).collect();
                let text = self.tokenizer.decode(&so_far).unwrap_or_default();
                let allowed = constraint.allowed_token_ids(&text, &vocab_refs);
                if allowed.is_empty() {
                    return None;
                }
                let combined = planes.combine_with(&allowed);
                if combined.iter().all(|w| *w == 0) {
                    return None;
                }
                Some(combined)
            })?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Constrain a completion to a JSON schema **and** a regex **and** static
    /// policy planes — all at once (SDD-503 / M00117). Two independent *dynamic*
    /// sources are recomputed per position — the grammar plane
    /// ([`sovereign_token_grammar_mask::TokenGrammarMask`]) and the regex plane
    /// ([`sovereign_regex_constrain::RegexConstraint`]) — and AND-combined with
    /// each other and with `policy_planes` through
    /// [`TokenLawPlanes::combine_with_dynamics`](sovereign_token_law_mask::TokenLawPlanes::combine_with_dynamics).
    /// A token survives only if the grammar, the regex, **and** every policy plane
    /// allow it — a multi-source composition no single constraint expresses (e.g.
    /// a JSON string whose *content* the regex further restricts). Stops on grammar
    /// completion, an empty source, or an empty intersection. Reproducible per
    /// `seed`; errors if `pattern` is not a valid regex.
    pub fn complete_json_schema_and_regex_with_laws(
        &self,
        prompt: &str,
        schema: &sovereign_json_schema_grammar::Schema,
        pattern: &str,
        policy_planes: &[&[u64]],
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let grammar = sovereign_json_schema_grammar::compile(schema);
        let constraint = sovereign_regex_constrain::RegexConstraint::new(pattern)
            .map_err(|e| LlmError::Regex(e.to_string()))?;
        let vocab_size = self.tokenizer.vocab_size();
        let vocab: Vec<String> = (0..vocab_size)
            .map(|id| self.tokenizer.decode(&[id as u32]).unwrap_or_default())
            .collect();
        let vocab_refs: Vec<&str> = vocab.iter().map(String::as_str).collect();
        let tgm = sovereign_token_grammar_mask::TokenGrammarMask::new(grammar, vocab.clone());
        let mut planes = sovereign_token_law_mask::TokenLawPlanes::new(vocab_size);
        for p in policy_planes {
            planes = planes.with_plane(p.to_vec());
        }
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids =
            model.generate_dynamic_token_law_until(&prompt_ids, max_new, seed, |generated| {
                let so_far: Vec<u32> = generated.iter().map(|&i| i as u32).collect();
                let text = self.tokenizer.decode(&so_far).unwrap_or_default();
                let gmask = tgm.mask(&text);
                if gmask.eos {
                    return None;
                }
                let g_ids = gmask.allowed_ids();
                if g_ids.is_empty() {
                    return None;
                }
                let r_ids = constraint.allowed_token_ids(&text, &vocab_refs);
                if r_ids.is_empty() {
                    return None;
                }
                let combined = planes.combine_with_dynamics(&[&g_ids, &r_ids]);
                if combined.iter().all(|w| *w == 0) {
                    return None;
                }
                Some(combined)
            })?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Generate a completion whose text is **guaranteed never to contain** any of
    /// `deny_patterns` — the **negative** token-law plane (SDD-504 / M00117
    /// "safety"). A denied substring can span token boundaries, so this drives a
    /// `sovereign-token-law-deny` Aho-Corasick automaton from the committed text
    /// and, each step, bans exactly the tokens whose bytes would *complete* a
    /// banned match (`DenyConstraint::safe_token_ids` → the allow-list). The
    /// guarantee is per-step and exact: a banned phrase can only appear at the byte
    /// that finishes it, and that token is masked at that step — not a post-hoc
    /// scanner. `deny_patterns` are literal substrings (e.g.
    /// `sovereign_injection_detect::PATTERNS`). Reproducible per `seed`.
    pub fn complete_with_safety_denylist(
        &self,
        prompt: &str,
        deny_patterns: &[&str],
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let deny = sovereign_token_law_deny::DenyConstraint::new(deny_patterns);
        let vocab_size = self.tokenizer.vocab_size();
        let vocab: Vec<String> = (0..vocab_size)
            .map(|id| self.tokenizer.decode(&[id as u32]).unwrap_or_default())
            .collect();
        let vocab_refs: Vec<&str> = vocab.iter().map(String::as_str).collect();
        let planes = sovereign_token_law_mask::TokenLawPlanes::new(vocab_size);
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids =
            model.generate_dynamic_token_law_until(&prompt_ids, max_new, seed, |generated| {
                let so_far: Vec<u32> = generated.iter().map(|&i| i as u32).collect();
                let text = self.tokenizer.decode(&so_far).unwrap_or_default();
                let safe = deny.safe_token_ids(&text, &vocab_refs);
                if safe.is_empty() {
                    return None;
                }
                Some(planes.combine_with(&safe))
            })?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Constrain a completion to a **regex** (a *positive* plane) **and** a safety
    /// **denylist** (a *negative* plane) at once (SDD-504 / M00117). Both are
    /// dynamic sources recomputed per position — the regex's viable-token ids and
    /// the denylist's safe-token ids — AND-combined via
    /// [`TokenLawPlanes::combine_with_dynamics`](sovereign_token_law_mask::TokenLawPlanes::combine_with_dynamics).
    /// The output both matches `pattern` and never contains a `deny_patterns`
    /// substring — a positive-and-negative composition no single constraint
    /// expresses. Stops on an empty source or an empty intersection. Reproducible
    /// per `seed`; errors if `pattern` is not a valid regex.
    pub fn complete_regex_with_safety_denylist(
        &self,
        prompt: &str,
        pattern: &str,
        deny_patterns: &[&str],
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let constraint = sovereign_regex_constrain::RegexConstraint::new(pattern)
            .map_err(|e| LlmError::Regex(e.to_string()))?;
        let deny = sovereign_token_law_deny::DenyConstraint::new(deny_patterns);
        let vocab_size = self.tokenizer.vocab_size();
        let vocab: Vec<String> = (0..vocab_size)
            .map(|id| self.tokenizer.decode(&[id as u32]).unwrap_or_default())
            .collect();
        let vocab_refs: Vec<&str> = vocab.iter().map(String::as_str).collect();
        let planes = sovereign_token_law_mask::TokenLawPlanes::new(vocab_size);
        let prompt_ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .iter()
            .map(|&i| i as usize)
            .collect();
        let mut model = self.model.clone();
        let gen_ids =
            model.generate_dynamic_token_law_until(&prompt_ids, max_new, seed, |generated| {
                let so_far: Vec<u32> = generated.iter().map(|&i| i as u32).collect();
                let text = self.tokenizer.decode(&so_far).unwrap_or_default();
                let r_ids = constraint.allowed_token_ids(&text, &vocab_refs);
                if r_ids.is_empty() {
                    return None;
                }
                let safe = deny.safe_token_ids(&text, &vocab_refs);
                if safe.is_empty() {
                    return None;
                }
                let combined = planes.combine_with_dynamics(&[&r_ids, &safe]);
                if combined.iter().all(|w| *w == 0) {
                    return None;
                }
                Some(combined)
            })?;
        let out_ids: Vec<u32> = gen_ids.iter().map(|&i| i as u32).collect();
        Ok(self.tokenizer.decode(&out_ids).unwrap_or_default())
    }

    /// Complete `prompt` and **extract the first balanced JSON value** from the
    /// output (`sovereign-json-extract`), returning `Some(value)` or `None` if the
    /// completion contains no JSON. Models emit structured answers wrapped in
    /// prose — `Sure! {"city":"Paris"}` — and a tool-calling / structured-output
    /// runtime needs just the value; this is the post-hoc extraction step (it
    /// scans for the first `{`/`[`, respects string literals, and hands the
    /// balanced span to `serde_json`). Reproducible per `seed`.
    pub fn complete_json(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<Option<serde_json::Value>, LlmError> {
        let text = self.complete(prompt, max_new, seed)?;
        Ok(sovereign_json_extract::extract_value(&text).ok())
    }

    /// Generate a completion for `prompt` and report the model's **confidence**
    /// in the tokens it produced. The prompt+completion is scored teacher-forced
    /// (`perplexity::token_logprobs`) and the *generated* slice is summarized with
    /// [`sovereign-logprobs`](sovereign_logprobs): mean log-prob, perplexity, and
    /// the weakest (least-confident) token. A serving loop uses a high perplexity
    /// / very low weakest-token logprob to flag an unreliable answer for review or
    /// regeneration. Returns `None` if nothing was generated (`max_new == 0` or an
    /// empty prompt). Reproducible per `seed`.
    pub fn completion_confidence(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<Option<ConfidenceReport>, LlmError> {
        let prompt_ids = self.tokenizer.encode(prompt);
        let gen_ids = self.generate_ids(prompt, max_new, seed)?;
        if gen_ids.is_empty() {
            return Ok(None);
        }
        // Score the whole prompt+completion, then keep the generated tail: each
        // generated token scored given everything before it.
        let mut full: Vec<usize> = prompt_ids.iter().map(|&i| i as usize).collect();
        full.extend(gen_ids.iter().map(|&i| i as usize));
        if full.len() < 2 {
            return Ok(None);
        }
        let all = sovereign_perplexity::token_logprobs(&self.model, &full)?;
        // `all` scores tokens[1..]; the generated tokens are the last gen_ids.len().
        let start = all.len().saturating_sub(gen_ids.len());
        let gen_lps = &all[start..];
        let weakest = sovereign_logprobs::weakest_token(gen_lps);
        Ok(Some(ConfidenceReport {
            tokens: gen_lps.len(),
            mean_logprob: sovereign_logprobs::mean_logprob(gen_lps),
            perplexity: sovereign_logprobs::perplexity(gen_lps),
            weakest_index: weakest.map(|(i, _)| i),
            weakest_logprob: weakest.map(|(_, lp)| lp).unwrap_or(0.0),
        }))
    }

    /// Complete `prompt`, then **scrub the output**: redact any secrets (API
    /// keys, tokens — `sovereign-secret-scan`) and then any PII (emails, SSNs,
    /// phone numbers — `sovereign-pii-redact`) from the generated text before
    /// returning it. A grounded runtime can echo sensitive material that leaked
    /// in from a retrieved document or the prompt; this is the egress filter that
    /// keeps it out of the response. Secrets are scrubbed first so a token that
    /// also looks like PII is tagged as the secret. Reproducible per `seed`.
    pub fn complete_redacted(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let text = self.complete(prompt, max_new, seed)?;
        let no_secrets = sovereign_secret_scan::redact(&text);
        Ok(sovereign_pii_redact::redact(&no_secrets))
    }

    /// Complete `prompt`, then run a **content-safety screen** on the output:
    /// the completion is scanned by `filter` (`sovereign-toxicity`, which
    /// normalizes leetspeak/obfuscation before matching a severity-tiered term
    /// list) and the text is returned with a `bool` verdict — `true` if its
    /// toxicity score is at or above `threshold`. A serving loop uses the verdict
    /// to block or regenerate a toxic completion. The caller supplies the
    /// configured filter (e.g. [`ToxicityFilter::with_builtin`](sovereign_toxicity::ToxicityFilter::with_builtin)).
    /// Reproducible per `seed`.
    pub fn complete_screened(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        filter: &sovereign_toxicity::ToxicityFilter,
        threshold: f64,
    ) -> Result<(String, bool), LlmError> {
        let text = self.complete(prompt, max_new, seed)?;
        let toxic = filter.is_toxic(&text, threshold);
        Ok((text, toxic))
    }

    /// Complete `prompt`, then run a **degeneration check** on the output: the
    /// completion text is analysed (`sovereign-degeneration`) for loop/repeat
    /// collapse — longest repeated substring, rep-n diversity, repeat coverage —
    /// against `config`, returning the text alongside the
    /// [`DegenerationReport`](sovereign_degeneration::DegenerationReport). A
    /// serving loop uses the report's `is_degenerate` flag to reject or
    /// regenerate a looping completion instead of returning it. Reproducible per
    /// `seed`; pass [`sovereign_degeneration::Config::default`] for standard
    /// thresholds.
    pub fn complete_checked(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        config: &sovereign_degeneration::Config,
    ) -> Result<(String, sovereign_degeneration::DegenerationReport), LlmError> {
        let text = self.complete(prompt, max_new, seed)?;
        let report = sovereign_degeneration::analyze(&text, config);
        Ok((text, report))
    }

    /// Complete `prompt`, returning the generated text **truncated at the first
    /// occurrence of any stop string** (the OpenAI `stop` parameter, which
    /// operates on text and so can span several tokens — unlike a single stop
    /// *token*). Empty stop strings are ignored; with no match the full
    /// completion is returned. Reproducible per `seed`. (Reference impl:
    /// generates up to `max_new` then trims.)
    pub fn complete_until_string(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        stops: &[&str],
    ) -> Result<String, LlmError> {
        let full = self.complete(prompt, max_new, seed)?;
        let cut = stops
            .iter()
            .filter(|s| !s.is_empty())
            .filter_map(|s| full.find(*s))
            .min();
        Ok(match cut {
            Some(i) => full[..i].to_string(),
            None => full,
        })
    }

    /// Compress `text` by dropping the tokens this model can already predict
    /// (selective prompt compression, the LLMLingua idea). The text is tokenized,
    /// every token is scored by its surprisal under **this** model (via
    /// [`sovereign_perplexity::token_logprobs`]), and the most-predictable tokens
    /// are dropped until about `keep_ratio` of them survive; the kept tokens are
    /// returned, decoded back to text, in their original order. The first and last
    /// tokens are always kept as anchors — the first is unscored (it has no
    /// predecessor) and a boundary token is rarely safe to drop.
    ///
    /// This composes the runtime's own scoring pass with
    /// [`sovereign_prompt_compress`] so a long retrieved/context prompt can be
    /// shrunk to fit a budget before generation, spending no extra model passes
    /// beyond the single scoring forward. `keep_ratio` is clamped to `[0, 1]`;
    /// text of fewer than two tokens is returned unchanged (nothing to score).
    pub fn compress_prompt(&self, text: &str, keep_ratio: f64) -> Result<String, LlmError> {
        let ids: Vec<u32> = self.tokenizer.encode(text);
        if ids.len() < 2 {
            return Ok(text.to_string());
        }
        let scored: Vec<usize> = ids.iter().map(|&i| i as usize).collect();
        // `token_logprobs` scores tokens[1..]; token 0 has no predecessor, so
        // prepend a sentinel (0.0 = perfectly predictable) and rely on the anchor
        // flag to keep it — the real surprisal drives selection of the rest.
        let mut logprobs = Vec::with_capacity(ids.len());
        logprobs.push(0.0);
        logprobs.extend(sovereign_perplexity::token_logprobs(&self.model, &scored)?);
        let keep = sovereign_prompt_compress::select_informative(&logprobs, keep_ratio, true);
        let kept = sovereign_prompt_compress::compress(&ids, &keep);
        Ok(self.tokenizer.decode(&kept).unwrap_or_default())
    }

    /// Complete `prompt`, returning the prompt followed by the generated text.
    pub fn complete_with_prompt(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let completion = self.complete(prompt, max_new, seed)?;
        Ok(format!("{prompt}{completion}"))
    }

    /// The token ids generated for `prompt` (without decoding to text).
    pub fn generate_ids(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<Vec<u32>, LlmError> {
        self.generate_ids_constrained(prompt, max_new, seed, &LogitMask::new())
    }

    /// Generate `n` independent samples for `prompt` (the OpenAI `n` / best-of
    /// parameter): sample `i` uses `base_seed + i`, so the set is diverse yet
    /// reproducible. With a non-greedy sampler the samples vary; under a greedy
    /// sampler they are identical. Feeds self-consistency voting via
    /// [`majority_sequence`].
    pub fn generate_ids_n(
        &self,
        prompt: &str,
        n: usize,
        max_new: usize,
        base_seed: u64,
    ) -> Result<Vec<Vec<u32>>, LlmError> {
        (0..n)
            .map(|i| self.generate_ids(prompt, max_new, base_seed.wrapping_add(i as u64)))
            .collect()
    }

    /// Diversity metrics over `n` independent samples for `prompt` — the
    /// best-of-n set from [`generate_ids_n`], decoded to text and measured with
    /// [`sovereign_diversity`]. A serving loop uses this to detect **mode
    /// collapse**: a sampler set too cold (or a degenerate model) returns near-
    /// identical samples — low distinct-n and unique-ratio, high Self-BLEU —
    /// whereas a healthy sampler spreads out. Reproducible per `base_seed`.
    pub fn sample_diversity(
        &self,
        prompt: &str,
        n: usize,
        max_new: usize,
        base_seed: u64,
    ) -> Result<SampleDiversity, LlmError> {
        let id_sets = self.generate_ids_n(prompt, n, max_new, base_seed)?;
        let texts: Vec<String> = id_sets
            .iter()
            .map(|ids| self.tokenizer.decode(ids).unwrap_or_default())
            .collect();
        let refs: Vec<&str> = texts.iter().map(String::as_str).collect();
        Ok(SampleDiversity {
            samples: refs.len(),
            distinct_1: sovereign_diversity::distinct_n_str(&refs, 1),
            distinct_2: sovereign_diversity::distinct_n_str(&refs, 2),
            self_bleu: sovereign_diversity::self_bleu_str(&refs, 4),
            unique_ratio: sovereign_diversity::unique_ratio(&refs),
        })
    }

    /// **Self-consistency with answer extraction**: generate `n` samples for
    /// `prompt`, pull the final answer out of each (`sovereign-answer-extract`
    /// honors `Final answer:` / `the answer is` / `Answer:` markers, else the
    /// last line), and return the **majority** answer with its vote count.
    /// Extracting before voting groups equivalent conclusions reached through
    /// different reasoning prose — the standard self-consistency recipe — which a
    /// raw-sequence vote ([`majority_sequence`]) misses. `None` only if `n == 0`.
    /// Reproducible per `base_seed`.
    pub fn consistent_answer(
        &self,
        prompt: &str,
        n: usize,
        max_new: usize,
        base_seed: u64,
    ) -> Result<Option<(String, usize)>, LlmError> {
        let id_sets = self.generate_ids_n(prompt, n, max_new, base_seed)?;
        let answers: Vec<String> = id_sets
            .iter()
            .map(|ids| {
                let text = self.tokenizer.decode(ids).unwrap_or_default();
                sovereign_answer_extract::extract_answer(&text)
            })
            .collect();
        Ok(majority_answer(&answers))
    }

    /// Generate token ids, stopping at the tokenizer's special token named
    /// `eos` (e.g. `"<eos>"`) — the natural serving loop. If that special is
    /// registered, generation stops the moment the model emits it (it is
    /// included); otherwise this is a plain `max_new` generation. Pairs the
    /// tokenizer's special tokens with early-stop.
    pub fn generate_ids_until_eos(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        eos: &str,
    ) -> Result<Vec<u32>, LlmError> {
        match self.tokenizer.special_id(eos) {
            Some(id) => self.generate_ids_until(prompt, max_new, seed, &[id]),
            None => self.generate_ids(prompt, max_new, seed),
        }
    }

    /// Complete `prompt` with composable [`GenOptions`], returning the decoded
    /// **text** (stop tokens / special tokens decode to nothing). The
    /// text-to-text counterpart of [`generate_ids_with`](Self::generate_ids_with)
    /// — one call for constrained + no-repeat-ngram + early-stop + min-length
    /// generation. Reproducible per `seed`.
    pub fn complete_with(
        &self,
        prompt: &str,
        seed: u64,
        opts: &GenOptions,
    ) -> Result<String, LlmError> {
        let ids = self.generate_ids_with(prompt, seed, opts, |_| {})?;
        Ok(self.tokenizer.decode(&ids).unwrap_or_default())
    }

    /// Unified, serving-grade generation: compose constrained masking, dynamic
    /// no-repeat-ngram blocking, early-stop, and per-token streaming via
    /// [`GenOptions`] — the single configurable entry point the simpler
    /// `generate_ids*` methods specialize. The `on_token` callback fires with
    /// each generated id; the full id sequence is returned. Pristine cache per
    /// call.
    pub fn generate_ids_with<F: FnMut(u32)>(
        &self,
        prompt: &str,
        seed: u64,
        opts: &GenOptions,
        mut on_token: F,
    ) -> Result<Vec<u32>, LlmError> {
        let ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .into_iter()
            .map(|t| t as usize)
            .collect();
        if ids.is_empty() {
            return Err(LlmError::EmptyPrompt);
        }
        let mut model = self.model.clone();
        let mut out = Vec::with_capacity(opts.max_new);
        model.generate_with(&ids, seed, opts, |t| {
            let id = t as u32;
            out.push(id);
            on_token(id);
        })?;
        Ok(out)
    }

    /// Generate token ids, stopping early at the first token in `stop_tokens`
    /// (which is included). The EOS / stop-sequence behaviour a real runtime
    /// needs. Pristine cache per call.
    pub fn generate_ids_until(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        stop_tokens: &[u32],
    ) -> Result<Vec<u32>, LlmError> {
        let ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .into_iter()
            .map(|t| t as usize)
            .collect();
        if ids.is_empty() {
            return Err(LlmError::EmptyPrompt);
        }
        let stops: Vec<usize> = stop_tokens.iter().map(|&t| t as usize).collect();
        let mut model = self.model.clone();
        let generated = model.generate_until(&ids, max_new, seed, &stops)?;
        Ok(generated.iter().map(|&t| t as u32).collect())
    }

    /// Generate token ids under a stateful [`Mirostat`] controller — output
    /// perplexity is held near the controller's target instead of using the
    /// config's static truncation. The controller's `μ` advances across the
    /// call. Starts from a pristine cache (model cloned).
    pub fn generate_ids_mirostat(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mirostat: &mut Mirostat,
    ) -> Result<Vec<u32>, LlmError> {
        let ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .into_iter()
            .map(|t| t as usize)
            .collect();
        if ids.is_empty() {
            return Err(LlmError::EmptyPrompt);
        }
        let mut model = self.model.clone();
        let generated = model.generate_mirostat(&ids, max_new, seed, mirostat)?;
        Ok(generated.iter().map(|&t| t as u32).collect())
    }

    /// Streaming generation: invoke `on_token` with each generated token id the
    /// moment it is produced, so a caller can emit tokens as they arrive (e.g.
    /// server-sent events) instead of waiting for the whole completion. Returns
    /// the full id sequence too. Starts from a pristine cache (model is cloned),
    /// so it never contaminates other calls.
    pub fn generate_ids_streaming<F: FnMut(u32)>(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mut on_token: F,
    ) -> Result<Vec<u32>, LlmError> {
        let ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .into_iter()
            .map(|t| t as usize)
            .collect();
        if ids.is_empty() {
            return Err(LlmError::EmptyPrompt);
        }
        let mut model = self.model.clone();
        let mut out = Vec::with_capacity(max_new);
        model.generate_masked_with(&ids, max_new, seed, &LogitMask::new(), |t| {
            let id = t as u32;
            out.push(id);
            on_token(id);
        })?;
        Ok(out)
    }

    /// Like [`generate_ids`](Self::generate_ids) but applies a [`LogitMask`]
    /// at every step — constrained decoding (allow-list / bans / bias).
    pub fn generate_ids_constrained(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
    ) -> Result<Vec<u32>, LlmError> {
        let ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .into_iter()
            .map(|t| t as usize)
            .collect();
        if ids.is_empty() {
            return Err(LlmError::EmptyPrompt);
        }
        // clone the model so generation starts from a pristine cache every call
        let mut model = self.model.clone();
        let generated = model.generate_masked(&ids, max_new, seed, mask)?;
        Ok(generated.iter().map(|&t| t as u32).collect())
    }

    /// Complete `prompt` under a [`LogitMask`], returning only the newly
    /// generated text. Confines generation to the mask's permitted tokens.
    pub fn complete_constrained(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
    ) -> Result<String, LlmError> {
        let generated = self.generate_ids_constrained(prompt, max_new, seed, mask)?;
        Ok(self.tokenizer.decode(&generated).unwrap_or_default())
    }
}

/// **Self-consistency** vote: the sequence that occurs most often across
/// `samples` (e.g. from [`generate_ids_n`](SovereignLlm::generate_ids_n)), with
/// its count. Ties break toward the sequence that appears earliest in
/// `samples` (stable). Returns `None` for an empty input. Sampling several
/// completions and keeping the majority is a simple, effective accuracy boost
/// for tasks with a single correct answer.
pub fn majority_sequence(samples: &[Vec<u32>]) -> Option<(Vec<u32>, usize)> {
    if samples.is_empty() {
        return None;
    }
    let mut best: Option<(usize, usize)> = None; // (first-seen index, count)
    for (i, s) in samples.iter().enumerate() {
        // Only score the first occurrence of each distinct sequence.
        if samples[..i].iter().any(|p| p == s) {
            continue;
        }
        let count = samples.iter().filter(|p| *p == s).count();
        let better = match best {
            None => true,
            Some((_, bc)) => count > bc, // strict: ties keep the earlier seen
        };
        if better {
            best = Some((i, count));
        }
    }
    best.map(|(i, count)| (samples[i].clone(), count))
}

/// **Self-consistency** vote over already-extracted answer *strings*: the answer
/// that occurs most often, with its count. Unlike [`majority_sequence`] (which
/// votes on raw token sequences), this groups equivalent conclusions reached via
/// different reasoning — the point of extracting the answer first. Ties break
/// toward the earliest-seen answer; returns `None` for an empty input.
pub fn majority_answer(answers: &[String]) -> Option<(String, usize)> {
    if answers.is_empty() {
        return None;
    }
    let mut best: Option<(usize, usize)> = None; // (first-seen index, count)
    for (i, a) in answers.iter().enumerate() {
        if answers[..i].iter().any(|p| p == a) {
            continue;
        }
        let count = answers.iter().filter(|p| *p == a).count();
        let better = match best {
            None => true,
            Some((_, bc)) => count > bc,
        };
        if better {
            best = Some((i, count));
        }
    }
    best.map(|(i, count)| (answers[i].clone(), count))
}

/// The result of a [`SemanticCachedLlm::complete`] call.
#[derive(Debug, Clone, PartialEq)]
pub struct CachedCompletion {
    /// The completion text (served from cache or freshly generated).
    pub text: String,
    /// Whether it was served from the semantic cache (no model run).
    pub cached: bool,
    /// The cosine similarity of the matched prompt, when `cached`.
    pub similarity: Option<f32>,
}

/// A [`SovereignLlm`] fronted by a **semantic completion cache**: before running
/// the model it looks the prompt up by embedding similarity, and returns a
/// cached completion when a previously-seen prompt clears the similarity
/// threshold — so a paraphrase of an earlier request (different words, same
/// meaning) is served for free instead of decoding again. Misses run the model
/// and populate the cache. Because both the embeddings and the decode are
/// deterministic per seed, the cache is reproducible.
///
/// Activates [`sovereign-semantic-cache`], previously built but unused.
///
/// [`sovereign-semantic-cache`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-semantic-cache
pub struct SemanticCachedLlm {
    inner: SovereignLlm,
    cache: sovereign_semantic_cache::SemanticCache,
}

impl SemanticCachedLlm {
    /// Wrap `inner`, returning a cache hit when a prior prompt's cosine
    /// similarity is `≥ threshold`, holding up to `capacity` entries.
    ///
    /// # Panics
    /// Panics if `capacity == 0`.
    pub fn new(inner: SovereignLlm, threshold: f32, capacity: usize) -> Self {
        Self {
            inner,
            cache: sovereign_semantic_cache::SemanticCache::new(threshold, capacity),
        }
    }

    /// Complete `prompt`, serving a semantically-similar cached completion when
    /// one clears the threshold; otherwise run the model and cache the result.
    pub fn complete(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<CachedCompletion, LlmError> {
        if let Some(hit) = self.cache.get(prompt) {
            return Ok(CachedCompletion {
                text: hit.completion,
                cached: true,
                similarity: Some(hit.similarity),
            });
        }
        let text = self.inner.complete(prompt, max_new, seed)?;
        self.cache.put(prompt, text.clone());
        Ok(CachedCompletion {
            text,
            cached: false,
            similarity: None,
        })
    }

    /// Cache hits observed so far.
    pub fn cache_hits(&self) -> u64 {
        self.cache.hits()
    }

    /// Cache misses observed so far.
    pub fn cache_misses(&self) -> u64 {
        self.cache.misses()
    }

    /// Number of cached entries.
    pub fn cache_len(&self) -> usize {
        self.cache.len()
    }

    /// The wrapped runtime.
    pub fn inner(&self) -> &SovereignLlm {
        &self.inner
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_ffn::SwiGlu;
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_sampler::{Sampler, SamplerConfig};
    use sovereign_transformer_block::BlockWeights;

    fn block(model_dim: usize, seed: f32) -> BlockWeights {
        let hd = model_dim;
        let mat = |s: f32, n: usize| (0..n).map(|i| ((i as f32 + s) * 0.013).sin()).collect();
        BlockWeights {
            model_dim,
            head_dim: hd,
            attn_norm: RmsNorm::new(model_dim),
            ffn_norm: RmsNorm::new(model_dim),
            w_q: mat(seed, hd * model_dim),
            w_k: mat(seed + 1.0, hd * model_dim),
            w_v: mat(seed + 2.0, hd * model_dim),
            w_o: mat(seed + 3.0, model_dim * hd),
            ffn: SwiGlu::new(
                model_dim,
                model_dim,
                mat(seed + 4.0, model_dim * model_dim),
                mat(seed + 5.0, model_dim * model_dim),
                mat(seed + 6.0, model_dim * model_dim),
            )
            .unwrap(),
        }
    }

    /// A model whose vocab matches a base (256-token) tokenizer.
    fn model_config(
        vocab: usize,
        model_dim: usize,
        layers: usize,
        sampler: Sampler,
    ) -> StackConfig {
        StackConfig {
            vocab,
            model_dim,
            embedding: (0..vocab * model_dim)
                .map(|i| ((i as f32) * 0.001).sin())
                .collect(),
            blocks: (0..layers)
                .map(|l| block(model_dim, l as f32 * 7.0))
                .collect(),
            final_norm: RmsNorm::new(model_dim),
            head: (0..vocab * model_dim)
                .map(|i| ((i as f32) * 0.001).cos())
                .collect(),
            sampler,
            recent_window: 64,
        }
    }

    fn runtime(sampler: Sampler) -> SovereignLlm {
        let tok = Tokenizer::default(); // 256-token base vocab
        let cfg = model_config(tok.vocab_size(), 4, 2, sampler);
        SovereignLlm::new(tok, cfg).unwrap()
    }

    /// A runtime whose tokenizer reserves an `<eos>` special token.
    fn runtime_with_eos(sampler: Sampler) -> SovereignLlm {
        let tok = Tokenizer::default().with_specials(["<eos>"]); // vocab 257
        let cfg = model_config(tok.vocab_size(), 4, 2, sampler);
        SovereignLlm::new(tok, cfg).unwrap()
    }

    #[test]
    fn self_consistent_greedy_is_unanimous() {
        // a deterministic sampler makes every sample identical → full agreement,
        // and the voted answer equals a single greedy completion
        let llm = runtime(Sampler::greedy());
        let vote = llm.complete_self_consistent("hello", 6, 4, 5).unwrap();
        assert_eq!(vote.total, 5);
        assert_eq!(vote.count, 5);
        assert!((vote.agreement - 1.0).abs() < 1e-9);
        assert_eq!(vote.answer, llm.complete("hello", 6, 4).unwrap());
    }

    #[test]
    fn self_consistent_is_reproducible() {
        let a = runtime(Sampler::new(SamplerConfig {
            temperature: 0.9,
            top_k: Some(40),
            ..SamplerConfig::default()
        }));
        let b = runtime(Sampler::new(SamplerConfig {
            temperature: 0.9,
            top_k: Some(40),
            ..SamplerConfig::default()
        }));
        let va = a.complete_self_consistent("hello there", 8, 7, 4).unwrap();
        let vb = b.complete_self_consistent("hello there", 8, 7, 4).unwrap();
        assert_eq!(va.answer, vb.answer);
        assert_eq!(va.count, vb.count);
        assert_eq!(va.total, 4);
    }

    #[test]
    fn self_consistent_zero_samples_errors() {
        let llm = runtime(Sampler::greedy());
        assert!(matches!(
            llm.complete_self_consistent("hello", 6, 4, 0),
            Err(LlmError::SelfConsistency(_))
        ));
    }

    #[test]
    fn calibrate_fits_a_temperature_and_reports_ece() {
        let llm = runtime(Sampler::greedy());
        let report = llm
            .calibrate("the quick brown fox jumps over the lazy dog", 10)
            .unwrap()
            .expect("enough tokens");
        // a real temperature was fit and a full teacher-forced pass was scored
        assert!(report.temperature > 0.0 && report.temperature.is_finite());
        assert!(report.samples >= 1);
        // ECE is a probability-scale error in [0, 1]
        assert!((0.0..=1.0).contains(&report.ece_before), "{report:?}");
        assert!((0.0..=1.0).contains(&report.ece_after), "{report:?}");
    }

    #[test]
    fn calibrate_none_for_too_short_and_is_reproducible() {
        let llm = runtime(Sampler::greedy());
        // a single token gives no next-token prediction to calibrate on
        assert!(llm.calibrate("a", 10).unwrap().is_none());
        // deterministic: same reference → same fit
        let a = llm.calibrate("hello there world", 8).unwrap();
        let b = llm.calibrate("hello there world", 8).unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn best_of_n_greedy_equals_single_complete() {
        // greedy → every candidate identical → the best is that same completion
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.complete_best_of_n("hello", 6, 4, 5).unwrap(),
            llm.complete("hello", 6, 4).unwrap()
        );
    }

    #[test]
    fn best_of_n_zero_clamps_to_single() {
        // n = 0 clamps to 1 → a single completion at base_seed
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.complete_best_of_n("hello", 6, 4, 0).unwrap(),
            llm.complete("hello", 6, 4).unwrap()
        );
    }

    #[test]
    fn best_of_n_picks_a_produced_candidate_and_is_reproducible() {
        // with a stochastic sampler the winner must be one of the n candidates,
        // and the choice is fully reproducible per base_seed
        let cfg = || {
            Sampler::new(SamplerConfig {
                temperature: 0.9,
                top_k: Some(40),
                ..SamplerConfig::default()
            })
        };
        let a = runtime(cfg());
        let b = runtime(cfg());
        let winner = a.complete_best_of_n("hello there", 8, 7, 4).unwrap();
        assert_eq!(
            winner,
            b.complete_best_of_n("hello there", 8, 7, 4).unwrap()
        );
        let candidates: Vec<String> = (0..4)
            .map(|i| a.complete("hello there", 8, 7 + i).unwrap())
            .collect();
        assert!(candidates.contains(&winner), "winner not among candidates");
    }

    #[test]
    fn semantic_cache_first_call_misses_then_repeat_hits() {
        let mut llm = SemanticCachedLlm::new(runtime(Sampler::greedy()), 0.9, 8);
        let first = llm.complete("hello world", 6, 4).unwrap();
        assert!(!first.cached, "first call must run the model");
        assert_eq!(llm.cache_len(), 1);
        assert_eq!(llm.cache_misses(), 1);
        // an exact repeat embeds identically (similarity 1.0) → served from cache
        let second = llm.complete("hello world", 6, 4).unwrap();
        assert!(second.cached, "exact repeat must hit the cache");
        assert_eq!(second.text, first.text);
        assert!(second.similarity.unwrap() > 0.999);
        assert_eq!(llm.cache_hits(), 1);
    }

    #[test]
    fn semantic_cache_miss_matches_plain_complete() {
        // faithful wiring: a cache miss returns exactly what the bare runtime would
        let plain = runtime(Sampler::greedy()).complete("hello", 6, 4).unwrap();
        let mut cached = SemanticCachedLlm::new(runtime(Sampler::greedy()), 0.9, 8);
        let r = cached.complete("hello", 6, 4).unwrap();
        assert!(!r.cached);
        assert_eq!(r.text, plain);
    }

    #[test]
    fn semantic_cache_threshold_one_only_hits_identical_prompts() {
        // threshold 1.0 → only an identical embedding hits; a distinct prompt misses
        let mut llm = SemanticCachedLlm::new(runtime(Sampler::greedy()), 1.0, 8);
        assert!(!llm.complete("the quick brown fox", 6, 4).unwrap().cached);
        assert!(
            !llm.complete("a completely different sentence", 6, 4)
                .unwrap()
                .cached
        );
        assert!(llm.complete("the quick brown fox", 6, 4).unwrap().cached);
        assert_eq!(llm.cache_hits(), 1);
        assert_eq!(llm.cache_misses(), 2);
    }

    #[test]
    fn generate_until_eos_uses_the_special_token() {
        let llm = runtime_with_eos(Sampler::new(SamplerConfig::default()));
        let eos = llm.tokenizer().special_id("<eos>").unwrap();
        // eos-aware generation equals generate_ids_until with the resolved id.
        let a = llm.generate_ids_until_eos("hello", 8, 4, "<eos>").unwrap();
        let b = llm.generate_ids_until("hello", 8, 4, &[eos]).unwrap();
        assert_eq!(a, b);
        assert!(a.len() <= 8);
    }

    #[test]
    fn generate_until_eos_unregistered_name_is_plain_generation() {
        let llm = runtime_with_eos(Sampler::new(SamplerConfig::default()));
        let plain = llm.generate_ids("hello", 6, 4).unwrap();
        let eos = llm
            .generate_ids_until_eos("hello", 6, 4, "<not-registered>")
            .unwrap();
        assert_eq!(eos, plain);
        assert_eq!(eos.len(), 6);
    }

    #[test]
    fn compress_prompt_shrinks_and_stays_decodable() {
        let llm = runtime(Sampler::greedy());
        let text = "the quick brown fox jumps over the lazy dog repeatedly";
        let full = llm.tokenizer().encode(text).len();
        // keep ~half the tokens
        let compressed = llm.compress_prompt(text, 0.5).unwrap();
        let kept = llm.tokenizer().encode(&compressed).len();
        assert!(kept < full, "compressed {kept} should be < original {full}");
        assert!(kept >= 2, "anchors keep at least the boundary tokens");
        // result is valid (decoded) text
        assert!(compressed.is_empty() || compressed.is_char_boundary(0));
    }

    #[test]
    fn compress_prompt_ratio_one_keeps_everything() {
        let llm = runtime(Sampler::greedy());
        let text = "alpha beta gamma delta";
        let ids = llm.tokenizer().encode(text);
        let kept = llm.compress_prompt(text, 1.0).unwrap();
        // keep_ratio 1.0 → every token survives → round-trips to the same ids
        assert_eq!(llm.tokenizer().encode(&kept), ids);
    }

    #[test]
    fn sample_diversity_detects_greedy_collapse() {
        // Greedy ignores the seed, so all n samples are identical → the bluntest
        // collapse signal: only one distinct string among n.
        let llm = runtime(Sampler::greedy());
        let d = llm.sample_diversity("hello world", 4, 6, 100).unwrap();
        assert_eq!(d.samples, 4);
        assert!((d.unique_ratio - 0.25).abs() < 1e-9); // 1 distinct / 4
        // every metric is a valid ratio
        for v in [d.distinct_1, d.distinct_2, d.self_bleu, d.unique_ratio] {
            assert!((0.0..=1.0).contains(&v), "out of range: {v}");
        }
    }

    #[test]
    fn complete_checked_wires_the_degeneration_report() {
        use sovereign_degeneration::{Config, analyze};
        let llm = runtime(Sampler::greedy());
        let cfg = Config::default();
        let (text, report) = llm.complete_checked("hello", 12, 7, &cfg).unwrap();
        // the text is exactly what complete() produces for the same args
        assert_eq!(text, llm.complete("hello", 12, 7).unwrap());
        // the report is exactly analyze() of that text — the wiring is faithful
        assert_eq!(report, analyze(&text, &cfg));
        assert!((0.0..=1.0).contains(&report.distinct_ngram_ratio));
    }

    #[test]
    fn complete_dry_inactive_equals_plain_complete() {
        let llm = runtime(Sampler::greedy());
        // multiplier 0 → DRY inactive → identical to plain complete
        assert_eq!(
            llm.complete_dry("hello", 6, 4, 0.0, 1.75, 2).unwrap(),
            llm.complete("hello", 6, 4).unwrap()
        );
    }

    #[test]
    fn complete_dry_is_reproducible() {
        let a = runtime(Sampler::greedy());
        let b = runtime(Sampler::greedy());
        assert_eq!(
            a.complete_dry("hello there", 8, 4, 2.0, 1.75, 1).unwrap(),
            b.complete_dry("hello there", 8, 4, 2.0, 1.75, 1).unwrap()
        );
    }

    #[test]
    fn complete_xtc_inactive_equals_plain_complete() {
        let llm = runtime(Sampler::greedy());
        // probability 0 → XTC never fires → identical to plain complete
        assert_eq!(
            llm.complete_xtc("hello", 6, 4, 0.1, 0.0).unwrap(),
            llm.complete("hello", 6, 4).unwrap()
        );
    }

    #[test]
    fn complete_xtc_is_reproducible() {
        let a = runtime(Sampler::greedy());
        let b = runtime(Sampler::greedy());
        // always-firing XTC is still fully reproducible per seed
        assert_eq!(
            a.complete_xtc("hello there", 8, 4, 0.01, 1.0).unwrap(),
            b.complete_xtc("hello there", 8, 4, 0.01, 1.0).unwrap()
        );
    }

    #[test]
    fn complete_penalized_identity_equals_plain_complete() {
        let llm = runtime(Sampler::greedy());
        // repetition 1.0 + frequency 0 + presence 0 → identity → plain complete
        assert_eq!(
            llm.complete_penalized("hello", 6, 4, 1.0, 0.0, 0.0)
                .unwrap(),
            llm.complete("hello", 6, 4).unwrap()
        );
    }

    #[test]
    fn complete_penalized_is_reproducible() {
        let a = runtime(Sampler::greedy());
        let b = runtime(Sampler::greedy());
        assert_eq!(
            a.complete_penalized("hello there", 8, 4, 1.3, 0.5, 0.2)
                .unwrap(),
            b.complete_penalized("hello there", 8, 4, 1.3, 0.5, 0.2)
                .unwrap()
        );
    }

    #[test]
    fn complete_typical_full_mass_equals_plain_complete() {
        let llm = runtime(Sampler::greedy());
        // mass 1.0 keeps the whole vocab → identical to plain complete
        assert_eq!(
            llm.complete_typical("hello", 6, 4, 1.0).unwrap(),
            llm.complete("hello", 6, 4).unwrap()
        );
    }

    #[test]
    fn complete_typical_is_reproducible() {
        let a = runtime(Sampler::greedy());
        let b = runtime(Sampler::greedy());
        assert_eq!(
            a.complete_typical("hello there", 8, 4, 0.9).unwrap(),
            b.complete_typical("hello there", 8, 4, 0.9).unwrap()
        );
    }

    #[test]
    fn complete_within_context_trims_an_overlong_prompt() {
        let llm = runtime(Sampler::greedy());
        let long = "the quick brown fox jumps over the lazy dog again and again";
        // faithful wiring: equals completing the tail-trimmed prompt
        let trimmed = sovereign_context_budget::trim(
            llm.tokenizer(),
            long,
            8,
            sovereign_context_budget::Keep::Tail,
        );
        assert!(sovereign_context_budget::token_count(llm.tokenizer(), &trimmed) <= 8);
        assert_eq!(
            llm.complete_within_context(long, 8, 6, 4).unwrap(),
            llm.complete(&trimmed, 6, 4).unwrap()
        );
    }

    #[test]
    fn complete_within_context_leaves_a_fitting_prompt_unchanged() {
        let llm = runtime(Sampler::greedy());
        // a short prompt within budget completes exactly like plain complete
        assert_eq!(
            llm.complete_within_context("hello", 64, 6, 4).unwrap(),
            llm.complete("hello", 6, 4).unwrap()
        );
    }

    #[test]
    fn token_healing_allows_only_boundary_consistent_first_tokens() {
        // Build a healer over the runtime's (byte) vocab and confirm the first-step
        // constraint complete_healed applies: after trimming the 'b' from "ab", only
        // tokens consistent with the prefix "b" are allowed.
        let llm = runtime(Sampler::greedy());
        let vocab: Vec<String> = (0..llm.vocab_size())
            .map(|id| llm.tokenizer().decode(&[id as u32]).unwrap_or_default())
            .collect();
        let healer = sovereign_token_healing::TokenHealer::new(vocab);
        let ids = llm.tokenizer().encode("ab");
        let healed = healer.heal(&ids);
        assert_eq!(healed.prefix, "b");
        let allowed = healer.allowed_continuations("b");
        // the 'b' byte (98) is consistent; 'z' (122) is not
        assert!(allowed.contains(&(b'b' as u32)));
        assert!(!allowed.contains(&(b'z' as u32)));
    }

    #[test]
    fn complete_healed_falls_back_for_single_token_prompt() {
        let llm = runtime(Sampler::greedy());
        // a single-byte prompt has nothing to trim → identical to plain complete
        assert_eq!(
            llm.complete_healed("a", 6, 4).unwrap(),
            llm.complete("a", 6, 4).unwrap()
        );
    }

    #[test]
    fn complete_healed_is_reproducible() {
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.complete_healed("hello", 6, 2).unwrap(),
            b.complete_healed("hello", 6, 2).unwrap()
        );
    }

    #[test]
    fn complete_regex_confines_output_to_the_pattern() {
        // The digit-only pattern masks every non-digit token each step, so the
        // model — whatever its weights — can only emit ASCII digits.
        let llm = runtime(Sampler::greedy());
        let out = llm.complete_regex("number: ", "[0-9]+", 6, 7).unwrap();
        assert_eq!(out.chars().count(), 6);
        assert!(out.chars().all(|c| c.is_ascii_digit()), "{out:?}");
    }

    #[test]
    fn complete_regex_is_reproducible_and_rejects_bad_patterns() {
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.complete_regex("x", "[a-c]+", 5, 3).unwrap(),
            b.complete_regex("x", "[a-c]+", 5, 3).unwrap()
        );
        // an invalid pattern is a Regex error, not a panic
        assert!(matches!(
            a.complete_regex("x", "[", 4, 1),
            Err(LlmError::Regex(_))
        ));
    }

    #[test]
    fn complete_json_schema_confines_output_to_the_grammar_alphabet() {
        use sovereign_json_schema_grammar::Schema;
        let llm = runtime(Sampler::greedy());
        // For {"ok": <bool>} the grammar can only ever emit the structural chars,
        // the key "ok", the booleans, and whitespace. The mask forbids everything
        // else every step — so no out-of-grammar char (a digit, a stray letter
        // like 'z') can appear, whatever the (random) weights.
        let schema = Schema::object([("ok".to_string(), Schema::Boolean)]);
        let out = llm.complete_json_schema("emit: ", &schema, 40, 7).unwrap();
        let allowed: std::collections::HashSet<char> = "{}\":oktruefalse \t\n\r".chars().collect();
        assert!(
            out.chars().all(|c| allowed.contains(&c)),
            "out-of-grammar char in {out:?}"
        );
    }

    #[test]
    fn json_schema_with_laws_composes_grammar_and_policy() {
        use sovereign_json_schema_grammar::Schema;
        // SDD-501: grammar ∧ policy. The {"ok": <bool>} grammar allows both
        // 't' (true) and 'f' (false). A policy plane BANS the byte 't' → the
        // model can no longer spell "true", so the composition forces "false"
        // and no 't' ever appears — a constraint NEITHER path does alone.
        let llm = runtime(Sampler::greedy());
        let schema = Schema::object([("ok".to_string(), Schema::Boolean)]);
        let words = llm.vocab_size().div_ceil(64);
        let mut ban_t = vec![u64::MAX; words];
        let t = b't' as usize;
        ban_t[t >> 6] &= !(1u64 << (t & 63));
        let out = llm
            .complete_json_schema_with_laws("emit: ", &schema, &[&ban_t], 40, 7)
            .unwrap();
        assert!(
            !out.contains('t'),
            "policy banned 't' but it appears: {out:?}"
        );
        // still confined to the grammar alphabet (the grammar plane still holds)
        let allowed: std::collections::HashSet<char> = "{}\":oktruefalse \t\n\r".chars().collect();
        assert!(
            out.chars().all(|c| allowed.contains(&c)),
            "out-of-grammar char in {out:?}"
        );
    }

    #[test]
    fn json_schema_with_no_laws_equals_the_grammar_only_path() {
        use sovereign_json_schema_grammar::Schema;
        // With zero policy planes the composition is exactly the grammar path —
        // proving the multi-plane route is a superset, not a divergence.
        let schema = Schema::object([("ok".to_string(), Schema::Boolean)]);
        let a = runtime(Sampler::greedy());
        let b = runtime(Sampler::greedy());
        assert_eq!(
            a.complete_json_schema_with_laws("emit: ", &schema, &[], 40, 7)
                .unwrap(),
            b.complete_json_schema("emit: ", &schema, 40, 7).unwrap(),
        );
    }

    #[test]
    fn regex_with_laws_composes_pattern_and_policy() {
        // SDD-503: regex as a REAL constraint source ∧ a policy plane. The
        // pattern [0-9]+ confines to digits; a policy plane bans the byte '5' →
        // the output is digits with no '5' — the two composed per step.
        let llm = runtime(Sampler::greedy());
        let words = llm.vocab_size().div_ceil(64);
        let mut ban_5 = vec![u64::MAX; words];
        let five = b'5' as usize;
        ban_5[five >> 6] &= !(1u64 << (five & 63));
        let out = llm
            .complete_regex_with_laws("number: ", "[0-9]+", &[&ban_5], 8, 7)
            .unwrap();
        assert!(!out.is_empty(), "should generate at least one digit");
        assert!(
            out.chars().all(|c| c.is_ascii_digit()),
            "regex [0-9]+ violated: {out:?}"
        );
        assert!(
            !out.contains('5'),
            "policy banned '5' but it appears: {out:?}"
        );
    }

    #[test]
    fn regex_with_laws_zero_planes_still_matches_the_pattern() {
        // With no policy planes the regex plane alone holds — output matches [0-9]+.
        let llm = runtime(Sampler::greedy());
        let out = llm
            .complete_regex_with_laws("number: ", "[0-9]+", &[], 6, 7)
            .unwrap();
        assert!(!out.is_empty());
        assert!(
            out.chars().all(|c| c.is_ascii_digit()),
            "not all digits: {out:?}"
        );
    }

    #[test]
    fn tool_name_allow_list_via_regex_alternation() {
        // SDD-503: a tool-name allow-list is just an alternation pattern. The
        // regex plane confines the output to a PREFIX of one of the allowed tool
        // names — the model can never spell a name outside the set.
        let llm = runtime(Sampler::greedy());
        let out = llm
            .complete_regex_with_laws("call: ", "(get_weather|search_web)", &[], 11, 7)
            .unwrap();
        assert!(!out.is_empty());
        assert!(
            "get_weather".starts_with(&out) || "search_web".starts_with(&out),
            "output {out:?} is not a prefix of an allowed tool name"
        );
    }

    #[test]
    fn json_schema_and_regex_compose_all_three() {
        use sovereign_json_schema_grammar::Schema;
        // SDD-503: grammar ∧ regex ∧ policy, all at once. The JSON-string grammar
        // allows ANY printable between the quotes (and even the empty string "");
        // the regex "[a-z]+" narrows the content to one-or-more LOWERCASE letters
        // (forbidding uppercase, digits, AND the empty string the grammar allows);
        // a policy plane bans 'z'. So every char is either a quote or a lowercase
        // letter that is not 'z' — a constraint no single source expresses.
        let llm = runtime(Sampler::greedy());
        let words = llm.vocab_size().div_ceil(64);
        let mut ban_z = vec![u64::MAX; words];
        let z = b'z' as usize;
        ban_z[z >> 6] &= !(1u64 << (z & 63));
        let out = llm
            .complete_json_schema_and_regex_with_laws(
                "emit: ",
                &Schema::StringType,
                "\"[a-z]+\"",
                &[&ban_z],
                12,
                7,
            )
            .unwrap();
        assert!(
            out.starts_with('"'),
            "grammar requires a leading quote: {out:?}"
        );
        assert!(out.len() >= 2, "regex forces at least one letter: {out:?}");
        assert!(
            out.chars()
                .all(|c| c == '"' || (c.is_ascii_lowercase() && c != 'z')),
            "grammar∧regex∧policy violated: {out:?}"
        );
        // the regex genuinely narrowed the grammar: no uppercase, no digit.
        assert!(
            !out.chars()
                .any(|c| c.is_ascii_uppercase() || c.is_ascii_digit()),
            "regex should forbid uppercase/digits the grammar allows: {out:?}"
        );
    }

    #[test]
    fn safety_denylist_never_emits_a_banned_byte() {
        // SDD-504: the negative plane. Banning the byte 'a' guarantees the output
        // contains no 'a', whatever the (random) weights would otherwise pick.
        let llm = runtime(Sampler::greedy());
        let out = llm
            .complete_with_safety_denylist("say: ", &["a"], 12, 7)
            .unwrap();
        assert!(
            !out.contains('a'),
            "denylist banned 'a' but it appears: {out:?}"
        );
        // the guarantee, checked by an independent post-hoc scan.
        let deny = sovereign_token_law_deny::DenyConstraint::new(["a"]);
        assert!(!deny.is_denied(&out));
    }

    #[test]
    fn regex_with_safety_denylist_composes_positive_and_negative() {
        // SDD-504: a POSITIVE constraint (regex [a-z]+) AND a NEGATIVE one
        // (denylist "z") at once → lowercase letters with no 'z' (a-y only) — a
        // composition no single constraint expresses.
        let llm = runtime(Sampler::greedy());
        let out = llm
            .complete_regex_with_safety_denylist("word: ", "[a-z]+", &["z"], 8, 7)
            .unwrap();
        assert!(!out.is_empty());
        assert!(
            out.chars().all(|c| c.is_ascii_lowercase() && c != 'z'),
            "regex∧denylist violated (want a-y): {out:?}"
        );
    }

    #[test]
    fn safety_denylist_consumes_the_real_injection_pattern_source() {
        // SDD-504: the denylist accepts a REAL safety source verbatim — the
        // sovereign-injection-detect prompt-injection phrase list — and the output
        // is guaranteed to contain none of them.
        let llm = runtime(Sampler::greedy());
        let out = llm
            .complete_with_safety_denylist(
                "assistant: ",
                sovereign_injection_detect::PATTERNS,
                16,
                7,
            )
            .unwrap();
        let deny =
            sovereign_token_law_deny::DenyConstraint::new(sovereign_injection_detect::PATTERNS);
        assert!(
            !deny.is_denied(&out),
            "an injection phrase slipped through: {out:?}"
        );
    }

    #[test]
    fn json_schema_mask_forbids_invalid_continuations() {
        use sovereign_json_schema_grammar::{Schema, compile};
        // The grammar mask, over the runtime vocab, allows a boolean to start
        // after `{"ok":` but forbids an unrelated letter.
        let llm = runtime(Sampler::greedy());
        let vocab: Vec<String> = (0..llm.vocab_size())
            .map(|id| llm.tokenizer().decode(&[id as u32]).unwrap_or_default())
            .collect();
        let schema = Schema::object([("ok".to_string(), Schema::Boolean)]);
        let tgm = sovereign_token_grammar_mask::TokenGrammarMask::new(compile(&schema), vocab);
        let mask = tgm.mask("{\"ok\":");
        assert!(mask.allows(b't' as usize), "true should be allowed");
        assert!(mask.allows(b'f' as usize), "false should be allowed");
        assert!(!mask.allows(b'z' as usize), "z must be forbidden");
    }

    #[test]
    fn complete_json_schema_is_reproducible() {
        use sovereign_json_schema_grammar::Schema;
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        let schema = Schema::Integer;
        assert_eq!(
            a.complete_json_schema("n=", &schema, 16, 3).unwrap(),
            b.complete_json_schema("n=", &schema, 16, 3).unwrap()
        );
    }

    #[test]
    fn complete_json_matches_extracting_from_the_completion() {
        let llm = runtime(Sampler::greedy());
        let raw = llm.complete("hello", 12, 5).unwrap();
        let expected = sovereign_json_extract::extract_value(&raw).ok();
        assert_eq!(llm.complete_json("hello", 12, 5).unwrap(), expected);
    }

    #[test]
    fn json_extraction_pulls_value_from_prose() {
        // The capability complete_json exposes: balanced JSON out of wrapped prose.
        let v = sovereign_json_extract::extract_value("Sure! {\"city\":\"Paris\"} ok").unwrap();
        assert_eq!(v["city"], "Paris");
        // no JSON → the method maps the error to None
        assert!(sovereign_json_extract::extract_value("no json here").is_err());
    }

    #[test]
    fn completion_confidence_summarizes_generated_tokens() {
        let llm = runtime(Sampler::greedy());
        let report = llm.completion_confidence("hello", 8, 5).unwrap().unwrap();
        // one logprob per generated token
        assert_eq!(
            report.tokens,
            llm.generate_ids("hello", 8, 5).unwrap().len()
        );
        // perplexity is a valid LM perplexity; mean logprob is a log-prob (≤ 0)
        assert!(report.perplexity >= 1.0 - 1e-9 && report.perplexity.is_finite());
        assert!(report.mean_logprob <= 1e-9);
        // the weakest token is no more confident than the mean
        assert!(report.weakest_logprob <= report.mean_logprob + 1e-9);
        assert!(report.weakest_index.unwrap() < report.tokens);
    }

    #[test]
    fn completion_confidence_zero_max_new_is_none() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(llm.completion_confidence("hello", 0, 5).unwrap(), None);
    }

    #[test]
    fn completion_confidence_is_reproducible() {
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.completion_confidence("confidence prompt", 8, 2).unwrap(),
            b.completion_confidence("confidence prompt", 8, 2).unwrap()
        );
    }

    #[test]
    fn complete_screened_wires_the_toxicity_filter() {
        use sovereign_toxicity::{Severity, ToxicityFilter};
        let llm = runtime(Sampler::greedy());
        let mut filter = ToxicityFilter::new();
        filter.add_term("zzbadzz", Severity::Severe);
        let (text, toxic) = llm.complete_screened("hello", 12, 5, &filter, 0.5).unwrap();
        // text is the plain completion; verdict is exactly the filter's verdict
        assert_eq!(text, llm.complete("hello", 12, 5).unwrap());
        assert_eq!(toxic, filter.is_toxic(&text, 0.5));
    }

    #[test]
    fn toxicity_filter_flags_a_planted_severe_term() {
        use sovereign_toxicity::{Severity, ToxicityFilter};
        let mut f = ToxicityFilter::new();
        f.add_term("badword", Severity::Severe);
        assert!(f.is_toxic("you said badword again", 0.5));
        assert!(!f.is_toxic("a perfectly clean sentence", 0.5));
    }

    #[test]
    fn complete_redacted_matches_the_manual_scrub_pipeline() {
        let llm = runtime(Sampler::greedy());
        let raw = llm.complete("hello", 12, 5).unwrap();
        let expected = sovereign_pii_redact::redact(&sovereign_secret_scan::redact(&raw));
        assert_eq!(llm.complete_redacted("hello", 12, 5).unwrap(), expected);
    }

    #[test]
    fn scrub_pipeline_removes_a_planted_secret_and_email() {
        // The composition the runtime applies removes both classes: an AWS key
        // (secret) and an email (PII) are gone after the two-stage scrub.
        let leaky = "key AKIAIOSFODNN7EXAMPLE and email bob@mail.com here";
        let scrubbed = sovereign_pii_redact::redact(&sovereign_secret_scan::redact(leaky));
        assert!(!scrubbed.contains("AKIAIOSFODNN7EXAMPLE"), "{scrubbed}");
        assert!(!scrubbed.contains("bob@mail.com"), "{scrubbed}");
    }

    #[test]
    fn complete_checked_flags_a_degenerate_loop() {
        // We can't force the random model to loop, so verify the gate itself
        // fires on a known decoding loop fed through the same config.
        use sovereign_degeneration::{Config, analyze};
        let loop_text = "go on and on and on and on and on and on and on and on";
        let r = analyze(loop_text, &Config::default());
        assert!(r.is_degenerate, "loop should be flagged: {r:?}");
    }

    #[test]
    fn complete_checked_is_reproducible() {
        use sovereign_degeneration::Config;
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        let cfg = Config::default();
        assert_eq!(
            a.complete_checked("repeat me", 10, 2, &cfg).unwrap(),
            b.complete_checked("repeat me", 10, 2, &cfg).unwrap()
        );
    }

    #[test]
    fn majority_answer_votes_and_breaks_ties_earliest() {
        let answers: Vec<String> = ["42", "the answer", "42", "other"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        assert_eq!(
            majority_answer(&answers),
            Some(("42".to_string(), 2)) // most common
        );
        // all distinct → earliest-seen wins the tie (count 1)
        let distinct: Vec<String> = ["b", "a", "c"].iter().map(|s| s.to_string()).collect();
        assert_eq!(majority_answer(&distinct), Some(("b".to_string(), 1)));
        assert_eq!(majority_answer(&[]), None);
    }

    #[test]
    fn consistent_answer_greedy_matches_single_extraction() {
        // Greedy → all n samples identical → the majority answer is just the
        // extracted answer of the one completion, with full vote count.
        let llm = runtime(Sampler::greedy());
        let one = llm.complete("hello", 10, 3).unwrap();
        let expected = sovereign_answer_extract::extract_answer(&one);
        let (ans, votes) = llm.consistent_answer("hello", 4, 10, 3).unwrap().unwrap();
        assert_eq!(ans, expected);
        assert_eq!(votes, 4); // all four agree under greedy
    }

    #[test]
    fn consistent_answer_zero_n_is_none() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(llm.consistent_answer("hello", 0, 10, 1).unwrap(), None);
    }

    #[test]
    fn consistent_answer_is_reproducible() {
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.consistent_answer("vote prompt", 5, 8, 9).unwrap(),
            b.consistent_answer("vote prompt", 5, 8, 9).unwrap()
        );
    }

    #[test]
    fn sample_diversity_single_sample() {
        let llm = runtime(Sampler::greedy());
        let d = llm.sample_diversity("hello", 1, 6, 1).unwrap();
        assert_eq!(d.samples, 1);
        assert_eq!(d.unique_ratio, 1.0); // one sample is trivially unique
        assert_eq!(d.self_bleu, 0.0); // Self-BLEU needs ≥ 2 samples
    }

    #[test]
    fn sample_diversity_is_reproducible() {
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.sample_diversity("the diversity prompt", 5, 8, 3).unwrap(),
            b.sample_diversity("the diversity prompt", 5, 8, 3).unwrap()
        );
    }

    #[test]
    fn compress_prompt_short_text_is_unchanged() {
        let llm = runtime(Sampler::greedy());
        // a single-byte/token input cannot be scored → returned verbatim
        assert_eq!(llm.compress_prompt("x", 0.5).unwrap(), "x");
    }

    #[test]
    fn compress_prompt_is_reproducible() {
        let a = runtime(Sampler::greedy());
        let b = runtime(Sampler::greedy());
        let t = "reproducible compression over the same model and text";
        assert_eq!(
            a.compress_prompt(t, 0.6).unwrap(),
            b.compress_prompt(t, 0.6).unwrap()
        );
    }

    #[test]
    fn vocab_must_match() {
        let tok = Tokenizer::default(); // 256
        let cfg = model_config(100, 4, 1, Sampler::greedy()); // wrong vocab
        assert_eq!(
            SovereignLlm::new(tok, cfg).unwrap_err(),
            LlmError::VocabMismatch {
                tokenizer: 256,
                model: 100
            }
        );
    }

    #[test]
    fn complete_produces_decodable_text() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let out = llm.complete("hello", 8, 42).unwrap();
        // generated text decodes (possibly lossy) — just assert it ran & is a String
        assert!(out.is_empty() || out.is_char_boundary(0));
        // 8 new tokens were generated
        assert_eq!(llm.generate_ids("hello", 8, 42).unwrap().len(), 8);
    }

    #[test]
    fn completion_is_reproducible_per_seed() {
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.generate_ids("the quick brown fox", 10, 7).unwrap(),
            b.generate_ids("the quick brown fox", 10, 7).unwrap()
        );
    }

    #[test]
    fn complete_with_prompt_prefixes_the_input() {
        let llm = runtime(Sampler::greedy());
        let full = llm.complete_with_prompt("abc", 4, 1).unwrap();
        assert!(full.starts_with("abc"), "{full:?}");
    }

    #[test]
    fn streaming_matches_batch_and_streams_each_token() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let batch = llm.generate_ids("hello sovereign", 8, 5).unwrap();
        let mut streamed = Vec::new();
        let returned = llm
            .generate_ids_streaming("hello sovereign", 8, 5, |id| streamed.push(id))
            .unwrap();
        assert_eq!(streamed, batch, "streamed ids must match batch");
        assert_eq!(returned, batch, "returned ids must match batch");
        assert_eq!(streamed.len(), 8);
    }

    #[test]
    fn streaming_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.generate_ids_streaming("", 4, 1, |_| {}).unwrap_err(),
            LlmError::EmptyPrompt
        );
    }

    #[test]
    fn mirostat_generation_runs_and_is_reproducible() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let mut ms_a = Mirostat::new(2.5, 0.1);
        let a = llm
            .generate_ids_mirostat("hello sovereign", 8, 3, &mut ms_a)
            .unwrap();
        assert_eq!(a.len(), 8);
        let v = llm.vocab_size() as u32;
        assert!(a.iter().all(|&t| t < v));
        // Same seed + fresh controller → identical ids.
        let mut ms_b = Mirostat::new(2.5, 0.1);
        let b = llm
            .generate_ids_mirostat("hello sovereign", 8, 3, &mut ms_b)
            .unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn mirostat_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        let mut ms = Mirostat::new(3.0, 0.1);
        assert_eq!(
            llm.generate_ids_mirostat("", 4, 1, &mut ms).unwrap_err(),
            LlmError::EmptyPrompt
        );
    }

    #[test]
    fn generate_until_stops_at_stop_token() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let first = llm.generate_ids("hello", 1, 4).unwrap()[0];
        let out = llm.generate_ids_until("hello", 16, 4, &[first]).unwrap();
        assert_eq!(out, vec![first]);
        // empty stop set → full length
        let full = llm.generate_ids_until("hello", 5, 4, &[]).unwrap();
        assert_eq!(full.len(), 5);
    }

    #[test]
    fn generate_until_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.generate_ids_until("", 4, 1, &[0]).unwrap_err(),
            LlmError::EmptyPrompt
        );
    }

    #[test]
    fn generate_with_composes_and_streams() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let opts = GenOptions::new(8).with_no_repeat_ngram(3);
        let mut streamed = Vec::new();
        let out = llm
            .generate_ids_with("hello sovereign", 3, &opts, |id| streamed.push(id))
            .unwrap();
        assert_eq!(streamed, out);
        assert!(out.len() <= 8);
        // reproducible
        let out2 = llm
            .generate_ids_with("hello sovereign", 3, &opts, |_| {})
            .unwrap();
        assert_eq!(out, out2);
    }

    #[test]
    fn complete_with_decodes_unified_generation() {
        let llm = runtime_with_eos(Sampler::new(SamplerConfig::default()));
        let eos = llm.tokenizer().special_id("<eos>").unwrap() as usize;
        let opts = GenOptions::new(8)
            .with_no_repeat_ngram(3)
            .with_stop_tokens([eos]);
        // text equals decoding the id sequence from generate_ids_with.
        let text = llm.complete_with("hello", 3, &opts).unwrap();
        let ids = llm.generate_ids_with("hello", 3, &opts, |_| {}).unwrap();
        assert_eq!(text, llm.tokenizer().decode(&ids).unwrap());
    }

    #[test]
    fn generate_ids_n_produces_n_samples() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let samples = llm.generate_ids_n("hello", 5, 6, 100).unwrap();
        assert_eq!(samples.len(), 5);
        // sample i uses base_seed + i → equals the single-call result.
        assert_eq!(samples[2], llm.generate_ids("hello", 6, 102).unwrap());
        // greedy sampler → all samples identical.
        let g = runtime(Sampler::greedy());
        let gs = g.generate_ids_n("hello", 4, 6, 0).unwrap();
        assert!(gs.windows(2).all(|w| w[0] == w[1]));
    }

    #[test]
    fn majority_sequence_picks_the_most_common() {
        let a = vec![1u32, 2, 3];
        let b = vec![9u32, 9];
        // a appears 3×, b once → a wins with count 3.
        let samples = vec![a.clone(), b.clone(), a.clone(), a.clone()];
        assert_eq!(majority_sequence(&samples), Some((a.clone(), 3)));
        // tie (each once) → earliest-seen wins.
        assert_eq!(majority_sequence(&[b.clone(), a.clone()]), Some((b, 1)));
        assert_eq!(majority_sequence(&[]), None);
    }

    #[test]
    fn complete_until_string_truncates_at_a_stop_sequence() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let full = llm.complete("hi there", 12, 7).unwrap();
        // No stops / non-matching stop → full completion.
        assert_eq!(
            llm.complete_until_string("hi there", 12, 7, &[]).unwrap(),
            full
        );
        assert_eq!(
            llm.complete_until_string("hi there", 12, 7, &["ZZ_UNLIKELY_ZZ"])
                .unwrap(),
            full
        );
        // Stopping at the first character truncates to empty.
        if let Some(c) = full.chars().next() {
            let stop = c.to_string();
            let out = llm
                .complete_until_string("hi there", 12, 7, &[&stop])
                .unwrap();
            assert!(
                out.is_empty(),
                "should truncate before the first char: {out:?}"
            );
        }
    }

    #[test]
    fn complete_with_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.complete_with("", 1, &GenOptions::new(4)).unwrap_err(),
            LlmError::EmptyPrompt
        );
    }

    #[test]
    fn generate_with_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.generate_ids_with("", 1, &GenOptions::new(4), |_| {})
                .unwrap_err(),
            LlmError::EmptyPrompt
        );
    }

    #[test]
    fn generated_ids_are_in_vocab() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let ids = llm.generate_ids("xyz", 12, 99).unwrap();
        let v = llm.vocab_size() as u32;
        assert!(ids.iter().all(|&t| t < v));
    }

    #[test]
    fn empty_prompt_is_an_error() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(llm.complete("", 4, 1).unwrap_err(), LlmError::EmptyPrompt);
    }

    #[test]
    fn generation_is_stateless_across_calls() {
        // Two calls on the SAME runtime with the same args must match (the
        // model is cloned per call, so call 1 never contaminates call 2).
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let a = llm.generate_ids("hello world", 10, 5).unwrap();
        let b = llm.generate_ids("hello world", 10, 5).unwrap();
        assert_eq!(a, b);
        // and a different prompt in between doesn't perturb it
        let _ = llm.generate_ids("other prompt entirely", 7, 9).unwrap();
        let c = llm.generate_ids("hello world", 10, 5).unwrap();
        assert_eq!(a, c);
    }

    #[test]
    fn constrained_completion_confines_to_allowed_tokens() {
        use sovereign_logit_mask::LogitMask;
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        // only bytes for 'A' (65) and 'B' (66) are allowed to be generated
        let mask = LogitMask::new().allow_only([65usize, 66]);
        let ids = llm.generate_ids_constrained("hello", 16, 3, &mask).unwrap();
        assert!(ids.iter().all(|&t| t == 65 || t == 66), "got {ids:?}");
        // and the decoded text is only As and Bs
        let text = llm.complete_constrained("hello", 16, 3, &mask).unwrap();
        assert!(text.chars().all(|c| c == 'A' || c == 'B'), "text {text:?}");
    }

    #[test]
    fn layers_and_vocab_report_correctly() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(llm.vocab_size(), 256);
        assert_eq!(llm.layers(), 2);
    }

    #[test]
    fn config_serde_round_trip() {
        let tok = Tokenizer::default();
        let cfg = LlmConfig {
            tokenizer: tok.clone(),
            model: model_config(tok.vocab_size(), 4, 1, Sampler::greedy()),
        };
        let j = serde_json::to_string(&cfg).unwrap();
        let back: LlmConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(cfg, back);
        // and it builds
        assert!(SovereignLlm::from_config(back).is_ok());
    }
}
