//! `sovereign-sse-parse` — read the streaming event format LLM APIs speak.
//!
//! Streaming completion APIs send their tokens as **Server-Sent Events**: a
//! sequence of `field: value` lines, with events separated by a blank line, e.g.
//!
//! ```text
//! data: {"delta":"Hel"}
//!
//! data: {"delta":"lo"}
//!
//! data: [DONE]
//! ```
//!
//! The catch is that the bytes arrive in arbitrary chunks — an event can be split
//! across two network reads, or several events can land in one. This crate is a
//! stateful parser you feed chunks to: it buffers whatever is incomplete and
//! returns the events that are now whole. It implements the parts of the SSE spec
//! that matter here — the `event`, `data`, `id`, and `retry` fields, multiple
//! `data:` lines joined with `\n`, a leading space after the colon stripped,
//! comment lines (starting with `:`) ignored, and a blank line dispatching the
//! accumulated event.
//!
//! [`SseParser::push`] takes a chunk and returns the completed [`SseEvent`]s;
//! [`SseParser::finish`] flushes any final event not terminated by a blank line.
//! [`SseEvent::is_done`] recognises the common `[DONE]` sentinel.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the sse-parse surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A parsed Server-Sent Event.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct SseEvent {
    /// The `event:` type, if any (defaults to `message` semantically when absent).
    pub event: Option<String>,
    /// The `data:` payload (multiple data lines joined by `\n`).
    pub data: String,
    /// The `id:` field, if any.
    pub id: Option<String>,
    /// The `retry:` reconnection time in milliseconds, if any and numeric.
    pub retry: Option<u64>,
}

impl SseEvent {
    /// Whether this event's data is the conventional end-of-stream sentinel
    /// `[DONE]` (trimmed).
    pub fn is_done(&self) -> bool {
        self.data.trim() == "[DONE]"
    }

    /// Whether the event carries no fields at all (would not be dispatched).
    fn is_empty(&self) -> bool {
        self.event.is_none() && self.data.is_empty() && self.id.is_none() && self.retry.is_none()
    }
}

/// A stateful SSE parser that buffers partial input across chunks.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SseParser {
    /// bytes received but not yet forming complete lines/events.
    buffer: String,
    /// the event currently being accumulated (fields seen since last blank line).
    current: SseEvent,
    /// whether any field has been added to `current` since the last dispatch.
    have_fields: bool,
}

impl SseParser {
    /// A fresh parser.
    pub fn new() -> Self {
        Self::default()
    }

    /// Feed a chunk of the response; returns any events completed by it.
    pub fn push(&mut self, chunk: &str) -> Vec<SseEvent> {
        self.buffer.push_str(chunk);
        let mut events = Vec::new();

        // process complete lines (terminated by '\n'); keep the trailing partial.
        loop {
            let Some(nl) = self.buffer.find('\n') else {
                break;
            };
            // take the line without the '\n', trimming a trailing '\r' (CRLF).
            let mut line = self.buffer[..nl].to_string();
            if line.ends_with('\r') {
                line.pop();
            }
            self.buffer.drain(..=nl);

            if line.is_empty() {
                // blank line → dispatch the accumulated event, if any.
                if self.have_fields && !self.current.is_empty() {
                    events.push(std::mem::take(&mut self.current));
                }
                self.current = SseEvent::default();
                self.have_fields = false;
            } else {
                self.consume_field(&line);
            }
        }
        events
    }

    /// Flush a final event that was not terminated by a blank line (e.g. the
    /// stream closed right after the last `data:` line). Returns it if present.
    pub fn finish(&mut self) -> Option<SseEvent> {
        // a trailing line without a newline is still a field to apply.
        if !self.buffer.is_empty() {
            let line = std::mem::take(&mut self.buffer);
            let line = line.strip_suffix('\r').unwrap_or(&line).to_string();
            if !line.is_empty() {
                self.consume_field(&line);
            }
        }
        if self.have_fields && !self.current.is_empty() {
            self.have_fields = false;
            Some(std::mem::take(&mut self.current))
        } else {
            None
        }
    }

