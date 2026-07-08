//! `sovereign-world-model` — M030 World Model plane.
//!
//! The dump's world-model plane is state / action / transition (Dreamer-
//! style): a model that *learns* the environment's dynamics from observed
//! transitions and can then predict and roll forward. This crate is the
//! tabular reference — distinct from [`sovereign_symbolic_plan`], whose
//! action effects are *fixed* by definition; here the effects are *learned*
//! from data.
//!
//! - [`WorldModel::observe`] records a `(state, action) → next_state`
//!   transition (count-based).
//! - [`WorldModel::predict`] returns the most-frequently-observed next state
//!   for a `(state, action)` (ties broken by lower state id).
//! - [`WorldModel::rollout`] chains predictions into a trajectory.
//! - [`WorldModel::accuracy`] scores predictions against held-out
//!   transitions — the prediction-error signal.
//!
//! States and actions are opaque `u64` ids.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the world-model surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// An observed `(state, action) → next_state` transition.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Transition {
    /// Starting state id.
    pub state: u64,
    /// Action id.
    pub action: u64,
    /// Resulting state id.
    pub next_state: u64,
}

/// A learned tabular transition model. (Runtime state; not JSON-serialized —
/// its `(state, action)` map keys aren't representable as JSON object keys.)
#[derive(Debug, Clone, Default)]
pub struct WorldModel {
    // (state, action) → { next_state → count }
    table: HashMap<(u64, u64), HashMap<u64, u64>>,
    observations: u64,
}

impl WorldModel {
    /// An empty model.
    pub fn new() -> Self {
        Self::default()
    }

    /// Record one observed transition.
    pub fn observe(&mut self, state: u64, action: u64, next_state: u64) {
        *self
            .table
            .entry((state, action))
            .or_default()
            .entry(next_state)
            .or_insert(0) += 1;
        self.observations += 1;
    }

    /// Total transitions observed.
    pub fn observations(&self) -> u64 {
        self.observations
    }

    /// Number of distinct `(state, action)` pairs seen.
    pub fn known_pairs(&self) -> usize {
        self.table.len()
    }

    /// Total transitions observed for one `(state, action)` pair (0 if unseen).
    /// Lets a consumer weight a prediction by how much history backs it.
    pub fn pair_observations(&self, state: u64, action: u64) -> u64 {
        self.table
            .get(&(state, action))
            .map(|outcomes| outcomes.values().sum())
            .unwrap_or(0)
    }

    /// Predict the most-likely next state for `(state, action)` — the modal
    /// observed outcome (ties broken by lower next-state id). `None` if the
    /// pair was never observed.
    pub fn predict(&self, state: u64, action: u64) -> Option<u64> {
        let outcomes = self.table.get(&(state, action))?;
        outcomes
            .iter()
            .max_by(|(an, ac), (bn, bc)| ac.cmp(bc).then(bn.cmp(an)))
            .map(|(&next, _)| next)
    }

    /// Probability the model assigns to a specific next state for a pair.
    pub fn probability(&self, state: u64, action: u64, next_state: u64) -> f64 {
        match self.table.get(&(state, action)) {
            Some(outcomes) => {
                let total: u64 = outcomes.values().sum();
                if total == 0 {
                    0.0
                } else {
                    *outcomes.get(&next_state).unwrap_or(&0) as f64 / total as f64
                }
            }
            None => 0.0,
        }
    }

    /// Roll a trajectory forward from `start` applying `actions` in order via
    /// predictions. Stops early if a `(state, action)` is unknown; the
    /// returned vector is the visited states *including* `start`.
    pub fn rollout(&self, start: u64, actions: &[u64]) -> Vec<u64> {
        let mut trajectory = vec![start];
        let mut state = start;
        for &action in actions {
            match self.predict(state, action) {
                Some(next) => {
                    state = next;
                    trajectory.push(next);
                }
                None => break,
            }
        }
        trajectory
    }

    /// Prediction accuracy over a held-out set of transitions: the fraction
    /// whose `next_state` matches the model's [`WorldModel::predict`].
    /// Unknown pairs count as misses. Empty set → `0.0`.
    pub fn accuracy(&self, test: &[Transition]) -> f64 {
        if test.is_empty() {
            return 0.0;
        }
        let correct = test
            .iter()
            .filter(|t| self.predict(t.state, t.action) == Some(t.next_state))
            .count();
        correct as f64 / test.len() as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn observe_then_predict() {
        let mut m = WorldModel::new();
        m.observe(1, 0, 2);
        assert_eq!(m.predict(1, 0), Some(2));
        assert_eq!(m.observations(), 1);
        assert_eq!(m.known_pairs(), 1);
    }

    #[test]
    fn pair_observations_counts_per_pair() {
        let mut m = WorldModel::new();
        m.observe(1, 0, 2);
        m.observe(1, 0, 3);
        m.observe(7, 0, 9);
        assert_eq!(m.pair_observations(1, 0), 2);
        assert_eq!(m.pair_observations(7, 0), 1);
        assert_eq!(m.pair_observations(42, 0), 0); // unseen
    }

    #[test]
    fn predict_returns_modal_outcome() {
        let mut m = WorldModel::new();
        // (1,0) → 2 twice, → 3 once: modal is 2
        m.observe(1, 0, 2);
        m.observe(1, 0, 3);
        m.observe(1, 0, 2);
        assert_eq!(m.predict(1, 0), Some(2));
        assert!((m.probability(1, 0, 2) - 2.0 / 3.0).abs() < 1e-9);
        assert!((m.probability(1, 0, 3) - 1.0 / 3.0).abs() < 1e-9);
    }

    #[test]
    fn unknown_pair_predicts_none() {
        let m = WorldModel::new();
        assert_eq!(m.predict(9, 9), None);
        assert_eq!(m.probability(9, 9, 1), 0.0);
    }

    #[test]
    fn rollout_chains_predictions() {
        let mut m = WorldModel::new();
        m.observe(0, 10, 1);
        m.observe(1, 11, 2);
        m.observe(2, 12, 3);
        assert_eq!(m.rollout(0, &[10, 11, 12]), vec![0, 1, 2, 3]);
    }

    #[test]
    fn rollout_stops_at_unknown() {
        let mut m = WorldModel::new();
        m.observe(0, 10, 1);
        // (1, 99) unknown → stop after reaching state 1
        assert_eq!(m.rollout(0, &[10, 99, 12]), vec![0, 1]);
    }

    #[test]
    fn accuracy_scores_against_held_out() {
        let mut m = WorldModel::new();
        m.observe(1, 0, 2);
        m.observe(3, 0, 4);
        let test = [
            Transition {
                state: 1,
                action: 0,
                next_state: 2,
            }, // correct
            Transition {
                state: 3,
                action: 0,
                next_state: 9,
            }, // wrong (model says 4)
            Transition {
                state: 5,
                action: 0,
                next_state: 6,
            }, // unknown → miss
        ];
        assert!((m.accuracy(&test) - 1.0 / 3.0).abs() < 1e-9);
        assert_eq!(m.accuracy(&[]), 0.0);
    }

    #[test]
    fn tie_breaks_by_lower_next_state() {
        let mut m = WorldModel::new();
        m.observe(1, 0, 5);
        m.observe(1, 0, 2); // equal counts → lower id (2) wins
        assert_eq!(m.predict(1, 0), Some(2));
    }

    #[test]
    fn transition_serde_round_trip() {
        let t = Transition {
            state: 1,
            action: 2,
            next_state: 3,
        };
        let j = serde_json::to_string(&t).unwrap();
        let back: Transition = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
