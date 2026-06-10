//! `sovereign-speculative` — lossless speculative decoding over real models.
//!
//! Autoregressive decoding is serial: one expensive target-model forward per
//! token. Speculative decoding amortizes that — a cheap **draft** model
//! proposes `draft_len` tokens, and the **target** model verifies them; every
//! proposed token that matches what the target would itself have produced is
//! accepted for free, and the first mismatch is corrected by the target. Each
//! round commits the accepted prefix plus one target token, so a good draft
//! yields several tokens per target pass.
//!
//! With **greedy** verification (used here) the scheme is *exactly lossless*:
//! every committed token is the target's own argmax at that position, so the
//! output is identical to decoding the target alone — regardless of how good
//! or bad the draft is. That identity is the headline test. The draft only
//! affects *speed* (the acceptance rate), never the result.
//!
//! Both models are `Clone` ([`sovereign-decoder-stack`]), which is what lets
//! the draft propose on a throwaway fork without committing.
//!
//! [`sovereign-decoder-stack`]: https://docs.rs/sovereign-decoder-stack
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_decoder_stack::{DecoderStack, StackError};
use sovereign_sampler::{Sampler, SamplerError};
use sovereign_spec_decode::{
    SpecError, optimal_draft_length, prompt_lookup_draft, verify_greedy, verify_sampled,
};
use thiserror::Error;

