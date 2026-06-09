//! `sovereign-classification-metrics` — score classifiers and routers.
//!
//! A router that picks a model, an intent classifier, a safety gate — all are
//! classifiers, and tuning them needs more than raw accuracy (which lies on
//! imbalanced data). This crate is the standard classification metric kit built
//! around a [`ConfusionMatrix`].
//!
//! From the matrix you get **accuracy**, and per class the **precision**
//! (of what we predicted class `c`, how much really was), **recall** (of the true
//! class `c`, how much we caught), and their **F1**. Those are summarised three
//! ways: **macro** (unweighted class average — treats rare classes equally),
//! **micro** (pool all decisions — equals accuracy for single-label tasks), and
//! **weighted** (by class support). **Cohen's kappa** corrects accuracy for the
//! agreement you'd expect by chance.
//!
//! For binary scorers, [`roc_auc`] computes the area under the ROC curve by the
//! rank (Mann-Whitney U) method — the probability a random positive outranks a
//! random negative — which needs scores, not just hard labels, and handles ties.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the classification-metrics surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A square confusion matrix over `n` classes; `counts[actual][predicted]`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConfusionMatrix {
    n: usize,
    counts: Vec<Vec<u64>>,
}

/// Per-class precision/recall/F1 with support (number of true instances).
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct ClassScore {
    /// Precision for this class.
    pub precision: f64,
    /// Recall for this class.
    pub recall: f64,
    /// F1 for this class.
    pub f1: f64,
    /// Number of true instances of this class.
    pub support: u64,
}

impl ConfusionMatrix {
    /// An all-zero matrix for `n` classes (labels `0..n`).
    ///
    /// # Panics
    /// Panics if `n == 0`.
    pub fn new(n: usize) -> Self {
        assert!(n > 0, "need at least one class");
        Self {
            n,
            counts: vec![vec![0; n]; n],
        }
    }

    /// Build from paired `(predicted, actual)` label slices over `n` classes.
    ///
    /// # Panics
    /// Panics if the slices differ in length or contain a label `>= n`.
    pub fn from_labels(predicted: &[usize], actual: &[usize], n: usize) -> Self {
        assert_eq!(predicted.len(), actual.len(), "length mismatch");
        let mut m = Self::new(n);
        for (&p, &a) in predicted.iter().zip(actual.iter()) {
            m.record(p, a);
        }
        m
    }

    /// Record one prediction.
    ///
    /// # Panics
    /// Panics if either label is `>= n`.
    pub fn record(&mut self, predicted: usize, actual: usize) {
        assert!(predicted < self.n && actual < self.n, "label out of range");
        self.counts[actual][predicted] += 1;
    }

    /// The number of classes.
    pub fn classes(&self) -> usize {
        self.n
    }

    /// The raw count for `(actual, predicted)`.
    pub fn count(&self, actual: usize, predicted: usize) -> u64 {
        self.counts[actual][predicted]
    }

    /// Total recorded predictions.
    pub fn total(&self) -> u64 {
        self.counts.iter().flatten().sum()
    }

    /// Overall accuracy (correct / total). 0 if nothing recorded.
    pub fn accuracy(&self) -> f64 {
        let total = self.total();
        if total == 0 {
            return 0.0;
        }
        let correct: u64 = (0..self.n).map(|c| self.counts[c][c]).sum();
        correct as f64 / total as f64
    }

    /// Per-class scores (index `c` is class `c`).
    pub fn class_scores(&self) -> Vec<ClassScore> {
        (0..self.n)
            .map(|c| {
                let tp = self.counts[c][c] as f64;
                let predicted_c: u64 = (0..self.n).map(|a| self.counts[a][c]).sum();
                let actual_c: u64 = self.counts[c].iter().sum();
                let precision = if predicted_c == 0 {
                    0.0
                } else {
                    tp / predicted_c as f64
                };
                let recall = if actual_c == 0 {
                    0.0
                } else {
                    tp / actual_c as f64
                };
                let f1 = if precision + recall == 0.0 {
                    0.0
                } else {
                    2.0 * precision * recall / (precision + recall)
                };
                ClassScore {
                    precision,
                    recall,
                    f1,
                    support: actual_c,
                }
            })
            .collect()
    }

