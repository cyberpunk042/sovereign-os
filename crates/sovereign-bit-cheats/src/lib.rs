//! `sovereign-bit-cheats` — the policy/logic half of the M008 bit-level cheats.
//!
//! The SIMD half (VPTERNLOG / VPCOMPRESS / k-mask / bloom / token-law) lives in
//! `sovereign-simd::cheats`; this crate holds the four cheats that are logic, not
//! vector math:
//!
//! - **M00113 bitfields-as-microcode** — the control word *is* executable
//!   policy: its fields decode into a micro-op program that runs to a decision.
//! - **M00119 two-level rule table** — `rule_id → table[rule_id][event_class]`,
//!   a cached two-level lookup.
//! - **M00121 branch-prediction analogy** — a 2-bit saturating-counter predictor
//!   (the 4090-predictor / Blackwell-retirement / reorder-commit analogy).
//! - **M00126 three-representation layout** — hot numeric ‖ hot bitfield ‖ cold
//!   text; hot ops never touch the cold text (F00670).
//!
//! Safe — forbids `unsafe`. Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the bit-cheats surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

// ── M00113 bitfields-as-microcode ──

/// A micro-op decoded from a control word's bitfields (M00113). The control word
/// isn't data the policy *reads* — it's a program the policy *runs*.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum MicroOp {
    /// mode == 1: durably commit the branch's effects.
    Commit,
    /// FLAG_SANDBOX: run isolated (no durable side effects).
    Sandbox,
    /// FLAG_SPECULATIVE: draft-only, discard on the real path.
    Speculate,
    /// FLAG_REPLAY: log for deterministic replay.
    Replay,
    /// FLAG_AUDIT: emit an audit record.
    Audit,
    /// FLAG_COMMIT_GATE: require the Auditor gate before committing.
    RequireGate,
}

/// The outcome of executing a control word's microcode program.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct PolicyOutcome {
    /// The branch may durably commit.
    pub commit: bool,
    /// Effects are sandboxed.
    pub sandboxed: bool,
    /// The branch is speculative (no durable effects).
    pub speculative: bool,
    /// The branch is replay-logged.
    pub replay: bool,
    /// The branch is audited.
    pub audited: bool,
    /// A gate is required before commit.
    pub gate_required: bool,
}

/// M00113 — decode a control word's bitfields into its micro-op program. Reads
/// the M00013 `mode` (bits 0..4) and the flag bits packed in `paramB`
/// (bits 48..64), the same bits [`sovereign_control_word::m00013::branch_permissions`]
/// reads — but as an executable sequence, not a permission struct.
#[must_use]
pub fn decode_microcode(control_word: u64) -> Vec<MicroOp> {
    use sovereign_control_word::{
        FLAG_AUDIT, FLAG_COMMIT_GATE, FLAG_REPLAY, FLAG_SANDBOX, FLAG_SPECULATIVE,
    };
    let mode = (control_word & 0xF) as u16;
    let flags = ((control_word >> 48) & 0xFFFF) as u16;
    let has = |f: u8| flags & (f as u16) != 0;
    let mut ops = Vec::new();
    if mode == sovereign_control_word::m00013::MODE_COMMIT {
        ops.push(MicroOp::Commit);
    }
    if has(FLAG_COMMIT_GATE) {
        ops.push(MicroOp::RequireGate);
    }
    if has(FLAG_SANDBOX) {
        ops.push(MicroOp::Sandbox);
    }
    if has(FLAG_REPLAY) {
        ops.push(MicroOp::Replay);
    }
    if has(FLAG_AUDIT) {
        ops.push(MicroOp::Audit);
    }
    if has(FLAG_SPECULATIVE) {
        ops.push(MicroOp::Speculate);
    }
    ops
}

