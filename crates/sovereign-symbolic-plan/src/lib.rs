//! `sovereign-symbolic-plan` — M031 Symbolic Planning plane.
//!
//! The dump's symbolic plane "does not replace models — it gives them
//! bones": formal structure that lets the system *prove things before
//! acting* (F02552, F02560 PDDL planners). This crate is the concrete core
//! of that plane — a STRIPS/PDDL-style forward planner plus a verifier.
//!
//! - **State** is a set of facts, packed as a 64-bit set (fact = bit index).
//! - **[`Action`]** has a precondition, an add list, and a delete list
//!   (classic STRIPS). It is applicable when the state contains its
//!   precondition; applying it sets the add bits and clears the delete bits.
//! - **[`plan`]** does breadth-first search over grounded actions to reach a
//!   goal, returning the shortest action sequence (a *plan*).
//! - **[`verify_plan`]** independently re-executes a plan and checks every
//!   step was applicable and the goal was reached — the "prove before
//!   acting" gate.
//!
//! Up to 64 facts (the bit width); deterministic and dependency-light.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod monitor;

pub use monitor::{SafetyProperty, Verdict, all_hold};

use serde::{Deserialize, Serialize};
use std::collections::{HashSet, VecDeque};
use thiserror::Error;

/// Schema version of the symbolic-plan surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A fact set, packed as a 64-bit mask (fact `i` = bit `i`).
pub type FactSet = u64;

/// Convenience: build a [`FactSet`] from fact indices.
pub fn facts(indices: &[u8]) -> FactSet {
    indices.iter().fold(0u64, |acc, &i| acc | (1u64 << i))
}

/// Whether `state` satisfies `goal` (every goal fact present).
#[inline]
pub fn satisfies(state: FactSet, goal: FactSet) -> bool {
    state & goal == goal
}

/// A STRIPS action: applicable when `precond ⊆ state`; applying clears `del`
/// then sets `add`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Action {
    /// Human-readable action name.
    pub name: String,
    /// Facts that must hold for the action to apply.
    pub precond: FactSet,
    /// Facts the action makes true.
    pub add: FactSet,
    /// Facts the action makes false.
    pub del: FactSet,
}

impl Action {
    /// Build an action from fact-index lists.
    pub fn new(name: &str, precond: &[u8], add: &[u8], del: &[u8]) -> Self {
        Self {
            name: name.to_string(),
            precond: facts(precond),
            add: facts(add),
            del: facts(del),
        }
    }

    /// Whether this action is applicable in `state`.
    #[inline]
    pub fn applicable(&self, state: FactSet) -> bool {
        state & self.precond == self.precond
    }

    /// Apply to `state` (clear `del`, then set `add`). Caller should check
    /// [`Action::applicable`] first.
    #[inline]
    pub fn apply(&self, state: FactSet) -> FactSet {
        (state & !self.del) | self.add
    }
}

/// A found plan: the action indices to execute, in order.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Plan {
    /// Indices into the action set, in execution order.
    pub steps: Vec<usize>,
}

impl Plan {
    /// Plan length (number of actions).
    pub fn len(&self) -> usize {
        self.steps.len()
    }

    /// Whether the plan is empty (the goal already held).
    pub fn is_empty(&self) -> bool {
        self.steps.is_empty()
    }
}

/// Planning failures.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum PlanError {
    /// A plan step indexed an action that doesn't exist.
    #[error("plan step {step} references action index {index} out of {count}")]
    BadActionIndex {
        /// Position in the plan.
        step: usize,
        /// The out-of-range index.
        index: usize,
        /// Number of actions available.
        count: usize,
    },
}

/// Forward breadth-first STRIPS planning: find the shortest action sequence
/// from `initial` to a state satisfying `goal`. Returns `None` if no plan is
/// found within `max_expansions` state expansions (the search bound).
///
/// BFS over a visited-state set guarantees the returned plan is of minimal
/// length.
pub fn plan(
    initial: FactSet,
    goal: FactSet,
    actions: &[Action],
    max_expansions: usize,
) -> Option<Plan> {
    if satisfies(initial, goal) {
        return Some(Plan { steps: vec![] });
    }
    let mut visited: HashSet<FactSet> = HashSet::new();
    visited.insert(initial);
    let mut queue: VecDeque<(FactSet, Vec<usize>)> = VecDeque::new();
    queue.push_back((initial, Vec::new()));
    let mut expansions = 0usize;

    while let Some((state, path)) = queue.pop_front() {
        if expansions >= max_expansions {
            break;
        }
        expansions += 1;
        for (i, action) in actions.iter().enumerate() {
            if !action.applicable(state) {
                continue;
            }
            let next = action.apply(state);
            if visited.insert(next) {
                let mut next_path = path.clone();
                next_path.push(i);
                if satisfies(next, goal) {
                    return Some(Plan { steps: next_path });
                }
                queue.push_back((next, next_path));
            }
        }
    }
    None
}