    /// Macro-averaged F1 (unweighted mean over classes).
    pub fn macro_f1(&self) -> f64 {
        let scores = self.class_scores();
        scores.iter().map(|s| s.f1).sum::<f64>() / self.n as f64
    }

    /// Macro-averaged precision and recall.
    pub fn macro_precision_recall(&self) -> (f64, f64) {
        let scores = self.class_scores();
        let p = scores.iter().map(|s| s.precision).sum::<f64>() / self.n as f64;
        let r = scores.iter().map(|s| s.recall).sum::<f64>() / self.n as f64;
        (p, r)
    }

    /// Micro-averaged F1. For single-label classification this equals accuracy.
    pub fn micro_f1(&self) -> f64 {
        // pool TP/FP/FN across classes
        let mut tp = 0u64;
        let mut fp = 0u64;
        let mut fn_ = 0u64;
        for c in 0..self.n {
            let tpc = self.counts[c][c];
            let predicted_c: u64 = (0..self.n).map(|a| self.counts[a][c]).sum();
            let actual_c: u64 = self.counts[c].iter().sum();
            tp += tpc;
            fp += predicted_c - tpc;
            fn_ += actual_c - tpc;
        }
        let denom = 2 * tp + fp + fn_;
        if denom == 0 {
            0.0
        } else {
            2.0 * tp as f64 / denom as f64
        }
    }

    /// Support-weighted F1 (mean of per-class F1 weighted by true support).
    pub fn weighted_f1(&self) -> f64 {
        let scores = self.class_scores();
        let total: u64 = scores.iter().map(|s| s.support).sum();
        if total == 0 {
            return 0.0;
        }
        scores.iter().map(|s| s.f1 * s.support as f64).sum::<f64>() / total as f64
    }

    /// Cohen's kappa: `(p_o − p_e) / (1 − p_e)`, agreement corrected for chance.
    /// Ranges from ≤ 0 (no better than chance) to 1 (perfect).
    pub fn cohens_kappa(&self) -> f64 {
        let total = self.total() as f64;
        if total == 0.0 {
            return 0.0;
        }
        let p_o = self.accuracy();
        // expected agreement = sum_c (row_c/total)*(col_c/total)
        let mut p_e = 0.0;
        for c in 0..self.n {
            let row: u64 = self.counts[c].iter().sum();
            let col: u64 = (0..self.n).map(|a| self.counts[a][c]).sum();
            p_e += (row as f64 / total) * (col as f64 / total);
        }
        if (1.0 - p_e).abs() < 1e-12 {
            1.0 // perfect-by-construction (single class)
        } else {
            (p_o - p_e) / (1.0 - p_e)
        }
    }
}

