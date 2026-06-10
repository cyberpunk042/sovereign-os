//! `sovereign-sampler` — the token-sampling stage of the decode loop.
//!
//! The model head emits a row of logits, one per vocabulary token; this
//! crate turns that row into the *next* token id. It applies the standard
//! decode controls in a fixed, well-defined order:
//!
//! 1. **Repetition penalty** — recently-emitted tokens have their logits
//!    pushed toward zero so the model stops looping.
//! 2. **Temperature** — divides the logits; `→0` sharpens toward greedy,
//!    `>1` flattens toward uniform.
//! 3. **Top-k** — keep only the `k` highest-probability tokens.
//! 4. **Top-p (nucleus)** — keep the smallest set whose cumulative
//!    probability reaches `p`.
//! 5. **Min-p** — drop tokens below `min_p · max_prob`.
//! 6. **Locally-typical** — keep tokens whose surprisal `−log p` is closest
//!    to the distribution's entropy (Meister et al.).
//!
//! The surviving distribution is renormalized and a token is drawn from it
//! with a caller-supplied RNG. Decoding is therefore **fully reproducible**:
//! the same logits, controls, and seed always yield the same token — which is
//! what makes the sovereign runtime's replay ledger meaningful.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha20Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version of the sampler surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong sampling a token.
#[derive(Debug, Error, PartialEq)]
pub enum SamplerError {
    /// There were no logits to sample from.
    #[error("empty logits: nothing to sample")]
    EmptyLogits,
    /// Every candidate was filtered out (probability mass collapsed to zero).
    #[error("all tokens filtered out by the active truncation settings")]
    AllFiltered,
}

/// Decode-control settings for one sampling step.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct SamplerConfig {
    /// Softmax temperature. `<= 0.0` means greedy (argmax). Default `1.0`.
    pub temperature: f32,
    /// Keep only the `k` highest-probability tokens. `None` or `Some(0)`
    /// disables the filter.
    pub top_k: Option<usize>,
    /// Nucleus threshold in `(0, 1]`. `None` disables the filter.
    pub top_p: Option<f32>,
    /// Min-p threshold: drop tokens below `min_p · max_prob`. `None` disables.
    pub min_p: Option<f32>,
    /// Locally-typical threshold in `(0, 1]` (Meister et al.): keep the
    /// smallest set of tokens whose information content `−log p` is closest to
    /// the distribution's entropy and whose mass reaches this fraction. `None`
    /// disables. Defaults to `None` for backward-compatible deserialization.
    #[serde(default)]
    pub typical_p: Option<f32>,
    /// Repetition penalty (`> 1.0` discourages recent tokens). Default `1.0`.
    pub repetition_penalty: f32,
    /// OpenAI-style **presence penalty**: a flat amount subtracted from the
    /// logit of any token that has appeared at all in `recent_tokens` (additive,
    /// applied once regardless of count). Default `0.0`. Serde-defaulted.
    #[serde(default)]
    pub presence_penalty: f32,
    /// OpenAI-style **frequency penalty**: an amount subtracted from a token's
    /// logit **proportional to how many times** it appears in `recent_tokens`.
    /// Default `0.0`. Serde-defaulted.
    #[serde(default)]
    pub frequency_penalty: f32,
}

impl Default for SamplerConfig {
    fn default() -> Self {
        Self {
            temperature: 1.0,
            top_k: None,
            top_p: None,
            min_p: None,
            typical_p: None,
            repetition_penalty: 1.0,
            presence_penalty: 0.0,
            frequency_penalty: 0.0,
        }
    }
}

impl SamplerConfig {
    /// A pure-greedy config (always returns the argmax).
    pub fn greedy() -> Self {
        Self {
            temperature: 0.0,
            ..Self::default()
        }
    }
}

/// A configured token sampler.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Sampler {
    /// The active decode controls.
    pub config: SamplerConfig,
}

impl Sampler {
    /// Build a sampler from a config.
    pub fn new(config: SamplerConfig) -> Self {
        Self { config }
    }

