//! `sovereign-control-word` — M002 control-word injected logic.
//!
//! The dump's execution model attaches a **control word** to every branch:
//! a packed 32/64-bit field of "injected logic" that deterministically
//! gates how the branch runs. This crate is that word — a `u64` with typed
//! bitfields:
//!
//! ```text
//! bits  0..8   opcode        (u8)
//! bits  8..11  precision     (PrecisionCode: ternary/int8/quantized/fp16)
//! bits 11..16  flags         (commit-gate / sandbox / replay / audit / speculative)
//! bits 16..48  operand       (u32)
//! bits 48..64  reserved      (must be zero)
//! ```
//!
//! Encoding is exact and reversible; [`ControlWord::from_raw`] rejects an
//! invalid precision code or any set reserved bit, so a malformed word is
//! caught rather than silently misread.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the control-word surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

// Field offsets / widths.
const OPCODE_SHIFT: u32 = 0;
const PRECISION_SHIFT: u32 = 8;
const FLAGS_SHIFT: u32 = 11;
const OPERAND_SHIFT: u32 = 16;
const RESERVED_SHIFT: u32 = 48;

const PRECISION_MASK: u64 = 0b111; // 3 bits
const FLAGS_MASK: u64 = 0b1_1111; // 5 bits
const OPERAND_MASK: u64 = 0xFFFF_FFFF; // 32 bits

/// `flags` bit: the branch may only commit through the Auditor gate.
pub const FLAG_COMMIT_GATE: u8 = 1 << 0;
/// `flags` bit: the branch must run sandboxed.
pub const FLAG_SANDBOX: u8 = 1 << 1;
/// `flags` bit: the branch is replay-logged.
pub const FLAG_REPLAY: u8 = 1 << 2;
/// `flags` bit: the branch is audited.
pub const FLAG_AUDIT: u8 = 1 << 3;
/// `flags` bit: the branch is speculative (draft path).
pub const FLAG_SPECULATIVE: u8 = 1 << 4;

/// The precision lane a branch executes on (selects the compute kernel).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PrecisionCode {
    /// 1.58-bit ternary (bitlinear).
    Ternary,
    /// INT8 VNNI (vnni).
    Int8,
    /// 4-bit NVFP4 (nvfp4).
    Quantized,
    /// FP16.
    Fp16,
}

impl PrecisionCode {
    fn to_bits(self) -> u64 {
        match self {
            PrecisionCode::Ternary => 0,
            PrecisionCode::Int8 => 1,
            PrecisionCode::Quantized => 2,
            PrecisionCode::Fp16 => 3,
        }
    }

    fn from_bits(b: u64) -> Option<PrecisionCode> {
        match b {
            0 => Some(PrecisionCode::Ternary),
            1 => Some(PrecisionCode::Int8),
            2 => Some(PrecisionCode::Quantized),
            3 => Some(PrecisionCode::Fp16),
            _ => None,
        }
    }
}

/// Control-word decode errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum ControlWordError {
    /// The precision field held an undefined code (4..7).
    #[error("invalid precision code {0} (valid: 0..=3)")]
    InvalidPrecision(u64),
    /// A reserved (high) bit was set.
    #[error("reserved bits set: {0:#x}")]
    ReservedBitsSet(u64),
}

/// A per-branch control word.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ControlWord(u64);

impl ControlWord {
    /// Build a control word from its fields. `flags` uses the `FLAG_*` bits;
    /// only the low 5 flag bits are kept.
    pub fn new(opcode: u8, precision: PrecisionCode, flags: u8, operand: u32) -> Self {
        let raw = (opcode as u64) << OPCODE_SHIFT
            | precision.to_bits() << PRECISION_SHIFT
            | ((flags as u64) & FLAGS_MASK) << FLAGS_SHIFT
            | (operand as u64) << OPERAND_SHIFT;
        ControlWord(raw)
    }

    /// The raw packed `u64`.
    pub fn raw(self) -> u64 {
        self.0
    }

