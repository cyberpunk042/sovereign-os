//! `sovereign-token-law-mask` — the M002 token-law bitset as a decode-time
//! logit mask.
//!
//! This is the **first real per-token call site of the M002 bit-machine**
//! (SDD-500). The M00117 `token_law_combine` kernel
//! ([`sovereign_simd::cheats`]) intersects the per-vocabulary allow-bitsets of
//! the active laws (grammar / schema / tool / safety / route) into one
//! allow-mask; this crate turns that mask into a logit transform — a token
//! whose allow-bit is `0` is set to `-inf` before sampling, so the model
//! **cannot** emit it. "Policy becomes bits", now gating a running model.
//!
//! ## Honest scope (SDD-500)
//! This constrains the **in-repo** decode stack
//! ([`sovereign-decoder-stack`]) — the box's own sovereign inference path. It
//! does **not** constrain the external-proxy `/v1/messages` path, which
//! generates out-of-process (llama-server / vLLM) and exposes no logits. That
//! boundary is a deliberate non-goal, not an oversight.
//!
//! ## Correctness, not acceleration (SDD-500 Q1)
//! The mask is exact and scalar, and **always applies when a law set is
//! present**, regardless of `avx-mode`. Only the AVX-512 acceleration of the
//! *law combine* ([`sovereign_simd::cheats::token_law_combine`]) is
//! `avx-mode`-gated — a legal token set is policy, and policy holds however AVX
//! is configured.
//!
//! Composes [`sovereign-logit-pipeline`] (the [`LogitProcessor`] trait) and
//! [`sovereign-simd`] (the `token_law_combine` kernel).
//!
//! [`sovereign-decoder-stack`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-decoder-stack
//! [`sovereign-logit-pipeline`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-logit-pipeline
//! [`sovereign-simd`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-simd
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_logit_pipeline::LogitProcessor;
use sovereign_simd::cheats::{LawCombine, allowed_token_count, token_law_combine};

/// Schema version of the token-law-mask surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Apply a token-law allow-mask to a logit row in place: every token whose
/// allow-bit is `0` is set to `-inf`.
///
/// `allow` is a per-vocabulary bitset packed 64 tokens per `u64` word (bit `t`
/// set = token `t` allowed). A token index past the mask's width is treated as
/// **disallowed** — the mask is authoritative, so a token it does not cover is
/// not in the allow set. Exact and scalar (no AVX needed for correctness).
pub fn mask_logits(allow: &[u64], logits: &mut [f32]) {
    for (t, l) in logits.iter_mut().enumerate() {
        let word = t >> 6; // t / 64
        let bit = t & 63; // t % 64
        let allowed = allow.get(word).is_some_and(|w| (w >> bit) & 1 == 1);
        if !allowed {
            *l = f32::NEG_INFINITY;
        }
    }
}

/// A decode-time token-law logit mask: the combined allow-set the model may
/// emit this step. Install it as a [`LogitProcessor`] in a
/// [`sovereign_logit_pipeline::LogitPipeline`], or apply it directly with
/// [`TokenLawMask::apply`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TokenLawMask {
    /// The combined allow-mask (`⌈V/64⌉` words; bit `t` set = token `t` allowed).
    allow: Vec<u64>,
}

impl TokenLawMask {
    /// Wrap a pre-combined allow-mask (the caller already ran the combine, or
    /// supplies a single law directly — SDD-500 Q4 v1 path).
    #[must_use]
    pub fn new(allow: Vec<u64>) -> Self {
        Self { allow }
    }

    /// Combine the active laws — each a per-vocabulary allow-bitset — into one
    /// mask via the M00117 [`token_law_combine`] kernel. [`LawCombine::And`]
    /// (the safe default) keeps a token only if **every** law allows it;
    /// [`LawCombine::Or`] keeps it if any law does.
    #[must_use]
    pub fn from_laws(laws: &[&[u64]], combine: LawCombine) -> Self {
        Self {
            allow: token_law_combine(laws, combine),
        }
    }

    /// The raw combined allow-mask.
    #[must_use]
    pub fn allow(&self) -> &[u64] {
        &self.allow
    }

    /// How many tokens the mask allows (popcount over the mask).
    #[must_use]
    pub fn allowed_count(&self) -> u32 {
        allowed_token_count(&self.allow)
    }

    /// Apply the mask to a logit row in place — disallowed tokens go to `-inf`.
    pub fn apply(&self, logits: &mut [f32]) {
        mask_logits(&self.allow, logits);
    }
}

impl LogitProcessor for TokenLawMask {
    fn process(&self, _history: &[usize], logits: &mut [f32]) {
        self.apply(logits);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Allow only tokens 1 and 3 in a 4-token vocab → mask word = 0b1010 = 10.
    fn allow_1_and_3() -> Vec<u64> {
        vec![0b1010u64]
    }

    #[test]
    fn masks_exactly_the_disallowed_tokens() {
        let mut logits = [0.5f32, 0.5, 0.5, 0.5];
        mask_logits(&allow_1_and_3(), &mut logits);
        assert_eq!(logits[0], f32::NEG_INFINITY);
        assert_eq!(logits[1], 0.5);
        assert_eq!(logits[2], f32::NEG_INFINITY);
        assert_eq!(logits[3], 0.5);
    }

    #[test]
    fn token_past_mask_width_is_disallowed() {
        // vocab of 3 but mask only covers word 0; token 64 (word 1) is absent.
        let mut logits = vec![0.0f32; 66];
        mask_logits(&[u64::MAX], &mut logits); // word 0: all 64 allowed
        for l in logits.iter().take(64) {
            assert_eq!(*l, 0.0); // tokens 0..64 allowed
        }
        assert_eq!(logits[64], f32::NEG_INFINITY); // beyond mask → disallowed
        assert_eq!(logits[65], f32::NEG_INFINITY);
    }

    #[test]
    fn empty_mask_bans_everything_full_mask_is_noop() {
        let mut all_banned = [1.0f32, 2.0, 3.0];
        mask_logits(&[], &mut all_banned);
        assert!(all_banned.iter().all(|l| *l == f32::NEG_INFINITY));

        let mut untouched = [1.0f32, 2.0, 3.0];
        mask_logits(&[u64::MAX], &mut untouched);
        assert_eq!(untouched, [1.0, 2.0, 3.0]);
    }

    #[test]
    fn from_laws_intersects_and_matches_the_kernel() {
        // Two laws over a 4-token vocab: law A allows {1,2,3}, law B allows {2,3}.
        let law_a = [0b1110u64]; // 1,2,3
        let law_b = [0b1100u64]; // 2,3
        let laws: [&[u64]; 2] = [&law_a, &law_b];
        let m = TokenLawMask::from_laws(&laws, LawCombine::And);
        // AND → {2,3} = 0b1100
        assert_eq!(m.allow(), &[0b1100u64]);
        assert_eq!(
            m.allow(),
            token_law_combine(&laws, LawCombine::And).as_slice()
        );
        assert_eq!(m.allowed_count(), 2);
    }

    #[test]
    fn logit_processor_impl_matches_apply() {
        let m = TokenLawMask::new(allow_1_and_3());
        let mut via_trait = [0.5f32; 4];
        let mut via_apply = [0.5f32; 4];
        m.process(&[], &mut via_trait);
        m.apply(&mut via_apply);
        assert_eq!(via_trait, via_apply);
    }
}
