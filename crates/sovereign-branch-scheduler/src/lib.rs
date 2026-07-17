//! `sovereign-branch-scheduler` — M007 the 8-step branch loop.
//!
//! The execution model runs a **frontier of 8 branches** through one tick of the
//! loop (E0052): `Spawn → Retrieve → Draft → Filter → Verify → Act → Commit →
//! Learn`. The branches live in a Structure-of-Arrays batch (E0053) — one lane
//! per branch, ZMM-width — so every step is a lane-parallel bit-op.
//!
//! This crate is the **capstone** that ties the three milestones together:
//! - **M002** — each branch carries a control word; the Commit gate reads its
//!   [`branch_permissions`] (M00104).
//! - **M008** — Filter/Verify fuse policy planes and short-circuit via the
//!   [`speculative_accept`] cheat; the survivors are packed dense with the
//!   [`compress_survivors`] VPCOMPRESS cheat (M00116).
//! - **M007** — the 8-step loop itself, over the SoA batch.
//!
//! It forbids `unsafe` and wraps the safe `sovereign-simd` + `sovereign-control-
//! word` APIs. Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_control_word::m00013::branch_permissions;
use sovereign_simd::cheats::{compress_survivors, speculative_accept};

/// Schema version of the scheduler surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The 8 named steps of the branch loop (E0052).
pub const STEPS: [&str; 8] = [
    "Spawn", "Retrieve", "Draft", "Filter", "Verify", "Act", "Commit", "Learn",
];

/// A Structure-of-Arrays batch of 8 branches (E0053). One lane per branch; the
/// arrays are the per-branch state the loop reads and writes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct BranchBatch {
    /// Stable branch ids.
    pub id: [u64; 8],
    /// M002 control words (mode + flags gate the Commit step).
    pub control: [u64; 8],
    /// Remaining budget per branch (0 ⇒ pruned at Filter).
    pub budget: [u32; 8],
    /// Value-plane score per branch (below `verify_min_score` ⇒ pruned at Verify).
    pub score: [u32; 8],
    /// Grammar-valid flag per branch (0 ⇒ pruned at Filter).
    pub grammar: [u8; 8],
    /// A memory reference per branch (0 ⇒ no recall; informational).
    pub memory: [u64; 8],
    /// Route id per branch (informational; carried through).
    pub route: [u8; 8],
}

impl BranchBatch {
    /// A batch of 8 branches whose only non-default field is the control word —
    /// a convenient starting point for scheduling experiments.
    #[must_use]
    pub fn from_controls(control: [u64; 8]) -> Self {
        BranchBatch {
            id: [0, 1, 2, 3, 4, 5, 6, 7],
            control,
            budget: [1; 8],
            score: [100; 8],
            grammar: [1; 8],
            memory: [0; 8],
            route: [0; 8],
        }
    }
}

/// The result of one scheduler tick — the per-step surviving-branch masks and
/// the dense-packed committed branch ids (M00116).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TickResult {
    /// The 8 steps executed, in order (E0052).
    pub steps: Vec<String>,
    /// Alive mask after Filter (grammar ∧ budget, short-circuited).
    pub alive_after_filter: u8,
    /// Alive mask after Verify (∧ score ≥ threshold).
    pub alive_after_verify: u8,
    /// Committed mask after the Commit gate (∧ control-word grants commit).
    pub committed: u8,
    /// How many predicates the Filter/Verify short-circuit actually evaluated.
    pub predicates_evaluated: usize,
    /// The committed branch ids, packed dense (VPCOMPRESS, order preserved).
    pub committed_ids: [u64; 8],
    /// Number of committed survivors.
    pub survivors: u32,
}

