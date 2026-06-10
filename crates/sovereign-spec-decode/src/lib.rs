//! `sovereign-spec-decode` — speculative decoding verification (DFlash family).
//!
//! The AVX++ dump flags **DFlash** ("3× faster code") as a speculative-
//! decoding technique: a cheap *draft* proposes several tokens, the
//! *target* verifies them in a single pass, and the longest correct prefix
//! is accepted in one shot — emitting many tokens per expensive target
//! call instead of one.
//!
//! This crate implements the core **greedy** accept rule (the deterministic
//! variant): accept the longest prefix of the draft that matches the
//! target's greedy tokens, then emit one corrected/bonus token. So a round
//! always emits `accepted + 1` tokens for a single target verification pass
//! — that ratio is the speedup.
//!
//! The per-token model math is the model's job; this is the exact
//! acceptance arithmetic, verifiable on its own.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the speculative-decode surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Outcome of one speculative round.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct SpecOutcome {
    /// Number of draft tokens accepted (the matching prefix length).
    pub accepted: usize,
    /// Tokens emitted this round (`accepted + 1`: the accepted prefix plus
    /// the corrected/bonus token).
    pub emitted: usize,
    /// The corrected/bonus token emitted after the accepted prefix.
    pub corrected_token: u32,
    /// How many tokens the draft proposed.
    pub draft_len: usize,
}

impl SpecOutcome {
    /// Tokens emitted per single target verification pass — the speedup of
    /// this round (`1.0` means no win; higher is better).
    pub fn speedup(&self) -> f64 {
        self.emitted as f64
    }

    /// Acceptance rate in `[0, 1]`: fraction of the draft that was accepted.
    /// An empty draft has rate `0.0`.
    pub fn acceptance_rate(&self) -> f64 {
        if self.draft_len == 0 {
            0.0
        } else {
            self.accepted as f64 / self.draft_len as f64
        }
    }
}

/// Errors from speculative verification.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum SpecError {
    /// The target greedy sequence must provide one token per draft position
    /// plus the bonus position: `target.len() >= draft.len() + 1`.
    #[error("target greedy length {target} must be >= draft length {draft} + 1")]
    TargetTooShort {
        /// Draft length.
        draft: usize,
        /// Target greedy length supplied.
        target: usize,
    },
    /// One distribution list had the wrong length for the draft.
    #[error("distribution count {got} must equal {want}")]
    DistCount {
        /// Distributions supplied.
        got: usize,
        /// Distributions required.
        want: usize,
    },
    /// Two distributions that must share a vocabulary had different lengths.
    #[error("vocab mismatch: {a} vs {b}")]
    VocabMismatch {
        /// First vocabulary size.
        a: usize,
        /// Second vocabulary size.
        b: usize,
    },
    /// A draft token id fell outside the distribution's vocabulary.
    #[error("draft token {token} out of vocab {vocab}")]
    TokenOutOfVocab {
        /// The offending token id.
        token: u32,
        /// Vocabulary size.
        vocab: usize,
    },
}

/// Outcome of one **sampled** speculative round (the distribution-preserving
/// variant): the accepted draft prefix plus exactly one correction/bonus
/// token, all sampled so the emitted sequence has the same distribution as if
/// every token were drawn from the target model directly.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SampledOutcome {
    /// Number of draft tokens accepted (the matching prefix length).
    pub accepted: usize,
    /// The tokens emitted this round: the `accepted` accepted draft tokens
    /// followed by one correction (on rejection) or bonus (on full accept).
    pub emitted_tokens: Vec<u32>,
    /// How many tokens the draft proposed.
    pub draft_len: usize,
}

impl SampledOutcome {
    /// Tokens emitted per single target verification pass — the speedup.
    pub fn speedup(&self) -> f64 {
        self.emitted_tokens.len() as f64
    }