/// Independently re-execute a plan from `initial`, stopping at the first
/// inapplicable step, and return the reached state. The caller checks
/// [`satisfies`] against the goal — or use [`plan_is_sound`] for the single
/// boolean gate. Errors only on an out-of-range action index.
pub fn verify_plan(
    initial: FactSet,
    actions: &[Action],
    plan: &Plan,
) -> Result<FactSet, PlanError> {
    let mut state = initial;
    for (step, &index) in plan.steps.iter().enumerate() {
        let action = actions.get(index).ok_or(PlanError::BadActionIndex {
            step,
            index,
            count: actions.len(),
        })?;
        if !action.applicable(state) {
            // Not applicable → stop; the plan does not formally hold here.
            return Ok(state);
        }
        state = action.apply(state);
    }
    Ok(state)
}

/// Verify a plan reaches the goal with every step applicable — a single
/// boolean "is this plan sound?" gate.
pub fn plan_is_sound(initial: FactSet, goal: FactSet, actions: &[Action], plan: &Plan) -> bool {
    let mut state = initial;
    for &index in &plan.steps {
        match actions.get(index) {
            Some(a) if a.applicable(state) => state = a.apply(state),
            _ => return false,
        }
    }
    satisfies(state, goal)
}

#[cfg(test)]
mod tests {
    use super::*;

    // Facts: 0 = at_a, 1 = at_b, 2 = at_c, 3 = key, 4 = door_open
    const AT_A: u8 = 0;
    const AT_B: u8 = 1;
    const AT_C: u8 = 2;
    const KEY: u8 = 3;
    const DOOR_OPEN: u8 = 4;

    fn world() -> Vec<Action> {
        vec![
            // move a→b
            Action::new("a_to_b", &[AT_A], &[AT_B], &[AT_A]),
            // pick up key at b
            Action::new("grab_key", &[AT_B], &[KEY], &[]),
            // open door (needs key)
            Action::new("open_door", &[KEY], &[DOOR_OPEN], &[]),
            // move b→c (needs open door)
            Action::new("b_to_c", &[AT_B, DOOR_OPEN], &[AT_C], &[AT_B]),
        ]
    }

    #[test]
    fn applicable_and_apply() {
        let a = Action::new("a_to_b", &[AT_A], &[AT_B], &[AT_A]);
        assert!(a.applicable(facts(&[AT_A])));
        assert!(!a.applicable(facts(&[AT_B])));
        assert_eq!(a.apply(facts(&[AT_A])), facts(&[AT_B]));
    }

    #[test]
    fn already_at_goal_is_empty_plan() {
        let p = plan(facts(&[AT_C]), facts(&[AT_C]), &world(), 1000).unwrap();
        assert!(p.is_empty());
    }

    #[test]
    fn finds_multi_step_plan() {
        // from at_a, reach at_c: a→b, grab_key, open_door, b→c
        let p = plan(facts(&[AT_A]), facts(&[AT_C]), &world(), 10_000).unwrap();
        assert!(plan_is_sound(facts(&[AT_A]), facts(&[AT_C]), &world(), &p));
        // shortest such plan is 4 steps
        assert_eq!(p.len(), 4);
    }

    #[test]
    fn unsolvable_returns_none() {
        // goal fact 7 is never produced by any action
        assert!(plan(facts(&[AT_A]), facts(&[7]), &world(), 10_000).is_none());
    }

    #[test]
    fn verify_accepts_sound_plan_rejects_tampered() {
        let init = facts(&[AT_A]);
        let goal = facts(&[AT_C]);
        let acts = world();
        let p = plan(init, goal, &acts, 10_000).unwrap();
        assert!(plan_is_sound(init, goal, &acts, &p));

        // Tamper: drop the first step → later steps become inapplicable.
        let tampered = Plan {
            steps: p.steps[1..].to_vec(),
        };
        assert!(!plan_is_sound(init, goal, &acts, &tampered));
    }

    #[test]
    fn verify_plan_reaches_goal_state() {
        let init = facts(&[AT_A]);
        let goal = facts(&[AT_C]);
        let acts = world();
        let p = plan(init, goal, &acts, 10_000).unwrap();
        let reached = verify_plan(init, &acts, &p).unwrap();
        assert!(satisfies(reached, goal));
    }

    #[test]
    fn verify_rejects_bad_action_index() {
        let bad = Plan { steps: vec![99] };
        let err = verify_plan(facts(&[AT_A]), &world(), &bad).unwrap_err();
        assert!(matches!(err, PlanError::BadActionIndex { .. }));
    }

    #[test]
    fn search_bound_can_fail_to_find() {
        // With a tiny expansion budget, the 4-step plan isn't found.
        assert!(plan(facts(&[AT_A]), facts(&[AT_C]), &world(), 1).is_none());
    }

    #[test]
    fn action_serde_round_trip() {
        let a = Action::new("open_door", &[KEY], &[DOOR_OPEN], &[]);
        let j = serde_json::to_string(&a).unwrap();
        let back: Action = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
