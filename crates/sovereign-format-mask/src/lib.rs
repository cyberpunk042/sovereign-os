//! `sovereign-format-mask` — format-constrained decoding for byte models.
//!
//! An allow-list constrains *which tokens* may be emitted, but not *where*.
//! This crate adds position: a [`Pattern`] is a sequence of character-class
//! [`Slot`]s — `DDD-DDDD` for a code, `YYYY-MM-DD` for a date — and given how
//! many bytes have been generated, it reports exactly the byte-tokens allowed
//! at that position. Feed those to the logit mask each step and the model can
//! only produce output matching the format; when the pattern is exhausted,
//! generation is complete.
//!
//! Because a byte-level tokenizer's token ids *are* byte values, the allowed
//! token set is literally the set of bytes the slot's class accepts. The
//! constraint is stateful in the cheapest possible way — it depends only on
//! the output length so far — which makes it deterministic and trivial to
//! drive from a decode loop.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the format-mask surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A character class: the set of bytes allowed at one position.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Slot {
    /// ASCII digits `0-9`.
    Digit,
    /// ASCII lowercase `a-z`.
    Lower,
    /// ASCII uppercase `A-Z`.
    Upper,
    /// ASCII letters `a-zA-Z`.
    Alpha,
    /// ASCII letters or digits.
    Alnum,
    /// Exactly this byte (a literal in the format).
    Literal(u8),
    /// Any one of these bytes.
    AnyOf(Vec<u8>),
}

impl Slot {
    /// Whether `b` is permitted by this class.
    pub fn accepts(&self, b: u8) -> bool {
        match self {
            Slot::Digit => b.is_ascii_digit(),
            Slot::Lower => b.is_ascii_lowercase(),
            Slot::Upper => b.is_ascii_uppercase(),
            Slot::Alpha => b.is_ascii_alphabetic(),
            Slot::Alnum => b.is_ascii_alphanumeric(),
            Slot::Literal(x) => b == *x,
            Slot::AnyOf(set) => set.contains(&b),
        }
    }

    /// The bytes this class accepts, ascending.
    pub fn allowed_bytes(&self) -> Vec<u8> {
        (0u8..=255).filter(|&b| self.accepts(b)).collect()
    }
}

/// A fixed-length positional format: one [`Slot`] per output byte.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Pattern {
    /// The slots, one per position.
    pub slots: Vec<Slot>,
}

impl Pattern {
    /// Build a pattern from slots.
    pub fn new(slots: Vec<Slot>) -> Self {
        Self { slots }
    }

    /// Total length the pattern produces.
    pub fn len(&self) -> usize {
        self.slots.len()
    }

    /// Whether the pattern is empty.
    pub fn is_empty(&self) -> bool {
        self.slots.is_empty()
    }

    /// Whether `generated_len` bytes complete the pattern.
    pub fn is_complete(&self, generated_len: usize) -> bool {
        generated_len >= self.slots.len()
    }

    /// The token ids (= byte values) allowed at output position `pos`. Returns
    /// `None` when `pos` is past the end (generation should stop).
    pub fn allowed_tokens_at(&self, pos: usize) -> Option<Vec<usize>> {
        self.slots
            .get(pos)
            .map(|s| s.allowed_bytes().into_iter().map(usize::from).collect())
    }

    /// Whether `output` (bytes) conforms to the pattern so far.
    pub fn matches(&self, output: &[u8]) -> bool {
        output.len() <= self.slots.len()
            && output.iter().zip(&self.slots).all(|(&b, s)| s.accepts(b))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slot_classes_accept_the_right_bytes() {
        assert!(Slot::Digit.accepts(b'5') && !Slot::Digit.accepts(b'a'));
        assert!(Slot::Lower.accepts(b'a') && !Slot::Lower.accepts(b'A'));
        assert!(Slot::Upper.accepts(b'Z') && !Slot::Upper.accepts(b'z'));
        assert!(Slot::Alpha.accepts(b'q') && Slot::Alpha.accepts(b'Q'));
        assert!(Slot::Alnum.accepts(b'7') && Slot::Alnum.accepts(b'k'));
        assert!(Slot::Literal(b'-').accepts(b'-') && !Slot::Literal(b'-').accepts(b'_'));
        let any = Slot::AnyOf(vec![b'x', b'y']);
        assert!(any.accepts(b'x') && !any.accepts(b'z'));
    }

    #[test]
    fn digit_slot_allows_exactly_ten_tokens() {
        let tokens = Slot::Digit.allowed_bytes();
        assert_eq!(tokens.len(), 10);
        assert_eq!(tokens[0], b'0');
        assert_eq!(tokens[9], b'9');
    }

    #[test]
    fn allowed_tokens_track_position() {
        // pattern: DD-DD  (digit digit literal('-') digit digit)
        let p = Pattern::new(vec![
            Slot::Digit,
            Slot::Digit,
            Slot::Literal(b'-'),
            Slot::Digit,
            Slot::Digit,
        ]);
        assert_eq!(p.len(), 5);
        // position 0 and 1: digits
        assert_eq!(p.allowed_tokens_at(0).unwrap().len(), 10);
        // position 2: only '-'
        assert_eq!(p.allowed_tokens_at(2).unwrap(), vec![usize::from(b'-')]);
        // past the end: None
        assert!(p.allowed_tokens_at(5).is_none());
        assert!(p.is_complete(5) && !p.is_complete(4));
    }

    #[test]
    fn matches_validates_conformance() {
        let p = Pattern::new(vec![Slot::Upper, Slot::Digit, Slot::Digit]);
        assert!(p.matches(b"A12"));
        assert!(p.matches(b"A1")); // prefix is fine
        assert!(!p.matches(b"a12")); // lowercase fails slot 0
        assert!(!p.matches(b"A123")); // too long
    }

    #[test]
    fn serde_round_trip() {
        let p = Pattern::new(vec![Slot::Alpha, Slot::AnyOf(vec![b'@']), Slot::Digit]);
        let j = serde_json::to_string(&p).unwrap();
        let back: Pattern = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }

    // Integration: drive a sampler through the pattern via the logit mask, then
    // verify the produced output conforms to the format.
    #[test]
    fn constrained_generation_matches_the_format() {
        use sovereign_logit_mask::LogitMask;
        use sovereign_sampler::{Sampler, SamplerConfig};

        // format: Upper Digit Digit Lower
        let p = Pattern::new(vec![Slot::Upper, Slot::Digit, Slot::Digit, Slot::Lower]);
        let sampler = Sampler::new(SamplerConfig::default());
        // arbitrary "model logits" over a 256-byte vocab
        let logits: Vec<f32> = (0..256).map(|i| ((i as f32) * 0.05).sin()).collect();

        let mut out = Vec::new();
        let mut pos = 0;
        while let Some(allowed) = p.allowed_tokens_at(pos) {
            let mask = LogitMask::new().allow_only(allowed);
            let masked = mask.masked(&logits);
            let tok = sampler.sample_seeded(&masked, &[], pos as u64 + 1).unwrap();
            out.push(tok as u8);
            pos += 1;
        }
        assert_eq!(out.len(), 4);
        assert!(p.matches(&out), "{:?}", String::from_utf8_lossy(&out));
        assert!(p.is_complete(out.len()));
    }
}
