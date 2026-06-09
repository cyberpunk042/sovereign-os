//! `sovereign-watermark` — a statistical signature in generated text.
//!
//! A sovereign system should be able to tell whether a piece of text came from
//! *its* model. Watermarking (Kirchenbauer et al., 2023) does this without
//! storing anything: at each generation step, hash the previous token (with a
//! secret key) to deterministically split the vocabulary into a **green** set of
//! fraction `gamma` and the rest "red", then add a bias `delta` to the green
//! logits. The model still generates fluent text, but it now prefers green tokens
//! slightly more often than chance — a signal invisible to a reader.
//!
//! **Detection** needs no model, only the text and the key: walk the tokens, and
//! for each one check whether it was green given its predecessor. Under the null
//! hypothesis (text not from the watermarked model) the green count is
//! `Binomial(T, gamma)`, so the **z-score**
//! `(green − gamma·T) / sqrt(T·gamma·(1−gamma))` is large only for watermarked
//! text. A threshold around `z = 4` gives a very low false-positive rate.
//!
//! [`Watermark::bias_logits`] applies the boost during generation;
//! [`Watermark::detect`] returns the z-score; [`Watermark::is_watermarked`]
//! thresholds it. Membership is computed by hashing `(key, prev_token, token)`,
//! so no green set is ever materialized.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the watermark surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A watermarking scheme parameterized by green fraction, bias, and secret key.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Watermark {
    /// Fraction of the vocabulary that is "green" at each step, in `(0, 1)`.
    pub gamma: f64,
    /// Logit boost added to green tokens during generation.
    pub delta: f32,
    /// Secret key mixed into the hash (so only the holder can detect).
    pub key: u64,
}

impl Watermark {
    /// A scheme with the given parameters.
    ///
    /// # Panics
    /// Panics if `gamma` is not in `(0, 1)`.
    pub fn new(gamma: f64, delta: f32, key: u64) -> Self {
        assert!(gamma > 0.0 && gamma < 1.0, "gamma must be in (0, 1)");
        Self { gamma, delta, key }
    }

    /// Whether `token` is in the green set for predecessor `prev_token`.
    pub fn is_green(&self, prev_token: usize, token: usize) -> bool {
        let h = mix(self.key, prev_token as u64, token as u64);
        // uniform in [0, 1); green iff below gamma.
        let u = (h >> 11) as f64 / (1u64 << 53) as f64;
        u < self.gamma
    }

    /// Add the green boost to `logits` in place for the step following
    /// `prev_token`. Green tokens get `+delta`.
    pub fn bias_logits(&self, logits: &mut [f32], prev_token: usize) {
        for (t, l) in logits.iter_mut().enumerate() {
            if self.is_green(prev_token, t) {
                *l += self.delta;
            }
        }
    }

    /// Count the green tokens in `tokens` (positions `1..`, each judged against
    /// its predecessor). Returns `(green_count, total_scored)`.
    pub fn green_count(&self, tokens: &[usize]) -> (usize, usize) {
        if tokens.len() < 2 {
            return (0, 0);
        }
        let mut green = 0;
        for w in tokens.windows(2) {
            if self.is_green(w[0], w[1]) {
                green += 1;
            }
        }
        (green, tokens.len() - 1)
    }

    /// The detection z-score for `tokens`: how many standard deviations the green
    /// count exceeds the chance expectation. Larger = stronger watermark evidence.
    /// Returns 0.0 for sequences too short to score.
    pub fn detect(&self, tokens: &[usize]) -> f64 {
        let (green, total) = self.green_count(tokens);
        if total == 0 {
            return 0.0;
        }
        let t = total as f64;
        let expected = self.gamma * t;
        let var = t * self.gamma * (1.0 - self.gamma);
        if var <= 0.0 {
            return 0.0;
        }
        (green as f64 - expected) / var.sqrt()
    }

    /// Whether `tokens` are watermarked at the given z-score threshold (a common
    /// choice is `4.0`).
    pub fn is_watermarked(&self, tokens: &[usize], z_threshold: f64) -> bool {
        self.detect(tokens) >= z_threshold
    }
}

