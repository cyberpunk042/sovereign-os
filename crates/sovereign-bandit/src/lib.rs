//! `sovereign-bandit` — learn which option works while still trying others.
//!
//! When a system can pick between several models, prompts, or strategies and only
//! learns how good a choice was *after* making it, that is a multi-armed bandit:
//! each "arm" pays an unknown, noisy reward, and you must balance **exploiting**
//! the arm that has looked best so far against **exploring** arms you have barely
//! tried (which might be better). This crate implements the three classic
//! policies, all over the same reward bookkeeping.
//!
//! - **Epsilon-greedy** ([`epsilon_greedy`]): pick the current best arm, but with
//!   probability `epsilon` pick a uniformly random one. Simple and robust.
//! - **UCB1** ([`ucb1`]): pick the arm with the highest *upper confidence bound*
//!   `mean + sqrt(2·ln t / n)` — automatically explores arms whose estimate is
//!   uncertain (few pulls), with no tuning. Deterministic.
//! - **Thompson sampling** ([`thompson_sample`]): for Bernoulli (0/1) rewards, keep
//!   a Beta posterior per arm, draw a sample from each, and pick the arm with the
//!   highest draw — exploration that shrinks naturally as evidence accrues.
//!
//! [`update`] folds an observed reward back into an arm. Randomness is a seeded
//! generator so a run is reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the bandit surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-arm reward statistics.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, Default)]
pub struct Arm {
    /// Number of times this arm was pulled.
    pub pulls: u64,
    /// Sum of rewards received.
    pub reward_sum: f64,
    /// Count of successes (reward >= 0.5), for Bernoulli/Thompson.
    pub successes: u64,
}

impl Arm {
    /// The empirical mean reward (0 if never pulled).
    pub fn mean(&self) -> f64 {
        if self.pulls == 0 {
            0.0
        } else {
            self.reward_sum / self.pulls as f64
        }
    }
}

/// A multi-armed bandit over `k` arms.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Bandit {
    arms: Vec<Arm>,
    total_pulls: u64,
    rng: u64,
}

impl Bandit {
    /// A bandit with `k` arms, seeded with `seed`.
    ///
    /// # Panics
    /// Panics if `k == 0`.
    pub fn new(k: usize, seed: u64) -> Self {
        assert!(k > 0, "need at least one arm");
        Self {
            arms: vec![Arm::default(); k],
            total_pulls: 0,
            rng: seed | 1,
        }
    }

    /// The number of arms.
    pub fn arms(&self) -> usize {
        self.arms.len()
    }

    /// Statistics for arm `i`.
    pub fn arm(&self, i: usize) -> Arm {
        self.arms[i]
    }

    /// Total pulls across all arms.
    pub fn total_pulls(&self) -> u64 {
        self.total_pulls
    }

    /// Record a `reward` for arm `i`. Rewards are typically in `[0, 1]`; a reward
    /// `>= 0.5` counts as a success for Thompson sampling.
    ///
    /// # Panics
    /// Panics if `i >= arms()`.
    pub fn update(&mut self, i: usize, reward: f64) {
        let a = &mut self.arms[i];
        a.pulls += 1;
        a.reward_sum += reward;
        if reward >= 0.5 {
            a.successes += 1;
        }
        self.total_pulls += 1;
    }

    fn next_u64(&mut self) -> u64 {
        self.rng = self.rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.rng;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    fn next_unit(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }

    /// The arm with the highest empirical mean (ties → lowest index).
    pub fn best_arm(&self) -> usize {
        self.arms
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.mean().total_cmp(&b.1.mean()).then(b.0.cmp(&a.0)))
            .map(|(i, _)| i)
            .unwrap_or(0)
    }

    /// Epsilon-greedy choice: the current best arm, or with probability `epsilon`
    /// a uniformly random arm.
    pub fn epsilon_greedy(&mut self, epsilon: f64) -> usize {
        if self.next_unit() < epsilon.clamp(0.0, 1.0) {
            (self.next_u64() % self.arms.len() as u64) as usize
        } else {
            self.best_arm()
        }
    }

    /// UCB1 choice: the arm maximizing `mean + sqrt(2·ln t / n)`. Unpulled arms
    /// have infinite bound, so each arm is tried once before exploitation begins.
    pub fn ucb1(&self) -> usize {
        let t = (self.total_pulls + 1) as f64;
        let mut best = 0usize;
        let mut best_score = f64::NEG_INFINITY;
        for (i, a) in self.arms.iter().enumerate() {
            let score = if a.pulls == 0 {
                f64::INFINITY
            } else {
                a.mean() + (2.0 * t.ln() / a.pulls as f64).sqrt()
            };
            if score > best_score {
                best_score = score;
                best = i;
            }
        }
        best
    }

    /// Thompson-sampling choice for Bernoulli rewards: draw from each arm's
    /// `Beta(successes + 1, failures + 1)` posterior and pick the highest draw.
    pub fn thompson_sample(&mut self) -> usize {
        let mut best = 0usize;
        let mut best_draw = f64::NEG_INFINITY;
        for i in 0..self.arms.len() {
            let a = self.arms[i];
            let alpha = a.successes as f64 + 1.0;
            let beta = (a.pulls - a.successes) as f64 + 1.0;
            let draw = self.sample_beta(alpha, beta);
            if draw > best_draw {
                best_draw = draw;
                best = i;
            }
        }
        best
    }