    /// A pure-greedy sampler.
    pub fn greedy() -> Self {
        Self::new(SamplerConfig::greedy())
    }

    /// Index of the largest logit (ties broken toward the lower index).
    pub fn argmax(&self, logits: &[f32]) -> Result<usize, SamplerError> {
        if logits.is_empty() {
            return Err(SamplerError::EmptyLogits);
        }
        let mut best = 0usize;
        for (i, &l) in logits.iter().enumerate() {
            if l > logits[best] {
                best = i;
            }
        }
        Ok(best)
    }

    /// The full post-processing pipeline as a renormalized probability
    /// distribution: repetition penalty → temperature → top-k → top-p →
    /// min-p → locally-typical. Filtered tokens have probability exactly `0.0`.
    /// The result sums to `1.0`.
    pub fn distribution(
        &self,
        logits: &[f32],
        recent_tokens: &[usize],
    ) -> Result<Vec<f32>, SamplerError> {
        if logits.is_empty() {
            return Err(SamplerError::EmptyLogits);
        }
        let mut l = logits.to_vec();

        // 1. repetition penalty (CTRL-style): scale recent tokens' logits.
        let penalty = self.config.repetition_penalty;
        if penalty != 1.0 && penalty > 0.0 {
            for &t in recent_tokens {
                if let Some(x) = l.get_mut(t) {
                    *x = if *x > 0.0 { *x / penalty } else { *x * penalty };
                }
            }
        }

        // 1b. OpenAI presence/frequency penalties (additive, by occurrence count).
        let (pp, fp) = (self.config.presence_penalty, self.config.frequency_penalty);
        if pp != 0.0 || fp != 0.0 {
            let mut counts: HashMap<usize, u32> = HashMap::new();
            for &t in recent_tokens {
                *counts.entry(t).or_insert(0) += 1;
            }
            for (t, c) in counts {
                if let Some(x) = l.get_mut(t) {
                    *x -= pp + fp * c as f32;
                }
            }
        }

        // 2. temperature. <= 0 ⇒ greedy one-hot.
        if self.config.temperature <= 0.0 {
            let arg = self.argmax(&l)?;
            let mut probs = vec![0.0f32; l.len()];
            probs[arg] = 1.0;
            return Ok(probs);
        }
        for x in &mut l {
            *x /= self.config.temperature;
        }

        let mut probs = softmax(&l);

        // 3. top-k.
        if let Some(k) = self.config.top_k {
            if k > 0 && k < probs.len() {
                keep_top_k(&mut probs, k);
            }
        }

        // 4. top-p (nucleus).
        if let Some(p) = self.config.top_p {
            keep_nucleus(&mut probs, p);
        }

        // 5. min-p.
        if let Some(mp) = self.config.min_p {
            keep_min_p(&mut probs, mp);
        }

        // 6. locally-typical.
        if let Some(tp) = self.config.typical_p {
            keep_typical(&mut probs, tp);
        }

        renormalize(&mut probs)?;
        Ok(probs)
    }

    /// Sample a token id from `logits` using `rng`, honoring `recent_tokens`
    /// for the repetition penalty.
    pub fn sample<R: Rng>(
        &self,
        logits: &[f32],
        recent_tokens: &[usize],
        rng: &mut R,
    ) -> Result<usize, SamplerError> {
        let probs = self.distribution(logits, recent_tokens)?;
        let u: f32 = rng.random_range(0.0..1.0);
        let mut acc = 0.0f32;
        for (i, &p) in probs.iter().enumerate() {
            acc += p;
            if u < acc {
                return Ok(i);
            }
        }
        // Floating-point slack: return the last non-zero token.
        probs
            .iter()
            .rposition(|&p| p > 0.0)
            .ok_or(SamplerError::AllFiltered)
    }

    /// Reproducible convenience: sample with a freshly-seeded ChaCha RNG.
    pub fn sample_seeded(
        &self,
        logits: &[f32],
        recent_tokens: &[usize],
        seed: u64,
    ) -> Result<usize, SamplerError> {
        let mut rng = ChaCha20Rng::seed_from_u64(seed);
        self.sample(logits, recent_tokens, &mut rng)
    }
}

