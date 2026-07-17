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

// ── runtime switch: the avx-mode state file (the hot-swap call site) ──

/// The AVX mode the daemon runs under — the master switch `avx-mode` persists to
/// its state file (`/etc/sovereign-os/avx-mode.active`). Reading it at a request
/// call site is the *hot-swap*: write the file, the next request sees the new
/// mode — no restart. Mirrors `scripts/hardware/avx-mode.py` (same modes, same
/// default, same state path + env override).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AvxMode {
    /// M002 control-word bit-machine — policy becomes bits.
    Custom,
    /// Stock AVX-512 math tiers (the honest default).
    BuiltIn,
    /// Both — the bit-machine routes, the math tiers compute.
    Hybrid,
    /// Scalar baseline, no AVX.
    Off,
}

impl AvxMode {
    /// Parse a mode string; anything unrecognised falls back to the honest
    /// default (`builtin`), matching `avx-mode.py`'s `DEFAULT_MODE`.
    #[must_use]
    pub fn parse(s: &str) -> AvxMode {
        match s.trim() {
            "custom" => AvxMode::Custom,
            "hybrid" => AvxMode::Hybrid,
            "off" => AvxMode::Off,
            _ => AvxMode::BuiltIn,
        }
    }

    /// The canonical mode string (matches the state-file contents).
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            AvxMode::Custom => "custom",
            AvxMode::BuiltIn => "builtin",
            AvxMode::Hybrid => "hybrid",
            AvxMode::Off => "off",
        }
    }

    /// Whether the **M002 control-word bit-machine** (the M00013 round engine) is
    /// the active path. True only for `custom` + `hybrid` — so the bit-machine is
    /// opt-in: the default `builtin` and `off` do NOT run it. This is the switch
    /// the round route reads.
    #[must_use]
    pub fn runs_bit_machine(self) -> bool {
        matches!(self, AvxMode::Custom | AvxMode::Hybrid)
    }
}

/// Resolve the AVX mode from a state-file body (the file's text). Pure —
/// testable without touching the filesystem. Missing/blank/invalid → `builtin`.
#[must_use]
pub fn avx_mode_from_contents(contents: Option<&str>) -> AvxMode {
    match contents {
        Some(s) => AvxMode::parse(s),
        None => AvxMode::BuiltIn,
    }
}

/// Read the AVX mode from a specific state-file path (pure w.r.t. env — the
/// caller supplies the path). A missing/unreadable file → `builtin`.
#[must_use]
pub fn avx_mode_from_path(path: &std::path::Path) -> AvxMode {
    match std::fs::read_to_string(path) {
        Ok(s) => AvxMode::parse(&s),
        Err(_) => AvxMode::BuiltIn,
    }
}

/// The state-file path — `$SOVEREIGN_OS_AVX_MODE_STATE` or the default
/// `/etc/sovereign-os/avx-mode.active` (matches `avx-mode.py`). Reading an env
/// var is safe; only *setting* one is `unsafe` on edition 2024.
#[must_use]
pub fn avx_mode_state_path() -> std::path::PathBuf {
    std::env::var("SOVEREIGN_OS_AVX_MODE_STATE")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| std::path::PathBuf::from("/etc/sovereign-os/avx-mode.active"))
}

/// Read the live AVX mode from the hot-swappable state file. This is the runtime
/// call site the daemon reads per request — write the file, the next call sees it.
#[must_use]
pub fn avx_mode_live() -> AvxMode {
    avx_mode_from_path(&avx_mode_state_path())
}

// ── M00018 per-lane DNA fingerprint (R00280-284) ──

/// The fingerprint algorithm (R00280). `Fnv1a` is the default — dependency-free,
/// deterministic, tamper-*evident* (the repo's replay-ledger precedent). `Blake3`
/// is the opt-in crypto-grade upgrade the spec names: a keyless BLAKE3 digest,
/// truncated to the low 8 bytes to keep the u64 fingerprint API. Same inputs →
/// same fingerprint either way; only the collision-resistance differs.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum FingerprintAlgo {
    /// FNV-1a 64-bit — dependency-free default.
    #[default]
    Fnv1a,
    /// BLAKE3 (crypto-grade), low-8-byte truncation to a u64.
    Blake3,
}

/// R00280 — the per-lane DNA fingerprint `hash(control_word ‖ rule_word ‖
/// state)` under the default FNV-1a algorithm. See [`lane_fingerprint_with`] to
/// pick BLAKE3. Deterministic: same inputs → same fingerprint, so drift is
/// meaningful.
#[must_use]
pub fn lane_fingerprint(control_word: u64, rule_word: u64, state: u64) -> u64 {
    lane_fingerprint_with(FingerprintAlgo::Fnv1a, control_word, rule_word, state)
}

