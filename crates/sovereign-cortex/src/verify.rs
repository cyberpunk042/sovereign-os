//! Real-time verification of the cortex's own decisions (AgentVerify-style,
//! F02556-F02558).
//!
//! The symbolic plane's safety monitors ([`sovereign_symbolic_plan`]) check
//! a *trace of fact-sets* against safety properties. This module projects
//! each [`CortexDecision`] into a fact-set, so a whole session's decisions
//! become a trace the monitors can verify — formal checks over what the
//! agent *actually did*, the dump's "real-time verification of reasoning
//! agents" applied to the cortex itself.

use crate::CortexDecision;
use sovereign_symbolic_plan::{SafetyProperty, all_hold, facts};
use sovereign_value_plane::NextAction;

/// Decision fact: the verdict committed.
pub const F_COMMITTED: u8 = 0;
/// Decision fact: the branch was pruned (a hard failure).
pub const F_PRUNED: u8 = 1;
/// Decision fact: work spilled to the cloud expert plane.
pub const F_CLOUD_SPILL: u8 = 2;
/// Decision fact: placement fell back off the canonical role.
pub const F_FELL_BACK: u8 = 3;
/// Decision fact: the branch was high-risk.
pub const F_HIGH_RISK: u8 = 4;
/// Decision fact: deeper (HRM) reasoning was engaged.
pub const F_REASONED: u8 = 5;

/// Risk score above which a decision is flagged [`F_HIGH_RISK`].
pub const HIGH_RISK_THRESHOLD: f32 = 0.7;

/// Project a decision into a fact-set for symbolic verification.
pub fn decision_facts(d: &CortexDecision) -> u64 {
    let mut bits: Vec<u8> = Vec::new();
    match d.assessment.suggested_next_action {
        NextAction::Commit => bits.push(F_COMMITTED),
        NextAction::Prune => bits.push(F_PRUNED),
        _ => {}
    }
    if d.placement.spilled_to_cloud {
        bits.push(F_CLOUD_SPILL);
    }
    if d.placement.fell_back {
        bits.push(F_FELL_BACK);
    }
    if d.assessment.risk_score > HIGH_RISK_THRESHOLD {
        bits.push(F_HIGH_RISK);
    }
    if d.reasoning.is_some() {
        bits.push(F_REASONED);
    }
    facts(&bits)
}

/// Build the fact-trace for a session's decisions (in order).
pub fn session_trace(decisions: &[CortexDecision]) -> Vec<u64> {
    decisions.iter().map(decision_facts).collect()
}

/// Verify a session's decisions against safety properties: `true` only if
/// every property holds over the decision trace (compositional, F02558).
pub fn verify_session(decisions: &[CortexDecision], properties: &[SafetyProperty]) -> bool {
    all_hold(properties, &session_trace(decisions))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Cortex, demo_requests, seed_memory};
    use sovereign_symbolic_plan::facts as f;

    #[test]
    fn committed_decision_has_committed_fact() {
        let cortex = Cortex::with_memory(seed_memory());
        let d = cortex.tick(&demo_requests().remove(0)).unwrap();
        let bits = decision_facts(&d);
        assert!(bits & (1 << F_COMMITTED) != 0);
        assert!(bits & (1 << F_CLOUD_SPILL) == 0);
    }

    #[test]
    fn clean_session_satisfies_safety_properties() {
        let mut cortex = Cortex::with_memory(seed_memory());
        let (decisions, _) = cortex.run_session(&demo_requests());
        // Safety: never spill to cloud; always reach a committed decision.
        let props = [
            SafetyProperty::Never(f(&[F_CLOUD_SPILL])),
            SafetyProperty::Always(f(&[F_COMMITTED])),
        ];
        assert!(verify_session(&decisions, &props));
    }

    #[test]
    fn cloud_spill_violates_no_spill_property() {
        // Force a cloud spill: FP16 deep job, Oracle overloaded, cloud on.
        let cortex = Cortex::new();
        let mut r = demo_requests().remove(1);
        r.oracle = sovereign_srp_scheduler::RolePressure::overloaded();
        r.allow_cloud = true;
        let d = cortex.tick(&r).unwrap();
        assert!(d.placement.spilled_to_cloud);

        let trace = session_trace(&[d]);
        let prop = SafetyProperty::Never(f(&[F_CLOUD_SPILL]));
        assert!(!prop.check(&trace).holds, "cloud spill must be flagged");
    }
}