    /// Acceptance rate in `[0, 1]`.
    pub fn acceptance_rate(&self) -> f64 {
        if self.draft_len == 0 {
            0.0
        } else {
            self.accepted as f64 / self.draft_len as f64
        }
    }
}

/// Sample a categorical index from `dist` (assumed non-negative, summing to
/// `> 0`) using one uniform draw `u ∈ [0, 1)`. Falls back to the last index
/// for floating-point edge cases.
fn sample_categorical(dist: &[f64], u: f64) -> u32 {
    let total: f64 = dist.iter().map(|p| p.max(0.0)).sum();
    if total <= 0.0 {
        return 0;
    }
    let mut threshold = u * total;
    for (i, &p) in dist.iter().enumerate() {
        threshold -= p.max(0.0);
        if threshold < 0.0 {
            return i as u32;
        }
    }
    (dist.len() - 1) as u32
}

/// Sampled speculative verification — the **modified rejection sampling** rule
/// (Leviathan et al. / Chen et al.) that DFlash relies on for sampling-based
/// decoding. For each draft position the draft token is accepted with
/// probability `min(1, p_target / p_draft)`; on the first rejection a
/// correction is drawn from the normalized residual `(p_target − p_draft)₊`,
/// and the round ends. If the whole draft is accepted, a bonus token is drawn
/// from the target distribution at the bonus position.
///
/// The point that distinguishes it from [`verify_greedy`]: the emitted
/// sequence is distributed **exactly** as target-model samples — no accuracy
/// is traded for the speedup. `p_draft` has one distribution per draft token;
/// `p_target` has one per draft token **plus** the bonus position (so
/// `p_target.len() == draft.len() + 1`). All distributions share a vocabulary.
/// `next_uniform` yields independent draws in `[0, 1)`.
pub fn verify_sampled(
    draft: &[u32],
    p_draft: &[Vec<f64>],
    p_target: &[Vec<f64>],
    next_uniform: &mut dyn FnMut() -> f64,
) -> Result<SampledOutcome, SpecError> {
    if p_draft.len() != draft.len() {
        return Err(SpecError::DistCount {
            got: p_draft.len(),
            want: draft.len(),
        });
    }
    if p_target.len() != draft.len() + 1 {
        return Err(SpecError::DistCount {
            got: p_target.len(),
            want: draft.len() + 1,
        });
    }

    let mut emitted = Vec::with_capacity(draft.len() + 1);
    for (i, &tok) in draft.iter().enumerate() {
        let (pd, pt) = (&p_draft[i], &p_target[i]);
        if pd.len() != pt.len() {
            return Err(SpecError::VocabMismatch {
                a: pd.len(),
                b: pt.len(),
            });
        }
        let t = tok as usize;
        if t >= pt.len() {
            return Err(SpecError::TokenOutOfVocab {
                token: tok,
                vocab: pt.len(),
            });
        }
        let (ptt, pdt) = (pt[t].max(0.0), pd[t].max(0.0));
        // Accept with prob min(1, p_target/p_draft); pd==0 → the draft could
        // not have proposed this honestly, accept (ratio saturates to 1).
        let ratio = if pdt > 0.0 { (ptt / pdt).min(1.0) } else { 1.0 };
        if next_uniform() < ratio {
            emitted.push(tok);
        } else {
            // Correction from the normalized positive residual.
            let residual: Vec<f64> = pt.iter().zip(pd).map(|(a, b)| (a - b).max(0.0)).collect();
            let corr = sample_categorical(&residual, next_uniform());
            emitted.push(corr);
            return Ok(SampledOutcome {
                accepted: i,
                emitted_tokens: emitted,
                draft_len: draft.len(),
            });
        }
    }
    // Whole draft accepted → bonus from the target at the bonus position.
    let bonus = sample_categorical(&p_target[draft.len()], next_uniform());
    emitted.push(bonus);
    Ok(SampledOutcome {
        accepted: draft.len(),
        emitted_tokens: emitted,
        draft_len: draft.len(),
    })
}