/// R00280 — the per-lane DNA fingerprint under a chosen algorithm.
#[must_use]
pub fn lane_fingerprint_with(
    algo: FingerprintAlgo,
    control_word: u64,
    rule_word: u64,
    state: u64,
) -> u64 {
    let mut buf = [0u8; 24];
    buf[0..8].copy_from_slice(&control_word.to_le_bytes());
    buf[8..16].copy_from_slice(&rule_word.to_le_bytes());
    buf[16..24].copy_from_slice(&state.to_le_bytes());
    match algo {
        FingerprintAlgo::Fnv1a => fnv1a(&buf),
        FingerprintAlgo::Blake3 => {
            let digest = blake3::hash(&buf);
            u64::from_le_bytes(digest.as_bytes()[0..8].try_into().unwrap())
        }
    }
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

    /// Persist the whole ledger (snapshots + cursor + config) to a JSON file.
    /// This is the persistence shape a ZFS snapshot / CRIU checkpoint would carry
    /// — serialize-to-file is real here; the OS-level ZFS/CRIU integration is a
    /// deliberate future step, not stubbed.
    pub fn save_json(&self, path: &std::path::Path) -> std::io::Result<()> {
        let json = serde_json::to_string(self).map_err(std::io::Error::other)?;
        std::fs::write(path, json)
    }

    /// Restore a ledger previously written by [`save_json`] — resumes replay at
    /// the saved cursor (R00283/284 forward/rewind continue across the reload).
    pub fn load_json(path: &std::path::Path) -> std::io::Result<Self> {
        let text = std::fs::read_to_string(path)?;
        serde_json::from_str(&text).map_err(std::io::Error::other)
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

// ── R00294 OTel-shaped round-step spans + R00330-333 strict/relaxed ──

/// An OpenTelemetry-shaped span for one round step (R00294) — observable step
/// boundaries without pulling the `opentelemetry` crate in. The fields mirror an
/// OTLP span so an exporter can forward them 1:1.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Span {
    /// The step name (`extract` / `decision` / `apply` / `memory` / `advance`).
    pub name: String,
    /// The step index within the round (0..5), the span's ordinal.
    pub step: u8,
    /// `ok` normally; `error` when a strict-mode step aborted (R00331).
    pub status: String,
}

/// The five round steps, in order (R00289-293) — the span names.
pub const ROUND_STEPS: [&str; 5] = ["extract", "decision", "apply", "memory", "advance"];

/// R00330-333 — how a round handles a step "failure" (a per-lane quarantine
/// trip, the only failure a pure round can raise).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RoundMode {
    /// R00330/R00331 — abort the round on the first quarantine trip, emit an
    /// error span with the failing step.
    Strict,
    /// R00332/R00333 — log the trip, continue to the next step (the default).
    #[default]
    Relaxed,
}

/// The outcome of a guarded round (R00330-333).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RoundOutcome {
    /// The resulting state (present in both modes — relaxed always completes,
    /// strict completes unless it aborted).
    pub state: RoundState,
    /// One span per step (R00294); the aborting step (strict) carries `error`.
    pub spans: Vec<Span>,
    /// Lanes that tripped quarantine this round (fingerprint drift > threshold).
    pub quarantined: Vec<usize>,
    /// Whether strict mode aborted the round.
    pub aborted: bool,
}