/// Schema version of the speculative-decoding surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong during speculative decoding.
#[derive(Debug, Error, PartialEq)]
pub enum SpeculativeError {
    /// The draft length was zero.
    #[error("draft_len must be >= 1")]
    ZeroDraftLen,
    /// The prompt was empty.
    #[error("prompt must contain at least one token")]
    EmptyPrompt,
    /// Draft and target disagreed on vocabulary size.
    #[error("vocab mismatch: draft {draft}, target {target}")]
    VocabMismatch {
        /// Draft vocab.
        draft: usize,
        /// Target vocab.
        target: usize,
    },
    /// A model forward error.
    #[error("model: {0}")]
    Model(#[from] StackError),
    /// A sampler error while shaping a distribution.
    #[error("sampler: {0}")]
    Sampler(#[from] SamplerError),
    /// A speculative-verification error.
    #[error("verify: {0}")]
    Verify(#[from] SpecError),
}

/// The outcome of a speculative decode.
#[derive(Debug, Clone, PartialEq)]
pub struct SpecResult {
    /// The generated tokens (identical to greedy target decoding).
    pub tokens: Vec<usize>,
    /// Total draft tokens proposed across all rounds.
    pub proposed: usize,
    /// Of those, how many were accepted (matched the target).
    pub accepted: usize,
    /// Number of verification rounds run.
    pub rounds: usize,
}

impl SpecResult {
    /// Fraction of proposed tokens that were accepted (`0.0` if none proposed).
    pub fn acceptance_rate(&self) -> f64 {
        if self.proposed == 0 {
            0.0
        } else {
            self.accepted as f64 / self.proposed as f64
        }
    }

    /// Realized speedup: committed tokens per verification round — i.e. tokens
    /// emitted per single target pass. This is the headline DFlash number, the
    /// *measured* analogue of `sovereign_spec_decode::expected_speedup`. `1.0`
    /// means no win (one token per pass); higher is better. `0.0` if no rounds
    /// ran. Note `tokens` is truncated to `max_new`, so a partial final round
    /// can make this a slight underestimate of the per-round acceptance.
    pub fn realized_speedup(&self) -> f64 {
        if self.rounds == 0 {
            0.0
        } else {
            self.tokens.len() as f64 / self.rounds as f64
        }
    }
}

/// A speculative decoder.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Speculative {
    /// Tokens the draft proposes per round.
    pub draft_len: usize,
    /// Maximum tokens to generate.
    pub max_new: usize,
}

impl Speculative {
    /// A speculative decoder with the given draft length and output budget.
    pub fn new(draft_len: usize, max_new: usize) -> Self {
        Self { draft_len, max_new }
    }

    /// Decode greedily-but-speculatively. The result equals greedy decoding of
    /// `target` alone; `draft` only affects the acceptance rate. Both base
    /// models are cloned and left untouched.
    pub fn decode(
        &self,
        draft: &DecoderStack,
        target: &DecoderStack,
        prompt: &[usize],
    ) -> Result<SpecResult, SpeculativeError> {
        if self.draft_len == 0 {
            return Err(SpeculativeError::ZeroDraftLen);
        }
        if prompt.is_empty() {
            return Err(SpeculativeError::EmptyPrompt);
        }
        if draft.vocab() != target.vocab() {
            return Err(SpeculativeError::VocabMismatch {
                draft: draft.vocab(),
                target: target.vocab(),
            });
        }

        let mut draft = draft.clone();
        let mut target = target.clone();
        let mut draft_logits = prime(&mut draft, prompt)?;
        let mut target_logits = prime(&mut target, prompt)?;

        let mut out = Vec::new();
        let mut proposed = 0usize;
        let mut accepted = 0usize;
        let mut rounds = 0usize;

        while out.len() < self.max_new {
            rounds += 1;

            // 1. draft proposes `draft_len` tokens on a throwaway fork.
            let mut ds = draft.clone();
            let mut dlog = draft_logits.clone();
            let mut proposals = Vec::with_capacity(self.draft_len);
            for _ in 0..self.draft_len {
                let t = argmax(&dlog);
                proposals.push(t);
                dlog = ds.forward(t)?;
            }
            proposed += proposals.len();

            // 2. target verifies; accept while it matches the target's argmax.
            let mut emitted = Vec::new();
            let mut tlog = target_logits;
            let mut all_accepted = true;
            for &q in &proposals {
                let a = argmax(&tlog);
                if a == q {
                    accepted += 1;
                    emitted.push(q);
                    tlog = target.forward(q)?;
                } else {
                    emitted.push(a); // corrected token (still the target's argmax)
                    tlog = target.forward(a)?;
                    all_accepted = false;
                    break;
                }
            }
            // 3. if every proposal matched, the target contributes one bonus token.
            if all_accepted {
                let bonus = argmax(&tlog);
                emitted.push(bonus);
                tlog = target.forward(bonus)?;
            }
            target_logits = tlog;

            // 4. advance the draft over exactly the committed tokens.
            for &e in &emitted {
                draft_logits = draft.forward(e)?;
            }
            out.extend_from_slice(&emitted);
        }

        out.truncate(self.max_new);
        Ok(SpecResult {
            tokens: out,
            proposed,
            accepted,
            rounds,
        })
    }

    /// Decode greedily-but-speculatively with an **adaptive draft length**: the
    /// number of proposed tokens per round is retuned from the running
    /// acceptance rate via `optimal_draft_length(α, cost_ratio, max_draft)`, so
    /// the draft grows when the draft tracks the target well and shrinks when it
    /// doesn't — maximizing throughput for the given draft `cost_ratio`. Starts
    /// from this decoder's `draft_len` (clamped to `1..=max_draft`). The output
    /// is identical to [`decode`](Self::decode) / greedy target decoding
    /// (lossless); only the speed adapts.
    pub fn decode_adaptive(
        &self,
        draft: &DecoderStack,
        target: &DecoderStack,
        prompt: &[usize],
        cost_ratio: f64,
        max_draft: usize,
    ) -> Result<SpecResult, SpeculativeError> {
        if prompt.is_empty() {
            return Err(SpeculativeError::EmptyPrompt);
        }
        if draft.vocab() != target.vocab() {
            return Err(SpeculativeError::VocabMismatch {
                draft: draft.vocab(),
                target: target.vocab(),
            });
        }
        let max_draft = max_draft.max(1);
        let mut k = self.draft_len.clamp(1, max_draft);

        let mut draft = draft.clone();
        let mut target = target.clone();
        let mut draft_logits = prime(&mut draft, prompt)?;
        let mut target_logits = prime(&mut target, prompt)?;

        let mut out = Vec::new();
        let mut proposed = 0usize;
        let mut accepted = 0usize;
        let mut rounds = 0usize;

        while out.len() < self.max_new {
            rounds += 1;

            // 1. draft proposes `k` tokens on a throwaway fork.
            let mut ds = draft.clone();
            let mut dlog = draft_logits.clone();
            let mut proposals = Vec::with_capacity(k);
            for _ in 0..k {
                let t = argmax(&dlog);
                proposals.push(t);
                dlog = ds.forward(t)?;
            }
            proposed += proposals.len();

            // 2. target verifies greedily; accept the matching prefix.
            let mut emitted = Vec::new();
            let mut tlog = target_logits;
            let mut all_accepted = true;
            for &q in &proposals {
                let a = argmax(&tlog);
                if a == q {
                    accepted += 1;
                    emitted.push(q);
                    tlog = target.forward(q)?;
                } else {
                    emitted.push(a);
                    tlog = target.forward(a)?;
                    all_accepted = false;
                    break;
                }
            }
            if all_accepted {
                let bonus = argmax(&tlog);
                emitted.push(bonus);
                tlog = target.forward(bonus)?;
            }
            target_logits = tlog;
            for &e in &emitted {
                draft_logits = draft.forward(e)?;
            }
            out.extend_from_slice(&emitted);

            // 3. retune the draft length from the running acceptance rate.
            if proposed > 0 {
                let alpha = accepted as f64 / proposed as f64;
                k = optimal_draft_length(alpha, cost_ratio, max_draft);
            }
        }

        out.truncate(self.max_new);
        Ok(SpecResult {
            tokens: out,
            proposed,
            accepted,
            rounds,
        })
    }

    /// Decode **sampled-but-speculatively**, distribution-preserving. Each
    /// round the draft *samples* `draft_len` tokens from its `sampler`-shaped
    /// distribution; the target teacher-forces those proposals on a fork to get
    /// its own distribution at every position; then the DFlash modified
    /// rejection rule ([`verify_sampled`]) decides the accepted prefix and the
    /// correction/bonus. The committed sequence has the **same distribution**
    /// as sampling the target alone with the same `sampler` and `seed` — the
    /// sampling analogue of [`decode`]'s greedy losslessness. With a greedy
    /// (`temperature <= 0`) sampler this reduces exactly to [`decode`].
    pub fn decode_sampled(
        &self,
        draft: &DecoderStack,
        target: &DecoderStack,
        prompt: &[usize],
        sampler: &Sampler,
        seed: u64,
    ) -> Result<SpecResult, SpeculativeError> {
        if self.draft_len == 0 {
            return Err(SpeculativeError::ZeroDraftLen);
        }
        if prompt.is_empty() {
            return Err(SpeculativeError::EmptyPrompt);
        }
        if draft.vocab() != target.vocab() {
            return Err(SpeculativeError::VocabMismatch {
                draft: draft.vocab(),
                target: target.vocab(),
            });
        }

        let mut draft = draft.clone();
        let mut target = target.clone();
        let mut draft_logits = prime(&mut draft, prompt)?;
        let mut target_logits = prime(&mut target, prompt)?;
        let mut rng = SplitMix::new(seed);

        let mut out = Vec::new();
        let mut proposed = 0usize;
        let mut accepted = 0usize;
        let mut rounds = 0usize;

        while out.len() < self.max_new {
            rounds += 1;

            // 1. draft samples `draft_len` tokens on a throwaway fork, recording
            //    the distribution it sampled each one from.
            let mut ds = draft.clone();
            let mut dlog = draft_logits.clone();
            let mut proposals = Vec::with_capacity(self.draft_len);
            let mut p_draft = Vec::with_capacity(self.draft_len);
            for _ in 0..self.draft_len {
                let dist = sampler.distribution(&dlog, &[])?;
                let t = sample_index(&dist, rng.next_uniform());
                p_draft.push(to_f64(&dist));
                proposals.push(t as u32);
                dlog = ds.forward(t)?;
            }
            proposed += proposals.len();

            // 2. target teacher-forces the proposals on a fork → one
            //    distribution per position including the bonus (draft_len + 1).
            let mut tf = target.clone();
            let mut tlog = target_logits.clone();
            let mut p_target = Vec::with_capacity(self.draft_len + 1);
            p_target.push(to_f64(&sampler.distribution(&tlog, &[])?));
            for &t in &proposals {
                tlog = tf.forward(t as usize)?;
                p_target.push(to_f64(&sampler.distribution(&tlog, &[])?));
            }

            // 3. distribution-preserving accept/correct.
            let outcome =
                verify_sampled(&proposals, &p_draft, &p_target, &mut || rng.next_uniform())?;
            accepted += outcome.accepted;

            // 4. commit the emitted tokens on the REAL draft + target.
            for &e in &outcome.emitted_tokens {
                target_logits = target.forward(e as usize)?;
                draft_logits = draft.forward(e as usize)?;
            }
            out.extend(outcome.emitted_tokens.iter().map(|&e| e as usize));
        }

        out.truncate(self.max_new);
        Ok(SpecResult {
            tokens: out,
            proposed,
            accepted,
            rounds,
        })
    }

    /// Decode **draft-free** speculatively via prompt-lookup (PLD): instead of a
    /// draft model, each round proposes the continuation of the most-recent
    /// earlier occurrence of the current `ngram` suffix (capped at `max_draft`),
    /// then the target verifies it greedily — committing the accepted prefix +
    /// one corrected token. When no lookup match exists, it emits a single
    /// target-greedy token. Like [`decode`](Self::decode) the output is exactly
    /// the target's greedy decoding (lossless); only the *speed* depends on how
    /// often the context repeats. Needs no second model.
    pub fn decode_prompt_lookup(
        &self,
        target: &DecoderStack,
        prompt: &[usize],
        ngram: usize,
        max_draft: usize,
    ) -> Result<SpecResult, SpeculativeError> {
        if prompt.is_empty() {
            return Err(SpeculativeError::EmptyPrompt);
        }
        let mut target = target.clone();
        let mut target_logits = prime(&mut target, prompt)?;
        let mut context: Vec<u32> = prompt.iter().map(|&t| t as u32).collect();

        let mut out = Vec::new();
        let mut proposed = 0usize;
        let mut accepted = 0usize;
        let mut rounds = 0usize;

        while out.len() < self.max_new {
            rounds += 1;
            let draft = prompt_lookup_draft(&context, ngram, max_draft);

            if draft.is_empty() {
                // No lookup match → emit one greedy target token.
                let t = argmax(&target_logits);
                out.push(t);
                context.push(t as u32);
                target_logits = target.forward(t)?;
                continue;
            }
            proposed += draft.len();

            // Teacher-force the target over the draft to get its greedy token at
            // each position (including the bonus), on a fork.
            let mut tf = target.clone();
            let mut tlog = target_logits.clone();
            let mut target_greedy = Vec::with_capacity(draft.len() + 1);
            target_greedy.push(argmax(&tlog) as u32);
            for &d in &draft {
                tlog = tf.forward(d as usize)?;
                target_greedy.push(argmax(&tlog) as u32);
            }

            // Greedy accept rule → accepted prefix + one corrected token.
            let outcome = verify_greedy(&draft, &target_greedy)?;
            accepted += outcome.accepted;
            let emitted: Vec<usize> = draft[..outcome.accepted]
                .iter()
                .map(|&t| t as usize)
                .chain(std::iter::once(outcome.corrected_token as usize))
                .collect();
            for &e in &emitted {
                target_logits = target.forward(e)?;
                context.push(e as u32);
                out.push(e);
            }
        }

        out.truncate(self.max_new);
        Ok(SpecResult {
            tokens: out,
            proposed,
            accepted,
            rounds,
        })
    }
}

/// A small deterministic splitmix64 → uniform `[0, 1)` source, so sampled
/// decoding is reproducible from a seed without a heavyweight RNG dependency.
struct SplitMix(u64);

impl SplitMix {
    fn new(seed: u64) -> Self {
        Self(seed)
    }

    fn next_uniform(&mut self) -> f64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^= z >> 31;
        (z >> 11) as f64 / (1u64 << 53) as f64
    }
}

/// Sample a categorical index from a (possibly filtered) probability vector
/// using one uniform draw. Robust to floating-point slack: returns the last
/// positive index if the cumulative walk overshoots.
fn sample_index(dist: &[f32], u: f64) -> usize {
    let total: f64 = dist.iter().map(|&p| p.max(0.0) as f64).sum();
    if total <= 0.0 {
        return 0;
    }
    let mut threshold = u * total;
    for (i, &p) in dist.iter().enumerate() {
        threshold -= p.max(0.0) as f64;
        if threshold < 0.0 {
            return i;
        }
    }
    dist.iter().rposition(|&p| p > 0.0).unwrap_or(0)
}

/// Widen an `f32` probability vector to the `f64` distributions `verify_sampled`
/// consumes.
fn to_f64(dist: &[f32]) -> Vec<f64> {
    dist.iter().map(|&p| p as f64).collect()
}

/// Feed a prompt into `model`, returning the logits for the next token.
fn prime(model: &mut DecoderStack, prompt: &[usize]) -> Result<Vec<f32>, SpeculativeError> {
    let mut logits = Vec::new();
    for &t in prompt {
        logits = model.forward(t)?;
    }
    Ok(logits)
}

/// Index of the largest logit (ties → lower index).
fn argmax(logits: &[f32]) -> usize {
    let mut best = 0;
    for i in 1..logits.len() {
        if logits[i] > logits[best] {
            best = i;
        }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_decoder_stack::StackConfig;
    use sovereign_ffn::SwiGlu;
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_sampler::{Sampler, SamplerConfig};
    use sovereign_transformer_block::BlockWeights;

    const MD: usize = 4;

    fn mat(s: f32, n: usize) -> Vec<f32> {
        (0..n).map(|i| ((i as f32 + s) * 0.023).sin()).collect()
    }

    fn model(vocab: usize, seed: f32) -> DecoderStack {
        let block = BlockWeights {
            model_dim: MD,
            head_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: mat(seed + 1.0, MD * MD),
            w_k: mat(seed + 2.0, MD * MD),
            w_v: mat(seed + 3.0, MD * MD),
            w_o: mat(seed + 4.0, MD * MD),
            ffn: SwiGlu::new(
                MD,
                MD,
                mat(seed + 5.0, MD * MD),
                mat(seed + 6.0, MD * MD),
                mat(seed + 7.0, MD * MD),
            )
            .unwrap(),
        };
        let cfg = StackConfig {
            vocab,
            model_dim: MD,
            embedding: mat(seed + 0.5, vocab * MD),
            blocks: vec![block],
            final_norm: RmsNorm::new(MD),
            head: mat(seed + 0.9, vocab * MD),
            sampler: Sampler::greedy(),
            recent_window: 64,
        };
        DecoderStack::new(cfg).unwrap()
    }

    /// Pure greedy decode of the target, for the lossless comparison.
    fn greedy(mut m: DecoderStack, prompt: &[usize], steps: usize) -> Vec<usize> {
        let mut logits = Vec::new();
        for &t in prompt {
            logits = m.forward(t).unwrap();
        }
        let mut out = Vec::new();
        for _ in 0..steps {
            let t = argmax(&logits);
            out.push(t);
            logits = m.forward(t).unwrap();
        }
        out
    }

    #[test]
    fn output_is_lossless_vs_greedy_target_with_a_different_draft() {
        let target = model(8, 0.0);
        let draft = model(8, 50.0); // a *different* (worse) draft
        let spec = Speculative::new(4, 10)
            .decode(&draft, &target, &[1, 2])
            .unwrap();
        let g = greedy(target.clone(), &[1, 2], 10);
        assert_eq!(spec.tokens, g, "speculative must equal greedy target");
    }

    #[test]
    fn lossless_even_for_several_draft_lengths() {
        let target = model(10, 0.0);
        let draft = model(10, 13.0);
        let g = greedy(target.clone(), &[3, 1, 4], 12);
        for k in [1usize, 2, 3, 5, 8] {
            let spec = Speculative::new(k, 12)
                .decode(&draft, &target, &[3, 1, 4])
                .unwrap();
            assert_eq!(spec.tokens, g, "draft_len {k}");
        }
    }

    #[test]
    fn prompt_lookup_decode_is_lossless_vs_greedy() {
        // Draft-free PLD speculative decoding must equal greedy target decoding,
        // regardless of how often (or whether) the context repeats.
        let target = model(10, 0.0);
        let g = greedy(target.clone(), &[3, 1, 4, 1, 5], 12);
        for (ngram, max_draft) in [(1usize, 3usize), (2, 4), (3, 2)] {
            let spec = Speculative::new(4, 12)
                .decode_prompt_lookup(&target, &[3, 1, 4, 1, 5], ngram, max_draft)
                .unwrap();
            assert_eq!(spec.tokens, g, "ngram {ngram}, max_draft {max_draft}");
            assert!(spec.accepted <= spec.proposed);
        }
    }

    #[test]
    fn prompt_lookup_decode_empty_prompt_errors() {
        let target = model(8, 0.0);
        assert_eq!(
            Speculative::new(3, 6)
                .decode_prompt_lookup(&target, &[], 2, 3)
                .unwrap_err(),
            SpeculativeError::EmptyPrompt
        );
    }

    #[test]
    fn adaptive_decode_is_lossless_vs_greedy() {
        // The adaptive draft length must not change the output — still exactly
        // greedy target decoding — for any cost_ratio / max_draft.
        let target = model(10, 0.0);
        let draft = model(10, 21.0);
        let g = greedy(target.clone(), &[3, 1, 4], 12);
        for (cost, maxk) in [(0.1, 8usize), (0.5, 4), (0.9, 6)] {
            let spec = Speculative::new(4, 12)
                .decode_adaptive(&draft, &target, &[3, 1, 4], cost, maxk)
                .unwrap();
            assert_eq!(spec.tokens, g, "cost {cost}, max_draft {maxk}");
            assert!(spec.accepted <= spec.proposed);
        }
    }

    #[test]
    fn adaptive_decode_validates_inputs() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        assert_eq!(
            Speculative::new(3, 6)
                .decode_adaptive(&draft, &target, &[], 0.2, 4)
                .unwrap_err(),
            SpeculativeError::EmptyPrompt
        );
        let small = model(5, 0.0);
        assert_eq!(
            Speculative::new(3, 6)
                .decode_adaptive(&small, &target, &[1], 0.2, 4)
                .unwrap_err(),
            SpeculativeError::VocabMismatch {
                draft: 5,
                target: 8
            }
        );
    }

    #[test]
    fn identical_draft_accepts_everything() {
        // draft == target → every proposal matches → 100% acceptance.
        let target = model(8, 0.0);
        let draft = model(8, 0.0);
        let spec = Speculative::new(4, 12)
            .decode(&draft, &target, &[1, 2])
            .unwrap();
        assert_eq!(spec.accepted, spec.proposed);
        assert!((spec.acceptance_rate() - 1.0).abs() < 1e-9);
    }

    #[test]
    fn returns_exactly_max_new_tokens() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        let spec = Speculative::new(3, 9)
            .decode(&draft, &target, &[1])
            .unwrap();
        assert_eq!(spec.tokens.len(), 9);
        assert!(spec.rounds >= 1);
        assert!(spec.accepted <= spec.proposed);
    }

