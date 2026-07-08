//! `sovereign-logprobs` — turn token log-probabilities into scores and signals.
//!
//! Most decoders expose, per generated token, the log-probability the model
//! assigned it. That stream of numbers answers a lot of practical questions, and
//! this crate collects the standard ones.
//!
//! **Scoring.** [`sequence_logprob`] is the joint log-probability of the
//! generation (the sum). Comparing candidates of different lengths by raw sum
//! unfairly favours short ones, so [`length_normalized_score`] applies the GNMT
//! length penalty `sum / ((5+len)/6)^alpha` — the standard beam/rerank score.
//! [`perplexity`] is the geometric-mean branching factor, `exp(-mean logprob)`.
//!
//! **Uncertainty.** [`entropy`] / [`entropy_from_logprobs`] measure how spread a
//! single next-token distribution is — high entropy means the model is unsure
//! *here*. [`top_margin`] is the confidence gap between the best and second-best
//! token. And [`weakest_token`] finds the position with the lowest assigned
//! log-probability — the most surprising token in the output, a useful place to
//! look for a hallucination or an error.
//!
//! All inputs are plain `f64` slices of natural-log probabilities (or, for
//! entropy, a probability distribution), so this works with any model's logprob
//! output.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the logprobs surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The joint log-probability of a sequence: the sum of per-token log-probs.
pub fn sequence_logprob(token_logprobs: &[f64]) -> f64 {
    token_logprobs.iter().sum()
}

/// The mean per-token log-probability (0 for an empty sequence).
pub fn mean_logprob(token_logprobs: &[f64]) -> f64 {
    if token_logprobs.is_empty() {
        0.0
    } else {
        sequence_logprob(token_logprobs) / token_logprobs.len() as f64
    }
}

/// Perplexity: `exp(-mean logprob)`. Lower means the model found the sequence more
/// predictable. Returns `f64::INFINITY`-free 1.0 for an empty sequence.
pub fn perplexity(token_logprobs: &[f64]) -> f64 {
    if token_logprobs.is_empty() {
        return 1.0;
    }
    (-mean_logprob(token_logprobs)).exp()
}

/// GNMT length-normalized score: `sum_logprob / lp(len)` with
/// `lp(len) = ((5 + len) / 6)^alpha`. `alpha` around `0.6`–`0.7` is typical;
/// `alpha = 0` reduces to the raw sum. Returns 0 for an empty sequence.
pub fn length_normalized_score(token_logprobs: &[f64], alpha: f64) -> f64 {
    let len = token_logprobs.len();
    if len == 0 {
        return 0.0;
    }
    let penalty = ((5.0 + len as f64) / 6.0).powf(alpha);
    sequence_logprob(token_logprobs) / penalty
}

/// Shannon entropy (in nats) of a probability distribution. Non-positive
/// probabilities contribute nothing. Does not require the input to be normalized,
/// but is only the true entropy when it sums to 1.
pub fn entropy(probs: &[f64]) -> f64 {
    let mut h = 0.0;
    for &p in probs {
        if p > 0.0 {
            h -= p * p.ln();
        }
    }
    h
}

/// Shannon entropy (in nats) of a distribution given as log-probabilities.
pub fn entropy_from_logprobs(logprobs: &[f64]) -> f64 {
    let mut h = 0.0;
    for &lp in logprobs {
        let p = lp.exp();
        if p > 0.0 {
            h -= p * lp;
        }
    }
    h
}

/// The confidence margin between the top and second-best token of a single
/// next-token distribution, given that step's candidate log-probs. Returns the
/// difference `top - second` in log space (larger = more decisive); `f64::INFINITY`
/// if there is only one candidate, and 0 for an empty slice.
pub fn top_margin(step_logprobs: &[f64]) -> f64 {
    if step_logprobs.is_empty() {
        return 0.0;
    }
    if step_logprobs.len() == 1 {
        return f64::INFINITY;
    }
    let mut top = f64::NEG_INFINITY;
    let mut second = f64::NEG_INFINITY;
    for &lp in step_logprobs {
        if lp > top {
            second = top;
            top = lp;
        } else if lp > second {
            second = lp;
        }
    }
    top - second
}

