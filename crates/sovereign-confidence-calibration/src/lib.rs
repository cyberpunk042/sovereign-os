//! `sovereign-confidence-calibration` — make predicted probabilities trustworthy.
//!
//! A model's softmax confidence is usually *miscalibrated*: a modern network that
//! says "90% sure" may be right only 70% of the time (over-confident) or the
//! reverse. A runtime that wants to threshold, route, or abstain on confidence
//! needs probabilities that mean what they say. This crate provides the standard
//! post-hoc fix and the metrics to check it.
//!
//! **Temperature scaling** ([`fit_temperature`]) learns a single scalar `T` that
//! divides the logits before the softmax, then picks the `T` minimizing negative
//! log-likelihood on a held-out set. `T > 1` softens over-confident predictions,
//! `T < 1` sharpens under-confident ones; crucially it never changes the argmax,
//! so accuracy is untouched while the probabilities become honest.
//!
//! **Expected Calibration Error** ([`expected_calibration_error`]) bins
//! predictions by their confidence and measures the average gap between confidence
//! and actual accuracy in each bin — the headline calibration number. The
//! **Brier score** ([`brier_score`]) is the mean squared error of the predicted
//! probability against the outcome, a proper scoring rule that rewards both
//! calibration and sharpness.
//!
//! All inputs are plain slices of logits/probabilities and integer labels, so
//! this works with any classifier or next-token head.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the calibration surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Numerically-stable softmax of `logits` divided by `temperature`.
///
/// # Panics
/// Panics if `temperature <= 0` or `logits` is empty.
pub fn softmax_t(logits: &[f64], temperature: f64) -> Vec<f64> {
    assert!(temperature > 0.0, "temperature must be > 0");
    assert!(!logits.is_empty(), "logits must be non-empty");
    let max = logits.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let exps: Vec<f64> = logits
        .iter()
        .map(|&l| ((l - max) / temperature).exp())
        .collect();
    let sum: f64 = exps.iter().sum();
    exps.iter().map(|&e| e / sum).collect()
}

/// Mean negative log-likelihood of the true `labels` under `logits` scaled by
/// `temperature`. Each row of `logits` is one example's class logits.
pub fn nll(logits: &[Vec<f64>], labels: &[usize], temperature: f64) -> f64 {
    if logits.is_empty() {
        return 0.0;
    }
    let mut total = 0.0;
    for (row, &y) in logits.iter().zip(labels.iter()) {
        let p = softmax_t(row, temperature);
        let py = p.get(y).copied().unwrap_or(1e-12).max(1e-12);
        total -= py.ln();
    }
    total / logits.len() as f64
}

/// Fit the temperature in `(0, max_t]` that minimizes NLL on the labelled set, by
/// golden-section search. Returns `1.0` (a no-op) for empty input.
pub fn fit_temperature(logits: &[Vec<f64>], labels: &[usize]) -> f64 {
    if logits.is_empty() {
        return 1.0;
    }
    // golden-section minimization over [lo, hi].
    let (mut lo, mut hi) = (0.05f64, 10.0f64);
    let gr = (5f64.sqrt() - 1.0) / 2.0; // 0.618...
    let mut c = hi - gr * (hi - lo);
    let mut d = lo + gr * (hi - lo);
    let mut fc = nll(logits, labels, c);
    let mut fd = nll(logits, labels, d);
    for _ in 0..100 {
        if (hi - lo).abs() < 1e-4 {
            break;
        }
        if fc < fd {
            hi = d;
            d = c;
            fd = fc;
            c = hi - gr * (hi - lo);
            fc = nll(logits, labels, c);
        } else {
            lo = c;
            c = d;
            fc = fd;
            d = lo + gr * (hi - lo);
            fd = nll(logits, labels, d);
        }
    }
    (lo + hi) / 2.0
}

/// Expected Calibration Error over `bins` equal-width confidence bins.
///
/// `confidences[i]` is the model's probability for its predicted class on example
/// `i`; `correct[i]` is whether that prediction was right. ECE is the
/// sample-weighted average of `|accuracy − confidence|` per bin, in `[0, 1]`
/// (lower is better calibrated).
///
/// # Panics
/// Panics if `bins == 0` or the slices differ in length.
pub fn expected_calibration_error(confidences: &[f64], correct: &[bool], bins: usize) -> f64 {
    assert!(bins > 0, "bins must be > 0");
    assert_eq!(confidences.len(), correct.len(), "length mismatch");
    let n = confidences.len();
    if n == 0 {
        return 0.0;
    }
    let mut bin_conf = vec![0.0f64; bins];
    let mut bin_acc = vec![0.0f64; bins];
    let mut bin_cnt = vec![0usize; bins];
    for (&c, &ok) in confidences.iter().zip(correct.iter()) {
        // bin index for confidence in [0,1]; 1.0 goes in the last bin.
        let mut b = (c * bins as f64).floor() as usize;
        if b >= bins {
            b = bins - 1;
        }
        bin_conf[b] += c;
        bin_acc[b] += if ok { 1.0 } else { 0.0 };
        bin_cnt[b] += 1;
    }
    let mut ece = 0.0;
    for b in 0..bins {
        if bin_cnt[b] == 0 {
            continue;
        }
        let conf = bin_conf[b] / bin_cnt[b] as f64;
        let acc = bin_acc[b] / bin_cnt[b] as f64;
        ece += (bin_cnt[b] as f64 / n as f64) * (acc - conf).abs();
    }
    ece
}

