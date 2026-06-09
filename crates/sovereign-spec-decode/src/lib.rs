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
}