    /// Parse one `field: value` (or comment) line into the current event.
    fn consume_field(&mut self, line: &str) {
        if line.starts_with(':') {
            return; // comment line, ignored
        }
        let (field, value) = match line.split_once(':') {
            Some((f, v)) => (f, v.strip_prefix(' ').unwrap_or(v)),
            None => (line, ""), // a field name with no colon → empty value
        };
        match field {
            "event" => {
                self.current.event = Some(value.to_string());
                self.have_fields = true;
            }
            "data" => {
                if !self.current.data.is_empty() {
                    self.current.data.push('\n');
                }
                self.current.data.push_str(value);
                self.have_fields = true;
            }
            "id" => {
                self.current.id = Some(value.to_string());
                self.have_fields = true;
            }
            "retry" => {
                if let Ok(ms) = value.trim().parse::<u64>() {
                    self.current.retry = Some(ms);
                    self.have_fields = true;
                }
            }
            _ => {} // unknown field: ignore per spec
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_event() {
        let mut p = SseParser::new();
        let evs = p.push("data: hello\n\n");
        assert_eq!(evs.len(), 1);
        assert_eq!(evs[0].data, "hello");
    }

    #[test]
    fn multiple_events_in_one_chunk() {
        let mut p = SseParser::new();
        let evs = p.push("data: a\n\ndata: b\n\ndata: c\n\n");
        let datas: Vec<&str> = evs.iter().map(|e| e.data.as_str()).collect();
        assert_eq!(datas, vec!["a", "b", "c"]);
    }

    #[test]
    fn event_split_across_chunks() {
        let mut p = SseParser::new();
        assert!(p.push("data: par").is_empty()); // partial, nothing yet
        assert!(p.push("tial mes").is_empty());
        let evs = p.push("sage\n\n");
        assert_eq!(evs.len(), 1);
        assert_eq!(evs[0].data, "partial message");
    }

    #[test]
    fn multiline_data_joined_with_newline() {
        let mut p = SseParser::new();
        let evs = p.push("data: line one\ndata: line two\n\n");
        assert_eq!(evs[0].data, "line one\nline two");
    }

    #[test]
    fn all_fields_parsed() {
        let mut p = SseParser::new();
        let evs = p.push("event: update\nid: 42\nretry: 3000\ndata: payload\n\n");
        let e = &evs[0];
        assert_eq!(e.event.as_deref(), Some("update"));
        assert_eq!(e.id.as_deref(), Some("42"));
        assert_eq!(e.retry, Some(3000));
        assert_eq!(e.data, "payload");
    }

    #[test]
    fn comments_and_unknown_fields_ignored() {
        let mut p = SseParser::new();
        let evs = p.push(": this is a comment\nfoo: bar\ndata: real\n\n");
        assert_eq!(evs.len(), 1);
        assert_eq!(evs[0].data, "real");
        assert_eq!(evs[0].event, None);
    }

    #[test]
    fn crlf_line_endings() {
        let mut p = SseParser::new();
        let evs = p.push("data: windows\r\n\r\n");
        assert_eq!(evs.len(), 1);
        assert_eq!(evs[0].data, "windows");
    }

    #[test]
    fn done_sentinel_recognized() {
        let mut p = SseParser::new();
        let evs = p.push("data: [DONE]\n\n");
        assert!(evs[0].is_done());
        let mut p2 = SseParser::new();
        let evs2 = p2.push("data: not done\n\n");
        assert!(!evs2[0].is_done());
    }

    #[test]
    fn finish_flushes_unterminated_event() {
        let mut p = SseParser::new();
        // stream ends without a trailing blank line
        assert!(p.push("data: tail").is_empty());
        let last = p.finish().unwrap();
        assert_eq!(last.data, "tail");
        // a second finish yields nothing
        assert!(p.finish().is_none());
    }

    #[test]
    fn realistic_llm_stream() {
        let mut p = SseParser::new();
        let mut text = String::new();
        // simulate token deltas arriving in awkward chunks
        for chunk in [
            "data: {\"delta\":\"Hel\"}\n\nda",
            "ta: {\"delta\":\"lo\"}\n\n",
            "data: {\"delta\":\"!\"}\n\ndata: [DONE]\n\n",
        ] {
            for ev in p.push(chunk) {
                if ev.is_done() {
                    break;
                }
                // pull the delta out of the JSON-ish payload (toy extraction)
                if let Some(start) = ev.data.find("\"delta\":\"") {
                    let rest = &ev.data[start + 9..];
                    if let Some(end) = rest.find('"') {
                        text.push_str(&rest[..end]);
                    }
                }
            }
        }
        assert_eq!(text, "Hello!");
    }

    #[test]
    fn serde_round_trip() {
        let p = SseParser::new();
        let j = serde_json::to_string(&p).unwrap();
        let _back: SseParser = serde_json::from_str(&j).unwrap();
        let e = SseEvent {
            event: Some("x".into()),
            data: "y".into(),
            id: None,
            retry: Some(5),
        };
        let je = serde_json::to_string(&e).unwrap();
        assert_eq!(serde_json::from_str::<SseEvent>(&je).unwrap(), e);
    }
}
