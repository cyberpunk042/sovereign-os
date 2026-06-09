//! `sovereign-xtc-sampler` — trade the obvious next token for a more interesting one.
//!
//! Raising temperature buys diversity by flattening the whole distribution, which
//! also pulls in genuinely bad tokens and degrades coherence. **XTC** (Exclude Top
//! Choices) takes a sharper cut: when the model is confident about *several*
//! tokens, it removes the most-probable ones and lets a lower — but still
//! plausible — token win. The result reads as more creative without the
//! word-salad failure mode of hot sampling.
//!
//! The safety property is what makes it usable: XTC only excludes a token when
//! there is another token above the same confidence `threshold` to fall back on.
//! If only one token clears the bar — a closing bracket that *must* come next, the
//! single correct word — nothing is removed and generation stays on track. And it
//! fires only with a tunable `probability` per step, so most steps are normal and
//! the effect is a gentle, occasional nudge rather than a constant distortion.
//!
//! Mechanically: softmax the logits, collect the tokens at or above `threshold`,
//! and if there are at least two, keep the *least* probable of them (the boundary
//! token) and the entire sub-threshold tail, masking the more-probable
//! above-threshold tokens to `-inf`. [`XtcSampler::excluded`] reports which tokens
//! that would be (independent of the activation roll); [`XtcSampler::apply_seeded`]
//! rolls activation from a seed and applies the mask; [`XtcSampler::apply_with_roll`]
//! takes the roll explicitly for deterministic use.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the XTC sampler surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// XTC sampler configuration.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct XtcSampler {
    /// Probability threshold; tokens at or above this are "confident choices".
    pub threshold: f32,
    /// Per-step probability that XTC activates at all (`0.0` disables it).
    pub probability: f32,
}

impl Default for XtcSampler {
    fn default() -> Self {
        // values in the range suggested by the original XTC proposal.
        Self {
            threshold: 0.1,
            probability: 0.5,
        }
    }
}

/// Numerically-stable softmax of `logits` (ignoring `-inf` entries, which map to 0).
fn softmax(logits: &[f32]) -> Vec<f32> {
    let max = logits.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    if !max.is_finite() {
        return vec![0.0; logits.len()];
    }
    let mut exps: Vec<f32> = logits.iter().map(|&l| (l - max).exp()).collect();
    let sum: f32 = exps.iter().sum();
    if sum > 0.0 {
        for e in &mut exps {
            *e /= sum;
        }
    }
    exps
}

/// SplitMix64-derived uniform roll in `[0, 1)` from a seed.
fn roll_from_seed(seed: u64) -> f32 {
    let mut z = seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^= z >> 31;
    ((z >> 11) as f32) / ((1u64 << 53) as f32)
}

impl XtcSampler {
    /// A sampler with the given threshold and activation probability.
    pub fn new(threshold: f32, probability: f32) -> Self {
        Self {
            threshold,
            probability,
        }
    }

    /// Whether the sampler can ever fire (positive probability and threshold).
    pub fn is_active(&self) -> bool {
        self.probability > 0.0 && self.threshold > 0.0
    }

    /// The token ids XTC would remove *if it activated*: the more-probable tokens
    /// among those at or above `threshold`, leaving the least-probable confident
    /// token and the whole sub-threshold tail. Empty if fewer than two tokens clear
    /// the threshold (nothing safe to exclude).
    pub fn excluded(&self, logits: &[f32]) -> Vec<usize> {
        if !self.is_active() {
            return Vec::new();
        }
        let probs = softmax(logits);
        // tokens at or above the threshold, with their probabilities.
        let mut above: Vec<(usize, f32)> = probs
            .iter()
            .enumerate()
            .filter(|&(_, &p)| p >= self.threshold)
            .map(|(i, &p)| (i, p))
            .collect();
        if above.len() < 2 {
            return Vec::new(); // need a fallback token to exclude anything
        }
        // sort ascending by probability (ties by index for determinism).
        above.sort_by(|a, b| a.1.total_cmp(&b.1).then(a.0.cmp(&b.0)));
        // keep above[0] (least probable confident token); exclude the rest.
        above[1..].iter().map(|&(i, _)| i).collect()
    }

    /// Apply XTC given an explicit activation `roll` in `[0, 1)`: if `roll <
    /// probability`, mask the excluded tokens in `logits` to `-inf`. Returns the
    /// number of tokens masked.
    pub fn apply_with_roll(&self, logits: &mut [f32], roll: f32) -> usize {
        if !self.is_active() || roll >= self.probability {
            return 0;
        }
        let excluded = self.excluded(logits);
        for &i in &excluded {
            logits[i] = f32::NEG_INFINITY;
        }
        excluded.len()
    }

    /// Apply XTC with the activation roll drawn from `seed`. Returns the number of
    /// tokens masked.
    pub fn apply_seeded(&self, logits: &mut [f32], seed: u64) -> usize {
        let roll = roll_from_seed(seed);
        self.apply_with_roll(logits, roll)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f32, b: f32) -> bool {
        (a - b).abs() < 1e-4
    }

    /// Build logits whose softmax gives roughly the requested probabilities by
    /// using log-probabilities directly.
    fn logits_from_probs(probs: &[f32]) -> Vec<f32> {
        probs.iter().map(|p| p.max(1e-9).ln()).collect()
    }

    #[test]
    fn excludes_top_when_multiple_confident() {
        // two clearly-confident tokens (0.5, 0.4) and a tail (0.1).
        let logits = logits_from_probs(&[0.5, 0.4, 0.1]);
        let xtc = XtcSampler::new(0.15, 1.0);
        let ex = xtc.excluded(&logits);
        // tokens 0 and 1 are above 0.15; keep the lower (1), exclude the higher (0).
        assert_eq!(ex, vec![0]);
    }

