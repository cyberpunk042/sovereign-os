//! `sovereign-holderpo` — M078 HölderPO + GRPO post-training pipeline.
//!
//! Per arXiv 2605.12058 ("Hölder Policy Optimisation"), HölderPO
//! generalises Group Relative Policy Optimisation (GRPO) by replacing
//! the fixed token-level probability aggregator with the Hölder mean
//! parameterised by `p`:
//!
//! - **p → -∞** = minimum (gradient concentrated on the weakest token)
//! - **p = 0**  = geometric mean (multiplicative aggregation; GRPO default)
//! - **p = 1**  = arithmetic mean (additive aggregation)
//! - **p → +∞** = maximum (gradient concentrated on the strongest token)
//!
//! Operator standing rule: We do not minimize anything.
//! Note: we catalogue peer-reviewed published algorithms; we do not
//! invent novel RL. Per arXiv 2605.12058 §3 the dynamic-p anneal
//! reaches 54.9% avg math accuracy + 93.8% ALFWorld success.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the HölderPO configuration surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Default Hölder parameter p at training start (geometric mean).
pub const DEFAULT_P_START: f64 = 0.0;

/// Default Hölder parameter p at training end (after anneal).
pub const DEFAULT_P_END: f64 = 8.0;

/// Anneal schedule — how `p` evolves during training.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AnnealSchedule {
    /// p stays constant (set to p_start). Used as ablation baseline.
    Constant,
    /// Linear interpolation from p_start to p_end across training steps.
    Linear,
    /// Cosine schedule from p_start to p_end (smooth transition).
    Cosine,
    /// Step schedule (stepped jumps every N steps; jumps_per_anneal).
    Step,
}

/// HölderPO training configuration.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct HolderPoConfig {
    /// Schema version. Must equal [`SCHEMA_VERSION`].
    pub schema_version: String,
    /// Starting Hölder parameter `p`. Default 0.0 (geometric mean = GRPO baseline).
    pub p_start: f64,
    /// Final Hölder parameter `p` after anneal. Default 8.0.
    pub p_end: f64,
    /// Anneal schedule.
    pub schedule: AnnealSchedule,
    /// Total training steps over which to anneal.
    pub total_steps: u64,
    /// Group size for GRPO advantage estimation (trajectories per group).
    pub group_size: u32,
    /// KL penalty coefficient (kept from GRPO baseline).
    pub kl_coef: f64,
    /// Clip range for advantage estimates.
    pub clip_range: f64,
}

impl Default for HolderPoConfig {
    fn default() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            p_start: DEFAULT_P_START,
            p_end: DEFAULT_P_END,
            schedule: AnnealSchedule::Cosine,
            total_steps: 10_000,
            group_size: 8,
            kl_coef: 0.01,
            clip_range: 0.2,
        }
    }
}

/// HölderPO errors.
#[derive(Debug, Error)]
pub enum HolderPoError {
    /// Schema version drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected schema version.
        expected: String,
        /// Observed schema version.
        actual: String,
    },
    /// Step index exceeds total_steps.
    #[error("step {step} >= total_steps {total}")]
    StepOutOfRange {
        /// Step index requested.
        step: u64,
        /// Configured total steps.
        total: u64,
    },
    /// Token-probability slice contained NaN or values outside (0, 1].
    #[error("invalid token probability: {0}")]
    InvalidTokenProbability(f64),
    /// Group size mismatch — trajectory count does not equal config.group_size.
    #[error("group size mismatch: expected {expected}, got {actual}")]
    GroupSizeMismatch {
        /// Configured group size.
        expected: u32,
        /// Observed trajectory count.
        actual: u32,
    },
}

impl HolderPoConfig {
    /// Validate config.
    pub fn validate(&self) -> Result<(), HolderPoError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HolderPoError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        Ok(())
    }

    /// Current Hölder parameter `p` at training step `step`.
    /// Returns `Err(StepOutOfRange)` if step ≥ total_steps.
    pub fn p_at_step(&self, step: u64) -> Result<f64, HolderPoError> {
        if self.total_steps == 0 {
            return Ok(self.p_start);
        }
        if step >= self.total_steps {
            return Err(HolderPoError::StepOutOfRange { step, total: self.total_steps });
        }
        let t = step as f64 / self.total_steps as f64;
        let p = match self.schedule {
            AnnealSchedule::Constant => self.p_start,
            AnnealSchedule::Linear => self.p_start + (self.p_end - self.p_start) * t,
            AnnealSchedule::Cosine => {
                // Smooth half-cosine ramp from p_start to p_end.
                let phase = (1.0 - (std::f64::consts::PI * t).cos()) / 2.0;
                self.p_start + (self.p_end - self.p_start) * phase
            }
            AnnealSchedule::Step => {
                // 4 evenly-spaced jumps across training.
                let stage = (t * 4.0).floor() / 4.0;
                self.p_start + (self.p_end - self.p_start) * stage
            }
        };
        Ok(p)
    }
}