/// Mix a key and two token ids into a 64-bit hash (splitmix-style finalizer).
fn mix(key: u64, a: u64, b: u64) -> u64 {
    let mut z = key
        .wrapping_mul(0x9E37_79B9_7F4A_7C15)
        .wrapping_add(a.wrapping_mul(0xBF58_476D_1CE4_E5B9))
        .wrapping_add(b.wrapping_mul(0x94D0_49BB_1331_11EB));
    z ^= z >> 30;
    z = z.wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z ^= z >> 27;
    z = z.wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Generate a watermarked token sequence greedily: at each step bias the
    /// logits and pick the argmax. Uses a flat base distribution so the watermark
    /// is what drives the choice.
    fn generate_watermarked(wm: &Watermark, vocab: usize, len: usize, start: usize) -> Vec<usize> {
        let mut tokens = vec![start];
        for _ in 1..len {
            let mut logits = vec![0.0f32; vocab];
            wm.bias_logits(&mut logits, *tokens.last().unwrap());
            // argmax (ties → lowest index)
            let next = (0..vocab)
                .max_by(|&a, &b| logits[a].total_cmp(&logits[b]).then(b.cmp(&a)))
                .unwrap();
            tokens.push(next);
        }
        tokens
    }

    /// An unwatermarked sequence: deterministic pseudo-random tokens.
    fn generate_random(vocab: usize, len: usize, seed: u64) -> Vec<usize> {
        let mut s = seed | 1;
        (0..len)
            .map(|_| {
                s = s.wrapping_mul(6364136223846793005).wrapping_add(1);
                ((s >> 33) as usize) % vocab
            })
            .collect()
    }

    #[test]
    fn green_membership_is_deterministic() {
        let wm = Watermark::new(0.5, 2.0, 12345);
        assert_eq!(wm.is_green(3, 7), wm.is_green(3, 7));
    }

    #[test]
    fn green_fraction_is_about_gamma() {
        let wm = Watermark::new(0.25, 2.0, 999);
        // over many (prev, token) pairs, ~25% should be green
        let mut green = 0;
        let n = 10_000;
        for t in 0..n {
            if wm.is_green(t % 50, t) {
                green += 1;
            }
        }
        let frac = green as f64 / n as f64;
        assert!((frac - 0.25).abs() < 0.03, "green fraction {frac}");
    }

    #[test]
    fn bias_boosts_green_tokens() {
        let wm = Watermark::new(0.5, 5.0, 7);
        let mut logits = vec![0.0f32; 20];
        wm.bias_logits(&mut logits, 3);
        for t in 0..20 {
            if wm.is_green(3, t) {
                assert!((logits[t] - 5.0).abs() < 1e-6);
            } else {
                assert!((logits[t]).abs() < 1e-6);
            }
        }
    }

    #[test]
    fn watermarked_text_has_high_z() {
        let wm = Watermark::new(0.5, 4.0, 42);
        let tokens = generate_watermarked(&wm, 100, 200, 0);
        let z = wm.detect(&tokens);
        // greedy-green generation → nearly all green → very high z
        assert!(z > 5.0, "z {z}");
        assert!(wm.is_watermarked(&tokens, 4.0));
    }

    #[test]
    fn unwatermarked_text_has_low_z() {
        let wm = Watermark::new(0.5, 4.0, 42);
        let tokens = generate_random(100, 500, 13);
        let z = wm.detect(&tokens);
        assert!(z.abs() < 4.0, "random text z too high: {z}");
        assert!(!wm.is_watermarked(&tokens, 4.0));
    }

    #[test]
    fn wrong_key_does_not_detect() {
        let wm = Watermark::new(0.5, 4.0, 42);
        let tokens = generate_watermarked(&wm, 100, 200, 0);
        // a detector with the wrong key sees only chance-level green
        let wrong = Watermark::new(0.5, 4.0, 99999);
        assert!(
            !wrong.is_watermarked(&tokens, 4.0),
            "wrong key detected: z={}",
            wrong.detect(&tokens)
        );
    }

    #[test]
    fn short_sequences_score_zero() {
        let wm = Watermark::new(0.5, 4.0, 1);
        assert_eq!(wm.detect(&[]), 0.0);
        assert_eq!(wm.detect(&[5]), 0.0);
    }

    #[test]
    fn serde_round_trip() {
        let wm = Watermark::new(0.3, 2.5, 777);
        let j = serde_json::to_string(&wm).unwrap();
        assert_eq!(serde_json::from_str::<Watermark>(&j).unwrap(), wm);
    }
}
