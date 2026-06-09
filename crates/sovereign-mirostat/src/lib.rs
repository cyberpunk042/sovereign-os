//! `sovereign-mirostat` — feedback-controlled (Mirostat v2) sampling.
//!
//! Static truncation (top-k / top-p) fixes *how many* tokens survive, not how
//! *surprising* the result is, so perplexity drifts over a long generation.
//! Mirostat instead targets a surprise level directly. It keeps a running
//! threshold `mu` and, each step:
//!
//! 1. drops every token whose surprise `−ln p` exceeds `mu` (always keeping at
//!    least the most likely token),
//! 2. samples from what remains, and
//! 3. nudges `mu` by `eta · (observed_surprise − tau)` — if the draw was *less*
//!    surprising than the target `tau`, `mu` rises (allow more diversity); if
//!    *more*, `mu` falls (truncate harder).
//!
//! The feedback loop holds the average surprise near `tau`, so output
//! perplexity stays roughly constant. It is fully deterministic for a given
//! seed. This is a distinct decoder from the static [`sovereign-sampler`].
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha20Rng;
use serde::{Deserialize, Serialize};

/// Schema version of the mirostat surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A Mirostat v2 sampler. Stateful: `mu` evolves across draws.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Mirostat {
    /// Target surprise (≈ target cross-entropy, nats). Higher = more diverse.
    pub tau: f32,
    /// Learning rate for the `mu` update.
    pub eta: f32,
    /// The running surprise threshold (initialized to `2·tau`).
    pub mu: f32,
}

impl Mirostat {
    /// A sampler targeting surprise `tau` with learning rate `eta`.
    ///
    /// # Panics
    /// Panics if `tau <= 0` or `eta < 0`.
    pub fn new(tau: f32, eta: f32) -> Self {
        assert!(tau > 0.0, "tau must be > 0");
        assert!(eta >= 0.0, "eta must be >= 0");
        Self {
            tau,
            eta,
            mu: 2.0 * tau,
        }
    }

    /// The current threshold.
    pub fn mu(&self) -> f32 {
        self.mu
    }

    /// Sample a token from `logits` with `rng`, updating `mu`.
    ///
    /// # Panics
    /// Panics if `logits` is empty.
    pub fn sample<R: Rng>(&mut self, logits: &[f32], rng: &mut R) -> usize {
        assert!(!logits.is_empty(), "logits must be non-empty");
        let probs = softmax(logits);

        // indices by descending probability (⇒ ascending surprise)
        let mut idx: Vec<usize> = (0..probs.len()).collect();
        idx.sort_by(|&a, &b| {
            probs[b]
                .partial_cmp(&probs[a])
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        // keep the prefix whose surprise is within mu (at least the top token)
        let mut kept = Vec::new();
        for &i in &idx {
            let surprise = -probs[i].max(f32::MIN_POSITIVE).ln();
            if kept.is_empty() || surprise <= self.mu {
                kept.push(i);
            } else {
                break;
            }
        }

        // sample from the kept set, renormalized
        let sum: f32 = kept.iter().map(|&i| probs[i]).sum();
        let target = rng.random_range(0.0..1.0) * sum;
        let mut acc = 0.0f32;
        let mut chosen = *kept.last().unwrap();
        for &i in &kept {
            acc += probs[i];
            if target < acc {
                chosen = i;
                break;
            }
        }

        // feedback: nudge mu toward the target surprise
        let observed = -probs[chosen].max(f32::MIN_POSITIVE).ln();
        self.mu -= self.eta * (observed - self.tau);
        chosen
    }

    /// Reproducible convenience: sample with a freshly-seeded RNG. Note that a
    /// fresh RNG each call makes single draws repeatable but does not advance a
    /// shared stream; use [`sample`](Self::sample) with one RNG for a sequence.
    pub fn sample_seeded(&mut self, logits: &[f32], seed: u64) -> usize {
        let mut rng = ChaCha20Rng::seed_from_u64(seed);
        self.sample(logits, &mut rng)
    }
}

/// Numerically-stable softmax.
fn softmax(logits: &[f32]) -> Vec<f32> {
    let max = logits.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    let exps: Vec<f32> = logits.iter().map(|l| (l - max).exp()).collect();
    let sum: f32 = exps.iter().sum();
    if sum == 0.0 {
        return vec![1.0 / logits.len() as f32; logits.len()];
    }
    exps.iter().map(|e| e / sum).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand_chacha::ChaCha20Rng;

    #[test]
    fn mu_initializes_to_twice_tau() {
        let m = Mirostat::new(3.0, 0.1);
        assert_eq!(m.mu(), 6.0);
    }

    #[test]
    fn samples_in_range() {
        let mut m = Mirostat::new(2.0, 0.1);
        let mut rng = ChaCha20Rng::seed_from_u64(1);
        for _ in 0..50 {
            let t = m.sample(&[0.5, 1.0, 0.2, 2.0, -1.0], &mut rng);
            assert!(t < 5);
        }
    }

    #[test]
    fn deterministic_per_seed() {
        let mut a = Mirostat::new(2.0, 0.1);
        let mut b = Mirostat::new(2.0, 0.1);
        let logits = [1.0, 0.5, 2.0, 0.1];
        assert_eq!(a.sample_seeded(&logits, 7), b.sample_seeded(&logits, 7));
    }

    #[test]
    fn confident_draws_raise_mu_toward_diversity() {
        // peaked logits → the drawn token has low surprise (< tau) → mu rises.
        let mut m = Mirostat::new(3.0, 0.5);
        let start = m.mu();
        let mut rng = ChaCha20Rng::seed_from_u64(0);
        let peaked = [10.0, 0.0, 0.0, 0.0]; // token 0 ≈ certain → surprise ≈ 0
        for _ in 0..10 {
            m.sample(&peaked, &mut rng);
        }
        assert!(m.mu() > start, "mu {} should rise above {start}", m.mu());
    }

    #[test]
    fn surprising_draws_lower_mu() {
        // near-uniform logits → high surprise (> tau small) → mu falls.
        let mut m = Mirostat::new(0.5, 0.5); // small target surprise
        let start = m.mu();
        let mut rng = ChaCha20Rng::seed_from_u64(3);
        let flat = [0.0; 8]; // uniform → surprise ln(8) ≈ 2.08 >> tau
        for _ in 0..10 {
            m.sample(&flat, &mut rng);
        }
        assert!(m.mu() < start, "mu {} should fall below {start}", m.mu());
    }

    #[test]
    fn low_mu_concentrates_on_top_tokens() {
        // force a tiny mu → only the most likely token survives → argmax.
        let mut m = Mirostat::new(2.0, 0.0); // eta 0 → mu fixed
        m.mu = 0.05; // very tight surprise budget
        let mut rng = ChaCha20Rng::seed_from_u64(9);
        let logits = [0.1, 5.0, 0.2, 0.3]; // token 1 dominates
        for _ in 0..30 {
            assert_eq!(m.sample(&logits, &mut rng), 1);
        }
    }

    #[test]
    fn eta_zero_keeps_mu_fixed() {
        let mut m = Mirostat::new(2.0, 0.0);
        let before = m.mu();
        let mut rng = ChaCha20Rng::seed_from_u64(5);
        m.sample(&[1.0, 2.0, 3.0], &mut rng);
        assert_eq!(m.mu(), before);
    }

    #[test]
    fn serde_round_trip() {
        let m = Mirostat::new(4.0, 0.2);
        let j = serde_json::to_string(&m).unwrap();
        let back: Mirostat = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
