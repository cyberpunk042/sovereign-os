//! `sovereign-control-word-service` — the M002 service layer.
//!
//! The round engine ([`sovereign_simd::round`]) is the compute; this crate is
//! the *service* around it: per-lane DNA fingerprints, quarantine on drift,
//! forward/rewind replay, Prometheus metrics, and lifecycle events. It wraps
//! the safe SIMD API and itself forbids `unsafe`.
//!
//! ## Dependency-free, deterministic
//!
//! Following the [`sovereign-replay-ledger`] precedent (its hash is FNV-1a,
//! "deterministic, dependency-free — tamper-evident"), this crate hand-rolls
//! FNV-1a fingerprints and hand-emits Prometheus text. R00280 names blake3 for
//! the DNA fingerprint; we deliberately match the repo's dependency-free stance
//! instead — blake3 is a future crypto-grade hardening, flagged here, not
//! silently swapped in. FNV-1a gives the tamper-*evident* diversity + drift
//! signal the metrics and quarantine need without a new supply-chain edge.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_simd::round::{RoundConfig, RoundState, round_update};

/// Schema version of the service surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

// ── FNV-1a (matches sovereign-replay-ledger) ──

/// FNV-1a 64-bit hash.
fn fnv1a(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

// ── M00018 per-lane DNA fingerprint (R00280-284) ──

/// R00280 — the per-lane DNA fingerprint `hash(control_word ‖ rule_word ‖
/// state)`. (Spec names blake3; we use FNV-1a per the repo's dependency-free
/// precedent — see the crate docs.) Deterministic: same inputs → same
/// fingerprint, so drift is meaningful.
#[must_use]
pub fn lane_fingerprint(control_word: u64, rule_word: u64, state: u64) -> u64 {
    let mut buf = [0u8; 24];
    buf[0..8].copy_from_slice(&control_word.to_le_bytes());
    buf[8..16].copy_from_slice(&rule_word.to_le_bytes());
    buf[16..24].copy_from_slice(&state.to_le_bytes());
    fnv1a(&buf)
}

/// The eight per-lane fingerprints of a round state. The lane's `memory` plane
/// serves as its control context (the 64-deep state history), so the
/// fingerprint folds memory ‖ rule ‖ state — a lane's full identity.
#[must_use]
pub fn round_fingerprints(s: &RoundState) -> [u64; 8] {
    let mut out = [0u64; 8];
    for i in 0..8 {
        out[i] = lane_fingerprint(s.memory[i], s.rule[i], s.state[i]);
    }
    out
}

/// F00129 — the per-lane DNA diversity index: the fraction of lanes with a
/// distinct fingerprint, in `0.0..=1.0`. 8 unique → 1.0; all identical → 0.125.
#[must_use]
pub fn diversity_index(fps: &[u64; 8]) -> f64 {
    let mut seen: Vec<u64> = Vec::with_capacity(8);
    for &f in fps {
        if !seen.contains(&f) {
            seen.push(f);
        }
    }
    seen.len() as f64 / 8.0
}

/// R00282 — quarantine report: which lanes drifted past a Hamming-distance
/// threshold between two fingerprint snapshots.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct QuarantineReport {
    /// The lanes (0..8) whose fingerprint drifted beyond `threshold_bits`.
    pub flagged: Vec<usize>,
    /// The per-lane Hamming distance (`popcount(prev ^ cur)`).
    pub drift_bits: [u32; 8],
    /// The threshold applied.
    pub threshold_bits: u32,
}

/// R00282 — flag lanes whose fingerprint changed by more than `threshold_bits`
/// (Hamming distance). `threshold_bits = 64` never flags; `0` flags any change.
#[must_use]
pub fn quarantine(prev: &[u64; 8], cur: &[u64; 8], threshold_bits: u32) -> QuarantineReport {
    let mut drift_bits = [0u32; 8];
    let mut flagged = Vec::new();
    for i in 0..8 {
        let d = (prev[i] ^ cur[i]).count_ones();
        drift_bits[i] = d;
        if d > threshold_bits {
            flagged.push(i);
        }
    }
    QuarantineReport {
        flagged,
        drift_bits,
        threshold_bits,
    }
}

// ── M00018/M00020 replay (R00283/284/329) ──

/// A forward/rewind replay of round states — an in-memory snapshot ledger with
/// a cursor. Forward re-runs the deterministic round from the current tip;
/// rewind seeks back over recorded snapshots (R00283 forward / R00284 backward /
/// R00329 multi-lane rewind).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoundReplay {
    snapshots: Vec<RoundState>,
    cursor: usize,
    cfg: RoundConfig,
}

