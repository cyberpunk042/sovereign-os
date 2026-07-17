//! M00019/M00020 — the strong-layout round-update kernel (M002).
//!
//! This is the bit-machine actually *running*: 8 lanes evolve in lock-step, one
//! ZMM register per plane (M00019 strong layout), through the 5-step round
//! (M00020). The scalar reference is the source of truth; the AVX-512F path is
//! proven bit-identical to it (integer ops — no float tolerance) by this
//! module's tests, and is genuinely exercised on the AVX-512 CI host.
//!
//! ## Strong ZMM layout (M00019 / R00285-289)
//!
//! | plane    | register | role                                    |
//! |----------|----------|-----------------------------------------|
//! | `state`  | zmm0     | the evolving cell state                 |
//! | `memory` | zmm1     | a per-lane shift-register of past state |
//! | `rule`   | zmm2     | the per-lane rule word (LUT)            |
//! | `random` | zmm3     | the per-lane xorshift RNG stream        |
//!
//! ## The 5-step round (M00020 / R00289-293), per lane, in order:
//!
//! 1. **extract**  — read state/memory/random → a 6-bit condition (M00016).
//! 2. **decision** — read rule, apply `(rule >> features) & 1` (R00290). The
//!    per-lane variable shift here IS M00021 (`VPSRLVQ`).
//! 3. **apply**    — write the decision bit into state (`state<<1 | decision`).
//! 4. **memory**   — fold the old state LSB into memory (a 64-deep history).
//! 5. **advance**  — step the lane's xorshift64 RNG.
//!
//! Composes M00012 lane-fields, M00014 masked-op mode, M00016 condition, M00018
//! per-lane DNA, and M00021 variable-shift — the F00165 composite kernel.

use sovereign_control_word::m00013::MaskedOpMode;

/// The four ZMM planes of a round (M00019 strong layout), 8 lanes each.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RoundState {
    /// zmm0 — the evolving cell state per lane.
    pub state: [u64; 8],
    /// zmm1 — a per-lane shift-register of past state LSBs.
    pub memory: [u64; 8],
    /// zmm2 — the per-lane rule word (a 64-entry LUT).
    pub rule: [u64; 8],
    /// zmm3 — the per-lane xorshift64 RNG stream.
    pub random: [u64; 8],
}

/// Knobs that select round behavior (all opt-in; defaults are the strong path).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RoundConfig {
    /// M00014 — branchless (default) vs branchy decision. Both produce the same
    /// output (proven by test); branchy is the obvious scalar reference form.
    pub masked_op: MaskedOpMode,
    /// M00018 — per-lane DNA: the effective rule is `rule ^ state`, so the rule
    /// is embedded in (and mutates with) each lane's own state → unique
    /// evolution per lane. Off = a fixed shared-shape rule plane.
    pub per_lane_dna: bool,
}

impl Default for RoundConfig {
    fn default() -> Self {
        RoundConfig {
            masked_op: MaskedOpMode::Branchless,
            per_lane_dna: false,
        }
    }
}

impl RoundConfig {
    /// Resolve over the defaults from a getter (pure — testable without touching
    /// process env). Reads `SOVEREIGN_CTRL_MASKED_OP_MODE` (F00106, shared with
    /// the control-word config) and `SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED`
    /// (F00126). Invalid values keep their default — the loader never fails.
    /// Only these two knobs are exposed: they are the ones this round kernel
    /// actually honors (nothing reads as opt-in while being inert).
    #[must_use]
    pub fn resolve(get: impl Fn(&str) -> Option<String>) -> Self {
        let mut c = RoundConfig::default();
        if let Some(v) = get("SOVEREIGN_CTRL_MASKED_OP_MODE") {
            c.masked_op = match v.as_str() {
                "branchy" => MaskedOpMode::Branchy,
                "branchless" => MaskedOpMode::Branchless,
                _ => c.masked_op,
            };
        }
        if let Some(v) = get("SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED") {
            c.per_lane_dna = match v.as_str() {
                "1" | "true" | "yes" | "on" => true,
                "0" | "false" | "no" | "off" => false,
                _ => c.per_lane_dna,
            };
        }
        c
    }