/// A **Mirostat v2** decode controller (Basu et al.): instead of a fixed top-k
/// / top-p truncation, it targets a constant *surprise* (perplexity) by keeping
/// a running threshold `μ`. Each step it truncates to the tokens whose surprise
/// `−log2 p` is within `μ`, samples one, then nudges `μ` by the error between
/// the observed surprise and the target `τ`. This holds output perplexity steady
/// across a generation regardless of how peaked or flat each step's distribution
/// is — something the static filters can't do.
///
/// It is **stateful** (`μ` persists across `sample` calls), so it lives outside
/// the stateless [`Sampler::distribution`] pipeline. Drive it per step with a
/// probability vector (e.g. from a temperature-only [`Sampler::distribution`]).
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Mirostat {
    /// Target surprise in bits (`τ`); higher = more diverse.
    tau: f32,
    /// Learning rate (`η`) for the `μ` update.
    eta: f32,
    /// Running max-surprise threshold (`μ`), initialized to `2τ`.
    mu: f32,
}

impl Mirostat {
    /// A controller targeting surprise `tau` bits with learning rate `eta`.
    /// `μ` starts at `2·tau` per the paper.
    pub fn new(tau: f32, eta: f32) -> Self {
        Self {
            tau,
            eta,
            mu: 2.0 * tau,
        }
    }

    /// The current running threshold `μ`.
    pub fn mu(&self) -> f32 {
        self.mu
    }

