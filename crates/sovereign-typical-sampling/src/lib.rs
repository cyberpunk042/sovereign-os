//! `sovereign-typical-sampling` — sample from the *typical* tokens, not just the top.
//!
//! Top-p/top-k keep the highest-probability tokens. Locally typical sampling
//! (Meister, Pimentel, Wiher, Cotterell, 2023) keeps a different set: the tokens
//! whose information content (`−log p`) is closest to the distribution's
//! *conditional entropy* `H = −Σ p log p`. The idea, from information theory, is
//! that natural language tends to carry a roughly constant amount of information
//! per token, so a model generates more human-like, less degenerate text when it
//! samples tokens that are *typically surprising* — neither boringly obvious
//! (very low surprisal) nor wildly unlikely (very high surprisal).
//!
//! The procedure: compute `H`; score each token by `|−log p − H|`; sort ascending
//! by that deviation; and keep tokens in that order until their cumulative
//! probability reaches the target `mass` (e.g. `0.95`). That kept set is the
//! "typical set"; renormalize and sample from it.
//!
//! [`typical_set`] returns the kept token indices; [`typical_mask_logits`]
//! truncates a logits slice in place (non-kept tokens → `−∞`) so it drops into an
//! existing sampler. Works from a probability distribution or from logits.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the typical-sampling surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The conditional entropy `H = −Σ p ln p` (nats) of a distribution.
pub fn entropy(probs: &[f64]) -> f64 {
    let mut h = 0.0;
    for &p in probs {
        if p > 0.0 {
            h -= p * p.ln();
        }
    }
    h
}

/// The typical set: indices kept by locally typical sampling at the given
/// cumulative `mass` (clamped to `(0, 1]`). Tokens are added in order of how
/// close their surprisal `−ln p` is to the entropy `H`, until the kept
/// probability reaches `mass`. Returns indices in the order kept (most typical
/// first). An empty or all-zero distribution yields an empty set.
pub fn typical_set(probs: &[f64], mass: f64) -> Vec<usize> {
    let mass = mass.clamp(f64::MIN_POSITIVE, 1.0);
    let total: f64 = probs.iter().filter(|&&p| p > 0.0).sum();
    if total <= 0.0 {
        return Vec::new();
    }
    let h = entropy(probs);
    // deviation of each token's surprisal from the entropy.
    let mut scored: Vec<(usize, f64, f64)> = probs
        .iter()
        .enumerate()
        .filter(|&(_, &p)| p > 0.0)
        .map(|(i, &p)| {
            let surprisal = -p.ln();
            (i, (surprisal - h).abs(), p)
        })
        .collect();
    // sort by deviation ascending; ties by index for determinism.
    scored.sort_by(|a, b| a.1.total_cmp(&b.1).then(a.0.cmp(&b.0)));

    let target = mass * total;
    let mut kept = Vec::new();
    let mut acc = 0.0;
    for (i, _, p) in scored {
        kept.push(i);
        acc += p;
        if acc >= target {
            break;
        }
    }
    kept
}

/// Mask `logits` in place for typical sampling at cumulative `mass`: tokens not in
/// the typical set are set to `f64::NEG_INFINITY`. Returns the number of tokens
/// kept.
pub fn typical_mask_logits(logits: &mut [f32], mass: f64) -> usize {
    let probs = softmax(logits);
    let keep: std::collections::HashSet<usize> = typical_set(&probs, mass).into_iter().collect();
    for (i, l) in logits.iter_mut().enumerate() {
        if !keep.contains(&i) {
            *l = f32::NEG_INFINITY;
        }
    }
    keep.len()
}

/// Numerically-stable softmax of a logits slice (returns probabilities).
fn softmax(logits: &[f32]) -> Vec<f64> {
    let max = logits.iter().cloned().fold(f32::NEG_INFINITY, f32::max) as f64;
    if !max.is_finite() {
        return vec![0.0; logits.len()];
    }
    let exps: Vec<f64> = logits
        .iter()
        .map(|&l| {
            if l == f32::NEG_INFINITY {
                0.0
            } else {
                (l as f64 - max).exp()
            }
        })
        .collect();
    let sum: f64 = exps.iter().sum();
    if sum <= 0.0 {
        return vec![0.0; logits.len()];
    }
    exps.iter().map(|&e| e / sum).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn entropy_values() {
        // uniform over 4 → ln 4
        assert!(approx(entropy(&[0.25, 0.25, 0.25, 0.25]), 4f64.ln()));
        // deterministic → 0
        assert!(approx(entropy(&[1.0, 0.0, 0.0]), 0.0));
    }

    #[test]
    fn typical_set_covers_target_mass() {
        let probs = [0.4, 0.3, 0.2, 0.1];
        let kept = typical_set(&probs, 0.9);
        let mass: f64 = kept.iter().map(|&i| probs[i]).sum();
        assert!(mass >= 0.9 - 1e-9, "kept mass {mass}");
        // not everything is necessarily kept
        assert!(kept.len() <= 4);
    }

    #[test]
    fn peaked_distribution_keeps_few() {
        // one dominant token → small typical set
        let probs = [0.95, 0.03, 0.01, 0.01];
        let kept = typical_set(&probs, 0.9);
        // the dominant token alone exceeds the mass once it's the most typical
        assert!(kept.len() <= 2, "kept {kept:?}");
    }

    #[test]
    fn uniform_keeps_proportional_count() {
        // uniform over 10; mass 0.5 → about half the tokens
        let probs = vec![0.1; 10];
        let kept = typical_set(&probs, 0.5);
        assert_eq!(kept.len(), 5);
    }

    #[test]
    fn excludes_atypical_tail_and_can_drop_argmax() {
        // a distribution where the argmax is *much* less surprising than entropy,
        // and a long flat body sits near the entropy. typical sampling may favor
        // the body. At minimum the very-low-prob tail is excluded at modest mass.
        let probs = [0.6, 0.1, 0.1, 0.1, 0.1];
        let kept = typical_set(&probs, 0.5);
        // not all five kept at mass 0.5
        assert!(kept.len() < 5);
    }

    #[test]
    fn mask_logits_keeps_only_typical() {
        let mut logits = [3.0f32, 1.0, 0.5, 0.2, -2.0];
        let n = typical_mask_logits(&mut logits, 0.8);
        assert!((1..=5).contains(&n));
        // masked-out entries are -inf; kept entries finite
        let finite = logits.iter().filter(|l| l.is_finite()).count();
        assert_eq!(finite, n);
        assert!(logits.contains(&f32::NEG_INFINITY) || n == 5);
    }

    #[test]
    fn empty_and_degenerate() {
        assert!(typical_set(&[], 0.9).is_empty());
        assert!(typical_set(&[0.0, 0.0], 0.9).is_empty());
    }

    #[test]
    fn mass_one_keeps_all_nonzero() {
        let probs = [0.5, 0.3, 0.2];
        let kept = typical_set(&probs, 1.0);
        assert_eq!(kept.len(), 3);
    }

    #[test]
    fn deterministic_ordering() {
        let probs = [0.25, 0.25, 0.25, 0.25];
        let a = typical_set(&probs, 0.5);
        let b = typical_set(&probs, 0.5);
        assert_eq!(a, b);
    }
}