    /// Decode a raw word, validating the precision code and reserved bits.
    pub fn from_raw(raw: u64) -> Result<Self, ControlWordError> {
        let reserved = raw >> RESERVED_SHIFT;
        if reserved != 0 {
            return Err(ControlWordError::ReservedBitsSet(
                reserved << RESERVED_SHIFT,
            ));
        }
        let prec = (raw >> PRECISION_SHIFT) & PRECISION_MASK;
        if PrecisionCode::from_bits(prec).is_none() {
            return Err(ControlWordError::InvalidPrecision(prec));
        }
        Ok(ControlWord(raw))
    }

    /// The opcode field.
    pub fn opcode(self) -> u8 {
        (self.0 >> OPCODE_SHIFT) as u8
    }

    /// The precision lane.
    pub fn precision(self) -> PrecisionCode {
        // Safe: only constructed via `new` / validated `from_raw`.
        PrecisionCode::from_bits((self.0 >> PRECISION_SHIFT) & PRECISION_MASK)
            .unwrap_or(PrecisionCode::Ternary)
    }

    /// The raw flag bits.
    pub fn flags(self) -> u8 {
        ((self.0 >> FLAGS_SHIFT) & FLAGS_MASK) as u8
    }

    /// Whether a given `FLAG_*` bit is set.
    pub fn has_flag(self, flag: u8) -> bool {
        self.flags() & flag != 0
    }

    /// The 32-bit operand field.
    pub fn operand(self) -> u32 {
        ((self.0 >> OPERAND_SHIFT) & OPERAND_MASK) as u32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_all_fields() {
        let cw = ControlWord::new(
            0xAB,
            PrecisionCode::Quantized,
            FLAG_COMMIT_GATE | FLAG_AUDIT,
            0xDEAD_BEEF,
        );
        assert_eq!(cw.opcode(), 0xAB);
        assert_eq!(cw.precision(), PrecisionCode::Quantized);
        assert!(cw.has_flag(FLAG_COMMIT_GATE));
        assert!(cw.has_flag(FLAG_AUDIT));
        assert!(!cw.has_flag(FLAG_SANDBOX));
        assert_eq!(cw.operand(), 0xDEAD_BEEF);
    }

    #[test]
    fn raw_decode_round_trip() {
        let cw = ControlWord::new(7, PrecisionCode::Fp16, FLAG_SPECULATIVE, 12345);
        let back = ControlWord::from_raw(cw.raw()).unwrap();
        assert_eq!(cw, back);
    }

    #[test]
    fn fields_are_isolated() {
        // Max each field; confirm no cross-talk.
        let cw = ControlWord::new(0xFF, PrecisionCode::Fp16, 0b1_1111, 0xFFFF_FFFF);
        assert_eq!(cw.opcode(), 0xFF);
        assert_eq!(cw.precision(), PrecisionCode::Fp16);
        assert_eq!(cw.flags(), 0b1_1111);
        assert_eq!(cw.operand(), 0xFFFF_FFFF);
    }

    #[test]
    fn precision_maps_to_each_kernel_lane() {
        for p in [
            PrecisionCode::Ternary,
            PrecisionCode::Int8,
            PrecisionCode::Quantized,
            PrecisionCode::Fp16,
        ] {
            let cw = ControlWord::new(0, p, 0, 0);
            assert_eq!(cw.precision(), p);
        }
    }

    #[test]
    fn invalid_precision_code_rejected() {
        // Force precision bits to 0b101 (5) — undefined.
        let raw = 5u64 << PRECISION_SHIFT;
        assert!(matches!(
            ControlWord::from_raw(raw).unwrap_err(),
            ControlWordError::InvalidPrecision(5)
        ));
    }

    #[test]
    fn reserved_bits_rejected() {
        let raw = 1u64 << 60; // a reserved high bit
        assert!(matches!(
            ControlWord::from_raw(raw).unwrap_err(),
            ControlWordError::ReservedBitsSet(_)
        ));
    }

    #[test]
    fn flags_truncate_to_five_bits() {
        // bit 5 (0b10_0000) is outside the flag field → dropped.
        let cw = ControlWord::new(0, PrecisionCode::Ternary, 0b10_0000, 0);
        assert_eq!(cw.flags(), 0);
    }

    #[test]
    fn serde_round_trip() {
        let cw = ControlWord::new(3, PrecisionCode::Int8, FLAG_REPLAY, 99);
        let j = serde_json::to_string(&cw).unwrap();
        let back: ControlWord = serde_json::from_str(&j).unwrap();
        assert_eq!(cw, back);
    }
}

/// M00013 — the canonical control-word field layout (M002 milestone).
///
/// The dump's M00013 layout packs 7 typed fields into one `u64`:
/// `mode / event / intensity / cooldown / neighborhood / paramA / paramB`
/// (R00180). This is a SECOND, *versioned* layout alongside [`ControlWord`]
/// (the opcode/precision/flags/operand word cortex emits today) — the spec makes
/// the layout a versioned knob (`control_word_layout_version`, F00092 / R00269),
/// so both coexist rather than one replacing the other.
///
/// This is the SAME bit-machine as `scripts/hardware/control-word.py` and the
/// `webapp/avx-modes` panel: a parity test pins all three to one word, so the
/// crate the runtime links, the CLI the operator runs, and the panel the operator
/// clicks can never disagree.
pub mod m00013 {
    use serde::{Deserialize, Serialize};
    use thiserror::Error;