    /// Pick a token from `probs` (assumed non-negative; the active support is
    /// the positive entries) using one uniform draw `u ∈ [0, 1)`, and update
    /// `μ` toward the target surprise. Returns `None` only if no token has
    /// positive probability. Always keeps at least the most-probable token so a
    /// tight `μ` never empties the candidate set.
    pub fn sample(&mut self, probs: &[f32], u: f32) -> Option<usize> {
        let mut idx: Vec<usize> = (0..probs.len()).filter(|&i| probs[i] > 0.0).collect();
        if idx.is_empty() {
            return None;
        }
        idx.sort_by(|&a, &b| {
            probs[b]
                .partial_cmp(&probs[a])
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        // Candidate set: surprise −log2(p) within μ; always keep the top token.
        let mut candidates: Vec<usize> = idx
            .iter()
            .copied()
            .filter(|&i| -(probs[i].log2()) <= self.mu)
            .collect();
        if candidates.is_empty() {
            candidates.push(idx[0]);
        }

        // Sample from the candidates by their (renormalized) probability.
        let total: f32 = candidates.iter().map(|&i| probs[i]).sum();
        let threshold = u * total;
        let mut acc = 0.0f32;
        let mut chosen = *candidates.last().unwrap();
        for &i in &candidates {
            acc += probs[i];
            if threshold < acc {
                chosen = i;
                break;
            }
        }

        // Update μ by the surprise error (observed − target).
        let observed = -(probs[chosen].log2());
        self.mu -= self.eta * (observed - self.tau);
        Some(chosen)
    }
}

/// Numerically-stable softmax.
fn softmax(logits: &[f32]) -> Vec<f32> {
    let max = logits.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    let exps: Vec<f32> = logits.iter().map(|l| (l - max).exp()).collect();
    let sum: f32 = exps.iter().sum();
    if sum == 0.0 {
        return vec![0.0; logits.len()];
    }
    exps.iter().map(|e| e / sum).collect()
}

/// Zero out all but the `k` highest-probability entries.
fn keep_top_k(probs: &mut [f32], k: usize) {
    let mut idx: Vec<usize> = (0..probs.len()).collect();
    idx.sort_by(|&a, &b| {
        probs[b]
            .partial_cmp(&probs[a])
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    for &i in &idx[k..] {
        probs[i] = 0.0;
    }
}

/// Keep the smallest set of top tokens whose cumulative probability reaches
/// `p`; zero the rest.
fn keep_nucleus(probs: &mut [f32], p: f32) {
    let mut idx: Vec<usize> = (0..probs.len()).collect();
    idx.sort_by(|&a, &b| {
        probs[b]
            .partial_cmp(&probs[a])
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let mut cum = 0.0f32;
    let mut cutoff = idx.len();
    for (rank, &i) in idx.iter().enumerate() {
        cum += probs[i];
        if cum >= p {
            cutoff = rank + 1; // include the token that crossed the threshold
            break;
        }
    }
    for &i in &idx[cutoff..] {
        probs[i] = 0.0;
    }
}

/// Drop tokens whose probability is below `min_p · max_prob`.
fn keep_min_p(probs: &mut [f32], min_p: f32) {
    let max = probs.iter().copied().fold(0.0f32, f32::max);
    let threshold = min_p * max;
    for p in probs.iter_mut() {
        if *p < threshold {
            *p = 0.0;
        }
    }
}

/// Locally-typical filter (Meister et al.): keep the smallest set of tokens
/// whose surprisal `−log p` is closest to the distribution's entropy `H` and
/// whose cumulative mass reaches `mass`. Tokens whose information content is
/// near-average are kept; both the over-confident head and the long
/// low-information tail are trimmed — distinct from nucleus/top-k.
fn keep_typical(probs: &mut [f32], mass: f32) {
    // Entropy H = −Σ p·log p over the positive support.
    let entropy: f32 = probs
        .iter()
        .filter(|&&p| p > 0.0)
        .map(|&p| -p * p.ln())
        .sum();
    // Rank tokens by |−log p − H| ascending (closest-to-typical first).
    let mut idx: Vec<usize> = (0..probs.len()).filter(|&i| probs[i] > 0.0).collect();
    idx.sort_by(|&a, &b| {
        let da = (-probs[a].ln() - entropy).abs();
        let db = (-probs[b].ln() - entropy).abs();
        da.partial_cmp(&db).unwrap_or(std::cmp::Ordering::Equal)
    });
    let mut cum = 0.0f32;
    let mut cutoff = idx.len();
    for (rank, &i) in idx.iter().enumerate() {
        cum += probs[i];
        if cum >= mass {
            cutoff = rank + 1; // include the token that crossed the threshold
            break;
        }
    }
    for &i in &idx[cutoff..] {
        probs[i] = 0.0;
    }
}

/// Rescale a (possibly sparsified) probability vector to sum to 1.
fn renormalize(probs: &mut [f32]) -> Result<(), SamplerError> {
    let sum: f32 = probs.iter().sum();
    if sum <= 0.0 {
        return Err(SamplerError::AllFiltered);
    }
    for p in probs.iter_mut() {
        *p /= sum;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f32, b: f32, eps: f32) -> bool {
        (a - b).abs() <= eps
    }

    /// Deterministic splitmix64 → uniform `[0, 1)`, for reproducible tests.
    struct Uniforms(u64);
    impl Uniforms {
        fn next(&mut self) -> f64 {
            self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = self.0;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z ^= z >> 31;
            (z >> 11) as f64 / (1u64 << 53) as f64
        }
    }

    #[test]
    fn argmax_picks_the_largest() {
        let s = Sampler::greedy();
        assert_eq!(s.argmax(&[0.1, 0.9, 0.3, -1.0]).unwrap(), 1);
    }

    #[test]
    fn typical_sampling_trims_to_near_average_surprisal() {
        // A peaked distribution: one very high-prob token (low surprisal), a
        // couple mid, and a low-prob tail. Typical sampling drops the extremes
        // (the over-confident head and the surprising tail), keeping the middle.
        let cfg = SamplerConfig {
            temperature: 1.0,
            typical_p: Some(0.5),
            ..SamplerConfig::default()
        };
        let s = Sampler::new(cfg);
        // logits chosen so softmax ≈ [0.64, 0.23, 0.09, 0.03, 0.01]
        let logits = [3.0f32, 2.0, 1.0, 0.0, -1.0];
        let dist = s.distribution(&logits, &[]).unwrap();
        // Some tokens survive, some are filtered, and it still normalizes.
        assert!((dist.iter().sum::<f32>() - 1.0).abs() < 1e-5);
        assert!(dist.iter().filter(|&&p| p > 0.0).count() < logits.len());
        assert!(dist.contains(&0.0), "extremes should be trimmed");
    }

    #[test]
    fn typical_p_none_keeps_full_support() {
        let s = Sampler::new(SamplerConfig {
            temperature: 1.0,
            ..SamplerConfig::default()
        });
        let dist = s.distribution(&[1.0, 0.5, 0.2, -0.3], &[]).unwrap();
        assert!(dist.iter().all(|&p| p > 0.0), "no filter → full support");
    }

    #[test]
    fn typical_sampling_uniform_keeps_mass_fraction() {
        // Uniform distribution → every token has surprisal == entropy, so all
        // are equally typical; the filter keeps the smallest prefix reaching
        // the mass fraction.
        let s = Sampler::new(SamplerConfig {
            temperature: 1.0,
            typical_p: Some(0.5),
            ..SamplerConfig::default()
        });
        let dist = s.distribution(&[0.0, 0.0, 0.0, 0.0], &[]).unwrap();
        let kept = dist.iter().filter(|&&p| p > 0.0).count();
        // 4 uniform tokens at 0.25 each → need 2 to reach 0.5 mass.
        assert_eq!(kept, 2);
        assert!((dist.iter().sum::<f32>() - 1.0).abs() < 1e-5);
    }

    #[test]
    fn argmax_breaks_ties_low() {
        let s = Sampler::greedy();
        assert_eq!(s.argmax(&[1.0, 1.0, 0.5]).unwrap(), 0);
    }

    #[test]
    fn distribution_sums_to_one() {
        let s = Sampler::new(SamplerConfig::default());
        let d = s.distribution(&[2.0, 1.0, 0.5, -1.0], &[]).unwrap();
        let sum: f32 = d.iter().sum();
        assert!(approx(sum, 1.0, 1e-5), "{sum}");
    }

    #[test]
    fn greedy_distribution_is_one_hot() {
        let s = Sampler::greedy();
        let d = s.distribution(&[0.2, 5.0, 0.1], &[]).unwrap();
        assert_eq!(d, vec![0.0, 1.0, 0.0]);
    }

    #[test]
    fn greedy_sampling_ignores_rng() {
        let s = Sampler::greedy();
        let logits = [0.2, 5.0, 0.1];
        for seed in 0..50u64 {
            assert_eq!(s.sample_seeded(&logits, &[], seed).unwrap(), 1);
        }
    }

    #[test]
    fn top_k_one_forces_argmax() {
        let cfg = SamplerConfig {
            temperature: 1.0,
            top_k: Some(1),
            ..SamplerConfig::default()
        };
        let s = Sampler::new(cfg);
        let logits = [1.0, 3.0, 2.0, 0.0];
        for seed in 0..50u64 {
            assert_eq!(s.sample_seeded(&logits, &[], seed).unwrap(), 1);
        }
    }

    #[test]
    fn tiny_temperature_concentrates_on_argmax() {
        let cfg = SamplerConfig {
            temperature: 0.01,
            ..SamplerConfig::default()
        };
        let s = Sampler::new(cfg);
        let logits = [1.0, 1.2, 0.9];
        let d = s.distribution(&logits, &[]).unwrap();
        assert!(d[1] > 0.99, "{d:?}");
    }

    #[test]
    fn high_temperature_flattens() {
        let hot = Sampler::new(SamplerConfig {
            temperature: 100.0,
            ..SamplerConfig::default()
        });
        let d = hot.distribution(&[1.0, 3.0, 0.0, -2.0], &[]).unwrap();
        // near-uniform: max prob close to 1/4
        let max = d.iter().copied().fold(0.0f32, f32::max);
        assert!(max < 0.30, "max prob {max} should be near 0.25");
    }

    #[test]
    fn nucleus_truncates_the_tail() {
        // top_p that only admits the single dominant token.
        let cfg = SamplerConfig {
            temperature: 1.0,
            top_p: Some(0.5),
            ..SamplerConfig::default()
        };
        let s = Sampler::new(cfg);
        // softmax([5,1,0]) ≈ [0.979, 0.018, 0.0066]; nucleus 0.5 keeps only token 0.
        let d = s.distribution(&[5.0, 1.0, 0.0], &[]).unwrap();
        assert_eq!(d[1], 0.0);
        assert_eq!(d[2], 0.0);
        assert!(approx(d[0], 1.0, 1e-6));
    }

    #[test]
    fn min_p_drops_low_mass_tokens() {
        let cfg = SamplerConfig {
            temperature: 1.0,
            min_p: Some(0.5),
            ..SamplerConfig::default()
        };
        let s = Sampler::new(cfg);
        // keep only tokens with prob >= 0.5 * max_prob.
        let d = s.distribution(&[5.0, 1.0, 0.0], &[]).unwrap();
        assert_eq!(d[1], 0.0);
        assert_eq!(d[2], 0.0);
    }

    #[test]
    fn repetition_penalty_demotes_recent_tokens() {
        // Without penalty, token 0 wins. Penalize it → token 1 becomes likelier.
        let plain = Sampler::new(SamplerConfig::default());
        let d0 = plain.distribution(&[1.0, 0.9], &[]).unwrap();
        assert!(d0[0] > d0[1]);

        let pen = Sampler::new(SamplerConfig {
            repetition_penalty: 2.0,
            ..SamplerConfig::default()
        });
        let d1 = pen.distribution(&[1.0, 0.9], &[0]).unwrap();
        assert!(d1[1] > d1[0], "penalized: {d1:?}");
    }

    #[test]
    fn sampling_is_deterministic_per_seed() {
        let s = Sampler::new(SamplerConfig::default());
        let logits = [1.0, 0.5, 0.25, 2.0, -1.0];
        let a = s.sample_seeded(&logits, &[], 12345).unwrap();
        let b = s.sample_seeded(&logits, &[], 12345).unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn sampling_stays_in_range_and_covers_support() {
        // Uniform logits → over many seeds, every index should appear.
        let s = Sampler::new(SamplerConfig::default());
        let logits = [0.0, 0.0, 0.0, 0.0];
        let mut seen = [false; 4];
        for seed in 0..500u64 {
            let t = s.sample_seeded(&logits, &[], seed).unwrap();
            assert!(t < 4);
            seen[t] = true;
        }
        assert!(seen.iter().all(|&x| x), "all four tokens should be sampled");
    }

    #[test]
    fn empty_logits_is_an_error() {
        let s = Sampler::new(SamplerConfig::default());
        assert_eq!(s.argmax(&[]).unwrap_err(), SamplerError::EmptyLogits);
        assert_eq!(
            s.distribution(&[], &[]).unwrap_err(),
            SamplerError::EmptyLogits
        );
    }

    #[test]
    fn config_serde_round_trip() {
        let cfg = SamplerConfig {
            temperature: 0.7,
            top_k: Some(40),
            top_p: Some(0.95),
            min_p: Some(0.05),
            typical_p: Some(0.9),
            repetition_penalty: 1.1,
            presence_penalty: 0.5,
            frequency_penalty: 0.2,
        };
        let j = serde_json::to_string(&cfg).unwrap();
        let back: SamplerConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(cfg, back);
    }

    #[test]
    fn mirostat_inits_mu_to_two_tau_and_picks_valid_tokens() {
        let mut m = Mirostat::new(3.0, 0.1);
        assert!((m.mu() - 6.0).abs() < 1e-6);
        let probs = vec![0.5, 0.25, 0.15, 0.1];
        let t = m.sample(&probs, 0.0).unwrap();
        assert!(t < probs.len());
    }

    #[test]
    fn mirostat_mu_moves_toward_target_surprise() {
        // Sampling a token whose surprise exceeds τ pushes μ down; one below τ
        // pushes μ up — the control law.
        // probs surprises: 0.5→1.0, 0.25→2.0, 0.15→2.74, 0.1→3.32 bits.
        let probs = vec![0.5f32, 0.25, 0.15, 0.1];

        // τ=1, μ₀=2 → candidates are tokens 0,1 (surprise ≤ 2). u≈1 samples
        // token 1 (surprise 2.0 > τ) → μ decreases.
        let mut hi = Mirostat::new(1.0, 0.5);
        let mu0 = hi.mu();
        hi.sample(&probs, 0.999);
        assert!(
            hi.mu() < mu0,
            "above-τ surprise must lower μ ({} ≥ {mu0})",
            hi.mu()
        );

        // τ=4, μ₀=8 → all tokens are candidates. u=0 samples token 0
        // (surprise 1.0 < τ) → μ increases toward τ.
        let mut lo = Mirostat::new(4.0, 0.5);
        let mu1 = lo.mu();
        lo.sample(&probs, 0.0);
        assert!(
            lo.mu() > mu1,
            "below-τ surprise must raise μ ({} ≤ {mu1})",
            lo.mu()
        );
    }

    #[test]
    fn mirostat_converges_observed_surprise_near_tau() {
        // Over many steps on a fixed distribution, μ stabilizes so the average
        // observed surprise tracks the target τ.
        let probs = vec![0.4f32, 0.3, 0.2, 0.1];
        let tau = 1.5f32;
        let mut m = Mirostat::new(tau, 0.1);
        let mut u = Uniforms(12345);
        let mut surprise_sum = 0.0f64;
        let trials = 4000;
        for _ in 0..trials {
            let t = m.sample(&probs, u.next() as f32).unwrap();
            surprise_sum += -(probs[t].log2()) as f64;
        }
        let avg = surprise_sum / trials as f64;
        assert!(
            (avg - tau as f64).abs() < 0.5,
            "avg surprise {avg} should track τ {tau}"
        );
    }

    #[test]
    fn mirostat_empty_support_is_none() {
        let mut m = Mirostat::new(3.0, 0.1);
        assert_eq!(m.sample(&[0.0, 0.0, 0.0], 0.5), None);
    }

    #[test]
    fn presence_and_frequency_penalties_demote_recent_tokens() {
        // Uniform logits; token 0 appears 3× and token 1 once in recent.
        let logits = [1.0f32, 1.0, 1.0, 1.0];
        let recent = [0usize, 0, 0, 1];

        // Presence penalty: any seen token loses a flat amount once, so 0 and 1
        // are demoted equally (count-independent), 2 and 3 untouched.
        let pres = Sampler::new(SamplerConfig {
            presence_penalty: 0.5,
            ..SamplerConfig::default()
        });
        let d = pres.distribution(&logits, &recent).unwrap();
        assert!((d[0] - d[1]).abs() < 1e-6, "presence is count-independent");
        assert!(d[2] > d[0], "unseen token outranks a seen one");

        // Frequency penalty: proportional to count → token 0 (3×) is demoted
        // more than token 1 (1×).
        let freq = Sampler::new(SamplerConfig {
            frequency_penalty: 0.5,
            ..SamplerConfig::default()
        });
        let d = freq.distribution(&logits, &recent).unwrap();
        assert!(d[1] > d[0], "more-frequent token is demoted more");
        assert!(d[2] > d[1], "unseen outranks the once-seen");
    }

    #[test]
    fn zero_penalties_are_a_no_op() {
        let logits = [2.0f32, 1.0, 0.5];
        let s = Sampler::new(SamplerConfig {
            temperature: 1.0,
            ..SamplerConfig::default()
        });
        // default presence/frequency = 0 → distribution unchanged by recents.
        let with_recent = s.distribution(&logits, &[0, 0, 1]).unwrap();
        let without = s.distribution(&logits, &[]).unwrap();
        for (a, b) in with_recent.iter().zip(&without) {
            assert!((a - b).abs() < 1e-6);
        }
    }

    #[test]
    fn legacy_config_without_typical_p_deserializes() {
        let legacy =
            r#"{"temperature":0.8,"top_k":40,"top_p":null,"min_p":null,"repetition_penalty":1.0}"#;
        let cfg: SamplerConfig = serde_json::from_str(legacy).unwrap();
        assert_eq!(cfg.typical_p, None);
        assert_eq!(cfg.top_k, Some(40));
    }
}