    /// Resolve from the `SOVEREIGN_CTRL_*` process env over the defaults.
    #[must_use]
    pub fn from_env() -> Self {
        Self::resolve(|k| std::env::var(k).ok())
    }
}

// ── the five per-lane steps (scalar source of truth) ──

/// Step 1 (M00016 / R00289): the 6-bit condition from state ⊕ memory ⊕ random.
/// "neighbor + stress + damage + random bits" folded into one 6-bit index.
#[inline]
#[must_use]
pub fn extract_features(state: u64, memory: u64, random: u64) -> u64 {
    (state ^ memory ^ random) & 0x3F
}

/// Step 2 (M00014 / R00290): the decision bit `(rule >> features) & 1`.
/// `masked_op` picks branchless vs branchy — identical output either way.
#[inline]
#[must_use]
pub fn decide(rule: u64, features: u64, masked_op: MaskedOpMode) -> u64 {
    match masked_op {
        MaskedOpMode::Branchless => (rule >> (features & 63)) & 1,
        MaskedOpMode::Branchy => {
            if (rule >> (features & 63)) & 1 == 1 {
                1
            } else {
                0
            }
        }
    }
}

/// Step 3 (R00291): shift the decision bit into the state history.
#[inline]
#[must_use]
pub fn apply_state(state: u64, decision: u64) -> u64 {
    (state << 1) | (decision & 1)
}

/// Step 4 (R00292): fold the old state LSB into the memory shift-register.
#[inline]
#[must_use]
pub fn update_memory(memory: u64, old_state: u64) -> u64 {
    (memory >> 1) | ((old_state & 1) << 63)
}

/// Step 5 (R00293): advance the lane's xorshift64 RNG. A zero lane stays zero
/// (seed the random plane non-zero); this keeps the SIMD path bit-identical.
#[inline]
#[must_use]
pub fn advance_rng(mut x: u64) -> u64 {
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    x
}

/// Run one round over all 8 lanes — the scalar reference (source of truth).
#[must_use]
pub fn round_update_scalar(s: &RoundState, cfg: RoundConfig) -> RoundState {
    let mut out = *s;
    for i in 0..8 {
        let eff_rule = if cfg.per_lane_dna {
            s.rule[i] ^ s.state[i]
        } else {
            s.rule[i]
        };
        let features = extract_features(s.state[i], s.memory[i], s.random[i]);
        let decision = decide(eff_rule, features, cfg.masked_op);
        out.state[i] = apply_state(s.state[i], decision);
        out.memory[i] = update_memory(s.memory[i], s.state[i]);
        out.random[i] = advance_rng(s.random[i]);
    }
    out
}

/// Run one round over all 8 lanes. Dispatches to an AVX-512F kernel (the whole
/// round in ZMM ops — 8 lanes per instruction) when the host supports it, else
/// the scalar reference. The result is bit-identical either way.
#[must_use]
pub fn round_update(s: &RoundState, cfg: RoundConfig) -> RoundState {
    #[cfg(target_arch = "x86_64")]
    {
        if crate::has_avx512f() {
            // SAFETY: gated by runtime is_x86_feature_detected!("avx512f").
            return unsafe { round_update_avx512(s, cfg) };
        }
    }
    round_update_scalar(s, cfg)
}