    #[test]
    fn base_models_are_untouched() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        let _ = Speculative::new(3, 6)
            .decode(&draft, &target, &[1])
            .unwrap();
        assert_eq!(target.position(), 0);
        assert_eq!(draft.position(), 0);
    }

    #[test]
    fn vocab_mismatch_zero_draft_empty_prompt_are_errors() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        assert_eq!(
            Speculative::new(0, 4)
                .decode(&draft, &target, &[1])
                .unwrap_err(),
            SpeculativeError::ZeroDraftLen
        );
        assert_eq!(
            Speculative::new(2, 4)
                .decode(&draft, &target, &[])
                .unwrap_err(),
            SpeculativeError::EmptyPrompt
        );
        let small = model(5, 0.0);
        assert_eq!(
            Speculative::new(2, 4)
                .decode(&small, &target, &[1])
                .unwrap_err(),
            SpeculativeError::VocabMismatch {
                draft: 5,
                target: 8
            }
        );
    }

    // --- sampled (distribution-preserving) decode ---

    #[test]
    fn sampled_with_greedy_sampler_equals_greedy_decode() {
        // The headline property: a greedy (temperature 0) sampler collapses
        // each distribution to one-hot, so decode_sampled reduces *exactly* to
        // the greedy decode() — same lossless output as the target alone.
        let target = model(8, 0.0);
        let draft = model(8, 50.0); // deliberately different draft
        let greedy_sampler = Sampler::greedy();
        for k in [1usize, 2, 4] {
            let sampled = Speculative::new(k, 10)
                .decode_sampled(&draft, &target, &[1, 2], &greedy_sampler, 0xABCDEF)
                .unwrap();
            let g = greedy(target.clone(), &[1, 2], 10);
            assert_eq!(sampled.tokens, g, "draft_len {k} must match greedy target");
        }
    }

    #[test]
    fn sampled_is_deterministic_for_a_fixed_seed() {
        let target = model(8, 0.0);
        let draft = model(8, 9.0);
        let sampler = Sampler::new(SamplerConfig {
            temperature: 1.0,
            ..SamplerConfig::default()
        });
        let a = Speculative::new(3, 12)
            .decode_sampled(&draft, &target, &[1, 2], &sampler, 42)
            .unwrap();
        let b = Speculative::new(3, 12)
            .decode_sampled(&draft, &target, &[1, 2], &sampler, 42)
            .unwrap();
        assert_eq!(a.tokens, b.tokens);
        // A different seed generally yields a different trajectory.
        let c = Speculative::new(3, 12)
            .decode_sampled(&draft, &target, &[1, 2], &sampler, 43)
            .unwrap();
        // (not asserting inequality — small vocab can collide — just that it runs)
        assert_eq!(c.tokens.len(), 12);
    }

    #[test]
    fn sampled_returns_exactly_max_new_and_leaves_models_untouched() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        let sampler = Sampler::new(SamplerConfig {
            temperature: 0.9,
            ..SamplerConfig::default()
        });
        let spec = Speculative::new(3, 9)
            .decode_sampled(&draft, &target, &[1], &sampler, 7)
            .unwrap();
        assert_eq!(spec.tokens.len(), 9);
        assert!(spec.accepted <= spec.proposed);
        assert_eq!(target.position(), 0);
        assert_eq!(draft.position(), 0);
    }

    #[test]
    fn realized_speedup_is_tokens_per_round() {
        // Self-draft → every proposal accepted → each round commits draft_len+1
        // tokens, so the realized speedup approaches draft_len+1.
        let target = model(8, 0.0);
        let spec = Speculative::new(4, 100)
            .decode(&target, &target, &[1, 2])
            .unwrap();
        assert!(
            (spec.realized_speedup() - spec.tokens.len() as f64 / spec.rounds as f64).abs() < 1e-9
        );
        // With 100% acceptance and draft_len 4, each round emits ~5 tokens.
        assert!(
            spec.realized_speedup() > 4.0,
            "speedup {} should exceed 4 at full acceptance",
            spec.realized_speedup()
        );
    }

    #[test]
    fn sampled_validates_inputs_like_greedy() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        let sampler = Sampler::greedy();
        assert_eq!(
            Speculative::new(0, 4)
                .decode_sampled(&draft, &target, &[1], &sampler, 0)
                .unwrap_err(),
            SpeculativeError::ZeroDraftLen
        );
        assert_eq!(
            Speculative::new(2, 4)
                .decode_sampled(&draft, &target, &[], &sampler, 0)
                .unwrap_err(),
            SpeculativeError::EmptyPrompt
        );
    }
}
