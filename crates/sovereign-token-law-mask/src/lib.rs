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

/// Pack an allow-*list* (token ids the caller permits) into the packed `Vec<u64>`
/// allow-mask this crate + [`token_law_combine`] consume. `words` is the mask
/// width `⌈V/64⌉` (so a plane covers the whole vocabulary even when few tokens
/// are allowed); ids `>= words*64` are dropped. This is the seam that lets a
/// dynamic constraint that reports allowed *ids* (e.g.
/// `sovereign-token-grammar-mask`'s `allowed_ids()`, or
/// `sovereign-regex-constrain`) become a token-law *plane* that composes with
/// the others (SDD-501).
#[must_use]
pub fn pack_allowed(ids: &[usize], words: usize) -> Vec<u64> {
    let mut mask = vec![0u64; words];
    for &t in ids {
        let word = t >> 6;
        if word < words {
            mask[word] |= 1u64 << (t & 63);
        }
    }
    mask
}

/// Compose several token-law **planes** — the M00117 "grammar / schema / tool /
/// safety / route" bitsets — into one allowed-token mask per step, so a running
/// model is confined by **all** of them at once (SDD-501). The static planes
/// (safety denylist, tool/schema allow-list — fixed across a generation) are
/// held here; a dynamic plane (a grammar/regex constraint recomputed each
/// position) is AND-combined in via [`TokenLawPlanes::combine_with`]. The
/// combine is the real M00117 [`token_law_combine`] kernel — `And`, so a token
/// survives only if every plane allows it.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct TokenLawPlanes {
    words: usize,
    static_planes: Vec<Vec<u64>>,
}

impl TokenLawPlanes {
    /// A plane set over a `vocab`-token vocabulary (mask width `⌈vocab/64⌉`).
    #[must_use]
    pub fn new(vocab: usize) -> Self {
        Self {
            words: vocab.div_ceil(64),
            static_planes: Vec::new(),
        }
    }

    /// The mask width in `u64` words (`⌈vocab/64⌉`).
    #[must_use]
    pub fn words(&self) -> usize {
        self.words
    }

    /// Add a static plane from a pre-packed allow-mask (widened/truncated to the
    /// vocabulary width so all planes align for the combine).
    #[must_use]
    pub fn with_plane(mut self, mut allow: Vec<u64>) -> Self {
        allow.resize(self.words, 0);
        self.static_planes.push(allow);
        self
    }

    /// Add a static plane from an allow-*list* of token ids (packed here).
    #[must_use]
    pub fn with_allow_ids(self, ids: &[usize]) -> Self {
        let words = self.words;
        self.with_plane(pack_allowed(ids, words))
    }

    /// Number of static planes held.
    #[must_use]
    pub fn plane_count(&self) -> usize {
        self.static_planes.len()
    }

    /// Combine the static planes alone (no dynamic constraint) into one
    /// allow-mask. With no planes this is "all allowed" (identity).
    #[must_use]
    pub fn combine_static(&self) -> Vec<u64> {
        if self.static_planes.is_empty() {
            return vec![u64::MAX; self.words];
        }
        let refs: Vec<&[u64]> = self.static_planes.iter().map(Vec::as_slice).collect();
        token_law_combine(&refs, LawCombine::And)
    }

    /// Combine a dynamic plane — given as the allow-*list* of token ids a
    /// per-position constraint reports (e.g. `TokenGrammarMask::allowed_ids`) —
    /// with all static planes, via the M00117 [`token_law_combine`] `And`
    /// kernel. The result is the set of tokens allowed by the grammar **and**
    /// every policy plane at once: pass it to
    /// `DecoderStack::generate_dynamic_token_law_until` or [`mask_logits`].
    ///
    /// This is the single-dynamic-source case of
    /// [`combine_with_dynamics`](Self::combine_with_dynamics).
    #[must_use]
    pub fn combine_with(&self, dynamic_allow_ids: &[usize]) -> Vec<u64> {
        self.combine_with_dynamics(&[dynamic_allow_ids])
    }