    #[test]
    fn keeps_tail_below_threshold() {
        let logits = logits_from_probs(&[0.45, 0.35, 0.15, 0.05]);
        let xtc = XtcSampler::new(0.2, 1.0);
        let ex = xtc.excluded(&logits);
        // above 0.2: tokens 0 (0.45) and 1 (0.35). keep 1, exclude 0.
        // tokens 2,3 are below threshold → never excluded.
        assert_eq!(ex, vec![0]);
        assert!(!ex.contains(&2) && !ex.contains(&3));
    }

    #[test]
    fn single_confident_token_is_safe() {
        // only one token above threshold → nothing excluded (must keep it).
        let logits = logits_from_probs(&[0.9, 0.05, 0.05]);
        let xtc = XtcSampler::new(0.2, 1.0);
        assert!(xtc.excluded(&logits).is_empty());
    }

    #[test]
    fn three_confident_keeps_only_lowest() {
        let logits = logits_from_probs(&[0.4, 0.3, 0.2, 0.1]);
        let xtc = XtcSampler::new(0.15, 1.0);
        let mut ex = xtc.excluded(&logits);
        ex.sort_unstable();
        // above 0.15: tokens 0,1,2. keep token 2 (0.2, lowest), exclude 0 and 1.
        assert_eq!(ex, vec![0, 1]);
    }

    #[test]
    fn apply_masks_excluded_to_neg_inf() {
        let mut logits = logits_from_probs(&[0.5, 0.4, 0.1]);
        let xtc = XtcSampler::new(0.15, 1.0);
        let n = xtc.apply_with_roll(&mut logits, 0.0); // roll < probability → fire
        assert_eq!(n, 1);
        assert_eq!(logits[0], f32::NEG_INFINITY);
        assert!(logits[1].is_finite());
        assert!(logits[2].is_finite());
    }

    #[test]
    fn does_not_fire_when_roll_exceeds_probability() {
        let mut logits = logits_from_probs(&[0.5, 0.4, 0.1]);
        let before = logits.clone();
        let xtc = XtcSampler::new(0.15, 0.5);
        let n = xtc.apply_with_roll(&mut logits, 0.9); // 0.9 >= 0.5 → no-op
        assert_eq!(n, 0);
        assert_eq!(logits, before);
    }

    #[test]
    fn probability_zero_never_fires() {
        let xtc = XtcSampler::new(0.15, 0.0);
        assert!(!xtc.is_active());
        let mut logits = logits_from_probs(&[0.5, 0.4, 0.1]);
        let before = logits.clone();
        assert_eq!(xtc.apply_with_roll(&mut logits, 0.0), 0);
        assert_eq!(logits, before);
    }

    #[test]
    fn threshold_boundary_inclusive() {
        // a token exactly at threshold counts as confident.
        let logits = logits_from_probs(&[0.5, 0.3, 0.2]);
        let xtc = XtcSampler::new(0.2, 1.0);
        let mut ex = xtc.excluded(&logits);
        ex.sort_unstable();
        // 0.2 is >= 0.2 → token 2 included; above = {0,1,2}; keep 2, exclude 0,1.
        assert_eq!(ex, vec![0, 1]);
    }

    #[test]
    fn seeded_activation_is_deterministic() {
        let xtc = XtcSampler::new(0.15, 0.5);
        let base = logits_from_probs(&[0.5, 0.4, 0.1]);
        let mut a = base.clone();
        let mut b = base.clone();
        let na = xtc.apply_seeded(&mut a, 42);
        let nb = xtc.apply_seeded(&mut b, 42);
        assert_eq!(na, nb);
        assert_eq!(a, b);
    }

    #[test]
    fn high_probability_fires_often_over_seeds() {
        // with probability 1.0 every seed should fire when exclusion is possible.
        let xtc = XtcSampler::new(0.15, 1.0);
        let base = logits_from_probs(&[0.5, 0.4, 0.1]);
        let mut fired = 0;
        for seed in 0..50u64 {
            let mut l = base.clone();
            if xtc.apply_seeded(&mut l, seed) > 0 {
                fired += 1;
            }
        }
        assert_eq!(fired, 50);
    }

    #[test]
    fn roughly_half_fire_at_probability_half() {
        let xtc = XtcSampler::new(0.15, 0.5);
        let base = logits_from_probs(&[0.5, 0.4, 0.1]);
        let mut fired = 0;
        for seed in 0..400u64 {
            let mut l = base.clone();
            if xtc.apply_seeded(&mut l, seed) > 0 {
                fired += 1;
            }
        }
        // expect ~200; allow a generous band for the small-sample roll.
        assert!((150..=250).contains(&fired), "fired {fired}/400");
    }

    #[test]
    fn empty_and_uniform_inputs() {
        let xtc = XtcSampler::default();
        assert!(xtc.excluded(&[]).is_empty());
        // all -inf (degenerate) → softmax all zero → nothing above threshold.
        assert!(
            xtc.excluded(&[f32::NEG_INFINITY, f32::NEG_INFINITY])
                .is_empty()
        );
    }

    #[test]
    fn serde_round_trip() {
        let xtc = XtcSampler::new(0.12, 0.66);
        let j = serde_json::to_string(&xtc).unwrap();
        let back: XtcSampler = serde_json::from_str(&j).unwrap();
        assert_eq!(xtc, back);
        assert!(approx(back.threshold, 0.12));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