    /// Layout version tag (F00092 / R00269).
    pub const LAYOUT_VERSION: u32 = 1;

    /// `(name, shift, width)` — R00180 canonical layout; sums to exactly 64 bits.
    pub const FIELDS: [(&str, u32, u32); 7] = [
        ("mode", 0, 4),
        ("event", 4, 4),
        ("intensity", 8, 8),
        ("cooldown", 16, 8),
        ("neighborhood", 24, 8),
        ("paramA", 32, 16),
        ("paramB", 48, 16),
    ];

    /// The 7 decoded M00013 fields.
    #[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
    pub struct Fields {
        /// bits 0..4 (0..=15)
        pub mode: u16,
        /// bits 4..8 (0..=15)
        pub event: u16,
        /// bits 8..16 (0..=255)
        pub intensity: u16,
        /// bits 16..24 (0..=255)
        pub cooldown: u16,
        /// bits 24..32 (0..=255)
        pub neighborhood: u16,
        /// bits 32..48 (0..=65535)
        pub param_a: u16,
        /// bits 48..64 (0..=65535)
        pub param_b: u16,
    }

    /// A field value exceeded its bit width (R00189).
    #[derive(Debug, Error, PartialEq, Eq)]
    #[error("field {field} = {value} overflows its {width}-bit range (0..={max})")]
    pub struct Overflow {
        /// Which field overflowed.
        pub field: &'static str,
        /// The offending value.
        pub value: u16,
        /// The field's bit width.
        pub width: u32,
        /// The field's max value.
        pub max: u16,
    }

    impl Fields {
        /// Pack the fields into the u64 control word, rejecting any field past
        /// its width (M00025 compose-without-overflow / R00189).
        pub fn pack(&self) -> Result<u64, Overflow> {
            let vals: [(&'static str, u16, u32, u32); 7] = [
                ("mode", self.mode, 0, 4),
                ("event", self.event, 4, 4),
                ("intensity", self.intensity, 8, 8),
                ("cooldown", self.cooldown, 16, 8),
                ("neighborhood", self.neighborhood, 24, 8),
                ("paramA", self.param_a, 32, 16),
                ("paramB", self.param_b, 48, 16),
            ];
            let mut word = 0u64;
            for (field, value, shift, width) in vals {
                let max = ((1u32 << width) - 1) as u16;
                if value > max {
                    return Err(Overflow {
                        field,
                        value,
                        width,
                        max,
                    });
                }
                word |= (value as u64) << shift;
            }
            Ok(word)
        }

        /// Decode a control word into its 7 fields (M00026 decompose).
        pub fn unpack(word: u64) -> Fields {
            let f = |shift: u32, width: u32| ((word >> shift) & ((1u64 << width) - 1)) as u16;
            Fields {
                mode: f(0, 4),
                event: f(4, 4),
                intensity: f(8, 8),
                cooldown: f(16, 8),
                neighborhood: f(24, 8),
                param_a: f(32, 16),
                param_b: f(48, 16),
            }
        }
    }

