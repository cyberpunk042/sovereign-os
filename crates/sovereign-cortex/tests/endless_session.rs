//! Capstone integration test: the endless-operation lifecycle.
//!
//! Exercises, through the public API only, the full long-running story the
//! cortex is built for — a bounded, continuously-learning session that
//! stays healthy over many turns: learns from committed outcomes, keeps
//! memory within its capacity bound, improves its verdicts, and ages stale
//! memory on maintenance.

use sovereign_cortex::{Cortex, demo_requests};

#[test]
fn endless_bounded_learning_session_stays_healthy() {
    let template = demo_requests().remove(0); // simple/local scenario — commits
    let reqs: Vec<_> = std::iter::repeat_with(|| template.clone())
        .take(20)
        .collect();

    // A small bound, far below the 20 requests we will learn from.
    let mut cortex = Cortex::bounded(3);
    let (decisions, report) = cortex.run_session(&reqs);

    // Every turn decided + committed + learned...
    assert_eq!(report.total, 20);
    assert_eq!(report.committed, 20);
    assert_eq!(report.learned, 20);
    assert_eq!(decisions.len(), 20);

    // ...yet memory never blew past the bound despite 20 learns.
    assert!(
        cortex.memory.len() <= 3,
        "bound must hold across the session, got {}",
        cortex.memory.len()
    );

    // Learning effect: a late decision (with recalled memory) scores at least
    // as high as a cold cortex deciding the same request from scratch.
    let cold = Cortex::new().tick(&template).unwrap();
    let warm = decisions.last().unwrap();
    assert!(
        warm.assessment.step_score >= cold.assessment.step_score,
        "warm {} should be >= cold {}",
        warm.assessment.step_score,
        cold.assessment.step_score
    );

    // Maintenance ages stale memory (far-future tick, ttl 1).
    let aged = cortex.maintain(1_000_000, 1);
    assert!(aged >= 1, "stale memory should age on maintenance");
}

#[test]
fn bounded_cortex_recalls_within_the_bound() {
    // After a long session, the bounded cortex still recalls supporting
    // memory on the next request (it kept its best memories).
    let template = demo_requests().remove(0);
    let reqs: Vec<_> = std::iter::repeat_with(|| template.clone())
        .take(10)
        .collect();

    let mut cortex = Cortex::bounded(2);
    let _ = cortex.run_session(&reqs);

    let next = cortex.tick(&template).unwrap();
    assert!(
        !next.recalled.is_empty(),
        "a learned-and-bounded cortex should still recall its retained memories"
    );
    assert!(cortex.memory.len() <= 2);
}
