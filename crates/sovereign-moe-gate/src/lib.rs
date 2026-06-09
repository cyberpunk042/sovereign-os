//! `sovereign-moe-gate` — M022 Cognitive Frame, system-level MoE gating.
//!
//! The dump frames the system as a Mixture-of-Experts at the *agent* level
//! (a "Cognitive Frame"): a gate scores the experts and routes each request
//! to the top few, blending their outputs by weight. This crate is that
//! gating primitive — distinct from the hardware-role router (M075,
//! `sovereign-router-7axis`): here the "experts" are cognitive modules, not
//! GPUs.
//!
//! - [`top_k_gate`] selects the `k` highest-scoring experts and returns
//!   softmax-normalized weights *over the selected set* (the standard MoE
//!   gate).
//! - [`MoeRouter`] additionally tracks per-expert utilization across many
//!   gating calls, exposing the load-balance imbalance — the signal MoE
//!   training/routing uses to avoid a few experts hogging all traffic.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the MoE-gate surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A routed expert with its blend weight.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Routing {
    /// Expert index.
    pub expert: usize,
    /// Softmax weight over the selected experts (weights sum to 1).
    pub weight: f32,
}

/// MoE gating errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum MoeError {
    /// A routed expert index was out of range for the router.
    #[error("expert index {index} out of range for {num_experts} experts")]
    ExpertOutOfRange {
        /// Offending index.
        index: usize,
        /// Number of experts configured.
        num_experts: usize,
    },
}

/// Select the top-`k` experts by `logits` and return softmax-normalized
/// weights over just those experts, ordered by weight (highest first; ties
/// broken by lower index). `k` is clamped to the number of experts; `k == 0`
/// or empty logits yields an empty routing.
pub fn top_k_gate(logits: &[f32], k: usize) -> Vec<Routing> {
    let k = k.min(logits.len());
    if k == 0 {
        return Vec::new();
    }
    // indices sorted by logit desc, tie-break by index asc
    let mut order: Vec<usize> = (0..logits.len()).collect();
    order.sort_by(|&a, &b| logits[b].total_cmp(&logits[a]).then(a.cmp(&b)));
    let selected = &order[..k];

    // softmax over the selected logits (numerically stable)
    let max = selected
        .iter()
        .map(|&i| logits[i])
        .fold(f32::NEG_INFINITY, f32::max);
    let exps: Vec<f32> = selected.iter().map(|&i| (logits[i] - max).exp()).collect();
    let sum: f32 = exps.iter().sum();

    selected
        .iter()
        .zip(exps)
        .map(|(&expert, e)| Routing {
            expert,
            weight: e / sum,
        })
        .collect()
}

/// A stateful MoE router tracking per-expert utilization for load balancing.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MoeRouter {
    /// Number of experts.
    pub num_experts: usize,
    /// Per-expert selection counts.
    counts: Vec<u64>,
    /// Total routing decisions made.
    total_routes: u64,
}

impl MoeRouter {
    /// A router over `num_experts` experts.
    pub fn new(num_experts: usize) -> Self {
        Self {
            num_experts,
            counts: vec![0; num_experts],
            total_routes: 0,
        }
    }

    /// Route one request: top-`k` gate over `logits`, recording the selected
    /// experts toward utilization. `logits.len()` must equal `num_experts`.
    pub fn route(&mut self, logits: &[f32], k: usize) -> Result<Vec<Routing>, MoeError> {
        if logits.len() != self.num_experts {
            return Err(MoeError::ExpertOutOfRange {
                index: logits.len(),
                num_experts: self.num_experts,
            });
        }
        let routing = top_k_gate(logits, k);
        for r in &routing {
            self.counts[r.expert] += 1;
        }
        self.total_routes += 1;
        Ok(routing)
    }

    /// Per-expert utilization (selection share); empty before any routing.
    pub fn utilization(&self) -> Vec<f64> {
        let total: u64 = self.counts.iter().sum();
        if total == 0 {
            return vec![0.0; self.num_experts];
        }
        self.counts
            .iter()
            .map(|&c| c as f64 / total as f64)
            .collect()
    }

    /// Load-balance imbalance as the coefficient of variation of expert
    /// utilization (`0.0` = perfectly balanced; higher = more skewed).
    pub fn imbalance(&self) -> f64 {
        let u = self.utilization();
        let n = u.len() as f64;
        if n == 0.0 {
            return 0.0;
        }
        let mean = u.iter().sum::<f64>() / n;
        if mean == 0.0 {
            return 0.0;
        }
        let var = u.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n;
        var.sqrt() / mean
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selects_top_k_by_logit() {
        // logits: expert 1 (3.0) highest, then 2 (2.0)
        let r = top_k_gate(&[1.0, 3.0, 2.0, 0.0], 2);
        assert_eq!(r.len(), 2);
        assert_eq!(r[0].expert, 1);
        assert_eq!(r[1].expert, 2);
    }

    #[test]
    fn weights_sum_to_one() {
        let r = top_k_gate(&[1.0, 3.0, 2.0, 0.5], 3);
        let sum: f32 = r.iter().map(|x| x.weight).sum();
        assert!((sum - 1.0).abs() < 1e-5, "sum was {sum}");
        // highest logit → highest weight
        assert!(r[0].weight >= r[1].weight);
    }

    #[test]
    fn k_clamps_to_expert_count() {
        let r = top_k_gate(&[1.0, 2.0], 5);
        assert_eq!(r.len(), 2);
    }

    #[test]
    fn k_zero_and_empty_are_empty() {
        assert!(top_k_gate(&[1.0, 2.0], 0).is_empty());
        assert!(top_k_gate(&[], 3).is_empty());
    }

    #[test]
    fn ties_break_by_lower_index() {
        let r = top_k_gate(&[2.0, 2.0, 1.0], 2);
        assert_eq!(r[0].expert, 0);
        assert_eq!(r[1].expert, 1);
    }

    #[test]
    fn router_tracks_utilization() {
        let mut router = MoeRouter::new(3);
        // always route to expert 0 (top-1)
        for _ in 0..10 {
            router.route(&[5.0, 0.0, 0.0], 1).unwrap();
        }
        let u = router.utilization();
        assert!((u[0] - 1.0).abs() < 1e-9);
        assert_eq!(u[1], 0.0);
    }

    #[test]
    fn balanced_routing_has_low_imbalance() {
        let mut router = MoeRouter::new(2);
        router.route(&[1.0, 0.0], 1).unwrap(); // expert 0
        router.route(&[0.0, 1.0], 1).unwrap(); // expert 1
        assert!(router.imbalance() < 1e-9, "should be balanced");

        let mut skewed = MoeRouter::new(2);
        for _ in 0..9 {
            skewed.route(&[1.0, 0.0], 1).unwrap();
        }
        skewed.route(&[0.0, 1.0], 1).unwrap();
        assert!(skewed.imbalance() > router.imbalance());
    }

    #[test]
    fn route_rejects_wrong_logit_count() {
        let mut router = MoeRouter::new(3);
        assert!(matches!(
            router.route(&[1.0, 2.0], 1).unwrap_err(),
            MoeError::ExpertOutOfRange { .. }
        ));
    }

    #[test]
    fn routing_serde_round_trip() {
        let r = top_k_gate(&[1.0, 2.0, 3.0], 2);
        let j = serde_json::to_string(&r).unwrap();
        let back: Vec<Routing> = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
