//! Black-box integration tests for the cortex assembly.
//!
//! These exercise the whole composed pipeline through the public API only
//! (as a downstream consumer would), with no access to crate internals —
//! complementing the in-crate unit tests.

use sovereign_cortex::{Cortex, demo_requests, seed_memory};

#[test]
fn every_demo_request_decides_and_ratifies() {
    let cortex = Cortex::with_memory(seed_memory());
    for (i, req) in demo_requests().iter().enumerate() {
        let (decision, cycle) = cortex.act(req).expect("demo request should decide");
        // Each demo scenario is a strong request → ratified Commit.
        assert!(
            cycle.committed(),
            "scenario {i} should ratify through Trinity: {}",
            decision.summary
        );
        // The decision carries a coherent compute profile.
        assert!(decision.compute.bits_per_param > 0.0);
        assert!(!decision.summary.is_empty());
    }
}

#[test]
fn memory_raises_confidence_end_to_end() {
    // Same weakened request, with vs without supporting memory.
    let mut req = demo_requests().remove(0);
    req.reward.evidence = 0.4;
    req.reward.confidence_calibration = 0.5;

    let with_mem = Cortex::with_memory(seed_memory()).tick(&req).expect("tick");
    let without_mem = Cortex::new().tick(&req).expect("tick");

    assert!(
        with_mem.recalled.len() > without_mem.recalled.len(),
        "seeded cortex should recall supporting memory"
    );
    assert!(
        with_mem.assessment.step_score > without_mem.assessment.step_score,
        "recalled evidence should raise the verdict score: {} vs {}",
        with_mem.assessment.step_score,
        without_mem.assessment.step_score
    );
}

#[test]
fn decision_serializes_to_wellformed_json() {
    let cortex = Cortex::with_memory(seed_memory());
    let decision = cortex.tick(&demo_requests().remove(0)).expect("tick");

    let json = serde_json::to_string(&decision).expect("serialize");
    let parsed: serde_json::Value = serde_json::from_str(&json).expect("parse back");

    // The composed shape is present and navigable.
    assert!(parsed.get("route").is_some());
    assert!(parsed.get("placement").is_some());
    assert!(parsed.get("assessment").is_some());
    assert!(parsed.get("compute").is_some());
    assert!(parsed["summary"].as_str().is_some());
}

#[test]
fn deliberation_over_request_rewards_runs_clean() {
    // Build candidate rewards by cloning the demo reward (no internal types
    // named) and a stronger variant; the strongest should win.
    let req = demo_requests().remove(0);
    let weak = req.reward.clone();
    let mut strong = req.reward.clone();
    strong.correctness = 1.0;
    strong.evidence = 1.0;

    let cortex = Cortex::with_memory(seed_memory());
    // Tier via the value-plane re-export through the cortex's dependency.
    let outcome = cortex
        .deliberate(
            &req,
            &[weak, strong],
            sovereign_value_plane::IntelligenceTier::Deliberate,
        )
        .expect("deliberate");
    assert_eq!(outcome.candidates_considered, 2);
    let best = outcome.best.expect("a winner");
    assert_eq!(best.branch_id, 1, "the stronger candidate should win");
}