impl RoundReplay {
    /// Start a replay from an initial state.
    #[must_use]
    pub fn new(initial: RoundState, cfg: RoundConfig) -> Self {
        RoundReplay {
            snapshots: vec![initial],
            cursor: 0,
            cfg,
        }
    }

    /// The state at the cursor.
    #[must_use]
    pub fn current(&self) -> &RoundState {
        &self.snapshots[self.cursor]
    }

    /// The cursor position (0 = initial).
    #[must_use]
    pub fn position(&self) -> usize {
        self.cursor
    }

    /// How many rounds are recorded (cursor can reach `len()-1`).
    #[must_use]
    pub fn len(&self) -> usize {
        self.snapshots.len()
    }

    /// Whether only the initial snapshot exists.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.snapshots.len() <= 1
    }

    /// R00283 — advance one round from the tip. If the cursor is behind the tip
    /// (after a rewind), advancing first re-uses the recorded snapshot
    /// (deterministic — the same round always yields the same next state); once
    /// at the tip it computes + records a new one.
    pub fn forward(&mut self) -> &RoundState {
        if self.cursor + 1 < self.snapshots.len() {
            self.cursor += 1;
        } else {
            let next = round_update(&self.snapshots[self.cursor], self.cfg);
            self.snapshots.push(next);
            self.cursor += 1;
        }
        &self.snapshots[self.cursor]
    }

    /// R00284/R00329 — rewind `n` rounds (saturating at the initial state). All
    /// eight lanes rewind together (multi-lane, R00329).
    pub fn rewind(&mut self, n: usize) -> &RoundState {
        self.cursor = self.cursor.saturating_sub(n);
        &self.snapshots[self.cursor]
    }

    /// Seek to an absolute recorded position (clamped to the recorded range).
    pub fn seek(&mut self, pos: usize) -> &RoundState {
        self.cursor = pos.min(self.snapshots.len() - 1);
        &self.snapshots[self.cursor]
    }
}

// ── M00020 lifecycle events (F00131/132/147/148, R00281) ──

/// A lifecycle event emitted around a round or DNA update.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Event {
    /// F00147 — pre-round branch snapshot (the fingerprints before the round).
    PreRound {
        /// Per-lane fingerprints before the round.
        fingerprints: [u64; 8],
    },
    /// F00148 — post-round state transition (fingerprints after the round).
    PostRound {
        /// Per-lane fingerprints after the round.
        fingerprints: [u64; 8],
        /// Lanes whose fingerprint changed this round.
        changed_lanes: Vec<usize>,
    },
    /// F00131 / R00281 — pre-DNA-update current DNA fingerprint emit.
    PreDnaUpdate {
        /// Per-lane fingerprints at DNA-update entry.
        fingerprints: [u64; 8],
    },
    /// F00132 — post-DNA-update delta (per-lane Hamming drift).
    PostDnaUpdate {
        /// Per-lane Hamming drift of the DNA fingerprints.
        drift_bits: [u32; 8],
    },
}

/// Run one round and emit the four lifecycle events around it (R00281,
/// F00131/132/147/148). Returns the new state and the event stream.
#[must_use]
pub fn round_with_events(s: &RoundState, cfg: RoundConfig) -> (RoundState, Vec<Event>) {
    let before = round_fingerprints(s);
    let mut events = vec![
        Event::PreRound {
            fingerprints: before,
        },
        Event::PreDnaUpdate {
            fingerprints: before,
        },
    ];
    let next = round_update(s, cfg);
    let after = round_fingerprints(&next);
    let mut drift_bits = [0u32; 8];
    let mut changed = Vec::new();
    for i in 0..8 {
        let d = (before[i] ^ after[i]).count_ones();
        drift_bits[i] = d;
        if before[i] != after[i] {
            changed.push(i);
        }
    }
    events.push(Event::PostDnaUpdate { drift_bits });
    events.push(Event::PostRound {
        fingerprints: after,
        changed_lanes: changed,
    });
    (next, events)
}

// ── metrics (F00129/138/145/154) — hand-rolled Prometheus text exposition ──

/// M00019 strong-layout register assignment (R00285-288) — an info gauge's
/// label set: which plane lives in which ZMM register.
pub const ZMM_ASSIGNMENT: [(&str, &str); 4] = [
    ("state", "zmm0"),
    ("memory", "zmm1"),
    ("rule", "zmm2"),
    ("random", "zmm3"),
];