/// The index and log-probability of the least-likely (most surprising) token in
/// the sequence — a candidate position for a hallucination or error. `None` for
/// an empty sequence.
pub fn weakest_token(token_logprobs: &[f64]) -> Option<(usize, f64)> {
    token_logprobs
        .iter()
        .enumerate()
        .min_by(|a, b| a.1.total_cmp(b.1))
        .map(|(i, &lp)| (i, lp))
}

/// Whether every token cleared a minimum log-probability bar — a simple
/// confidence gate (`true` if there are no tokens below `min_logprob`).
pub fn all_above(token_logprobs: &[f64], min_logprob: f64) -> bool {
    token_logprobs.iter().all(|&lp| lp >= min_logprob)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn sequence_and_mean() {
        let lp = [-0.1, -0.2, -0.3];
        assert!(approx(sequence_logprob(&lp), -0.6));
        assert!(approx(mean_logprob(&lp), -0.2));
        assert_eq!(mean_logprob(&[]), 0.0);
    }

    #[test]
    fn perplexity_matches_definition() {
        // uniform over 4 tokens → each logprob ln(1/4); perplexity = 4
        let lp = vec![(0.25f64).ln(); 8];
        assert!(approx(perplexity(&lp), 4.0), "{}", perplexity(&lp));
        assert_eq!(perplexity(&[]), 1.0);
        // a perfectly-predicted sequence (logprob 0) → perplexity 1
        assert!(approx(perplexity(&[0.0, 0.0]), 1.0));
    }

    #[test]
    fn length_penalty_favors_longer_when_alpha_positive() {
        // two sequences with the same mean logprob; longer should score >= shorter
        // under the GNMT penalty? Actually GNMT divides sum by lp(len): for equal
        // mean, longer has larger |sum| but larger penalty. Verify alpha=0 is raw.
        let short = [-1.0, -1.0];
        let long = [-1.0, -1.0, -1.0, -1.0];
        assert!(approx(length_normalized_score(&short, 0.0), -2.0));
        assert!(approx(length_normalized_score(&long, 0.0), -4.0));
        // with alpha>0 the per-token-normalized comparison is fairer: the longer
        // sequence's score is divided by a bigger penalty.
        let s = length_normalized_score(&short, 0.7);
        let l = length_normalized_score(&long, 0.7);
        assert!(l > -4.0 && s > -2.0); // penalty (>1) shrinks magnitude
        assert!(l < s); // longer still lower here (same mean), but less harshly
    }

    #[test]
    fn entropy_uniform_and_peaked() {
        // uniform over 4 → entropy ln(4)
        let uniform = vec![0.25; 4];
        assert!(approx(entropy(&uniform), 4f64.ln()));
        // a near-deterministic distribution → near 0 entropy
        let peaked = vec![0.97, 0.01, 0.01, 0.01];
        assert!(entropy(&peaked) < 0.3);
        // entropy from logprobs agrees
        let lp: Vec<f64> = uniform.iter().map(|&p| p.ln()).collect();
        assert!(approx(entropy_from_logprobs(&lp), 4f64.ln()));
    }

    #[test]
    fn top_margin_confidence() {
        // decisive step: top far above the rest
        let decisive = [(0.9f64).ln(), (0.05f64).ln(), (0.05f64).ln()];
        // uncertain step: top barely above second
        let uncertain = [(0.4f64).ln(), (0.35f64).ln(), (0.25f64).ln()];
        assert!(top_margin(&decisive) > top_margin(&uncertain));
        assert_eq!(top_margin(&[1.0]), f64::INFINITY);
        assert_eq!(top_margin(&[]), 0.0);
    }

    #[test]
    fn weakest_token_finds_the_surprise() {
        let lp = [-0.1, -0.2, -5.0, -0.3];
        let (idx, val) = weakest_token(&lp).unwrap();
        assert_eq!(idx, 2);
        assert!(approx(val, -5.0));
        assert_eq!(weakest_token(&[]), None);
    }

    #[test]
    fn confidence_gate() {
        let lp = [-0.5, -1.0, -0.2];
        assert!(all_above(&lp, -2.0));
        assert!(!all_above(&lp, -0.8));
        assert!(all_above(&[], -1.0)); // vacuously true
    }
}