    /// Combine **several** dynamic planes — each an allow-*list* of token ids
    /// reported by an independent per-position constraint (a grammar's
    /// `allowed_ids`, a regex's `allowed_token_ids`, a tool-name enum) — with all
    /// static policy planes, via the M00117 [`token_law_combine`] `And` kernel. A
    /// token survives only if **every** dynamic source **and** every static plane
    /// allows it — so a model can be confined by grammar ∧ regex ∧ policy at once
    /// (SDD-503). With no dynamic and no static planes the result is all-allowed
    /// (identity).
    #[must_use]
    pub fn combine_with_dynamics(&self, dynamic_allow_id_lists: &[&[usize]]) -> Vec<u64> {
        let dynamics: Vec<Vec<u64>> = dynamic_allow_id_lists
            .iter()
            .map(|ids| pack_allowed(ids, self.words))
            .collect();
        let mut refs: Vec<&[u64]> = Vec::with_capacity(dynamics.len() + self.static_planes.len());
        refs.extend(dynamics.iter().map(Vec::as_slice));
        refs.extend(self.static_planes.iter().map(Vec::as_slice));
        if refs.is_empty() {
            return vec![u64::MAX; self.words];
        }
        token_law_combine(&refs, LawCombine::And)
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

    #[test]
    fn pack_allowed_sets_the_right_bits_and_drops_out_of_range() {
        // allow {1, 3, 65} over a 2-word (128-token) mask
        let m = pack_allowed(&[1, 3, 65], 2);
        assert_eq!(m, vec![0b1010u64, 1u64 << 1]); // word0: bits1,3 ; word1: bit65-64=1
        // an id past the width is dropped, not a panic
        assert_eq!(pack_allowed(&[200], 1), vec![0u64]);
    }

    #[test]
    fn planes_and_compose_grammar_with_static_policy() {
        // vocab 8. Static safety plane bans token 5 → allows {0,1,2,3,4,6,7}.
        // Dynamic grammar plane (this step) allows {2, 5, 6}.
        // AND → {2, 6} (5 is grammar-legal but safety-banned; the composition
        // is exactly the M00117 intersection).
        let planes = TokenLawPlanes::new(8).with_allow_ids(&[0, 1, 2, 3, 4, 6, 7]);
        assert_eq!(planes.plane_count(), 1);
        let combined = planes.combine_with(&[2, 5, 6]);
        // combined allow bits = {2,6} = 0b0100_0100 = 0x44
        assert_eq!(combined, vec![0b0100_0100u64]);
        // and it equals the raw kernel of the two packed planes
        let grammar = pack_allowed(&[2, 5, 6], 1);
        let safety = pack_allowed(&[0, 1, 2, 3, 4, 6, 7], 1);
        let refs: [&[u64]; 2] = [&grammar, &safety];
        assert_eq!(combined, token_law_combine(&refs, LawCombine::And));
    }

    #[test]
    fn empty_planes_are_identity_grammar_alone_survives() {
        // No static planes → combine_with is just the (packed) grammar plane.
        let planes = TokenLawPlanes::new(8);
        assert_eq!(planes.combine_static(), vec![u64::MAX]); // all allowed
        assert_eq!(planes.combine_with(&[1, 4]), pack_allowed(&[1, 4], 1));
    }

    #[test]
    fn with_plane_widens_to_the_vocabulary() {
        // a narrow plane (1 word) added to a 2-word plane set is zero-widened
        // so the combine aligns instead of truncating the vocabulary.
        let planes = TokenLawPlanes::new(100).with_plane(vec![0b11u64]); // words = 2
        assert_eq!(planes.words(), 2);
        let combined = planes.combine_with(&[0, 1, 70]);
        // grammar {0,1,70} AND static {0,1} (widened) = {0,1}
        assert_eq!(combined, vec![0b11u64, 0u64]);
    }

    #[test]
    fn multiple_dynamic_planes_all_intersect_with_policy() {
        // vocab 8. Static safety plane bans token 6 → {0,1,2,3,4,5,7}.
        // Dynamic source A (grammar) allows {2,5,6}; dynamic source B (regex)
        // allows {5,6,7}. grammar ∧ regex = {5,6}; ∧ safety (no 6) = {5}.
        // A constraint NO single source expresses — SDD-503 multi-source.
        let planes = TokenLawPlanes::new(8).with_allow_ids(&[0, 1, 2, 3, 4, 5, 7]);
        let a = [2usize, 5, 6];
        let b = [5usize, 6, 7];
        let combined = planes.combine_with_dynamics(&[&a, &b]);
        assert_eq!(combined, pack_allowed(&[5], 1));
    }

    #[test]
    fn combine_with_is_the_single_dynamic_case_of_combine_with_dynamics() {
        let planes = TokenLawPlanes::new(8).with_allow_ids(&[0, 1, 2, 3, 4, 6, 7]);
        let ids = [2usize, 5, 6];
        assert_eq!(
            planes.combine_with(&ids),
            planes.combine_with_dynamics(&[&ids])
        );
    }

    #[test]
    fn no_planes_at_all_is_identity() {
        // no static planes, no dynamic sources → everything allowed.
        let planes = TokenLawPlanes::new(8);
        assert_eq!(planes.combine_with_dynamics(&[]), vec![u64::MAX]);
    }
}
