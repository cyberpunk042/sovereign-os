//! `sovereign-viterbi` — the most likely hidden-state path behind observations.
//!
//! A hidden Markov model explains a sequence of observations as the trace of an
//! unseen state that hops according to transition probabilities and emits each
//! observation with state-dependent probabilities. The decoding question —
//! *which state sequence most likely produced what we saw?* — is answered exactly
//! by the **Viterbi algorithm**: a dynamic program that, for each time step and
//! state, keeps only the single best path ending there, because any longer
//! optimal path must extend an optimal prefix.
//!
//! The recurrence is `δ_t(s) = max_p [ δ_{t-1}(p) + trans(p→s) ] + emit_s(o_t)`,
//! run in **log space** so a long product of small probabilities adds instead of
//! underflowing to zero. A backpointer table records which predecessor `p`
//! achieved each maximum, and a final backward pass reconstructs the winning path
//! from the best terminal state. The cost is `O(T · S²)` for `T` observations and
//! `S` states.
//!
//! [`Hmm::new`] takes ordinary probabilities (validated and converted to logs);
//! [`Hmm::decode`] takes per-step *log* emission scores — so observations can come
//! from any model, including a neural one — and returns the best state path with
//! its total log-probability.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the Viterbi surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors building or running the model.
#[derive(Debug, Clone, PartialEq, Error)]
pub enum ViterbiError {
    /// The model has no states.
    #[error("an HMM needs at least one state")]
    NoStates,
    /// A probability vector/row had the wrong length.
    #[error("expected {expected} entries, got {got}")]
    BadShape {
        /// Expected length.
        expected: usize,
        /// Actual length.
        got: usize,
    },
    /// A probability was negative, NaN, or infinite.
    #[error("probability {value} at {where_} is not a finite value in [0, 1]")]
    BadProbability {
        /// Offending value.
        value: f64,
        /// Where it appeared (for diagnostics).
        where_: String,
    },
    /// An emission row did not match the number of states.
    #[error("emission at step {step} has {got} scores but the model has {expected} states")]
    BadEmission {
        /// Time step.
        step: usize,
        /// Expected (number of states).
        expected: usize,
        /// Actual length.
        got: usize,
    },
}

/// A hidden Markov model stored in log space.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Hmm {
    n: usize,
    /// log initial-state probabilities.
    log_init: Vec<f64>,
    /// `log_trans[p][s]` = log P(state s | previous state p).
    log_trans: Vec<Vec<f64>>,
}

/// A decoded result: the best state path and its total log-probability.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Decoded {
    /// The most likely state sequence (one state index per observation).
    pub path: Vec<usize>,
    /// The log-probability of that path together with the observations.
    pub log_prob: f64,
}

fn ln(p: f64) -> f64 {
    if p == 0.0 { f64::NEG_INFINITY } else { p.ln() }
}

fn check_prob(value: f64, where_: &str) -> Result<(), ViterbiError> {
    if !value.is_finite() || !(0.0..=1.0).contains(&value) {
        return Err(ViterbiError::BadProbability {
            value,
            where_: where_.to_string(),
        });
    }
    Ok(())
}

impl Hmm {
    /// Build from initial-state probabilities and an `n × n` transition matrix.
    /// Probabilities are validated to be in `[0, 1]`; rows are *not* required to
    /// sum to exactly 1 (so you can pass unnormalised scores), but each value
    /// must be a valid probability.
    pub fn new(init: Vec<f64>, trans: Vec<Vec<f64>>) -> Result<Self, ViterbiError> {
        let n = init.len();
        if n == 0 {
            return Err(ViterbiError::NoStates);
        }
        if trans.len() != n {
            return Err(ViterbiError::BadShape {
                expected: n,
                got: trans.len(),
            });
        }
        for (i, &p) in init.iter().enumerate() {
            check_prob(p, &format!("init[{i}]"))?;
        }
        for (p, row) in trans.iter().enumerate() {
            if row.len() != n {
                return Err(ViterbiError::BadShape {
                    expected: n,
                    got: row.len(),
                });
            }
            for (s, &v) in row.iter().enumerate() {
                check_prob(v, &format!("trans[{p}][{s}]"))?;
            }
        }
        Ok(Self {
            n,
            log_init: init.iter().map(|&p| ln(p)).collect(),
            log_trans: trans
                .iter()
                .map(|row| row.iter().map(|&p| ln(p)).collect())
                .collect(),
        })
    }

