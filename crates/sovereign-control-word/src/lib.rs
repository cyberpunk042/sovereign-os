//! `sovereign-control-word` — M002 / M00013: the 64-bit control word + rule-word LUT.
//!
//! Control-word-injected logic: a single `u64` carries the parameters that
//! drive a branchless, masked per-lane operation, and a second `u64` is a
//! 64-entry boolean lookup table indexed by a 6-bit condition. No branches, no
//! parsing — the scheduler injects a word, the lanes act on its bits.
//!
//! Control word layout (M00013), low bit → high:
//!
//! | bits  | field        | width |
//! |-------|--------------|-------|
//! | 0..3  | mode         | 4     |
//! | 4..7  | event        | 4     |
//! | 8..15 | intensity    | 8     |
//! | 16..23| cooldown     | 8     |
//! | 24..31| neighborhood | 8     |
//! | 32..47| param_a      | 16    |
//! | 48..63| param_b      | 16    |

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The decoded control word (M00013). `mode` and `event` use the low 4 bits
/// (0..=15); the rest use their full width.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct ControlWord {
    /// bits 0..3 — mode (0..=15).
    pub mode: u8,
    /// bits 4..7 — event (0..=15).
    pub event: u8,
    /// bits 8..15 — intensity.
    pub intensity: u8,
    /// bits 16..23 — cooldown.
    pub cooldown: u8,
    /// bits 24..31 — neighborhood.
    pub neighborhood: u8,
    /// bits 32..47 — param A.
    pub param_a: u16,
    /// bits 48..63 — param B.
    pub param_b: u16,
}

impl ControlWord {
    /// Pack the fields into a `u64`. `mode`/`event` are masked to 4 bits, so a
    /// value above 15 keeps only its low nibble (the field's width).
    #[must_use]
    pub fn pack(&self) -> u64 {
        (u64::from(self.mode) & 0xf)
            | (u64::from(self.event) & 0xf) << 4
            | u64::from(self.intensity) << 8
            | u64::from(self.cooldown) << 16
            | u64::from(self.neighborhood) << 24
            | u64::from(self.param_a) << 32
            | u64::from(self.param_b) << 48
    }

    /// Decode a `u64` control word. Total inverse of [`Self::pack`] for any
    /// `mode`/`event` already in 0..=15.
    #[must_use]
    pub fn unpack(word: u64) -> Self {
        Self {
            mode: (word & 0xf) as u8,
            event: ((word >> 4) & 0xf) as u8,
            intensity: ((word >> 8) & 0xff) as u8,
            cooldown: ((word >> 16) & 0xff) as u8,
            neighborhood: ((word >> 24) & 0xff) as u8,
            param_a: ((word >> 32) & 0xffff) as u16,
            param_b: ((word >> 48) & 0xffff) as u16,
        }
    }
}

/// A 64-entry boolean lookup table packed into one `u64` (E0013 / E0018).
///
/// Each bit is the table's answer for one 6-bit condition: bit `c` is the
/// result for condition `c`. [`Self::decide`] is the branchless evaluation
/// `(word >> condition) & 1`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct RuleWord(pub u64);

impl RuleWord {
    /// Evaluate the table for a 6-bit `condition` (its low 6 bits are used):
    /// `(rule_word >> condition) & 1`.
    #[must_use]
    pub fn decide(self, condition: u8) -> bool {
        (self.0 >> (condition & 63)) & 1 == 1
    }

    /// Set the table's answer for `condition`.
    pub fn set(&mut self, condition: u8, answer: bool) {
        let bit = 1u64 << (condition & 63);
        if answer {
            self.0 |= bit;
        } else {
            self.0 &= !bit;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> ControlWord {
        ControlWord {
            mode: 0x3,
            event: 0xA,
            intensity: 0x12,
            cooldown: 0x34,
            neighborhood: 0x56,
            param_a: 0x789a,
            param_b: 0xbcde,
        }
    }

    #[test]
    fn pack_places_fields_at_documented_bits() {
        let w = sample().pack();
        // Reconstruct by hand to lock the layout.
        let expected = 0x3
            | 0xA << 4
            | 0x12u64 << 8
            | 0x34u64 << 16
            | 0x56u64 << 24
            | 0x789au64 << 32
            | 0xbcdeu64 << 48;
        assert_eq!(w, expected);
    }

    #[test]
    fn pack_unpack_roundtrips() {
        let c = sample();
        assert_eq!(ControlWord::unpack(c.pack()), c);
        for raw in [0u64, u64::MAX, 0x0123_4567_89ab_cdef] {
            assert_eq!(ControlWord::unpack(raw).pack(), raw);
        }
    }

    #[test]
    fn mode_event_are_four_bit_fields() {
        // mode=3, event=10 occupy only the low byte's two nibbles.
        let w = sample().pack();
        assert_eq!(w & 0xff, 0xA3); // event<<4 | mode
        // a mode above 15 keeps only its low nibble.
        let over = ControlWord {
            mode: 0xF7,
            ..Default::default()
        };
        assert_eq!(ControlWord::unpack(over.pack()).mode, 0x7);
    }

    #[test]
    fn rule_word_lut_is_branchless_bit_lookup() {
        // Table answers true for even conditions only.
        let mut r = RuleWord::default();
        for c in 0u8..64 {
            r.set(c, c % 2 == 0);
        }
        for c in 0u8..64 {
            assert_eq!(r.decide(c), c % 2 == 0, "condition {c}");
        }
        // decide masks to 6 bits: condition 64 wraps to 0.
        assert_eq!(r.decide(64), r.decide(0));
    }

    #[test]
    fn control_word_serde_roundtrip() {
        let c = sample();
        let j = serde_json::to_string(&c).unwrap();
        let back: ControlWord = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