/// Compute the Hölder mean M_p(x) = ( (1/n) Σ x_i^p )^(1/p).
///
/// Special cases:
/// - p == 0 → geometric mean (via log-mean for numerical stability)
/// - p → +∞ → max(x)
/// - p → -∞ → min(x)
///
/// `xs` must be non-empty and strictly positive; returns
/// [`HolderPoError::InvalidTokenProbability`] otherwise.
pub fn holder_mean(xs: &[f64], p: f64) -> Result<f64, HolderPoError> {
    if xs.is_empty() {
        return Err(HolderPoError::InvalidTokenProbability(0.0));
    }
    for &x in xs {
        if !x.is_finite() || x <= 0.0 || x > 1.0 {
            return Err(HolderPoError::InvalidTokenProbability(x));
        }
    }
    let n = xs.len() as f64;
    if p.abs() < 1e-9 {
        // Geometric mean via log-mean for numerical stability.
        let log_sum: f64 = xs.iter().map(|x| x.ln()).sum();
        return Ok((log_sum / n).exp());
    }
    // Saturating limits when p large in magnitude.
    if p > 1e6 {
        return Ok(xs.iter().copied().fold(f64::MIN, f64::max));
    }
    if p < -1e6 {
        return Ok(xs.iter().copied().fold(f64::MAX, f64::min));
    }
    let sum: f64 = xs.iter().map(|x| x.powf(p)).sum();
    Ok((sum / n).powf(1.0 / p))
}

/// Single trajectory in a GRPO group.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Trajectory {
    /// Token-level probabilities under the current policy (each in (0, 1]).
    pub token_probs: Vec<f64>,
    /// Reward signal from the value model / verifier.
    pub reward: f64,
}

/// Aggregate token-level probabilities for each trajectory using the
/// Hölder mean at parameter `p`. Returns the aggregated probability
/// per trajectory in input order.
pub fn aggregate_trajectory_probs(
    trajectories: &[Trajectory],
    p: f64,
) -> Result<Vec<f64>, HolderPoError> {
    let mut out = Vec::with_capacity(trajectories.len());
    for t in trajectories {
        out.push(holder_mean(&t.token_probs, p)?);
    }
    Ok(out)
}

