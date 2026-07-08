//! Black-box integration test of the cortex's full self-governance loop:
//! decide → learn → audit (hash-chained ledger) → verify (safety monitors),
//! exercised through the public API as a downstream consumer would.

use sovereign_cortex::verify::F_CLOUD_SPILL;
use sovereign_cortex::{Cortex, SafetyProperty, demo_requests, facts, seed_memory, verify_session};

#[test]
fn session_is_audited_and_formally_safe() {
    let mut cortex = Cortex::with_memory(seed_memory());
    let (decisions, report) = cortex.run_session(&demo_requests());

    // every decided request is committed in this demo
    assert_eq!(report.committed, decisions.len());

    // 1. the decision audit trail is complete and tamper-evident
    assert_eq!(cortex.ledger.len(), decisions.len());
    assert!(cortex.ledger.verify().is_ok(), "audit trail must verify");

    // 2. the session satisfies the safety envelope (no cloud spill)
    let safety = [SafetyProperty::Never(facts(&[F_CLOUD_SPILL]))];
    assert!(
        verify_session(&decisions, &safety),
        "private workstation must never spill to cloud"
    );
}

#[test]
fn tampering_the_audit_trail_is_detected() {
    let mut cortex = Cortex::new();
    let _ = cortex.run_session(&demo_requests());
    assert!(cortex.ledger.verify().is_ok());

    // Reconstruct the ledger with one entry's payload altered → verify fails.
    let mut entries = cortex.ledger.entries().to_vec();
    assert!(!entries.is_empty());
    entries[0].payload = "FORGED".to_string();
    let forged = sovereign_replay_ledger::ReplayLedger::from_entries(entries);
    assert!(forged.verify().is_err(), "tampering must be detected");
}
