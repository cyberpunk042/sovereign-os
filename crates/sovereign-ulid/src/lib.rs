//! `sovereign-ulid` — unique ids that sort by the time they were made.
//!
//! A request or trace needs an id that is unique, but a plain random UUID throws
//! away something useful: if ids *sorted* by creation time, logs and database rows
//! would naturally order themselves and range scans would be cheap. A **ULID**
//! gives both. It is 128 bits — a 48-bit millisecond timestamp in the high bits
//! followed by 80 bits of randomness — written as 26 **Crockford base32**
//! characters. Because the timestamp leads and base32 preserves byte order, two
//! ULIDs compare in time order as plain strings, while the 80 random bits make a
//! collision within a millisecond astronomically unlikely.
//!
//! [`Ulid`] is the value; [`Ulid::to_string`] / [`Ulid::parse`] convert to and
//! from the canonical text; [`Ulid::timestamp_ms`] recovers the creation time.
//! [`UlidGenerator`] produces them from a seeded generator (so tests are
//! deterministic) and is **monotonic**: if two ids are requested in the same
//! millisecond it increments the random field instead of drawing a fresh one, so
//! ids created back-to-back still sort in creation order.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the ulid surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Crockford base32 alphabet (no I, L, O, U to avoid ambiguity).
const ALPHABET: &[u8; 32] = b"0123456789ABCDEFGHJKMNPQRSTVWXYZ";

/// The maximum 48-bit timestamp value.
const MAX_TIME: u64 = (1 << 48) - 1;

/// A 128-bit ULID.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Ulid(pub u128);

impl Ulid {
    /// Build from a `timestamp_ms` (48 bits used) and 80 bits of `randomness`.
    pub fn from_parts(timestamp_ms: u64, randomness: u128) -> Self {
        let ts = (timestamp_ms & MAX_TIME) as u128;
        let rand = randomness & ((1u128 << 80) - 1);
        Ulid((ts << 80) | rand)
    }

    /// The 48-bit creation timestamp in milliseconds.
    pub fn timestamp_ms(&self) -> u64 {
        (self.0 >> 80) as u64
    }

    /// The 80-bit randomness field.
    pub fn randomness(&self) -> u128 {
        self.0 & ((1u128 << 80) - 1)
    }

    /// The canonical 26-character Crockford base32 string.
    pub fn to_canonical(&self) -> String {
        let mut buf = [0u8; 26];
        let mut v = self.0;
        // encode least-significant 5 bits last; fill from the end.
        for slot in buf.iter_mut().rev() {
            *slot = ALPHABET[(v & 0x1f) as usize];
            v >>= 5;
        }
        // SAFETY-free: all bytes are ASCII from ALPHABET.
        String::from_utf8(buf.to_vec()).unwrap()
    }

    /// Parse a 26-character canonical ULID string (case-insensitive).
    pub fn parse(s: &str) -> Option<Ulid> {
        if s.len() != 26 {
            return None;
        }
        let mut v: u128 = 0;
        for c in s.bytes() {
            let d = decode_char(c)?;
            v = (v << 5) | d as u128;
        }
        Some(Ulid(v))
    }
}

impl std::fmt::Display for Ulid {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.to_canonical())
    }
}

/// Decode one Crockford base32 character to its 5-bit value (case-insensitive,
/// mapping the ambiguous I/L→1 and O→0).
fn decode_char(c: u8) -> Option<u8> {
    let up = c.to_ascii_uppercase();
    match up {
        b'0' | b'O' => Some(0),
        b'1' | b'I' | b'L' => Some(1),
        b'2'..=b'9' => Some(up - b'0'),
        // letters A.. skipping I, L, O, U
        b'A'..=b'H' => Some(up - b'A' + 10),
        b'J' | b'K' => Some(up - b'J' + 18),
        b'M' | b'N' => Some(up - b'M' + 20),
        b'P'..=b'T' => Some(up - b'P' + 22),
        b'V'..=b'Z' => Some(up - b'V' + 27),
        _ => None,
    }
}

/// A monotonic, seeded ULID generator.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UlidGenerator {
    rng: u64,
    last_ms: u64,
    last_random: u128,
}

impl UlidGenerator {
    /// A generator seeded with `seed`.
    pub fn new(seed: u64) -> Self {
        Self {
            rng: seed | 1,
            last_ms: 0,
            last_random: 0,
        }
    }