    /// M00017 — the 64-entry boolean rule LUT inside one u64: the branchless
    /// decision bit `(rule_word >> (condition & 63)) & 1`. Scalar today; the
    /// AVX-512 masked form evaluates 8 lanes of this per instruction.
    pub fn lut(rule_word: u64, condition: u32) -> u8 {
        ((rule_word >> (condition & 63)) & 1) as u8
    }

    /// M00017/M00015 — evaluate one rule word against MANY conditions at once.
    ///
    /// This is the parallelism primitive: the AVX-512 lift broadcasts `rule_word`
    /// into a ZMM, shifts by the 8 per-lane conditions (`VPSHLDVQ`) and masks
    /// bit 0, deciding 8 branches per instruction. The scalar loop here is the
    /// portable fallback (`sovereign-cpu-dispatch` ScalarBaseline) — same result,
    /// one lane at a time. The intrinsic backend lives behind `sovereign-simd`
    /// (the only crate allowed `unsafe`) + runtime CPU dispatch; this crate stays
    /// `forbid(unsafe_code)` and always-correct.
    pub fn lut_batch(rule_word: u64, conditions: &[u32]) -> Vec<u8> {
        conditions.iter().map(|&c| lut(rule_word, c)).collect()
    }

    /// M00104 — a branch query over many control words: the bitmask of which of
    /// the first ≤64 branches have `field == value`.
    ///
    /// This is how "which branches are shell-allowed / commit-mode / risky" is
    /// answered in ONE pass: extract the field from each word, compare, set the
    /// branch's bit. The AVX-512 lift does 8 words per masked compare
    /// (`VPCMPEQ` → k-mask); the scalar loop is the portable fallback. Branch `i`
    /// maps to bit `i` of the returned mask (branches past 64 are ignored — a
    /// 64-branch frontier is one `u64` mask, the natural k-register width).
    pub fn field_query_mask(words: &[u64], shift: u32, width: u32, value: u16) -> u64 {
        let field_mask = (1u64 << width) - 1;
        let mut out = 0u64;
        for (i, &w) in words.iter().take(64).enumerate() {
            if ((w >> shift) & field_mask) as u16 == value {
                out |= 1u64 << i;
            }
        }
        out
    }

    // ── M00104 — the control word GATES what a branch may do ──
    // The word stops being an audit artifact and becomes policy: these masks
    // decide, from the bits alone, whether a branch may touch the shell / files
    // / network. `mode` is the next-action (bits 0..4); `paramB` (bits 48..64)
    // carries the FLAG_* bits cortex packs (commit-gate / sandbox / audit /
    // speculative). This is "policy becomes bits" made executable.

    /// `mode` value for a committed branch (NextAction::Commit → opcode 1).
    pub const MODE_COMMIT: u16 = 1;

    /// The permissions a branch's control word grants (M00104 branch queries).
    #[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
    pub struct Permissions {
        /// May run a shell command (committed, non-speculative).
        pub shell_allowed: bool,
        /// May write files (committed, non-speculative, non-sandboxed).
        pub file_write_allowed: bool,
        /// May reach the network (not sandboxed).
        pub network_allowed: bool,
        /// Must pass the Auditor commit-gate before any durable effect.
        pub verification_required: bool,
        /// A draft/speculative branch — no durable side effects.
        pub speculative_only: bool,
    }

    /// Decode the M00013 word's permissions (M00104). Reads `mode` (bits 0..4)
    /// and the flag bits packed in `paramB` (bits 48..64). Pure bit-tests — the
    /// same shift-and-AND the AVX-512 scheduler runs 8-wide.
    pub fn branch_permissions(word: u64) -> Permissions {
        let mode = (word & 0xF) as u16;
        let flags = ((word >> 48) & 0xFFFF) as u16;
        let has = |flag: u8| flags & (flag as u16) != 0;
        let committed = mode == MODE_COMMIT;
        let speculative = has(crate::FLAG_SPECULATIVE);
        let sandboxed = has(crate::FLAG_SANDBOX);
        Permissions {
            shell_allowed: committed && !speculative,
            file_write_allowed: committed && !speculative && !sandboxed,
            network_allowed: !sandboxed,
            verification_required: has(crate::FLAG_COMMIT_GATE),
            speculative_only: speculative,
        }
    }

