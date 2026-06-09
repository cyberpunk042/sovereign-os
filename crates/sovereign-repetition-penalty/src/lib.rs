//! `sovereign-repetition-penalty` — discourage repeats by bending the logits.
//!
//! Left to itself a sampler will happily loop or echo the prompt. The standard
//! cure is to penalise tokens the model has already produced, *softly* — lowering
//! their logits rather than banning them outright (which [`no-repeat-ngram`] and
//! logit masking do). This crate is the three penalties every production sampler
//! exposes, applied in place to a logits slice given the generated token history.
//!
//! - **Repetition penalty** (CTRL): for each already-seen token, divide its logit
//!   by `penalty` when positive and multiply when negative — so a token's score is
//!   pushed toward zero whichever side it is on. `penalty = 1.0` is a no-op;
//!   `>1` discourages repeats.
//! - **Frequency penalty** (OpenAI): subtract `alpha * count` from each token's
//!   logit, so the more often a token has appeared the harder it is penalised —
//!   the right tool against runaway loops.
//! - **Presence penalty** (OpenAI): subtract `beta` once from any token that has
//!   appeared at all, nudging the model toward new vocabulary regardless of count.
//!
//! [`Penalties`] bundles all three with their parameters and applies them in one
//! call; the individual `apply_*` functions are exposed too. Out-of-range token
//! ids in the history are ignored.
//!
//! [`no-repeat-ngram`]: https://docs.rs/sovereign-no-repeat-ngram
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the repetition-penalty surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-token occurrence counts over the generated `history`.
fn counts(history: &[usize]) -> HashMap<usize, u32> {
    let mut m = HashMap::new();
    for &t in history {
        *m.entry(t).or_insert(0) += 1;
    }
    m
}

/// Apply the CTRL repetition penalty in place. For every token id seen in
/// `history`, a positive logit is divided by `penalty` and a negative logit is
/// multiplied by it. `penalty <= 0` or `== 1.0` is a no-op.
pub fn apply_repetition_penalty(logits: &mut [f32], history: &[usize], penalty: f32) {
    if penalty <= 0.0 || (penalty - 1.0).abs() < f32::EPSILON {
        return;
    }
    for &t in counts(history).keys() {
        if t < logits.len() {
            let l = logits[t];
            logits[t] = if l > 0.0 { l / penalty } else { l * penalty };
        }
    }
}

/// Apply the frequency penalty in place: subtract `alpha * count` from each
/// token's logit, where `count` is how many times it appears in `history`.
pub fn apply_frequency_penalty(logits: &mut [f32], history: &[usize], alpha: f32) {
    if alpha == 0.0 {
        return;
    }
    for (&t, &c) in counts(history).iter() {
        if t < logits.len() {
            logits[t] -= alpha * c as f32;
        }
    }
}

/// Apply the presence penalty in place: subtract `beta` once from any token that
/// appears at all in `history`.
pub fn apply_presence_penalty(logits: &mut [f32], history: &[usize], beta: f32) {
    if beta == 0.0 {
        return;
    }
    for &t in counts(history).keys() {
        if t < logits.len() {
            logits[t] -= beta;
        }
    }
}

/// A bundle of the three penalties with their parameters.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Penalties {
    /// CTRL repetition penalty (`1.0` = off; `>1` discourages).
    pub repetition: f32,
    /// Frequency penalty `alpha` (`0.0` = off).
    pub frequency: f32,
    /// Presence penalty `beta` (`0.0` = off).
    pub presence: f32,
}

impl Default for Penalties {
    fn default() -> Self {
        // identity: no penalties applied.
        Self {
            repetition: 1.0,
            frequency: 0.0,
            presence: 0.0,
        }
    }
}

impl Penalties {
    /// Apply all configured penalties to `logits` given `history`, in the
    /// conventional order: repetition (scaling), then frequency, then presence
    /// (the additive penalties last so scaling doesn't rescale them).
    pub fn apply(&self, logits: &mut [f32], history: &[usize]) {
        apply_repetition_penalty(logits, history, self.repetition);
        apply_frequency_penalty(logits, history, self.frequency);
        apply_presence_penalty(logits, history, self.presence);
    }

