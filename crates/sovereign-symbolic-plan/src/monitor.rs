//! Temporal-logic safety monitors (M031: temporal-logic monitors / FSMs,
//! F02563/F02564; AgentVerify-style LTL checks, F02557).
//!
//! Where [`crate::plan`] decides *what to do*, this module checks a *trace*
//! of states against a safety property — the runtime verification the dump
//! calls for ("real-time verification of reasoning agents", F02556). A
//! trace is the sequence of [`crate::FactSet`] states an agent passed
//! through; a [`SafetyProperty`] is checked against it, yielding a
//! [`Verdict`] that pinpoints the first violating step.
//!
//! The four properties cover the common agent-safety patterns: an invariant
//! that must always hold, facts that must never occur, a goal that must
//! eventually hold, and an ordering constraint (one fact must not occur
//! before another).

use crate::{FactSet, satisfies};
use serde::{Deserialize, Serialize};

/// A safety property checked against a state trace.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SafetyProperty {
    /// Invariant: every state must contain all these facts.
    Always(FactSet),
    /// Forbidden: no state may contain any of these facts.
    Never(FactSet),
    /// Liveness (bounded to the trace): some state must contain all of these.
    Eventually(FactSet),
    /// Ordering: `then` must not become true before `first` has been true.
    Precedes {
        /// The fact set that must occur first.
        first: FactSet,
        /// The fact set that may only occur after `first`.
        then: FactSet,
    },
}

/// The result of checking a property against a trace.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Verdict {
    /// Whether the property held over the whole trace.
    pub holds: bool,
    /// The first trace index that violates the property, if any.
    pub violated_at: Option<usize>,
}

impl Verdict {
    /// A passing verdict.
    pub const PASS: Verdict = Verdict {
        holds: true,
        violated_at: None,
    };

    fn fail_at(i: usize) -> Verdict {
        Verdict {
            holds: false,
            violated_at: Some(i),
        }
    }
}

impl SafetyProperty {
    /// Check this property against a state `trace` (states in time order).
    pub fn check(&self, trace: &[FactSet]) -> Verdict {
        match *self {
            SafetyProperty::Always(req) => {
                for (i, &s) in trace.iter().enumerate() {
                    if !satisfies(s, req) {
                        return Verdict::fail_at(i);
                    }
                }
                Verdict::PASS
            }
            SafetyProperty::Never(forbidden) => {
                for (i, &s) in trace.iter().enumerate() {
                    if s & forbidden != 0 {
                        return Verdict::fail_at(i);
                    }
                }
                Verdict::PASS
            }
            SafetyProperty::Eventually(req) => {
                if trace.iter().any(|&s| satisfies(s, req)) {
                    Verdict::PASS
                } else {
                    // Liveness failure isn't localized to one step.
                    Verdict {
                        holds: false,
                        violated_at: None,
                    }
                }
            }
            SafetyProperty::Precedes { first, then } => {
                let mut seen_first = false;
                for (i, &s) in trace.iter().enumerate() {
                    if satisfies(s, first) {
                        seen_first = true;
                    }
                    if satisfies(s, then) && !seen_first {
                        return Verdict::fail_at(i);
                    }
                }
                Verdict::PASS
            }
        }
    }
}

/// Check several properties against a trace; returns `true` only if all hold
/// (compositional verification — the dump's finding that compositional formal
/// checks beat monolithic ones, F02558).
pub fn all_hold(properties: &[SafetyProperty], trace: &[FactSet]) -> bool {
    properties.iter().all(|p| p.check(trace).holds)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::facts;

    // 0 = armed, 1 = safe, 2 = fired, 3 = authorized
    const ARMED: u8 = 0;
    const SAFE: u8 = 1;
    const FIRED: u8 = 2;
    const AUTHORIZED: u8 = 3;

    #[test]
    fn always_invariant_holds_and_fails() {
        let good = [facts(&[SAFE]), facts(&[SAFE, ARMED]), facts(&[SAFE])];
        assert_eq!(
            SafetyProperty::Always(facts(&[SAFE])).check(&good),
            Verdict::PASS
        );

        let bad = [facts(&[SAFE]), facts(&[ARMED])]; // step 1 missing SAFE
        let v = SafetyProperty::Always(facts(&[SAFE])).check(&bad);
        assert!(!v.holds);
        assert_eq!(v.violated_at, Some(1));
    }

    #[test]
    fn never_catches_forbidden_fact() {
        let trace = [facts(&[ARMED]), facts(&[ARMED, FIRED])];
        let v = SafetyProperty::Never(facts(&[FIRED])).check(&trace);
        assert!(!v.holds);
        assert_eq!(v.violated_at, Some(1));
        // a clean trace passes
        assert!(
            SafetyProperty::Never(facts(&[FIRED]))
                .check(&[facts(&[ARMED])])
                .holds
        );
    }

    #[test]
    fn eventually_requires_occurrence() {
        let reached = [facts(&[ARMED]), facts(&[FIRED])];
        assert!(
            SafetyProperty::Eventually(facts(&[FIRED]))
                .check(&reached)
                .holds
        );

        let never = [facts(&[ARMED]), facts(&[SAFE])];
        let v = SafetyProperty::Eventually(facts(&[FIRED])).check(&never);
        assert!(!v.holds);
        assert_eq!(v.violated_at, None); // liveness failure isn't localized
    }

    #[test]
    fn precedes_enforces_ordering() {
        // authorization must precede firing
        let prop = SafetyProperty::Precedes {
            first: facts(&[AUTHORIZED]),
            then: facts(&[FIRED]),
        };
        let ok = [facts(&[AUTHORIZED]), facts(&[AUTHORIZED, FIRED])];
        assert!(prop.check(&ok).holds);

        let violation = [facts(&[ARMED]), facts(&[FIRED])]; // fired w/o prior auth
        let v = prop.check(&violation);
        assert!(!v.holds);
        assert_eq!(v.violated_at, Some(1));
    }

    #[test]
    fn precedes_same_step_is_allowed() {
        // first and then in the same state counts as "first seen".
        let prop = SafetyProperty::Precedes {
            first: facts(&[AUTHORIZED]),
            then: facts(&[FIRED]),
        };
        let same = [facts(&[AUTHORIZED, FIRED])];
        assert!(prop.check(&same).holds);
    }

    #[test]
    fn compositional_all_hold() {
        let trace = [
            facts(&[SAFE, AUTHORIZED]),
            facts(&[SAFE, AUTHORIZED, FIRED]),
        ];
        let props = [
            SafetyProperty::Always(facts(&[SAFE])),
            SafetyProperty::Precedes {
                first: facts(&[AUTHORIZED]),
                then: facts(&[FIRED]),
            },
        ];
        assert!(all_hold(&props, &trace));

        // add a property that fails → composition fails
        let with_bad = [
            SafetyProperty::Never(facts(&[FIRED])),
            SafetyProperty::Always(facts(&[SAFE])),
        ];
        assert!(!all_hold(&with_bad, &trace));
    }

    #[test]
    fn empty_trace_passes_safety_fails_liveness() {
        assert!(SafetyProperty::Always(facts(&[SAFE])).check(&[]).holds);
        assert!(SafetyProperty::Never(facts(&[FIRED])).check(&[]).holds);
        assert!(!SafetyProperty::Eventually(facts(&[FIRED])).check(&[]).holds);
    }

    #[test]
    fn property_serde_round_trip() {
        let p = SafetyProperty::Precedes {
            first: facts(&[AUTHORIZED]),
            then: facts(&[FIRED]),
        };
        let j = serde_json::to_string(&p).unwrap();
        let back: SafetyProperty = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