/// Binary ROC-AUC by the rank (Mann-Whitney U) method: the probability that a
/// random positive has a higher score than a random negative, with ties counted
/// as half. `scores[i]` is the model's score for the positive class and
/// `labels[i]` whether instance `i` is actually positive.
///
/// Returns 0.5 (chance) when there are no positives or no negatives.
pub fn roc_auc(scores: &[f64], labels: &[bool]) -> f64 {
    assert_eq!(scores.len(), labels.len(), "length mismatch");
    let n = scores.len();
    if n == 0 {
        return 0.5;
    }
    // rank the scores (average ranks for ties), ranks 1..=n.
    let mut idx: Vec<usize> = (0..n).collect();
    idx.sort_by(|&a, &b| scores[a].total_cmp(&scores[b]));
    let mut ranks = vec![0.0f64; n];
    let mut i = 0;
    while i < n {
        let mut j = i + 1;
        while j < n && scores[idx[j]] == scores[idx[i]] {
            j += 1;
        }
        // average rank for the tie group [i, j)
        let avg = ((i + 1 + j) as f64) / 2.0; // (sum of (i+1..=j))/(count) simplified
        for &k in &idx[i..j] {
            ranks[k] = avg;
        }
        i = j;
    }
    let n_pos = labels.iter().filter(|&&l| l).count();
    let n_neg = n - n_pos;
    if n_pos == 0 || n_neg == 0 {
        return 0.5;
    }
    let sum_pos_ranks: f64 = (0..n).filter(|&k| labels[k]).map(|k| ranks[k]).sum();
    let u = sum_pos_ranks - (n_pos * (n_pos + 1)) as f64 / 2.0;
    u / (n_pos * n_neg) as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn accuracy_and_perfect() {
        // 3-class, all correct
        let pred = [0, 1, 2, 1, 0];
        let act = [0, 1, 2, 1, 0];
        let cm = ConfusionMatrix::from_labels(&pred, &act, 3);
        assert!(approx(cm.accuracy(), 1.0));
        assert!(approx(cm.macro_f1(), 1.0));
        assert!(approx(cm.cohens_kappa(), 1.0));
    }

    #[test]
    fn binary_precision_recall_f1() {
        // class 1 = positive. pred vs act:
        // TP=2, FP=1, FN=1, TN=2
        let pred = [1, 1, 1, 0, 0, 0];
        let act = [1, 1, 0, 1, 0, 0];
        let cm = ConfusionMatrix::from_labels(&pred, &act, 2);
        let s = cm.class_scores();
        // class 1: precision 2/3, recall 2/3, f1 2/3
        assert!(approx(s[1].precision, 2.0 / 3.0), "{}", s[1].precision);
        assert!(approx(s[1].recall, 2.0 / 3.0), "{}", s[1].recall);
        assert!(approx(s[1].f1, 2.0 / 3.0));
        assert_eq!(s[1].support, 3);
        assert!(approx(cm.accuracy(), 4.0 / 6.0));
    }

    #[test]
    fn micro_f1_equals_accuracy_single_label() {
        let pred = [0, 1, 2, 0, 1];
        let act = [0, 2, 2, 0, 1];
        let cm = ConfusionMatrix::from_labels(&pred, &act, 3);
        assert!(
            approx(cm.micro_f1(), cm.accuracy()),
            "micro {} acc {}",
            cm.micro_f1(),
            cm.accuracy()
        );
    }

    #[test]
    fn macro_vs_weighted_on_imbalance() {
        // class 0 dominant and well-predicted; rare class 1 poorly predicted.
        let mut cm = ConfusionMatrix::new(2);
        for _ in 0..90 {
            cm.record(0, 0); // 90 correct majority
        }
        for _ in 0..10 {
            cm.record(0, 1); // 10 minority all misclassified as 0
        }
        // weighted F1 should be higher than macro (majority dominates weighted)
        assert!(cm.weighted_f1() > cm.macro_f1());
        // minority recall is 0
        assert!(approx(cm.class_scores()[1].recall, 0.0));
    }

    #[test]
    fn kappa_zero_for_chance_agreement() {
        // predictions independent of truth at 50/50 → kappa ≈ 0
        let mut cm = ConfusionMatrix::new(2);
        cm.record(0, 0);
        cm.record(0, 1);
        cm.record(1, 0);
        cm.record(1, 1);
        assert!(
            cm.cohens_kappa().abs() < 1e-9,
            "kappa {}",
            cm.cohens_kappa()
        );
    }

    #[test]
    fn roc_auc_perfect_and_chance() {
        // perfect separation: all positives score above all negatives
        let scores = [0.1, 0.2, 0.8, 0.9];
        let labels = [false, false, true, true];
        assert!(approx(roc_auc(&scores, &labels), 1.0));
        // reversed → 0.0
        let rev = [false, false, true, true];
        let scores_rev = [0.9, 0.8, 0.2, 0.1];
        assert!(approx(roc_auc(&scores_rev, &rev), 0.0));
    }

    #[test]
    fn roc_auc_handles_ties() {
        // two tied scores straddling the label boundary → 0.5 contribution
        let scores = [0.5, 0.5];
        let labels = [true, false];
        assert!(approx(roc_auc(&scores, &labels), 0.5));
    }

    #[test]
    fn roc_auc_degenerate_returns_half() {
        assert!(approx(roc_auc(&[0.1, 0.2], &[true, true]), 0.5)); // no negatives
        assert!(approx(roc_auc(&[], &[]), 0.5));
    }

    #[test]
    fn serde_round_trip() {
        let cm = ConfusionMatrix::from_labels(&[0, 1, 1], &[0, 1, 0], 2);
        let j = serde_json::to_string(&cm).unwrap();
        let back: ConfusionMatrix = serde_json::from_str(&j).unwrap();
        assert_eq!(cm, back);
        assert!(approx(back.accuracy(), cm.accuracy()));
    }
}