/// AVX-512F round: the five steps as ZMM lane-parallel ops over 8 u64 lanes.
/// `VPSRLVQ` (step 2, per-lane variable shift = M00021), `VPSLLQ`/`VPSRLQ`,
/// `VPXORQ`, `VPANDQ`, `VPORQ` — no host loop over lanes.
///
/// # Safety
/// The caller must ensure the host supports `avx512f` (the runtime check in
/// [`round_update`]). Reads/writes only the fixed 8-lane arrays; no OOB.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
unsafe fn round_update_avx512(s: &RoundState, cfg: RoundConfig) -> RoundState {
    use std::arch::x86_64::*;
    let mut out = *s;
    // SAFETY: all intrinsics below are AVX-512F, enabled by this fn's
    // `#[target_feature]` + the caller's runtime gate. Each load/store touches a
    // full 8×u64 plane (exactly one ZMM), in-bounds by construction.
    unsafe {
        let state = _mm512_loadu_si512(s.state.as_ptr() as *const __m512i);
        let memory = _mm512_loadu_si512(s.memory.as_ptr() as *const __m512i);
        let rule = _mm512_loadu_si512(s.rule.as_ptr() as *const __m512i);
        let random = _mm512_loadu_si512(s.random.as_ptr() as *const __m512i);

        // M00018 per-lane DNA — effective rule = rule ^ state (else rule).
        let eff_rule = if cfg.per_lane_dna {
            _mm512_xor_si512(rule, state)
        } else {
            rule
        };

        // Step 1 extract: features = (state ^ memory ^ random) & 0x3F.
        let feats = _mm512_and_si512(
            _mm512_xor_si512(_mm512_xor_si512(state, memory), random),
            _mm512_set1_epi64(0x3F),
        );
        // Step 2 decision: (eff_rule >> feats) & 1  — VPSRLVQ variable shift.
        let decision = _mm512_and_si512(_mm512_srlv_epi64(eff_rule, feats), _mm512_set1_epi64(1));
        // Step 3 apply: (state << 1) | decision.
        let new_state = _mm512_or_si512(_mm512_slli_epi64(state, 1), decision);
        // Step 4 memory: (memory >> 1) | ((state & 1) << 63).
        let state_lsb = _mm512_and_si512(state, _mm512_set1_epi64(1));
        let new_memory = _mm512_or_si512(
            _mm512_srli_epi64(memory, 1),
            _mm512_slli_epi64(state_lsb, 63),
        );
        // Step 5 advance RNG: xorshift64 (13 << , 7 >> , 17 <<).
        let mut r = random;
        r = _mm512_xor_si512(r, _mm512_slli_epi64(r, 13));
        r = _mm512_xor_si512(r, _mm512_srli_epi64(r, 7));
        r = _mm512_xor_si512(r, _mm512_slli_epi64(r, 17));

        _mm512_storeu_si512(out.state.as_mut_ptr() as *mut __m512i, new_state);
        _mm512_storeu_si512(out.memory.as_mut_ptr() as *mut __m512i, new_memory);
        _mm512_storeu_si512(out.random.as_mut_ptr() as *mut __m512i, r);
    }
    out
}

// ── M00021 standalone variable per-lane shift (VPSLLVQ) ──

/// M00021 — per-lane variable left shift: `values[i] << shifts[i]`, 8 lanes.
/// Dispatches to `VPSLLVQ` (one instruction for all 8 lanes) when the host has
/// AVX-512F; scalar reference otherwise. Bit-identical.
#[must_use]
pub fn variable_shift_left(values: &[u64; 8], shifts: &[u64; 8]) -> [u64; 8] {
    #[cfg(target_arch = "x86_64")]
    {
        if crate::has_avx512f() {
            // SAFETY: gated by runtime is_x86_feature_detected!("avx512f").
            return unsafe { variable_shift_left_avx512(values, shifts) };
        }
    }
    variable_shift_left_scalar(values, shifts)
}

/// Scalar reference for [`variable_shift_left`] (a shift ≥ 64 yields 0, matching
/// `VPSLLVQ` semantics — `u64::checked_shl` returns `None` there).
#[must_use]
pub fn variable_shift_left_scalar(values: &[u64; 8], shifts: &[u64; 8]) -> [u64; 8] {
    let mut out = [0u64; 8];
    for i in 0..8 {
        out[i] = values[i].checked_shl(shifts[i] as u32).unwrap_or(0);
    }
    out
}

/// # Safety
/// Caller must ensure the host supports `avx512f`.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
unsafe fn variable_shift_left_avx512(values: &[u64; 8], shifts: &[u64; 8]) -> [u64; 8] {
    use std::arch::x86_64::*;
    let mut out = [0u64; 8];
    // SAFETY: AVX-512F intrinsics, enabled by target_feature + caller gate;
    // loads/store touch exactly one 8×u64 ZMM each, in-bounds.
    unsafe {
        let v = _mm512_loadu_si512(values.as_ptr() as *const __m512i);
        let sh = _mm512_loadu_si512(shifts.as_ptr() as *const __m512i);
        let r = _mm512_sllv_epi64(v, sh);
        _mm512_storeu_si512(out.as_mut_ptr() as *mut __m512i, r);
    }
    out
}