    /// The number of states.
    pub fn num_states(&self) -> usize {
        self.n
    }

    /// Decode the most likely state path for a sequence of **log** emission
    /// scores: `emissions[t][s]` is `log P(observation_t | state s)`. Returns the
    /// path and its total log-probability, or `None` for an empty observation
    /// sequence.
    pub fn decode(&self, emissions: &[Vec<f64>]) -> Result<Option<Decoded>, ViterbiError> {
        let t = emissions.len();
        if t == 0 {
            return Ok(None);
        }
        for (step, e) in emissions.iter().enumerate() {
            if e.len() != self.n {
                return Err(ViterbiError::BadEmission {
                    step,
                    expected: self.n,
                    got: e.len(),
                });
            }
        }

        // delta[s] = best log-prob of any path ending in state s at the current step.
        let mut delta: Vec<f64> = (0..self.n)
            .map(|s| self.log_init[s] + emissions[0][s])
            .collect();
        // backpointers[step][s] = best predecessor of s at `step`.
        let mut back: Vec<Vec<usize>> = vec![vec![0; self.n]; t];

        for step in 1..t {
            let mut next = vec![f64::NEG_INFINITY; self.n];
            for s in 0..self.n {
                // best predecessor p
                let mut best_p = 0usize;
                let mut best_score = f64::NEG_INFINITY;
                for p in 0..self.n {
                    let score = delta[p] + self.log_trans[p][s];
                    if score > best_score {
                        best_score = score;
                        best_p = p;
                    }
                }
                next[s] = best_score + emissions[step][s];
                back[step][s] = best_p;
            }
            delta = next;
        }

        // best terminal state
        let mut best_last = 0usize;
        let mut best_score = f64::NEG_INFINITY;
        for s in 0..self.n {
            if delta[s] > best_score {
                best_score = delta[s];
                best_last = s;
            }
        }

        // backtrack
        let mut path = vec![0usize; t];
        path[t - 1] = best_last;
        for step in (1..t).rev() {
            path[step - 1] = back[step][path[step]];
        }

        Ok(Some(Decoded {
            path,
            log_prob: best_score,
        }))
    }

