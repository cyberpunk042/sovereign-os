//! `sovereign-worker-status-word` — E0111 / M00212: the worker 64-bit status
//! word.
//!
//! "Telemetry becomes bits — each worker gets a status word." Bit-level
//! control with telemetry: each worker encodes its live state into one `u64`
//! the scheduler can read with a single load, no parsing. This crate fixes the
//! wire format (the engine writes it, the scheduler reads it) per the
//! catalogued byte layout:
//!
//! | bits  | field            | feature |
//! |-------|------------------|---------|
//! | 0..7  | load bucket      | F01079  |
//! | 8..15 | memory pressure  | F01080  |
//! | 16..23| thermal pressure | F01081  |
//! | 24..31| queue depth      | F01082  |
//! | 32..39| error state      | F01083  |
//! | 40..47| health           | F01084  |
//! | 48..55| policy mode      | F01085  |
//! | 56..63| flags            | F01086  |
//!
//! Each field is one byte (0..=255); the meaning of a bucket value is the
//! engine's contract, but the *layout* is fixed here so producer and consumer
//! never disagree.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The eight byte-fields of a worker status word (M00212).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct WorkerStatusWord {
    /// bits 0..7 — load bucket (F01079).
    pub load_bucket: u8,
    /// bits 8..15 — memory pressure (F01080).
    pub memory_pressure: u8,
    /// bits 16..23 — thermal pressure (F01081).
    pub thermal_pressure: u8,
    /// bits 24..31 — queue depth (F01082).
    pub queue_depth: u8,
    /// bits 32..39 — error state (F01083).
    pub error_state: u8,
    /// bits 40..47 — health (F01084).
    pub health: u8,
    /// bits 48..55 — policy mode (F01085).
    pub policy_mode: u8,
    /// bits 56..63 — flags bitfield (F01086).
    pub flags: u8,
}

impl WorkerStatusWord {
    /// Byte offset (bit shift) of each field, low to high.
    const SHIFTS: [u32; 8] = [0, 8, 16, 24, 32, 40, 48, 56];

    /// Pack the eight fields into a single `u64` — what a worker stores and a
    /// scheduler reads with one load.
    #[must_use]
    pub fn pack(&self) -> u64 {
        let bytes = [
            self.load_bucket,
            self.memory_pressure,
            self.thermal_pressure,
            self.queue_depth,
            self.error_state,
            self.health,
            self.policy_mode,
            self.flags,
        ];
        let mut w = 0u64;
        for (b, shift) in bytes.into_iter().zip(Self::SHIFTS) {
            w |= u64::from(b) << shift;
        }
        w
    }

    /// Unpack a `u64` status word into its eight byte-fields. Total inverse of
    /// [`Self::pack`].
    #[must_use]
    pub fn unpack(word: u64) -> Self {
        let byte = |shift: u32| ((word >> shift) & 0xFF) as u8;
        Self {
            load_bucket: byte(0),
            memory_pressure: byte(8),
            thermal_pressure: byte(16),
            queue_depth: byte(24),
            error_state: byte(32),
            health: byte(40),
            policy_mode: byte(48),
            flags: byte(56),
        }
    }

    /// Read flag bit `n` (0..=7) of the flags byte (F01086).
    #[must_use]
    pub fn flag(&self, n: u8) -> bool {
        debug_assert!(n < 8, "flag index must be 0..=7");
        (self.flags >> (n & 7)) & 1 == 1
    }

    /// Set flag bit `n` (0..=7) of the flags byte to `on`.
    pub fn set_flag(&mut self, n: u8, on: bool) {
        let mask = 1u8 << (n & 7);
        if on {
            self.flags |= mask;
        } else {
            self.flags &= !mask;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> WorkerStatusWord {
        WorkerStatusWord {
            load_bucket: 0x11,
            memory_pressure: 0x22,
            thermal_pressure: 0x33,
            queue_depth: 0x44,
            error_state: 0x55,
            health: 0x66,
            policy_mode: 0x77,
            flags: 0x88,
        }
    }

    #[test]
    fn pack_places_each_field_at_its_documented_byte() {
        // Little-end byte order: load in the lowest byte, flags in the highest.
        assert_eq!(sample().pack(), 0x8877_6655_4433_2211);
    }

    #[test]
    fn pack_unpack_roundtrips() {
        let w = sample();
        assert_eq!(WorkerStatusWord::unpack(w.pack()), w);
        // And over the full u64 space at the boundaries.
        for raw in [0u64, u64::MAX, 0x0102_0304_0506_0708] {
            assert_eq!(WorkerStatusWord::unpack(raw).pack(), raw);
        }
    }

    #[test]
    fn each_field_isolates_to_its_byte() {
        // Setting only one field must light only its byte.
        let mut w = WorkerStatusWord::default();
        w.thermal_pressure = 0xFF;
        assert_eq!(w.pack(), 0x0000_0000_00FF_0000);
        let mut h = WorkerStatusWord::default();
        h.health = 0xAB;
        assert_eq!(h.pack(), 0x0000_AB00_0000_0000);
        let mut f = WorkerStatusWord::default();
        f.flags = 0x01;
        assert_eq!(f.pack(), 0x0100_0000_0000_0000);
    }

    #[test]
    fn unpack_extracts_documented_bytes() {
        let w = WorkerStatusWord::unpack(0x8877_6655_4433_2211);
        assert_eq!(w.load_bucket, 0x11);
        assert_eq!(w.queue_depth, 0x44);
        assert_eq!(w.policy_mode, 0x77);
        assert_eq!(w.flags, 0x88);
    }

    #[test]
    fn flag_bits_get_and_set() {
        let mut w = WorkerStatusWord::default();
        assert!(!w.flag(3));
        w.set_flag(3, true);
        assert!(w.flag(3));
        assert_eq!(w.flags, 0b0000_1000);
        w.set_flag(7, true);
        assert!(w.flag(7));
        w.set_flag(3, false);
        assert!(!w.flag(3));
        assert_eq!(w.flags, 0b1000_0000);
    }

    #[test]
    fn serde_roundtrip() {
        let w = sample();
        let j = serde_json::to_string(&w).unwrap();
        let back: WorkerStatusWord = serde_json::from_str(&j).unwrap();
        assert_eq!(w, back);
    }
}
