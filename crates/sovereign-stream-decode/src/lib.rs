//! `sovereign-stream-decode` — incremental UTF-8 decoding for token streaming.
//!
//! A byte-level tokenizer's tokens are byte sequences, and a single emitted
//! token can carry only *part* of a multi-byte UTF-8 character — the other
//! bytes arrive with the next token. A streaming runtime that decodes each
//! token in isolation would therefore emit broken/replacement characters at
//! token boundaries. This crate fixes that: feed it the bytes as they come,
//! and it emits the longest valid-UTF-8 prefix immediately while **holding
//! back any trailing incomplete multi-byte sequence** until the continuation
//! bytes arrive.
//!
//! The invariant — pinned as a test — is that concatenating the streamed
//! output across *any* chunk boundaries equals decoding the whole byte
//! sequence at once. Genuinely invalid bytes (not just incomplete) are emitted
//! immediately as the replacement character, so the stream never stalls.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the stream-decode surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Expected total byte length of a UTF-8 sequence given its lead byte.
/// Returns 1 for ASCII, 2–4 for multi-byte leads, and 0 for a continuation
/// byte or an invalid lead.
fn utf8_len(lead: u8) -> usize {
    match lead {
        0x00..=0x7F => 1,
        0xC0..=0xDF => 2,
        0xE0..=0xEF => 3,
        0xF0..=0xF7 => 4,
        _ => 0, // continuation byte (0x80..=0xBF) or invalid (0xF8..)
    }
}

fn is_continuation(b: u8) -> bool {
    (0x80..=0xBF).contains(&b)
}

/// Length of the trailing bytes that form an *incomplete* (but so-far-valid)
/// multi-byte UTF-8 sequence — bytes that should be held back until their
/// continuation arrives. Returns 0 if the tail is complete or invalid.
fn incomplete_tail_len(b: &[u8]) -> usize {
    let n = b.len();
    let mut conts = 0usize;
    let mut i = n;
    while i > 0 {
        i -= 1;
        let byte = b[i];
        if is_continuation(byte) {
            conts += 1;
            if conts > 3 {
                return 0; // more continuations than any lead allows → malformed
            }
            continue;
        }
        // `byte` is a lead (or ASCII, or an invalid lead)
        let expected = utf8_len(byte);
        let have = n - i; // = conts + 1
        if expected >= 2 && have < expected {
            return have; // an incomplete multi-byte sequence at the tail
        }
        return 0; // complete sequence, ASCII, or malformed lead → emit now
    }
    0
}

/// An incremental UTF-8 byte-stream decoder.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Utf8Stream {
    /// Buffered trailing bytes of an incomplete multi-byte sequence.
    buf: Vec<u8>,
}

impl Utf8Stream {
    /// A fresh, empty stream.
    pub fn new() -> Self {
        Self::default()
    }

    /// Number of bytes currently held back (an incomplete sequence).
    pub fn pending(&self) -> usize {
        self.buf.len()
    }

    /// Feed more bytes; return the text that is now complete. Any incomplete
    /// trailing multi-byte sequence is retained for the next call.
    pub fn push(&mut self, bytes: &[u8]) -> String {
        self.buf.extend_from_slice(bytes);
        let tail = incomplete_tail_len(&self.buf);
        let split = self.buf.len() - tail;
        // emit the complete prefix (lossy: genuinely invalid bytes → U+FFFD)
        let emitted = String::from_utf8_lossy(&self.buf[..split]).into_owned();
        self.buf.drain(..split);
        emitted
    }