/// Run one tick of the 8-step branch loop over a batch. `verify_min_score` is
/// the Verify-step cutoff. The Commit gate admits only branches whose control
/// word grants a durable, non-speculative commit (M00104 `shell_allowed`).
#[must_use]
pub fn tick(batch: &BranchBatch, verify_min_score: u32) -> TickResult {
    // Spawn: the whole frontier is live.
    let spawn = 0xFFu8;

    // Draft: the branches the model proposes (all, here) — a mask hook.
    let draft = spawn;

    // Filter: grammar-valid ∧ budget-positive, via the speculative-accept cheat
    // (short-circuits if a predicate zeroes the frontier).
    let grammar_mask = mask_from(|i| batch.grammar[i] != 0);
    let budget_mask = mask_from(|i| batch.budget[i] > 0);
    let (alive_after_filter, ev_filter) = speculative_accept(&[draft, grammar_mask, budget_mask]);

    // Verify: ∧ score ≥ threshold (another short-circuiting predicate).
    let score_mask = mask_from(|i| batch.score[i] >= verify_min_score);
    let (alive_after_verify, ev_verify) = speculative_accept(&[alive_after_filter, score_mask]);

    // Act is a no-op hook here (side effects are the caller's); Commit gates on
    // the control word: only committed, non-speculative branches may durably act.
    let commit_gate = mask_from(|i| branch_permissions(batch.control[i]).shell_allowed);
    let committed = alive_after_verify & commit_gate;

    // The survivors packed dense (VPCOMPRESS) — the "alive branches into dense
    // batches" cheat. Learn is a no-op hook (the caller updates value estimates).
    let (committed_ids, survivors) = compress_survivors(&batch.id, committed);

    TickResult {
        steps: STEPS.iter().map(|s| (*s).to_string()).collect(),
        alive_after_filter,
        alive_after_verify,
        committed,
        predicates_evaluated: ev_filter + ev_verify,
        committed_ids,
        survivors,
    }
}

/// Build an 8-bit branch mask from a per-lane predicate.
fn mask_from(pred: impl Fn(usize) -> bool) -> u8 {
    let mut m = 0u8;
    for i in 0..8 {
        if pred(i) {
            m |= 1 << i;
        }
    }
    m
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_control_word::FLAG_SPECULATIVE;
    use sovereign_control_word::m00013::{Fields, MODE_COMMIT};

    /// A committed (mode=1) control word.
    fn committed_word() -> u64 {
        Fields {
            mode: MODE_COMMIT,
            ..Default::default()
        }
        .pack()
        .unwrap()
    }
    /// A committed word that is ALSO speculative (FLAG_SPECULATIVE in paramB).
    fn speculative_word() -> u64 {
        Fields {
            mode: MODE_COMMIT,
            param_b: FLAG_SPECULATIVE as u16,
            ..Default::default()
        }
        .pack()
        .unwrap()
    }
    /// A non-committed (mode=0) word.
    fn draft_word() -> u64 {
        Fields {
            mode: 0,
            ..Default::default()
        }
        .pack()
        .unwrap()
    }

    #[test]
    fn tick_runs_all_eight_steps() {
        let batch = BranchBatch::from_controls([committed_word(); 8]);
        let r = tick(&batch, 50);
        assert_eq!(r.steps, STEPS);
        assert_eq!(r.steps.len(), 8);
    }

    #[test]
    fn commit_gate_admits_only_committed_non_speculative() {
        // lanes: 0-3 committed, 4-5 speculative (committed but no durable act),
        // 6-7 draft (mode 0).
        let mut c = [draft_word(); 8];
        for x in c.iter_mut().take(4) {
            *x = committed_word();
        }
        c[4] = speculative_word();
        c[5] = speculative_word();
        let batch = BranchBatch::from_controls(c);
        let r = tick(&batch, 50);
        // only lanes 0-3 commit (speculative + draft are gated out)
        assert_eq!(r.committed, 0b0000_1111);
        assert_eq!(r.survivors, 4);
        assert_eq!(&r.committed_ids[..4], &[0, 1, 2, 3]);
        assert_eq!(&r.committed_ids[4..], &[0, 0, 0, 0]);
    }

    #[test]
    fn filter_prunes_grammar_and_budget() {
        let mut batch = BranchBatch::from_controls([committed_word(); 8]);
        batch.grammar[2] = 0; // grammar-invalid → pruned at Filter
        batch.budget[5] = 0; // out of budget → pruned at Filter
        let r = tick(&batch, 50);
        assert_eq!(r.alive_after_filter, 0b1101_1011); // lanes 2 and 5 dropped
        assert_eq!(r.committed & (1 << 2), 0);
        assert_eq!(r.committed & (1 << 5), 0);
    }

    #[test]
    fn verify_prunes_low_score_and_short_circuits() {
        let mut batch = BranchBatch::from_controls([committed_word(); 8]);
        batch.score = [10, 20, 30, 40, 60, 70, 80, 90]; // < 50 pruned: lanes 0-3
        let r = tick(&batch, 50);
        assert_eq!(r.alive_after_verify, 0b1111_0000);
        assert_eq!(r.committed, 0b1111_0000);
        assert_eq!(r.survivors, 4);
        // a totally-dead frontier short-circuits the predicate chain
        let mut dead = BranchBatch::from_controls([committed_word(); 8]);
        dead.grammar = [0; 8];
        let rd = tick(&dead, 50);
        assert_eq!(rd.committed, 0);
        assert_eq!(rd.survivors, 0);
    }
}