    /// Convenience: decode from **probability** emissions (each `[0, 1]`),
    /// converting to log internally.
    pub fn decode_probs(&self, emissions: &[Vec<f64>]) -> Result<Option<Decoded>, ViterbiError> {
        let log: Vec<Vec<f64>> = emissions
            .iter()
            .map(|row| row.iter().map(|&p| ln(p)).collect())
            .collect();
        self.decode(&log)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The Wikipedia "Healthy/Fever" example.
    /// States: 0 = Healthy, 1 = Fever. Observations: normal, cold, dizzy.
    fn flu_model() -> Hmm {
        // start: Healthy 0.6, Fever 0.4
        // trans: H->H 0.7, H->F 0.3 ; F->H 0.4, F->F 0.6
        Hmm::new(vec![0.6, 0.4], vec![vec![0.7, 0.3], vec![0.4, 0.6]]).unwrap()
    }

    /// Emission probabilities P(obs | state) for the three observations.
    fn flu_emissions() -> Vec<Vec<f64>> {
        // P(normal|H)=0.5, P(cold|H)=0.4, P(dizzy|H)=0.1
        // P(normal|F)=0.1, P(cold|F)=0.3, P(dizzy|F)=0.6
        // sequence observed: normal, cold, dizzy
        vec![
            vec![0.5, 0.1], // normal
            vec![0.4, 0.3], // cold
            vec![0.1, 0.6], // dizzy
        ]
    }

    #[test]
    fn classic_flu_example_path() {
        let hmm = flu_model();
        let d = hmm.decode_probs(&flu_emissions()).unwrap().unwrap();
        // known answer: Healthy, Healthy, Fever
        assert_eq!(d.path, vec![0, 0, 1]);
        // and the log-prob matches the hand-computed 0.01512 (= 0.0151632? check)
        // delta path prob ≈ 0.01512; allow tolerance
        assert!(
            (d.log_prob.exp() - 0.01512).abs() < 1e-4,
            "p={}",
            d.log_prob.exp()
        );
    }

    #[test]
    fn single_observation_picks_best_state() {
        let hmm = flu_model();
        // one dizzy observation: Fever far more likely to emit dizzy
        let d = hmm.decode_probs(&[vec![0.1, 0.6]]).unwrap().unwrap();
        assert_eq!(d.path, vec![1]); // Fever
    }

    #[test]
    fn deterministic_transitions_force_a_path() {
        // 3 states in a forced cycle 0->1->2->0; whatever you start with, the
        // path is determined by transitions regardless of emissions.
        let init = vec![1.0, 0.0, 0.0];
        let trans = vec![
            vec![0.0, 1.0, 0.0], // 0 -> 1
            vec![0.0, 0.0, 1.0], // 1 -> 2
            vec![1.0, 0.0, 0.0], // 2 -> 0
        ];
        let hmm = Hmm::new(init, trans).unwrap();
        // flat emissions: every state equally likely to emit
        let flat = vec![vec![1.0, 1.0, 1.0]; 5];
        let d = hmm.decode_probs(&flat).unwrap().unwrap();
        assert_eq!(d.path, vec![0, 1, 2, 0, 1]);
    }

    #[test]
    fn emissions_override_when_transitions_are_uniform() {
        // uniform transitions → the path just follows the strongest emission each
        // step.
        let init = vec![0.5, 0.5];
        let trans = vec![vec![0.5, 0.5], vec![0.5, 0.5]];
        let hmm = Hmm::new(init, trans).unwrap();
        let emis = vec![
            vec![0.9, 0.1], // favor 0
            vec![0.2, 0.8], // favor 1
            vec![0.7, 0.3], // favor 0
        ];
        let d = hmm.decode_probs(&emis).unwrap().unwrap();
        assert_eq!(d.path, vec![0, 1, 0]);
    }

    #[test]
    fn log_and_prob_interfaces_agree() {
        let hmm = flu_model();
        let probs = flu_emissions();
        let logs: Vec<Vec<f64>> = probs
            .iter()
            .map(|r| r.iter().map(|&p| p.ln()).collect())
            .collect();
        let a = hmm.decode_probs(&probs).unwrap().unwrap();
        let b = hmm.decode(&logs).unwrap().unwrap();
        assert_eq!(a.path, b.path);
        assert!((a.log_prob - b.log_prob).abs() < 1e-12);
    }

    #[test]
    fn empty_observations_is_none() {
        let hmm = flu_model();
        assert_eq!(hmm.decode(&[]).unwrap(), None);
    }

    #[test]
    fn zero_probability_paths_are_avoided() {
        // state 1 can never emit observation here (prob 0) → path must use state 0
        let hmm = flu_model();
        let emis = vec![vec![0.5, 0.0], vec![0.4, 0.0]];
        let d = hmm.decode_probs(&emis).unwrap().unwrap();
        assert_eq!(d.path, vec![0, 0]);
        assert!(d.log_prob.is_finite());
    }

    #[test]
    fn rejects_malformed_models() {
        assert_eq!(Hmm::new(vec![], vec![]), Err(ViterbiError::NoStates));
        assert!(matches!(
            Hmm::new(vec![0.5, 0.5], vec![vec![1.0]]),
            Err(ViterbiError::BadShape { .. })
        ));
        assert!(matches!(
            Hmm::new(vec![1.5], vec![vec![1.0]]),
            Err(ViterbiError::BadProbability { .. })
        ));
    }

    #[test]
    fn rejects_wrong_emission_shape() {
        let hmm = flu_model();
        let bad = vec![vec![0.5, 0.5, 0.5]]; // 3 scores, model has 2 states
        assert!(matches!(
            hmm.decode(&bad),
            Err(ViterbiError::BadEmission { .. })
        ));
    }

    #[test]
    fn serde_round_trip() {
        let hmm = flu_model();
        let j = serde_json::to_string(&hmm).unwrap();
        let back: Hmm = serde_json::from_str(&j).unwrap();
        // floats can shift by a ULP through JSON, so compare behaviour, not bits
        assert_eq!(back.num_states(), hmm.num_states());
        let a = hmm.decode_probs(&flu_emissions()).unwrap().unwrap();
        let b = back.decode_probs(&flu_emissions()).unwrap().unwrap();
        assert_eq!(b.path, vec![0, 0, 1]);
        assert_eq!(a.path, b.path);
        assert!((a.log_prob - b.log_prob).abs() < 1e-9);
    }
}