/// Greedy speculative verification (the DFlash accept rule).
///
/// `draft` is the cheap model's proposed tokens; `target_greedy` is the
/// target model's greedy token at each position **including one bonus
/// position** (so it must be at least `draft.len() + 1` long). Accept the
/// longest prefix where `draft[i] == target_greedy[i]`; at the first
/// mismatch (or after a fully-accepted draft) emit `target_greedy[accepted]`
/// as the correction/bonus.
pub fn verify_greedy(draft: &[u32], target_greedy: &[u32]) -> Result<SpecOutcome, SpecError> {
    if target_greedy.len() < draft.len() + 1 {
        return Err(SpecError::TargetTooShort {
            draft: draft.len(),
            target: target_greedy.len(),
        });
    }
    let mut accepted = 0;
    while accepted < draft.len() && draft[accepted] == target_greedy[accepted] {
        accepted += 1;
    }
    Ok(SpecOutcome {
        accepted,
        emitted: accepted + 1,
        corrected_token: target_greedy[accepted],
        draft_len: draft.len(),
    })
}

/// Run several speculative rounds and report the aggregate speedup: total
/// tokens emitted divided by the number of rounds (target passes). Each
/// tuple is `(draft, target_greedy)` for that round.
pub fn aggregate_speedup(rounds: &[(Vec<u32>, Vec<u32>)]) -> Result<f64, SpecError> {
    if rounds.is_empty() {
        return Ok(0.0);
    }
    let mut emitted = 0usize;
    for (draft, target) in rounds {
        emitted += verify_greedy(draft, target)?.emitted;
    }
    Ok(emitted as f64 / rounds.len() as f64)
}