/// The M002 service metrics snapshot (the gauges the cockpit + Prometheus read).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Metrics {
    /// F00129 — per-lane DNA diversity index (0.0..=1.0).
    pub dna_diversity_index: f64,
    /// F00145 — round-update steps per second (5 steps × rounds / elapsed).
    pub round_update_steps_per_sec: f64,
    /// F00154 — variable-shift cost ratio vs the AND/XOR baseline (R00298).
    pub variable_shift_cost_ratio: f64,
}

impl Metrics {
    /// Render the metrics as Prometheus text exposition (the same hand-rolled
    /// format gatewayd's `/metrics` uses). Emits the four M002 gauges incl.
    /// F00138's `zmm_layout_register_assignment` info gauge (one series per
    /// plane→register label pair, value `1`).
    #[must_use]
    pub fn render_prometheus(&self) -> String {
        let mut s = String::new();
        s.push_str("# HELP sovereign_os_per_lane_dna_diversity_index Fraction of lanes with a distinct DNA fingerprint.\n");
        s.push_str("# TYPE sovereign_os_per_lane_dna_diversity_index gauge\n");
        s.push_str(&format!(
            "sovereign_os_per_lane_dna_diversity_index {}\n",
            fmt_f64(self.dna_diversity_index)
        ));
        s.push_str("# HELP sovereign_os_round_update_steps_per_sec Round-update steps executed per second.\n");
        s.push_str("# TYPE sovereign_os_round_update_steps_per_sec gauge\n");
        s.push_str(&format!(
            "sovereign_os_round_update_steps_per_sec {}\n",
            fmt_f64(self.round_update_steps_per_sec)
        ));
        s.push_str("# HELP sovereign_os_variable_shift_cost_ratio Variable-shift cost vs the AND/XOR baseline.\n");
        s.push_str("# TYPE sovereign_os_variable_shift_cost_ratio gauge\n");
        s.push_str(&format!(
            "sovereign_os_variable_shift_cost_ratio {}\n",
            fmt_f64(self.variable_shift_cost_ratio)
        ));
        s.push_str("# HELP sovereign_os_zmm_layout_register_assignment Strong-layout plane→ZMM register assignment (info).\n");
        s.push_str("# TYPE sovereign_os_zmm_layout_register_assignment gauge\n");
        for (plane, reg) in ZMM_ASSIGNMENT {
            s.push_str(&format!(
                "sovereign_os_zmm_layout_register_assignment{{plane=\"{plane}\",register=\"{reg}\"}} 1\n"
            ));
        }
        s
    }
}

/// Compute the F00129 diversity + F00145 steps/sec metrics from a round state
/// and a measured `(rounds, elapsed_secs)`. `variable_shift_cost_ratio` is the
/// caller's measured/estimated ratio (R00298); pass `1.0` when unmeasured.
#[must_use]
pub fn metrics_from(
    s: &RoundState,
    rounds: u64,
    elapsed_secs: f64,
    variable_shift_cost_ratio: f64,
) -> Metrics {
    let fps = round_fingerprints(s);
    let steps_per_sec = if elapsed_secs > 0.0 {
        (rounds as f64 * 5.0) / elapsed_secs
    } else {
        0.0
    };
    Metrics {
        dna_diversity_index: diversity_index(&fps),
        round_update_steps_per_sec: steps_per_sec,
        variable_shift_cost_ratio,
    }
}