    /// Whether this is the identity (no penalty would change any logit).
    pub fn is_identity(&self) -> bool {
        (self.repetition - 1.0).abs() < f32::EPSILON
            && self.frequency == 0.0
            && self.presence == 0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f32, b: f32) -> bool {
        (a - b).abs() < 1e-6
    }

    #[test]
    fn repetition_penalty_lowers_positive_logit() {
        let mut logits = [2.0f32, 1.0, 0.5];
        apply_repetition_penalty(&mut logits, &[0], 2.0);
        // token 0 positive → divided by 2
        assert!(approx(logits[0], 1.0));
        // untouched tokens unchanged
        assert!(approx(logits[1], 1.0) && approx(logits[2], 0.5));
    }

    #[test]
    fn repetition_penalty_handles_negative_logit() {
        let mut logits = [-2.0f32, 1.0];
        apply_repetition_penalty(&mut logits, &[0], 2.0);
        // negative → multiplied by 2 (pushed further down)
        assert!(approx(logits[0], -4.0));
    }

    #[test]
    fn repetition_penalty_one_is_noop() {
        let mut logits = [2.0f32, -1.0];
        let before = logits;
        apply_repetition_penalty(&mut logits, &[0, 1], 1.0);
        assert_eq!(logits, before);
    }

    #[test]
    fn frequency_penalty_scales_with_count() {
        let mut logits = [5.0f32, 5.0];
        // token 0 appears 3 times, token 1 once
        apply_frequency_penalty(&mut logits, &[0, 0, 0, 1], 0.5);
        assert!(approx(logits[0], 5.0 - 0.5 * 3.0)); // 3.5
        assert!(approx(logits[1], 5.0 - 0.5)); // 4.5
    }

    #[test]
    fn presence_penalty_is_flat_per_seen_token() {
        let mut logits = [5.0f32, 5.0, 5.0];
        // token 0 seen many times, token 1 once, token 2 never
        apply_presence_penalty(&mut logits, &[0, 0, 0, 1], 1.0);
        assert!(approx(logits[0], 4.0)); // -1 regardless of count
        assert!(approx(logits[1], 4.0));
        assert!(approx(logits[2], 5.0)); // unseen untouched
    }

    #[test]
    fn out_of_range_history_ignored() {
        let mut logits = [1.0f32, 2.0];
        // token id 99 is out of range; must not panic, must not change logits
        apply_frequency_penalty(&mut logits, &[99], 1.0);
        assert_eq!(logits, [1.0, 2.0]);
    }

    #[test]
    fn penalties_bundle_applies_all() {
        let mut logits = [10.0f32, 10.0, 10.0];
        let p = Penalties {
            repetition: 2.0,
            frequency: 1.0,
            presence: 0.5,
        };
        // token 0 appears twice
        p.apply(&mut logits, &[0, 0, 1]);
        // token 0: 10/2 = 5, then -1*2 = 3, then -0.5 = 2.5
        assert!(approx(logits[0], 2.5), "got {}", logits[0]);
        // token 1: 10/2 = 5, -1*1 = 4, -0.5 = 3.5
        assert!(approx(logits[1], 3.5), "got {}", logits[1]);
        // token 2 unseen: unchanged
        assert!(approx(logits[2], 10.0));
    }

    #[test]
    fn identity_default_changes_nothing() {
        let p = Penalties::default();
        assert!(p.is_identity());
        let mut logits = [1.0f32, 2.0, 3.0];
        let before = logits;
        p.apply(&mut logits, &[0, 1, 2]);
        assert_eq!(logits, before);
    }

    #[test]
    fn discourages_the_repeated_token_relative_to_others() {
        // after a loop of token 0, its logit should fall below an equally-scored
        // unseen token, so the sampler will prefer something new.
        let mut logits = [5.0f32, 5.0];
        Penalties {
            repetition: 1.3,
            frequency: 0.7,
            presence: 0.0,
        }
        .apply(&mut logits, &[0, 0, 0, 0]);
        assert!(logits[0] < logits[1], "repeated token not discouraged");
    }

    #[test]
    fn serde_round_trip() {
        let p = Penalties {
            repetition: 1.2,
            frequency: 0.3,
            presence: 0.1,
        };
        let j = serde_json::to_string(&p).unwrap();
        assert_eq!(serde_json::from_str::<Penalties>(&j).unwrap(), p);
    }
}