/// M00113 — execute a micro-op program to a [`PolicyOutcome`]. Speculative or
/// sandboxed programs cannot commit (the effects are non-durable).
#[must_use]
pub fn execute_microcode(ops: &[MicroOp]) -> PolicyOutcome {
    let mut o = PolicyOutcome::default();
    for op in ops {
        match op {
            MicroOp::Commit => o.commit = true,
            MicroOp::Sandbox => o.sandboxed = true,
            MicroOp::Speculate => o.speculative = true,
            MicroOp::Replay => o.replay = true,
            MicroOp::Audit => o.audited = true,
            MicroOp::RequireGate => o.gate_required = true,
        }
    }
    // a speculative or sandboxed branch never durably commits.
    if o.speculative || o.sandboxed {
        o.commit = false;
    }
    o
}

// ── M00119 two-level rule table ──

/// M00119 — a cached two-level rule table: `rule_id → row → table[event_class]`.
/// The outer index selects a rule's row, the inner a decision per event class.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct TwoLevelTable {
    rows: Vec<Vec<u8>>,
}

impl TwoLevelTable {
    /// Build from `rule_id`-indexed rows of per-event-class decisions.
    #[must_use]
    pub fn new(rows: Vec<Vec<u8>>) -> Self {
        TwoLevelTable { rows }
    }

    /// Look up the decision for `(rule_id, event_class)`. Out-of-range → `None`.
    #[must_use]
    pub fn lookup(&self, rule_id: usize, event_class: usize) -> Option<u8> {
        self.rows
            .get(rule_id)
            .and_then(|row| row.get(event_class))
            .copied()
    }

    /// Number of rules (rows).
    #[must_use]
    pub fn rules(&self) -> usize {
        self.rows.len()
    }
}

// ── M00121 branch-prediction analogy ──

/// A 2-bit saturating counter (the classic branch-predictor cell).
/// 0-1 predict "not taken", 2-3 predict "taken".
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct SaturatingCounter(u8);

impl Default for SaturatingCounter {
    fn default() -> Self {
        SaturatingCounter(1) // weakly not-taken
    }
}

impl SaturatingCounter {
    /// Predict: `true` = taken (counter ≥ 2).
    #[must_use]
    pub fn predict(self) -> bool {
        self.0 >= 2
    }
    /// Update toward the actual outcome (saturating at 0..=3).
    pub fn update(&mut self, taken: bool) {
        if taken {
            self.0 = (self.0 + 1).min(3);
        } else {
            self.0 = self.0.saturating_sub(1);
        }
    }
}

/// M00121 — a branch predictor over N branch slots (the 4090-predictor analogy):
/// predict whether a branch will be "taken" (accepted) from its history, retire
/// the actual outcome, and track accuracy (the reorder-commit signal).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BranchPredictor {
    counters: Vec<SaturatingCounter>,
    hits: u64,
    total: u64,
}

impl BranchPredictor {
    /// A predictor with `slots` branch slots.
    #[must_use]
    pub fn new(slots: usize) -> Self {
        BranchPredictor {
            counters: vec![SaturatingCounter::default(); slots],
            hits: 0,
            total: 0,
        }
    }

    /// Predict the outcome for `slot` (false for an out-of-range slot).
    #[must_use]
    pub fn predict(&self, slot: usize) -> bool {
        self.counters
            .get(slot)
            .map(|c| c.predict())
            .unwrap_or(false)
    }

    /// Retire the actual outcome for `slot`: score the prediction, then update.
    pub fn retire(&mut self, slot: usize, taken: bool) {
        if let Some(c) = self.counters.get_mut(slot) {
            if c.predict() == taken {
                self.hits += 1;
            }
            self.total += 1;
            c.update(taken);
        }
    }

    /// Prediction accuracy so far (0.0..=1.0); 1.0 before any retirement.
    #[must_use]
    pub fn accuracy(&self) -> f64 {
        if self.total == 0 {
            1.0
        } else {
            self.hits as f64 / self.total as f64
        }
    }
}

// ── M00126 three-representation layout ──

/// M00126 — a branch in three representations: a hot numeric vector, a hot
/// bitfield law, and a cold text payload. Hot ops read only the first two; the
/// cold text is loaded lazily and a load counter proves the hot path never
/// touches it (F00670).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThreeRep {
    /// Hot numeric representation (scores / logits).
    pub dense: Vec<f32>,
    /// Hot bitfield law (grammar / tool / route bits).
    pub bitfield: u64,
    /// Cold text payload — only materialized on an explicit cold read.
    text: String,
    /// How many times the cold text has been read (starts 0).
    cold_reads: u64,
}

