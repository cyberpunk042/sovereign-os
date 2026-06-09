//! `sovereign-stop-sequence` — stop-sequence detection for generation control.
//!
//! A chat or instruction model should stop generating when it emits a known
//! marker — `"\nUser:"`, an end-of-turn token's text, a closing delimiter. This
//! crate is that boundary. In the simplest case [`StopSequences::cut`] trims a
//! completed reply at the earliest stop. For *streaming*, [`StreamStop`] scans
//! text as it arrives: it emits everything that cannot possibly be part of a
//! stop, holds back only the minimal trailing bytes that *might* begin one, and
//! reports the moment a stop completes — so a stop split across two token
//! chunks is still caught, and at most `max_len − 1` bytes are ever buffered.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the stop-sequence surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A set of stop strings.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct StopSequences {
    /// The stop strings (empty entries are ignored).
    seqs: Vec<String>,
}

impl StopSequences {
    /// An empty set (never stops).
    pub fn new() -> Self {
        Self::default()
    }

    /// Build from a list of stop strings (empty strings are dropped).
    pub fn from<I, S>(seqs: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        Self {
            seqs: seqs
                .into_iter()
                .map(Into::into)
                .filter(|s| !s.is_empty())
                .collect(),
        }
    }

    /// Whether any stop string is configured.
    pub fn is_empty(&self) -> bool {
        self.seqs.is_empty()
    }

    /// The longest stop string's byte length (0 if none).
    pub fn max_len(&self) -> usize {
        self.seqs.iter().map(|s| s.len()).max().unwrap_or(0)
    }

    /// Byte index where the earliest stop sequence begins in `text`, if any.
    pub fn first_stop(&self, text: &str) -> Option<usize> {
        self.seqs.iter().filter_map(|s| text.find(s.as_str())).min()
    }

    /// `text` truncated at the earliest stop (or the whole string if none).
    pub fn cut<'a>(&self, text: &'a str) -> &'a str {
        match self.first_stop(text) {
            Some(i) => &text[..i],
            None => text,
        }
    }
}

/// A streaming stop scanner: feed text chunks, get the safe-to-emit prefix, and
/// learn when a stop has completed.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StreamStop {
    stops: StopSequences,
    pending: String,
    stopped: bool,
}

/// What a [`StreamStop::push`] produced.
#[derive(Debug, Clone, PartialEq)]
pub struct StreamOut {
    /// Text safe to emit downstream now.
    pub text: String,
    /// Whether a stop sequence completed on this push (generation should end).
    pub stopped: bool,
}

impl StreamStop {
    /// A scanner for the given stop set.
    pub fn new(stops: StopSequences) -> Self {
        Self {
            stops,
            pending: String::new(),
            stopped: false,
        }
    }

    /// Whether a stop has already been hit (further pushes emit nothing).
    pub fn is_stopped(&self) -> bool {
        self.stopped
    }

    /// Feed a chunk; return the safe-to-emit text and whether a stop completed.
    pub fn push(&mut self, chunk: &str) -> StreamOut {
        if self.stopped {
            return StreamOut {
                text: String::new(),
                stopped: true,
            };
        }
        self.pending.push_str(chunk);

        if let Some(i) = self.stops.first_stop(&self.pending) {
            let text = self.pending[..i].to_string();
            self.pending.clear();
            self.stopped = true;
            return StreamOut {
                text,
                stopped: true,
            };
        }

        // No stop yet: hold back the last (max_len - 1) bytes, which could be
        // the start of a stop completed by a later chunk. Snap down to a char
        // boundary so we never split a character.
        let hold = self.stops.max_len().saturating_sub(1);
        let mut split = self.pending.len().saturating_sub(hold);
        while split > 0 && !self.pending.is_char_boundary(split) {
            split -= 1;
        }
        let text = self.pending[..split].to_string();
        self.pending.drain(..split);
        StreamOut {
            text,
            stopped: false,
        }
    }

    /// Flush any held text (call when generation ends without a stop).
    pub fn finish(&mut self) -> String {
        std::mem::take(&mut self.pending)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_stop_finds_earliest() {
        let s = StopSequences::from(["END", "User:"]);
        let text = "hello User: stuff END more";
        // "User:" at 6 is earlier than "END" at 18
        assert_eq!(s.first_stop(text), Some(6));
    }

    #[test]
    fn cut_truncates_at_stop() {
        let s = StopSequences::from(["\nUser:"]);
        assert_eq!(s.cut("reply text\nUser: next"), "reply text");
        assert_eq!(s.cut("no stop here"), "no stop here");
    }

    #[test]
    fn empty_set_never_stops() {
        let s = StopSequences::new();
        assert!(s.is_empty());
        assert_eq!(s.first_stop("anything"), None);
        assert_eq!(s.cut("anything"), "anything");
    }

    #[test]
    fn empty_strings_are_dropped() {
        let s = StopSequences::from(["", "x", ""]);
        assert_eq!(s.max_len(), 1);
        assert_eq!(s.first_stop("axb"), Some(1));
    }

    #[test]
    fn streaming_detects_a_clean_stop() {
        let mut s = StreamStop::new(StopSequences::from(["STOP"]));
        let out = s.push("abc STOP def");
        assert_eq!(out.text, "abc ");
        assert!(out.stopped);
        assert!(s.is_stopped());
        // further pushes emit nothing
        assert_eq!(s.push("more").text, "");
    }

    #[test]
    fn streaming_catches_a_stop_split_across_chunks() {
        let mut s = StreamStop::new(StopSequences::from(["STOP"]));
        let mut emitted = String::new();
        emitted.push_str(&s.push("ab ST").text); // holds "ST" (could start STOP)
        assert!(!s.is_stopped());
        let o2 = s.push("OP rest");
        emitted.push_str(&o2.text);
        assert!(o2.stopped);
        // everything before the stop was emitted, nothing after
        assert_eq!(emitted, "ab ");
    }

    #[test]
    fn streaming_without_stop_emits_everything_via_finish() {
        let mut s = StreamStop::new(StopSequences::from(["STOP"]));
        let mut out = String::new();
        out.push_str(&s.push("hello ").text);
        out.push_str(&s.push("world").text);
        out.push_str(&s.finish());
        assert_eq!(out, "hello world");
        assert!(!s.is_stopped());
    }

    #[test]
    fn streaming_holds_back_at_most_max_len_minus_one() {
        let stops = StopSequences::from(["ENDOFTURN"]); // len 9
        let mut s = StreamStop::new(stops);
        let _ = s.push("a long stream of text with no stop in it at all");
        // after a push with no stop, pending holds < max_len bytes
        assert!(s.pending.len() < 9);
    }

    #[test]
    fn streaming_preserves_utf8_boundaries() {
        // multi-byte chars must not be split by the hold-back logic
        let mut s = StreamStop::new(StopSequences::from(["STOP"]));
        let mut out = String::new();
        out.push_str(&s.push("héllo 世界").text);
        out.push_str(&s.push(" 🌍 done").text);
        out.push_str(&s.finish());
        assert_eq!(out, "héllo 世界 🌍 done");
    }

    #[test]
    fn serde_round_trip() {
        let s = StreamStop::new(StopSequences::from(["A", "BB"]));
        let j = serde_json::to_string(&s).unwrap();
        let back: StreamStop = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