/// Multiclass Brier score: mean squared error between the predicted probability
/// vectors and the one-hot true labels (lower is better). Each row of `probs`
/// must be a probability distribution.
pub fn brier_score(probs: &[Vec<f64>], labels: &[usize]) -> f64 {
    if probs.is_empty() {
        return 0.0;
    }
    let mut total = 0.0;
    for (row, &y) in probs.iter().zip(labels.iter()) {
        for (c, &p) in row.iter().enumerate() {
            let target = if c == y { 1.0 } else { 0.0 };
            total += (p - target) * (p - target);
        }
    }
    total / probs.len() as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64, tol: f64) -> bool {
        (a - b).abs() < tol
    }

    #[test]
    fn softmax_temperature_softens_and_sharpens() {
        let logits = [2.0, 1.0, 0.0];
        let p1 = softmax_t(&logits, 1.0);
        let hot = softmax_t(&logits, 5.0); // higher T → more uniform
        let cold = softmax_t(&logits, 0.2); // lower T → more peaked
        assert!(hot[0] < p1[0], "hot should be less peaked");
        assert!(cold[0] > p1[0], "cold should be more peaked");
        // all distributions sum to 1
        for p in [&p1, &hot, &cold] {
            assert!(approx(p.iter().sum::<f64>(), 1.0, 1e-12));
        }
    }

    #[test]
    fn fit_temperature_softens_overconfident_logits() {
        // construct an over-confident model: huge logits but often wrong.
        // example correct class alternates, but logits always strongly favor 0.
        let mut logits = Vec::new();
        let mut labels = Vec::new();
        for i in 0..100 {
            logits.push(vec![5.0, 0.0]); // very confident in class 0
            labels.push(if i % 2 == 0 { 0 } else { 1 }); // right only half the time
        }
        let t = fit_temperature(&logits, &labels);
        // it should raise the temperature well above 1 to soften confidence
        assert!(t > 1.5, "temperature {t} should soften over-confidence");
        // and the softened NLL should be lower than the raw NLL
        assert!(nll(&logits, &labels, t) < nll(&logits, &labels, 1.0));
    }

    #[test]
    fn fit_temperature_near_one_for_calibrated_data() {
        // well-calibrated: confidence matches accuracy. class-0 logit margin
        // chosen so softmax ~0.73, and ~73% are actually class 0.
        let mut logits = Vec::new();
        let mut labels = Vec::new();
        for i in 0..100 {
            logits.push(vec![1.0, 0.0]); // softmax ≈ [0.731, 0.269]
            labels.push(if i < 73 { 0 } else { 1 });
        }
        let t = fit_temperature(&logits, &labels);
        // already roughly calibrated → temperature should stay near 1
        assert!(t > 0.6 && t < 1.8, "temperature {t} should be near 1");
    }

    #[test]
    fn ece_zero_for_perfectly_calibrated() {
        // bin of confidence 0.7 where exactly 70% are correct → ECE 0
        let mut conf = Vec::new();
        let mut correct = Vec::new();
        for i in 0..100 {
            conf.push(0.7);
            correct.push(i < 70);
        }
        let ece = expected_calibration_error(&conf, &correct, 10);
        assert!(ece < 1e-9, "ece {ece}");
    }

    #[test]
    fn ece_detects_overconfidence() {
        // claims 0.99 confidence but only 50% correct → large ECE ≈ 0.49
        let mut conf = Vec::new();
        let mut correct = Vec::new();
        for i in 0..100 {
            conf.push(0.99);
            correct.push(i % 2 == 0);
        }
        let ece = expected_calibration_error(&conf, &correct, 10);
        assert!(approx(ece, 0.49, 0.02), "ece {ece}");
    }

    #[test]
    fn brier_rewards_good_probabilities() {
        // confident-and-correct beats uncertain
        let confident = vec![vec![0.95, 0.05], vec![0.05, 0.95]];
        let unsure = vec![vec![0.5, 0.5], vec![0.5, 0.5]];
        let labels = [0usize, 1];
        assert!(brier_score(&confident, &labels) < brier_score(&unsure, &labels));
        // confident-and-wrong is worst
        let wrong = vec![vec![0.05, 0.95], vec![0.95, 0.05]];
        assert!(brier_score(&wrong, &labels) > brier_score(&unsure, &labels));
    }

    #[test]
    fn temperature_scaling_preserves_argmax() {
        let logits = [3.0, 1.0, 2.0];
        for t in [0.1, 1.0, 5.0, 50.0] {
            let p = softmax_t(&logits, t);
            let argmax = p
                .iter()
                .enumerate()
                .max_by(|a, b| a.1.total_cmp(b.1))
                .unwrap()
                .0;
            assert_eq!(argmax, 0, "argmax changed at T={t}");
        }
    }

    #[test]
    fn empty_inputs_are_safe() {
        assert_eq!(fit_temperature(&[], &[]), 1.0);
        assert_eq!(nll(&[], &[], 1.0), 0.0);
        assert_eq!(brier_score(&[], &[]), 0.0);
        assert_eq!(expected_calibration_error(&[], &[], 10), 0.0);
    }
}