/// R00330-333 — run one round with OTel-shaped step spans (R00294) and a
/// strict/relaxed quarantine gate. A lane whose DNA fingerprint drifts more than
/// `quarantine_threshold_bits` this round is a "step failure": strict aborts and
/// marks the `decision` span `error`; relaxed records it and completes. With a
/// threshold of 64 (never trips) this is a plain traced round.
#[must_use]
pub fn round_guarded(
    s: &RoundState,
    cfg: RoundConfig,
    mode: RoundMode,
    quarantine_threshold_bits: u32,
) -> RoundOutcome {
    let before = round_fingerprints(s);
    let next = round_update(s, cfg);
    let after = round_fingerprints(&next);
    let report = quarantine(&before, &after, quarantine_threshold_bits);
    let tripped = !report.flagged.is_empty();
    let abort = tripped && mode == RoundMode::Strict;

    let mut spans = Vec::with_capacity(5);
    for (i, name) in ROUND_STEPS.iter().enumerate() {
        // strict abort surfaces on the `decision` step (the gate point)
        let status = if abort && *name == "decision" {
            "error"
        } else {
            "ok"
        };
        spans.push(Span {
            name: (*name).to_string(),
            step: i as u8,
            status: status.to_string(),
        });
    }
    RoundOutcome {
        state: if abort { *s } else { next }, // strict abort rolls back to entry
        spans,
        quarantined: report.flagged,
        aborted: abort,
    }
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
    fn avx_mode_parse_and_bit_machine_gate() {
        // parse + canonical round-trip
        for (s, m) in [
            ("custom", AvxMode::Custom),
            ("builtin", AvxMode::BuiltIn),
            ("hybrid", AvxMode::Hybrid),
            ("off", AvxMode::Off),
        ] {
            assert_eq!(AvxMode::parse(s), m);
            assert_eq!(m.as_str(), s);
            assert_eq!(AvxMode::parse(m.as_str()), m);
        }
        // whitespace tolerated (the state file has a trailing newline)
        assert_eq!(AvxMode::parse(" custom\n"), AvxMode::Custom);
        // unknown / blank → honest default builtin (matches avx-mode.py)
        assert_eq!(AvxMode::parse("nonsense"), AvxMode::BuiltIn);
        assert_eq!(avx_mode_from_contents(None), AvxMode::BuiltIn);
        // the bit-machine is opt-in: only custom + hybrid run it
        assert!(AvxMode::Custom.runs_bit_machine());
        assert!(AvxMode::Hybrid.runs_bit_machine());
        assert!(!AvxMode::BuiltIn.runs_bit_machine());
        assert!(!AvxMode::Off.runs_bit_machine());
    }

    #[test]
    fn avx_mode_reads_a_state_file() {
        // a real temp file — no env-set (unsafe on edition 2024), no fs mocks.
        let dir = std::env::temp_dir();
        let path = dir.join(format!("cws-avx-mode-test-{}.active", std::process::id()));
        std::fs::write(&path, "custom\n").unwrap();
        assert_eq!(avx_mode_from_path(&path), AvxMode::Custom);
        std::fs::write(&path, "off").unwrap();
        assert_eq!(avx_mode_from_path(&path), AvxMode::Off);
        let _ = std::fs::remove_file(&path);
        // a missing file → builtin
        assert_eq!(avx_mode_from_path(&path), AvxMode::BuiltIn);
    }

    #[test]
    fn blake3_fingerprint_is_opt_in_and_distinct() {
        // default stays FNV-1a (unchanged behavior — the parity constant holds)
        assert_eq!(
            lane_fingerprint(1, 2, 3),
            lane_fingerprint_with(FingerprintAlgo::Fnv1a, 1, 2, 3)
        );
        assert_eq!(
            lane_fingerprint_with(FingerprintAlgo::Fnv1a, 1, 2, 3),
            0xda2b_fb22_5e0d_1f05
        );
        // blake3 is deterministic, input-sensitive, and differs from FNV-1a
        let b = lane_fingerprint_with(FingerprintAlgo::Blake3, 1, 2, 3);
        assert_eq!(b, lane_fingerprint_with(FingerprintAlgo::Blake3, 1, 2, 3));
        assert_ne!(b, lane_fingerprint_with(FingerprintAlgo::Blake3, 1, 2, 4));
        assert_ne!(b, lane_fingerprint(1, 2, 3), "blake3 differs from fnv1a");
    }

    #[test]
    fn guarded_round_strict_aborts_relaxed_continues() {
        let s = state(5);
        // threshold 64 never trips → both modes complete a plain traced round
        let relaxed = round_guarded(&s, RoundConfig::default(), RoundMode::Relaxed, 64);
        assert!(!relaxed.aborted);
        assert_eq!(relaxed.spans.len(), 5);
        assert!(relaxed.spans.iter().all(|sp| sp.status == "ok"));
        assert_eq!(
            relaxed.state,
            round_update_scalar(&s, RoundConfig::default())
        );
        // threshold 0 trips on any drift → strict aborts + rolls back, error span
        let strict = round_guarded(&s, RoundConfig::default(), RoundMode::Strict, 0);
        if !strict.quarantined.is_empty() {
            assert!(strict.aborted);
            assert_eq!(strict.state, s, "strict abort rolls back to entry");
            assert!(strict.spans.iter().any(|sp| sp.status == "error"));
            // relaxed with the same threshold records but completes
            let relaxed0 = round_guarded(&s, RoundConfig::default(), RoundMode::Relaxed, 0);
            assert!(!relaxed0.aborted);
            assert_eq!(relaxed0.quarantined, strict.quarantined);
        }
    }

    #[test]
    fn replay_persists_and_restores() {
        let mut r = RoundReplay::new(state(9), RoundConfig::default());
        for _ in 0..4 {
            r.forward();
        }
        let path = std::env::temp_dir().join(format!("cws-replay-{}.json", std::process::id()));
        r.save_json(&path).unwrap();
        let loaded = RoundReplay::load_json(&path).unwrap();
        assert_eq!(loaded.position(), r.position());
        assert_eq!(loaded.current(), r.current());
        // replay continues across the reload — forward from the restored cursor
        let mut l = loaded;
        assert_eq!(l.forward(), r.clone().forward());
        let _ = std::fs::remove_file(&path);
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