/// Format an f64 for Prometheus (finite → shortest, non-finite → `0`).
fn fmt_f64(v: f64) -> String {
    if v.is_finite() {
        format!("{v}")
    } else {
        "0".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_simd::round::round_update_scalar;

    fn state(seed: u64) -> RoundState {
        // simple deterministic non-zero seeding
        let mk = |base: u64| {
            let mut a = [0u64; 8];
            for (i, x) in a.iter_mut().enumerate() {
                *x = base
                    .wrapping_mul(0x9E37_79B9_7F4A_7C15)
                    .wrapping_add(i as u64 + 1);
            }
            a
        };
        RoundState {
            state: mk(seed),
            memory: mk(seed ^ 1),
            rule: mk(seed ^ 2),
            random: mk(seed ^ 3),
        }
    }

    #[test]
    fn fingerprint_is_deterministic_and_input_sensitive() {
        assert_eq!(lane_fingerprint(1, 2, 3), lane_fingerprint(1, 2, 3));
        assert_ne!(lane_fingerprint(1, 2, 3), lane_fingerprint(1, 2, 4));
        assert_ne!(lane_fingerprint(1, 2, 3), lane_fingerprint(9, 2, 3));
    }

    #[test]
    fn fingerprint_parity_with_python_engine() {
        // The Python mirror (scripts/hardware/control-word-service.py) and this
        // crate MUST agree. Both pin THESE FNV-1a constants — neither can drift.
        assert_eq!(lane_fingerprint(1, 2, 3), 0xda2b_fb22_5e0d_1f05);
        // the 8 per-lane fingerprints of the 3-round parity state
        let s = RoundState {
            state: [0x8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40],
            memory: [
                0x2000_0000_0000_0000,
                0,
                0x2000_0000_0000_0000,
                0,
                0x2000_0000_0000_0000,
                0,
                0x2000_0000_0000_0000,
                1,
            ],
            rule: [1, 2, 3, 4, 5, 6, 7, 8],
            random: [0; 8],
        };
        assert_eq!(
            round_fingerprints(&s),
            [
                0x4fc1_e349_a99a_8d6c,
                0x0f7a_dbf7_d55a_f597,
                0xdd6a_7f6a_7eb9_5ffe,
                0x6681_0795_55fe_7de1,
                0x3470_ab07_ff5c_e848,
                0xf429_a3b6_2b1d_5073,
                0xc219_4728_d47b_bada,
                0x91cd_071e_974d_82ec,
            ]
        );
        assert_eq!(diversity_index(&round_fingerprints(&s)), 1.0);
    }

    #[test]
    fn diversity_index_bounds() {
        assert_eq!(diversity_index(&[7; 8]), 0.125); // all identical → 1/8
        assert_eq!(diversity_index(&[1, 2, 3, 4, 5, 6, 7, 8]), 1.0); // all unique
    }

    #[test]
    fn quarantine_flags_drift() {
        let prev = [0u64; 8];
        let mut cur = [0u64; 8];
        cur[3] = 0xFF; // 8 bits of drift on lane 3
        let r = quarantine(&prev, &cur, 4);
        assert_eq!(r.flagged, vec![3]);
        assert_eq!(r.drift_bits[3], 8);
        // threshold 64 never flags; 0 flags any change
        assert!(quarantine(&prev, &cur, 64).flagged.is_empty());
        assert_eq!(quarantine(&prev, &cur, 0).flagged, vec![3]);
    }

    #[test]
    fn replay_forward_rewind_is_deterministic() {
        let s = state(42);
        let cfg = RoundConfig::default();
        let mut r = RoundReplay::new(s, cfg);
        for _ in 0..5 {
            r.forward();
        }
        assert_eq!(r.position(), 5);
        let at5 = *r.current();
        // rewind 3 then forward 3 must land on the identical state (R00283/284)
        r.rewind(3);
        assert_eq!(r.position(), 2);
        for _ in 0..3 {
            r.forward();
        }
        assert_eq!(r.position(), 5);
        assert_eq!(*r.current(), at5);
        // and position 5 equals 5 pure-scalar rounds from the seed
        let mut scal = s;
        for _ in 0..5 {
            scal = round_update_scalar(&scal, cfg);
        }
        assert_eq!(at5, scal);
        // rewind past the start saturates at 0
        r.rewind(100);
        assert_eq!(r.position(), 0);
        assert_eq!(*r.current(), s);
    }

    #[test]
    fn events_bracket_the_round() {
        let s = state(7);
        let (next, events) = round_with_events(&s, RoundConfig::default());
        assert_eq!(next, round_update_scalar(&s, RoundConfig::default()));
        assert_eq!(events.len(), 4);
        assert!(matches!(events[0], Event::PreRound { .. }));
        assert!(matches!(events[1], Event::PreDnaUpdate { .. }));
        assert!(matches!(events[2], Event::PostDnaUpdate { .. }));
        assert!(matches!(events[3], Event::PostRound { .. }));
        // post-round fingerprints must equal an independent computation
        if let Event::PostRound { fingerprints, .. } = &events[3] {
            assert_eq!(*fingerprints, round_fingerprints(&next));
        }
    }

    #[test]
    fn prometheus_text_has_all_four_gauges() {
        let m = metrics_from(&state(3), 1000, 0.5, 1.8);
        let text = m.render_prometheus();
        for name in [
            "sovereign_os_per_lane_dna_diversity_index",
            "sovereign_os_round_update_steps_per_sec",
            "sovereign_os_variable_shift_cost_ratio",
            "sovereign_os_zmm_layout_register_assignment",
        ] {
            assert!(
                text.contains(&format!("# TYPE {name} gauge")),
                "missing {name}"
            );
        }
        // steps/sec = 1000 rounds × 5 steps / 0.5s = 10000
        assert!(text.contains("sovereign_os_round_update_steps_per_sec 10000"));
        // all 4 planes assigned to their register
        assert!(text.contains("plane=\"state\",register=\"zmm0\""));
        assert!(text.contains("plane=\"random\",register=\"zmm3\""));
    }
}