    /// Flush any held bytes (lossy if they remain incomplete/invalid) and reset.
    pub fn finish(&mut self) -> String {
        let out = String::from_utf8_lossy(&self.buf).into_owned();
        self.buf.clear();
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ascii_passes_through_immediately() {
        let mut s = Utf8Stream::new();
        assert_eq!(s.push(b"hello"), "hello");
        assert_eq!(s.pending(), 0);
    }

    #[test]
    fn holds_back_split_multibyte_until_complete() {
        // 'é' is 0xC3 0xA9. Deliver the lead byte alone, then the continuation.
        let mut s = Utf8Stream::new();
        let out1 = s.push(&[0xC3]);
        assert_eq!(out1, ""); // incomplete → nothing emitted
        assert_eq!(s.pending(), 1);
        let out2 = s.push(&[0xA9]);
        assert_eq!(out2, "é");
        assert_eq!(s.pending(), 0);
    }

    #[test]
    fn emits_prefix_and_holds_incomplete_tail() {
        // "aé" delivered as [a, 0xC3] then [0xA9]
        let mut s = Utf8Stream::new();
        assert_eq!(s.push(&[b'a', 0xC3]), "a"); // emit 'a', hold 0xC3
        assert_eq!(s.pending(), 1);
        assert_eq!(s.push(&[0xA9]), "é");
    }

    #[test]
    fn four_byte_char_split_across_three_chunks() {
        // '🌍' = F0 9F 8C 8D
        let mut s = Utf8Stream::new();
        assert_eq!(s.push(&[0xF0, 0x9F]), "");
        assert_eq!(s.pending(), 2);
        assert_eq!(s.push(&[0x8C]), "");
        assert_eq!(s.pending(), 3);
        assert_eq!(s.push(&[0x8D]), "🌍");
        assert_eq!(s.pending(), 0);
    }

    #[test]
    fn streaming_equals_whole_decode_for_any_split() {
        let text = "héllo — 世界 🌍 ok";
        let bytes = text.as_bytes();
        // try every single split point
        for split in 0..=bytes.len() {
            let mut s = Utf8Stream::new();
            let mut out = String::new();
            out.push_str(&s.push(&bytes[..split]));
            out.push_str(&s.push(&bytes[split..]));
            out.push_str(&s.finish());
            assert_eq!(out, text, "split at {split}");
        }
    }

    #[test]
    fn byte_at_a_time_equals_whole_decode() {
        let text = "café 世界 🌍";
        let mut s = Utf8Stream::new();
        let mut out = String::new();
        for &b in text.as_bytes() {
            out.push_str(&s.push(&[b]));
        }
        out.push_str(&s.finish());
        assert_eq!(out, text);
    }

    #[test]
    fn truly_invalid_bytes_are_emitted_not_stalled() {
        // 0xFF is never a valid UTF-8 byte → must not be held back forever.
        let mut s = Utf8Stream::new();
        let out = s.push(&[0xFF]);
        assert_eq!(s.pending(), 0);
        assert!(out.contains('\u{FFFD}'));
    }

    #[test]
    fn finish_flushes_incomplete_as_replacement() {
        let mut s = Utf8Stream::new();
        assert_eq!(s.push(&[0xC3]), ""); // held
        let flushed = s.finish();
        assert!(flushed.contains('\u{FFFD}'));
        assert_eq!(s.pending(), 0);
    }

    #[test]
    fn serde_round_trip() {
        let mut s = Utf8Stream::new();
        s.push(&[0xE4, 0xB8]); // 2 of 3 bytes of '中'
        let j = serde_json::to_string(&s).unwrap();
        let back: Utf8Stream = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
        assert_eq!(back.pending(), 2);
    }

    // Streaming a tokenizer's per-token bytes reconstructs the full decode.
    #[test]
    fn streams_tokenizer_output_without_splitting_chars() {
        use sovereign_tokenizer::Tokenizer;
        let tok = Tokenizer::default(); // byte-level: each token is one byte
        let text = "世界🌍 hi";
        let ids = tok.encode(text);
        let mut s = Utf8Stream::new();
        let mut out = String::new();
        for &id in &ids {
            let bytes = tok.token_bytes(id).unwrap();
            out.push_str(&s.push(bytes));
        }
        out.push_str(&s.finish());
        assert_eq!(out, text);
        assert_eq!(out, tok.decode(&ids).unwrap());
    }
}