impl ThreeRep {
    /// Build a three-representation branch.
    #[must_use]
    pub fn new(dense: Vec<f32>, bitfield: u64, text: impl Into<String>) -> Self {
        ThreeRep {
            dense,
            bitfield,
            text: text.into(),
            cold_reads: 0,
        }
    }

    /// A hot numeric op: the sum of the dense vector. Never touches cold text.
    #[must_use]
    pub fn hot_score(&self) -> f32 {
        self.dense.iter().sum()
    }

    /// A hot bitfield op: whether a law bit is set. Never touches cold text.
    #[must_use]
    pub fn hot_law(&self, bit: u32) -> bool {
        self.bitfield & (1u64 << (bit & 63)) != 0
    }

    /// The cold read — materialize the text payload (increments the load count).
    pub fn cold_text(&mut self) -> &str {
        self.cold_reads += 1;
        &self.text
    }

    /// How many times the cold text has actually been loaded.
    #[must_use]
    pub fn cold_reads(&self) -> u64 {
        self.cold_reads
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_control_word::m00013::{Fields, MODE_COMMIT};
    use sovereign_control_word::{FLAG_AUDIT, FLAG_SANDBOX, FLAG_SPECULATIVE};

    fn word(mode: u16, flags: u16) -> u64 {
        Fields {
            mode,
            param_b: flags,
            ..Default::default()
        }
        .pack()
        .unwrap()
    }

    #[test]
    fn microcode_decodes_and_executes() {
        // committed + audited → commits, audited
        let ops = decode_microcode(word(MODE_COMMIT, FLAG_AUDIT as u16));
        let o = execute_microcode(&ops);
        assert!(o.commit && o.audited);
        assert!(!o.sandboxed && !o.speculative);
        // committed + sandboxed → cannot durably commit
        let o = execute_microcode(&decode_microcode(word(MODE_COMMIT, FLAG_SANDBOX as u16)));
        assert!(!o.commit && o.sandboxed);
        // committed + speculative → cannot commit
        let o = execute_microcode(&decode_microcode(word(
            MODE_COMMIT,
            FLAG_SPECULATIVE as u16,
        )));
        assert!(!o.commit && o.speculative);
    }

    #[test]
    fn two_level_table_looks_up() {
        let t = TwoLevelTable::new(vec![vec![1, 2, 3], vec![4, 5, 6]]);
        assert_eq!(t.lookup(0, 2), Some(3));
        assert_eq!(t.lookup(1, 0), Some(4));
        assert_eq!(t.lookup(2, 0), None); // rule out of range
        assert_eq!(t.lookup(0, 9), None); // event out of range
        assert_eq!(t.rules(), 2);
    }

    #[test]
    fn branch_predictor_learns() {
        let mut p = BranchPredictor::new(4);
        // train slot 0 toward "always taken"
        for _ in 0..5 {
            p.retire(0, true);
        }
        assert!(p.predict(0), "should predict taken after training");
        // train slot 1 toward "never taken"
        for _ in 0..5 {
            p.retire(1, false);
        }
        assert!(!p.predict(1));
        // accuracy climbs on a consistent stream
        let mut q = BranchPredictor::new(1);
        for _ in 0..10 {
            q.retire(0, true);
        }
        assert!(q.accuracy() > 0.8, "acc={}", q.accuracy());
    }

    #[test]
    fn three_rep_hot_path_never_loads_cold_text() {
        // F00670 — hot ops must not touch the cold text.
        let mut r = ThreeRep::new(vec![1.0, 2.0, 3.0], 0b1010, "the cold payload");
        assert_eq!(r.hot_score(), 6.0);
        assert!(r.hot_law(1) && !r.hot_law(0));
        assert_eq!(r.cold_reads(), 0, "hot ops must not load cold text");
        // an explicit cold read counts
        assert_eq!(r.cold_text(), "the cold payload");
        assert_eq!(r.cold_reads(), 1);
    }
}