    // ── M00027 / M00028 — the generic bit-packing helper (R00263 / R00264) ──

    /// Generic bit-packer (M00027, R00263): pack 8 lanes (low byte of each) into
    /// one u64 — lane `i` occupies bits `i*8 .. i*8+8`. The layout-agnostic helper
    /// the typed [`Fields`] builds on.
    pub fn pack_u64(lanes: &[u16; 8]) -> u64 {
        let mut w = 0u64;
        for (i, &v) in lanes.iter().enumerate() {
            w |= ((v & 0xFF) as u64) << (i * 8);
        }
        w
    }

    /// Generic bit-extract (M00028, R00264): the inverse of [`pack_u64`].
    pub fn unpack_u64(word: u64) -> [u16; 8] {
        let mut out = [0u16; 8];
        for (i, o) in out.iter_mut().enumerate() {
            *o = ((word >> (i * 8)) & 0xFF) as u16;
        }
        out
    }

    // ── Overflow policy (R00318 / R00319 / R00320) ──

    /// How field packing treats a value past its bit width.
    #[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
    #[serde(rename_all = "kebab-case")]
    pub enum OverflowMode {
        /// Reject (the safe default cortex relies on). R00320.
        #[default]
        Abort,
        /// Mask to the field width. R00319.
        Wrap,
        /// Clamp to the field's max. R00318.
        Saturate,
    }

    impl Fields {
        /// Pack under an explicit [`OverflowMode`] (R00318-320). `Abort` matches
        /// [`Fields::pack`]; `Wrap` masks; `Saturate` clamps.
        pub fn pack_mode(&self, mode: OverflowMode) -> Result<u64, Overflow> {
            let vals: [(&'static str, u16, u32, u32); 7] = [
                ("mode", self.mode, 0, 4),
                ("event", self.event, 4, 4),
                ("intensity", self.intensity, 8, 8),
                ("cooldown", self.cooldown, 16, 8),
                ("neighborhood", self.neighborhood, 24, 8),
                ("paramA", self.param_a, 32, 16),
                ("paramB", self.param_b, 48, 16),
            ];
            let mut word = 0u64;
            for (field, value, shift, width) in vals {
                let max = ((1u32 << width) - 1) as u16;
                let v = match mode {
                    OverflowMode::Abort if value > max => {
                        return Err(Overflow {
                            field,
                            value,
                            width,
                            max,
                        });
                    }
                    OverflowMode::Saturate => value.min(max),
                    _ => value & max, // Wrap (and the in-range Abort case)
                };
                word |= (v as u64) << shift;
            }
            Ok(word)
        }
    }

    // ── M00022 / M00023 / M00024 — rule words of 32 / 64 / 128 bits ──

    /// A boolean rule table of 32, 64, or 128 entries — one bit per condition.
    /// 32-bit → 5-bit condition, 64-bit → 6-bit, 128-bit → 7-bit (two u64 limbs).
    #[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
    pub enum RuleWord {
        /// 32-entry table (R00250 / R00300-301).
        U32(u32),
        /// 64-entry table (R00251 / R00302-303).
        U64(u64),
        /// 128-entry table across two limbs (R00252 / R00304-307).
        U128 {
            /// entries 0..64
            lo: u64,
            /// entries 64..128
            hi: u64,
        },
    }

    impl RuleWord {
        /// The condition width in bits (5 / 6 / 7).
        pub fn condition_bits(&self) -> u32 {
            match self {
                RuleWord::U32(_) => 5,
                RuleWord::U64(_) => 6,
                RuleWord::U128 { .. } => 7,
            }
        }