// ── M00012 u64 lane-fields (state_lo / state_hi / control / scratch) ──

/// M00012 — the four 16-bit fields packed into one u64 lane (standard layout):
/// `state_lo` bits 0..16, `state_hi` 16..32, `control` 32..48, `scratch` 48..64.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct LaneFields {
    /// bits 0..16.
    pub state_lo: u16,
    /// bits 16..32.
    pub state_hi: u16,
    /// bits 32..48.
    pub control: u16,
    /// bits 48..64.
    pub scratch: u16,
}

impl LaneFields {
    /// Pack the four fields into a u64 lane.
    #[must_use]
    pub fn pack(self) -> u64 {
        (self.state_lo as u64)
            | (self.state_hi as u64) << 16
            | (self.control as u64) << 32
            | (self.scratch as u64) << 48
    }

    /// Unpack a u64 lane into the four fields.
    #[must_use]
    pub fn unpack(word: u64) -> LaneFields {
        LaneFields {
            state_lo: word as u16,
            state_hi: (word >> 16) as u16,
            control: (word >> 32) as u16,
            scratch: (word >> 48) as u16,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::{Rng, SeedableRng};
    use rand_chacha::ChaCha8Rng;

    fn seeded_state(seed: u64) -> RoundState {
        let mut rng = ChaCha8Rng::seed_from_u64(seed);
        let mut mk = || {
            let mut a = [0u64; 8];
            for x in &mut a {
                *x = rng.random::<u64>() | 1; // non-zero (RNG plane must not lock at 0)
            }
            a
        };
        RoundState {
            state: mk(),
            memory: mk(),
            rule: mk(),
            random: mk(),
        }
    }

    #[test]
    fn avx512_round_equals_scalar_reference() {
        for &dna in &[false, true] {
            let cfg = RoundConfig {
                per_lane_dna: dna,
                ..Default::default()
            };
            for seed in [1u64, 42, 0xDEAD_BEEF, 0x5A5A_5A5A] {
                let s = seeded_state(seed);
                assert_eq!(
                    round_update(&s, cfg),
                    round_update_scalar(&s, cfg),
                    "SIMD != scalar (dna={dna}, seed={seed})"
                );
            }
        }
    }

    #[test]
    fn branchless_and_branchy_are_identical() {
        // F00110 — masked-op mode must not change the output.
        let s = seeded_state(7);
        let bl = round_update_scalar(
            &s,
            RoundConfig {
                masked_op: MaskedOpMode::Branchless,
                ..Default::default()
            },
        );
        let by = round_update_scalar(
            &s,
            RoundConfig {
                masked_op: MaskedOpMode::Branchy,
                ..Default::default()
            },
        );
        assert_eq!(bl, by);
    }

    #[test]
    fn round_is_deterministic_across_1000_iterations() {
        // F00146 — same seed → same state after 1000 rounds, every time.
        let run = || {
            let mut s = seeded_state(0x1234);
            for _ in 0..1000 {
                s = round_update(&s, RoundConfig::default());
            }
            s
        };
        assert_eq!(run(), run());
        // and the SIMD path agrees with a pure-scalar 1000-round run
        let mut scal = seeded_state(0x1234);
        for _ in 0..1000 {
            scal = round_update_scalar(&scal, RoundConfig::default());
        }
        assert_eq!(run(), scal);
    }

    #[test]
    fn per_lane_dna_diverges_per_lane() {
        // F00130 — DNA mode: lanes seeded with the SAME rule but different state
        // evolve differently (the rule is embedded in each lane's own state).
        let mut s = seeded_state(99);
        for r in &mut s.rule {
            *r = 0xACE1; // identical rule in every lane
        }
        let cfg = RoundConfig {
            per_lane_dna: true,
            ..Default::default()
        };
        let mut cur = s;
        for _ in 0..20 {
            cur = round_update(&cur, cfg);
        }
        // not all lanes collapsed to the same state
        let first = cur.state[0];
        assert!(
            cur.state.iter().any(|&x| x != first),
            "DNA mode did not diverge per lane"
        );
    }

    #[test]
    fn variable_shift_matches_scalar_and_semantics() {
        // F00155 — VPSLLVQ correctness incl. shift ≥ 64 → 0.
        let vals = [1u64, 1, 0xFF, 0xDEAD, 1 << 40, u64::MAX, 2, 3];
        let shifts = [0u64, 63, 8, 4, 20, 1, 64, 100];
        let simd = variable_shift_left(&vals, &shifts);
        let scal = variable_shift_left_scalar(&vals, &shifts);
        assert_eq!(simd, scal);
        assert_eq!(simd[0], 1);
        assert_eq!(simd[1], 1u64 << 63);
        assert_eq!(simd[6], 0, "shift == 64 must yield 0");
        assert_eq!(simd[7], 0, "shift > 64 must yield 0");
    }

    #[test]
    fn parity_with_python_engine() {
        // The Python mirror (scripts/hardware/simd-round.py) and this crate MUST
        // agree. Both pin THIS 3-round result for state=memory=rule=random=
        // [1..=8] — neither can drift without a test failing.
        let s = RoundState {
            state: [1, 2, 3, 4, 5, 6, 7, 8],
            memory: [1, 2, 3, 4, 5, 6, 7, 8],
            rule: [1, 2, 3, 4, 5, 6, 7, 8],
            random: [1, 2, 3, 4, 5, 6, 7, 8],
        };
        let mut cur = s;
        for _ in 0..3 {
            cur = round_update(&cur, RoundConfig::default());
        }
        assert_eq!(cur.state, [0x8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40]);
        assert_eq!(
            cur.memory,
            [
                0x2000_0000_0000_0000,
                0x0,
                0x2000_0000_0000_0000,
                0x0,
                0x2000_0000_0000_0000,
                0x0,
                0x2000_0000_0000_0000,
                0x1
            ]
        );
        assert_eq!(cur.rule, [1, 2, 3, 4, 5, 6, 7, 8]);
        assert_eq!(
            cur.random,
            [
                0x9b1e_842f_6e86_2629,
                0x363d_895a_d50e_6812,
                0xad23_0d75_bb88_4e3b,
                0x6c7b_12b5_aa1c_d024,
                0xf765_969a_c49a_f60d,
                0x5a46_9bef_7f12_b836,
                0xc158_1fc0_1194_9e1f,
                0xd8f6_256b_5439_a048
            ]
        );
    }

    #[test]
    fn round_config_env_resolution() {
        // defaults
        assert_eq!(RoundConfig::resolve(|_| None), RoundConfig::default());
        // both knobs hot-swap via their env vars
        let full = RoundConfig::resolve(|k| {
            Some(
                match k {
                    "SOVEREIGN_CTRL_MASKED_OP_MODE" => "branchy",
                    "SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED" => "true",
                    _ => return None,
                }
                .to_string(),
            )
        });
        assert_eq!(full.masked_op, MaskedOpMode::Branchy);
        assert!(full.per_lane_dna);
        // invalid values keep defaults
        let bad = RoundConfig::resolve(|k| {
            Some(
                match k {
                    "SOVEREIGN_CTRL_MASKED_OP_MODE" => "sideways",
                    "SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED" => "maybe",
                    _ => return None,
                }
                .to_string(),
            )
        });
        assert_eq!(bad, RoundConfig::default());
    }

    #[test]
    fn lane_fields_round_trip() {
        let f = LaneFields {
            state_lo: 0x1234,
            state_hi: 0x5678,
            control: 0x9ABC,
            scratch: 0xDEF0,
        };
        assert_eq!(LaneFields::unpack(f.pack()), f);
        // field isolation — max each, no cross-talk
        let mx = LaneFields {
            state_lo: 0xFFFF,
            state_hi: 0xFFFF,
            control: 0xFFFF,
            scratch: 0xFFFF,
        };
        assert_eq!(mx.pack(), u64::MAX);
        assert_eq!(LaneFields::unpack(u64::MAX), mx);
    }
}