    /// Sample from a Beta(alpha, beta) via two Gamma draws (Marsaglia-Tsang).
    fn sample_beta(&mut self, alpha: f64, beta: f64) -> f64 {
        let x = self.sample_gamma(alpha);
        let y = self.sample_gamma(beta);
        if x + y <= 0.0 { 0.5 } else { x / (x + y) }
    }

    /// Sample from Gamma(shape, 1) via the Marsaglia-Tsang method (shape >= 1; for
    /// shape < 1 use the boost trick).
    fn sample_gamma(&mut self, shape: f64) -> f64 {
        if shape < 1.0 {
            let u = self.next_unit().max(1e-12);
            return self.sample_gamma(shape + 1.0) * u.powf(1.0 / shape);
        }
        let d = shape - 1.0 / 3.0;
        let c = 1.0 / (9.0 * d).sqrt();
        loop {
            let x = self.sample_normal();
            let v = (1.0 + c * x).powi(3);
            if v <= 0.0 {
                continue;
            }
            let u = self.next_unit().max(1e-12);
            if u.ln() < 0.5 * x * x + d - d * v + d * v.ln() {
                return d * v;
            }
        }
    }

    /// Standard normal via Box-Muller.
    fn sample_normal(&mut self) -> f64 {
        let u1 = self.next_unit().max(1e-12);
        let u2 = self.next_unit();
        (-2.0 * u1.ln()).sqrt() * (std::f64::consts::TAU * u2).cos()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A deterministic reward oracle: arm `best` pays 1 with high probability.
    fn pull(arm: usize, best: usize, rng: &mut u64) -> f64 {
        *rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
        let u = ((*rng >> 33) as f64) / (1u64 << 31) as f64;
        let p = if arm == best { 0.8 } else { 0.2 };
        if u < p { 1.0 } else { 0.0 }
    }

    #[test]
    fn arm_mean_tracks_rewards() {
        let mut b = Bandit::new(2, 1);
        b.update(0, 1.0);
        b.update(0, 0.0);
        assert!((b.arm(0).mean() - 0.5).abs() < 1e-9);
        assert_eq!(b.arm(0).pulls, 2);
        assert_eq!(b.arm(0).successes, 1);
    }

    #[test]
    fn epsilon_greedy_learns_best_arm() {
        let mut b = Bandit::new(3, 42);
        let best = 1;
        let mut oracle = 999u64;
        for _ in 0..3000 {
            let arm = b.epsilon_greedy(0.1);
            let r = pull(arm, best, &mut oracle);
            b.update(arm, r);
        }
        // the best arm should have the highest mean and most pulls
        assert_eq!(b.best_arm(), best);
        assert!(b.arm(best).pulls > b.arm(0).pulls);
        assert!(b.arm(best).pulls > b.arm(2).pulls);
    }

    #[test]
    fn ucb1_tries_every_arm_first() {
        let mut b = Bandit::new(4, 7);
        // first 4 selections (before any pulls) should cover all arms once each.
        let mut chosen = std::collections::HashSet::new();
        for _ in 0..4 {
            let arm = b.ucb1();
            chosen.insert(arm);
            b.update(arm, 0.0);
        }
        assert_eq!(chosen.len(), 4, "UCB1 should explore all arms first");
    }

    #[test]
    fn ucb1_converges_to_best_arm() {
        let mut b = Bandit::new(3, 5);
        let best = 2;
        let mut oracle = 123u64;
        let mut last_choices = Vec::new();
        for step in 0..3000 {
            let arm = b.ucb1();
            let r = pull(arm, best, &mut oracle);
            b.update(arm, r);
            if step >= 2900 {
                last_choices.push(arm);
            }
        }
        // most of the final choices should be the best arm
        let best_count = last_choices.iter().filter(|&&a| a == best).count();
        assert!(best_count > last_choices.len() / 2, "ucb1 didn't converge");
    }

    #[test]
    fn thompson_learns_best_arm() {
        let mut b = Bandit::new(3, 99);
        let best = 0;
        let mut oracle = 77u64;
        for _ in 0..3000 {
            let arm = b.thompson_sample();
            let r = pull(arm, best, &mut oracle);
            b.update(arm, r);
        }
        assert_eq!(b.best_arm(), best);
        assert!(b.arm(best).pulls > b.arm(1).pulls);
    }

    #[test]
    fn deterministic_for_seed() {
        let mut a = Bandit::new(3, 2024);
        let mut c = Bandit::new(3, 2024);
        for _ in 0..100 {
            let x = a.epsilon_greedy(0.3);
            let y = c.epsilon_greedy(0.3);
            assert_eq!(x, y);
            a.update(x, 1.0);
            c.update(y, 1.0);
        }
    }

    #[test]
    fn single_arm() {
        let mut b = Bandit::new(1, 1);
        assert_eq!(b.epsilon_greedy(0.5), 0);
        assert_eq!(b.ucb1(), 0);
        assert_eq!(b.thompson_sample(), 0);
    }

    #[test]
    fn serde_round_trip() {
        let mut b = Bandit::new(3, 8);
        b.update(0, 1.0);
        b.update(1, 0.0);
        let j = serde_json::to_string(&b).unwrap();
        let back: Bandit = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