        /// The decision bit for `condition` (masked to this width). The generic
        /// M00017 LUT across all three widths (R00300-307).
        pub fn decide(&self, condition: u32) -> u8 {
            match self {
                RuleWord::U32(w) => ((w >> (condition & 31)) & 1) as u8,
                RuleWord::U64(w) => ((w >> (condition & 63)) & 1) as u8,
                RuleWord::U128 { lo, hi } => {
                    let c = condition & 127; // 7-bit
                    let limb = if c < 64 { lo } else { hi }; // bit-6 selects limb
                    ((limb >> (c & 63)) & 1) as u8 // bits 0..5 select entry
                }
            }
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn fields_tile_64_bits_with_no_gap_or_overlap() {
            let mut covered = 0u64;
            for (_n, shift, width) in FIELDS {
                let mask = ((1u64 << width) - 1) << shift;
                assert_eq!(covered & mask, 0, "fields overlap");
                covered |= mask;
            }
            assert_eq!(covered, u64::MAX, "fields must fill exactly 64 bits");
        }

        #[test]
        fn pack_unpack_round_trips_exactly() {
            let f = Fields {
                mode: 3,
                event: 1,
                intensity: 200,
                cooldown: 17,
                neighborhood: 255,
                param_a: 4242,
                param_b: 65535,
            };
            let w = f.pack().unwrap();
            assert_eq!(Fields::unpack(w), f);
        }

        #[test]
        fn overflow_is_rejected_per_field() {
            let bad_mode = Fields {
                mode: 16,
                event: 0,
                intensity: 0,
                cooldown: 0,
                neighborhood: 0,
                param_a: 0,
                param_b: 0,
            };
            assert_eq!(bad_mode.pack().unwrap_err().field, "mode");
        }

        #[test]
        fn lut_is_the_shift_and_and_decision_bit() {
            // 0b101010 = 0x2A → bits 0..5 = 0,1,0,1,0,1
            for (cond, expect) in [(0, 0), (1, 1), (2, 0), (3, 1), (4, 0), (5, 1)] {
                assert_eq!(lut(0x2A, cond), expect, "LUT bit {cond}");
            }
            assert_eq!(lut(0x2A, 64), lut(0x2A, 0)); // 6-bit wrap
        }

        #[test]
        fn parity_with_python_engine_and_panel() {
            // scripts/hardware/control-word.py AND webapp/avx-modes both produce
            // THIS word for mode=3 / intensity=200 / paramA=4242. The crate the
            // runtime links MUST agree with the CLI + panel — one bit-machine.
            let f = Fields {
                mode: 3,
                event: 0,
                intensity: 200,
                cooldown: 0,
                neighborhood: 0,
                param_a: 4242,
                param_b: 0,
            };
            assert_eq!(f.pack().unwrap(), 0x0000_1092_0000_C803);
        }

        fn zero() -> Fields {
            Fields {
                mode: 0,
                event: 0,
                intensity: 0,
                cooldown: 0,
                neighborhood: 0,
                param_a: 0,
                param_b: 0,
            }
        }

        #[test]
        fn lut_batch_decides_many_conditions_at_once() {
            // 0b101010 = 0x2A → conditions 0..6 decide 0,1,0,1,0,1 in ONE call
            assert_eq!(lut_batch(0x2A, &[0, 1, 2, 3, 4, 5]), vec![0, 1, 0, 1, 0, 1]);
            assert!(lut_batch(0x2A, &[]).is_empty());
        }

        #[test]
        fn field_query_mask_selects_matching_branches() {
            // three branches with mode = 1, 3, 3 → query mode==3 hits branches 1 & 2
            let words = [
                Fields { mode: 1, ..zero() }.pack().unwrap(),
                Fields { mode: 3, ..zero() }.pack().unwrap(),
                Fields { mode: 3, ..zero() }.pack().unwrap(),
            ];
            assert_eq!(field_query_mask(&words, 0, 4, 3), 0b110); // mode bits 0..4
            assert_eq!(field_query_mask(&words, 0, 4, 1), 0b001);
            assert_eq!(field_query_mask(&words, 0, 4, 9), 0); // no branch matches
        }

        #[test]
        fn branch_permissions_gate_from_the_bits() {
            // committed, audit+commit-gate set, not sandboxed, not speculative
            let committed = Fields {
                mode: MODE_COMMIT,
                param_b: (crate::FLAG_COMMIT_GATE | crate::FLAG_AUDIT) as u16,
                ..zero()
            }
            .pack()
            .unwrap();
            let p = branch_permissions(committed);
            assert!(p.shell_allowed && p.file_write_allowed && p.network_allowed);
            assert!(p.verification_required && !p.speculative_only);

            // speculative branch → may not run shell / write files (draft only)
            let spec = Fields {
                mode: MODE_COMMIT,
                param_b: crate::FLAG_SPECULATIVE as u16,
                ..zero()
            }
            .pack()
            .unwrap();
            let p = branch_permissions(spec);
            assert!(!p.shell_allowed && !p.file_write_allowed && p.speculative_only);

            // sandboxed (risky) branch → no file-write, no network
            let sandboxed = Fields {
                mode: MODE_COMMIT,
                param_b: crate::FLAG_SANDBOX as u16,
                ..zero()
            }
            .pack()
            .unwrap();
            let p = branch_permissions(sandboxed);
            assert!(!p.file_write_allowed && !p.network_allowed && p.shell_allowed);

            // non-committed (expand) → no shell
            let expand = Fields { mode: 2, ..zero() }.pack().unwrap();
            assert!(!branch_permissions(expand).shell_allowed);
        }

        #[test]
        fn generic_pack_unpack_round_trips() {
            let lanes = [0u16, 1, 2, 200, 255, 128, 7, 42];
            assert_eq!(unpack_u64(pack_u64(&lanes)), lanes);
            // each lane is one byte at i*8
            assert_eq!(pack_u64(&[0xFF, 0, 0, 0, 0, 0, 0, 0]) & 0xFF, 0xFF);
            assert_eq!(pack_u64(&[0, 0, 0, 0, 0, 0, 0, 0xFF]) >> 56, 0xFF);
        }

        #[test]
        fn overflow_modes_wrap_saturate_abort() {
            // paramA (16-bit, max 65535) is fine; mode (4-bit, max 15) overflows at 16
            let f = Fields { mode: 20, ..zero() };
            assert!(f.pack_mode(OverflowMode::Abort).is_err());
            assert_eq!(f.pack_mode(OverflowMode::Saturate).unwrap() & 0xF, 15); // clamp
            assert_eq!(f.pack_mode(OverflowMode::Wrap).unwrap() & 0xF, 20 & 0xF); // 4
            // in-range value is identical across all modes
            let g = Fields {
                mode: 3,
                param_a: 4242,
                ..zero()
            };
            let w = g.pack().unwrap();
            for m in [
                OverflowMode::Abort,
                OverflowMode::Wrap,
                OverflowMode::Saturate,
            ] {
                assert_eq!(g.pack_mode(m).unwrap(), w);
            }
        }

        #[test]
        fn rule_word_widths_32_64_128() {
            assert_eq!(RuleWord::U32(0).condition_bits(), 5);
            assert_eq!(RuleWord::U64(0).condition_bits(), 6);
            assert_eq!(RuleWord::U128 { lo: 0, hi: 0 }.condition_bits(), 7);
            // 0b101010 = 0x2A in each width → bit 1 = 1, bit 2 = 0
            for rw in [
                RuleWord::U32(0x2A),
                RuleWord::U64(0x2A),
                RuleWord::U128 { lo: 0x2A, hi: 0 },
            ] {
                assert_eq!(rw.decide(1), 1);
                assert_eq!(rw.decide(2), 0);
            }
            // 128-bit: condition 64 selects the hi limb, bit 0
            assert_eq!(RuleWord::U128 { lo: 0, hi: 1 }.decide(64), 1);
            assert_eq!(RuleWord::U128 { lo: 1, hi: 0 }.decide(0), 1);
            // 32-bit and 64-bit agree on the first 32 conditions (R00258)
            for c in 0..32 {
                assert_eq!(
                    RuleWord::U32(0xDEAD_BEEF).decide(c),
                    RuleWord::U64(0xDEAD_BEEF).decide(c)
                );
            }
        }
    }
}