/// Expected tokens emitted per target pass for a draft of length `k` whose
/// per-token acceptance probability is `alpha` (the closed-form speedup of
/// greedy speculative decoding, Leviathan et al.):
///
/// ```text
/// E[tokens] = (1 - alpha^(k+1)) / (1 - alpha)     for alpha < 1
///           = k + 1                                for alpha = 1
/// ```
///
/// `alpha` is clamped to `[0, 1]`. Use this to reason about the win for a
/// given draft length before running anything.
pub fn expected_speedup(alpha: f64, k: usize) -> f64 {
    let a = alpha.clamp(0.0, 1.0);
    if a >= 1.0 {
        return (k + 1) as f64;
    }
    (1.0 - a.powi(k as i32 + 1)) / (1.0 - a)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn expected_speedup_at_alpha_one_is_k_plus_one() {
        assert_eq!(expected_speedup(1.0, 3), 4.0);
        assert_eq!(expected_speedup(1.0, 0), 1.0);
    }

    #[test]
    fn expected_speedup_at_alpha_zero_is_one() {
        assert_eq!(expected_speedup(0.0, 5), 1.0);
    }

    #[test]
    fn expected_speedup_closed_form() {
        // alpha=0.5, k=3 → (1 - 0.5^4)/(1 - 0.5) = 0.9375/0.5 = 1.875
        assert!((expected_speedup(0.5, 3) - 1.875).abs() < 1e-9);
    }

    #[test]
    fn expected_speedup_is_monotonic_in_alpha() {
        let lo = expected_speedup(0.3, 4);
        let hi = expected_speedup(0.8, 4);
        assert!(hi > lo);
    }

    #[test]
    fn expected_speedup_clamps_out_of_range_alpha() {
        assert_eq!(expected_speedup(1.5, 2), 3.0); // clamped to 1.0
        assert_eq!(expected_speedup(-0.5, 7), 1.0); // clamped to 0.0
    }

    #[test]
    fn full_accept_emits_all_plus_bonus() {
        // draft fully matches; bonus token is target[3].
        let o = verify_greedy(&[1, 2, 3], &[1, 2, 3, 4]).unwrap();
        assert_eq!(o.accepted, 3);
        assert_eq!(o.emitted, 4); // 3 accepted + 1 bonus
        assert_eq!(o.corrected_token, 4);
        assert_eq!(o.speedup(), 4.0);
        assert_eq!(o.acceptance_rate(), 1.0);
    }

    #[test]
    fn partial_accept_corrects_at_first_mismatch() {
        // draft[2]=9 mismatches target[2]=3 → accept 2, emit target[2]=3.
        let o = verify_greedy(&[1, 2, 9], &[1, 2, 3, 4]).unwrap();
        assert_eq!(o.accepted, 2);
        assert_eq!(o.emitted, 3);
        assert_eq!(o.corrected_token, 3);
        assert!((o.acceptance_rate() - 2.0 / 3.0).abs() < 1e-9);
    }

    #[test]
    fn immediate_mismatch_still_emits_one() {
        let o = verify_greedy(&[9, 9, 9], &[1, 2, 3, 4]).unwrap();
        assert_eq!(o.accepted, 0);
        assert_eq!(o.emitted, 1); // no speedup, but still correct progress
        assert_eq!(o.corrected_token, 1);
        assert_eq!(o.speedup(), 1.0);
        assert_eq!(o.acceptance_rate(), 0.0);
    }

    #[test]
    fn empty_draft_emits_the_target_token() {
        let o = verify_greedy(&[], &[5]).unwrap();
        assert_eq!(o.accepted, 0);
        assert_eq!(o.emitted, 1);
        assert_eq!(o.corrected_token, 5);
        assert_eq!(o.acceptance_rate(), 0.0);
    }

    #[test]
    fn target_too_short_is_rejected() {
        // need at least draft.len()+1 = 4 target tokens
        let err = verify_greedy(&[1, 2, 3], &[1, 2, 3]).unwrap_err();
        assert_eq!(
            err,
            SpecError::TargetTooShort {
                draft: 3,
                target: 3
            }
        );
    }

    #[test]
    fn aggregate_speedup_averages_emitted_per_round() {
        let rounds = vec![
            (vec![1, 2, 3], vec![1, 2, 3, 4]), // emit 4
            (vec![1, 9], vec![1, 7, 0]),       // accept 1, emit 2
        ];
        // (4 + 2) / 2 = 3.0 tokens per target pass
        assert!((aggregate_speedup(&rounds).unwrap() - 3.0).abs() < 1e-9);
    }

    #[test]
    fn aggregate_empty_is_zero() {
        assert_eq!(aggregate_speedup(&[]).unwrap(), 0.0);
    }

    #[test]
    fn outcome_serde_round_trip() {
        let o = verify_greedy(&[1, 2], &[1, 2, 9]).unwrap();
        let j = serde_json::to_string(&o).unwrap();
        let back: SpecOutcome = serde_json::from_str(&j).unwrap();
        assert_eq!(o, back);
    }

    // --- sampled (distribution-preserving) verification ---

    /// Deterministic splitmix64 → uniform `[0, 1)` stream, for reproducible
    /// statistical tests without a `rand` dependency.
    struct Uniforms(u64);
    impl Uniforms {
        fn next(&mut self) -> f64 {
            self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = self.0;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z ^= z >> 31;
            // 53-bit mantissa → [0,1)
            (z >> 11) as f64 / (1u64 << 53) as f64
        }
    }

    #[test]
    fn sampled_full_accept_emits_draft_plus_bonus() {
        // p_target == p_draft and u always < 1 ratio → every draft accepted.
        let draft = [0u32, 1];
        let pd = vec![vec![0.5, 0.5], vec![0.5, 0.5]];
        let pt = vec![vec![0.5, 0.5], vec![0.5, 0.5], vec![1.0, 0.0]];
        let mut u = Uniforms(1);
        let o = verify_sampled(&draft, &pd, &pt, &mut || u.next()).unwrap();
        assert_eq!(o.accepted, 2);
        assert_eq!(o.emitted_tokens.len(), 3); // 2 accepted + bonus
        assert_eq!(o.emitted_tokens[0..2], [0, 1]);
        assert_eq!(o.emitted_tokens[2], 0); // bonus dist is [1,0] → token 0
    }

    #[test]
    fn sampled_rejection_emits_residual_correction() {
        // Draft proposes token 0, but target never emits it (p_target[0]=0) and
        // the draft is certain of it → guaranteed rejection. Residual = target.
        let draft = [0u32];
        let pd = vec![vec![1.0, 0.0, 0.0]];
        let pt = vec![vec![0.0, 0.4, 0.6], vec![1.0, 0.0, 0.0]];
        let mut u = Uniforms(7);
        let o = verify_sampled(&draft, &pd, &pt, &mut || u.next()).unwrap();
        assert_eq!(o.accepted, 0);
        assert_eq!(o.emitted_tokens.len(), 1);
        assert!(matches!(o.emitted_tokens[0], 1 | 2)); // from residual {1,2}
    }

    #[test]
    fn sampled_preserves_the_target_distribution() {
        // The defining property: across many rounds the first emitted token is
        // distributed exactly as p_target[0], whatever the draft proposes or
        // how wrong p_draft is. vocab = 3, single draft token.
        let p_target0 = [0.2_f64, 0.3, 0.5];
        let pd = vec![vec![0.7, 0.2, 0.1]]; // deliberately mismatched draft
        let pt = vec![p_target0.to_vec(), vec![1.0, 0.0, 0.0]];
        let mut u = Uniforms(0xDEADBEEF);
        let trials = 400_000;
        let mut counts = [0u64; 3];
        for _ in 0..trials {
            // Draft token sampled from the draft model itself.
            let draft_tok = sample_categorical(&pd[0], u.next());
            let o = verify_sampled(&[draft_tok], &pd, &pt, &mut || u.next()).unwrap();
            counts[o.emitted_tokens[0] as usize] += 1;
        }
        for (k, &want) in p_target0.iter().enumerate() {
            let got = counts[k] as f64 / trials as f64;
            assert!(
                (got - want).abs() < 0.01,
                "token {k}: empirical {got} vs target {want}"
            );
        }
    }

    #[test]
    fn sampled_high_target_prob_always_accepts() {
        // p_target[draft] >= p_draft[draft] → ratio saturates to 1, accept for
        // any uniform draw, so the draft token is always emitted first.
        let draft = [1u32];
        let pd = vec![vec![0.5, 0.5]];
        let pt = vec![vec![0.1, 0.9], vec![1.0, 0.0]];
        for seed in 0..50u64 {
            let mut u = Uniforms(seed);
            let o = verify_sampled(&draft, &pd, &pt, &mut || u.next()).unwrap();
            assert_eq!(o.emitted_tokens[0], 1);
            assert_eq!(o.accepted, 1);
        }
    }

    #[test]
    fn sampled_shape_errors() {
        let mut u = Uniforms(1);
        // wrong p_draft count
        assert_eq!(
            verify_sampled(&[0], &[], &[vec![1.0], vec![1.0]], &mut || u.next()).unwrap_err(),
            SpecError::DistCount { got: 0, want: 1 }
        );
        // wrong p_target count (needs draft+1)
        assert_eq!(
            verify_sampled(&[0], &[vec![1.0]], &[vec![1.0]], &mut || u.next()).unwrap_err(),
            SpecError::DistCount { got: 1, want: 2 }
        );
        // token out of vocab
        assert_eq!(
            verify_sampled(
                &[5],
                &[vec![1.0, 0.0]],
                &[vec![1.0, 0.0], vec![1.0, 0.0]],
                &mut || u.next()
            )
            .unwrap_err(),
            SpecError::TokenOutOfVocab { token: 5, vocab: 2 }
        );
    }
}