/// Compute GRPO-style group-relative advantages: subtract group mean
/// reward and (optionally) normalise by std.
pub fn group_relative_advantages(rewards: &[f64], normalise: bool) -> Vec<f64> {
    if rewards.is_empty() {
        return vec![];
    }
    let n = rewards.len() as f64;
    let mean = rewards.iter().sum::<f64>() / n;
    if !normalise {
        return rewards.iter().map(|r| r - mean).collect();
    }
    let var = rewards.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / n;
    let std = var.sqrt().max(1e-9);
    rewards.iter().map(|r| (r - mean) / std).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_default_validates() {
        HolderPoConfig::default().validate().unwrap();
    }

    #[test]
    fn p_at_step_constant_schedule() {
        let mut c = HolderPoConfig::default();
        c.schedule = AnnealSchedule::Constant;
        c.p_start = 0.0;
        c.p_end = 8.0;
        for step in [0, 100, 5000, 9999] {
            assert_eq!(c.p_at_step(step).unwrap(), 0.0);
        }
    }

    #[test]
    fn p_at_step_linear_endpoints() {
        let mut c = HolderPoConfig::default();
        c.schedule = AnnealSchedule::Linear;
        c.p_start = 0.0;
        c.p_end = 8.0;
        c.total_steps = 100;
        assert!((c.p_at_step(0).unwrap() - 0.0).abs() < 1e-9);
        // Last valid step is total_steps - 1; t ≈ 0.99
        let final_p = c.p_at_step(99).unwrap();
        assert!((final_p - 7.92).abs() < 1e-6);
    }

    #[test]
    fn p_at_step_cosine_midpoint() {
        let mut c = HolderPoConfig::default();
        c.schedule = AnnealSchedule::Cosine;
        c.p_start = 0.0;
        c.p_end = 8.0;
        c.total_steps = 100;
        // At t=0.5 cosine schedule is exactly at midpoint = 4.0
        let mid = c.p_at_step(50).unwrap();
        assert!((mid - 4.0).abs() < 1e-9, "expected 4.0 got {mid}");
    }

    #[test]
    fn p_at_step_out_of_range() {
        let c = HolderPoConfig::default();
        assert!(matches!(
            c.p_at_step(c.total_steps).unwrap_err(),
            HolderPoError::StepOutOfRange { .. }
        ));
    }

    #[test]
    fn holder_mean_geometric_when_p_zero() {
        // geomean(0.1, 0.4) = sqrt(0.04) = 0.2
        let m = holder_mean(&[0.1, 0.4], 0.0).unwrap();
        assert!((m - 0.2).abs() < 1e-9, "got {m}");
    }

    #[test]
    fn holder_mean_arithmetic_when_p_one() {
        let m = holder_mean(&[0.1, 0.3, 0.5], 1.0).unwrap();
        assert!((m - 0.3).abs() < 1e-9, "got {m}");
    }

    #[test]
    fn holder_mean_quadratic_when_p_two() {
        // (((0.3^2 + 0.4^2)/2)^(1/2)) = sqrt(0.125) ≈ 0.35355
        let m = holder_mean(&[0.3, 0.4], 2.0).unwrap();
        assert!((m - 0.353553).abs() < 1e-5, "got {m}");
    }

    #[test]
    fn holder_mean_approaches_max_as_p_large() {
        let m = holder_mean(&[0.1, 0.5, 0.9], 100.0).unwrap();
        assert!(m > 0.85, "got {m} expected near 0.9");
    }

    #[test]
    fn holder_mean_approaches_min_as_p_very_negative() {
        let m = holder_mean(&[0.1, 0.5, 0.9], -100.0).unwrap();
        assert!(m < 0.15, "got {m} expected near 0.1");
    }

    #[test]
    fn holder_mean_rejects_zero_probability() {
        assert!(matches!(
            holder_mean(&[0.5, 0.0, 0.3], 0.5).unwrap_err(),
            HolderPoError::InvalidTokenProbability(0.0)
        ));
    }

    #[test]
    fn holder_mean_rejects_nan() {
        assert!(matches!(
            holder_mean(&[0.5, f64::NAN], 1.0).unwrap_err(),
            HolderPoError::InvalidTokenProbability(_)
        ));
    }

    #[test]
    fn holder_mean_rejects_empty() {
        assert!(matches!(
            holder_mean(&[], 1.0).unwrap_err(),
            HolderPoError::InvalidTokenProbability(_)
        ));
    }

    #[test]
    fn aggregate_trajectory_probs_per_trajectory() {
        let trajectories = vec![
            Trajectory { token_probs: vec![0.1, 0.4], reward: 1.0 },
            Trajectory { token_probs: vec![0.5, 0.5], reward: 0.5 },
        ];
        let aggs = aggregate_trajectory_probs(&trajectories, 0.0).unwrap();
        assert!((aggs[0] - 0.2).abs() < 1e-9);
        assert!((aggs[1] - 0.5).abs() < 1e-9);
    }

    #[test]
    fn group_relative_advantages_center_around_mean() {
        let rs = vec![1.0, 2.0, 3.0, 4.0];
        let adv = group_relative_advantages(&rs, false);
        // mean = 2.5; advantages = [-1.5, -0.5, 0.5, 1.5]
        assert_eq!(adv, vec![-1.5, -0.5, 0.5, 1.5]);
    }

    #[test]
    fn group_relative_advantages_normalised_unit_variance() {
        let rs = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let adv = group_relative_advantages(&rs, true);
        let mean = adv.iter().sum::<f64>() / adv.len() as f64;
        assert!(mean.abs() < 1e-9);
        let var = adv.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / adv.len() as f64;
        assert!((var.sqrt() - 1.0).abs() < 1e-9);
    }

    #[test]
    fn schedule_serde_uses_kebab_case() {
        let j = serde_json::to_string(&AnnealSchedule::Cosine).unwrap();
        assert_eq!(j, "\"cosine\"");
    }
}