    fn next_random(&mut self) -> u128 {
        // two splitmix64 draws → 80 bits used.
        let hi = self.splitmix() as u128;
        let lo = self.splitmix() as u128;
        ((hi << 64) | lo) & ((1u128 << 80) - 1)
    }

    fn splitmix(&mut self) -> u64 {
        self.rng = self.rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.rng;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Generate a ULID for `timestamp_ms`. Monotonic: if the timestamp matches the
    /// previous call's, the random field is incremented (rather than re-drawn) so
    /// the new id still sorts after the last one.
    pub fn generate(&mut self, timestamp_ms: u64) -> Ulid {
        let ts = timestamp_ms & MAX_TIME;
        let rand = if ts == self.last_ms {
            // same millisecond: increment, wrapping within 80 bits.
            (self.last_random + 1) & ((1u128 << 80) - 1)
        } else {
            self.next_random()
        };
        self.last_ms = ts;
        self.last_random = rand;
        Ulid::from_parts(ts, rand)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_through_canonical() {
        let u = Ulid::from_parts(0x0123_4567_89AB, 0x1122_3344_5566_7788_99AA);
        let s = u.to_canonical();
        assert_eq!(s.len(), 26);
        assert_eq!(Ulid::parse(&s), Some(u));
    }

    #[test]
    fn timestamp_recovered() {
        let ts = 1_700_000_000_000u64; // a realistic ms epoch
        let u = Ulid::from_parts(ts, 12345);
        assert_eq!(u.timestamp_ms(), ts);
        assert_eq!(u.randomness(), 12345);
    }

    #[test]
    fn ids_sort_by_time_as_strings() {
        let mut g = UlidGenerator::new(42);
        let a = g.generate(1000).to_canonical();
        let b = g.generate(2000).to_canonical();
        let c = g.generate(3000).to_canonical();
        // lexical order of the strings matches chronological order
        assert!(a < b && b < c, "{a} {b} {c}");
    }

    #[test]
    fn monotonic_within_same_millisecond() {
        let mut g = UlidGenerator::new(7);
        let a = g.generate(5000);
        let b = g.generate(5000);
        let c = g.generate(5000);
        // same timestamp, but each strictly greater (incremented randomness)
        assert!(a < b && b < c);
        assert_eq!(a.timestamp_ms(), b.timestamp_ms());
        assert_eq!(b.randomness(), a.randomness() + 1);
    }

    #[test]
    fn deterministic_for_seed() {
        let mut a = UlidGenerator::new(99);
        let mut b = UlidGenerator::new(99);
        for t in [1u64, 2, 3, 3, 4] {
            assert_eq!(a.generate(t), b.generate(t));
        }
    }

    #[test]
    fn parse_is_case_insensitive_and_rejects_bad() {
        let u = Ulid::from_parts(123, 456);
        let s = u.to_canonical();
        assert_eq!(Ulid::parse(&s.to_lowercase()), Some(u));
        assert_eq!(Ulid::parse("too short"), None);
        assert_eq!(Ulid::parse(&"!".repeat(26)), None); // invalid chars
    }

    #[test]
    fn crockford_ambiguous_chars_decode() {
        // I/L → 1, O → 0 ; build a string then mangle ambiguous chars
        let u = Ulid::from_parts(1, 1);
        let canonical = u.to_canonical();
        // replacing a '1' with 'I' or 'l' must decode to the same value
        let with_i = canonical.replacen('1', "I", 1);
        if with_i != canonical {
            assert_eq!(Ulid::parse(&with_i), Some(u));
        }
    }

    #[test]
    fn randomness_fits_80_bits() {
        let mut g = UlidGenerator::new(1);
        for t in 0..100 {
            let u = g.generate(t);
            assert!(u.randomness() < (1u128 << 80));
        }
    }

    #[test]
    fn display_matches_canonical() {
        let u = Ulid::from_parts(42, 42);
        assert_eq!(format!("{u}"), u.to_canonical());
    }

    #[test]
    fn serde_round_trip() {
        let g = UlidGenerator::new(5);
        let j = serde_json::to_string(&g).unwrap();
        assert_eq!(serde_json::from_str::<UlidGenerator>(&j).unwrap(), g);
        let u = Ulid::from_parts(7, 7);
        let ju = serde_json::to_string(&u).unwrap();
        assert_eq!(serde_json::from_str::<Ulid>(&ju).unwrap(), u);
    }
}
