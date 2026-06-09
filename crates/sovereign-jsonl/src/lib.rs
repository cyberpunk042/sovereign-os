//! `sovereign-jsonl` — one JSON value per line, read and written cleanly.
//!
//! JSON Lines is the workhorse format for datasets and structured logs: each line
//! is an independent JSON value, so a file streams record-by-record without
//! loading the whole thing, and new records append without rewriting. This crate
//! handles the format's practical edge cases.
//!
//! Reading is **tolerant**: blank lines are skipped, and a malformed line is
//! reported (with its number) rather than aborting the whole file — [`parse`]
//! returns only the good records plus the indices that failed, so one bad line in
//! a million-line dataset doesn't lose the rest. [`parse_strict`] errors on the
//! first bad line when you need all-or-nothing.
//!
//! Writing is the inverse: [`to_jsonl`] serializes a slice of values into the
//! newline-delimited form (no trailing newline issues — exactly one `\n` between
//! records).
//!
//! For live streams there is [`JsonlReader`], which you feed byte chunks: it
//! buffers an incomplete trailing line across reads and yields the values that are
//! now complete, the same pattern a network reader needs.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde_json::Value;

/// Schema version of the jsonl surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Parse JSONL text tolerantly: returns the successfully-parsed values and the
/// (0-based) line numbers that failed to parse. Blank/whitespace-only lines are
/// skipped and not counted as errors.
pub fn parse(text: &str) -> (Vec<Value>, Vec<usize>) {
    let mut values = Vec::new();
    let mut errors = Vec::new();
    for (i, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        match serde_json::from_str::<Value>(line) {
            Ok(v) => values.push(v),
            Err(_) => errors.push(i),
        }
    }
    (values, errors)
}

/// Parse JSONL strictly: returns an error on the first malformed line (blank lines
/// are still skipped).
pub fn parse_strict(text: &str) -> Result<Vec<Value>, JsonlError> {
    let mut values = Vec::new();
    for (i, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        match serde_json::from_str::<Value>(line) {
            Ok(v) => values.push(v),
            Err(e) => {
                return Err(JsonlError {
                    line: i,
                    message: e.to_string(),
                });
            }
        }
    }
    Ok(values)
}

/// A parse error tied to a line number.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JsonlError {
    /// The 0-based line number that failed.
    pub line: usize,
    /// The underlying parser message.
    pub message: String,
}

impl std::fmt::Display for JsonlError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "JSONL parse error on line {}: {}",
            self.line, self.message
        )
    }
}

impl std::error::Error for JsonlError {}

/// Serialize values into JSONL: one compact JSON value per line, separated by
/// `\n`, with a trailing newline.
pub fn to_jsonl(values: &[Value]) -> String {
    let mut out = String::new();
    for v in values {
        // serde_json::to_string never produces an interior newline for a Value.
        out.push_str(&serde_json::to_string(v).unwrap_or_else(|_| "null".to_string()));
        out.push('\n');
    }
    out
}

/// A streaming JSONL reader that buffers a partial trailing line across chunks.
#[derive(Debug, Clone, Default)]
pub struct JsonlReader {
    buffer: String,
}

impl JsonlReader {
    /// A fresh reader.
    pub fn new() -> Self {
        Self::default()
    }

    /// Feed a chunk; returns the values for any lines completed by it (a line is
    /// complete once its terminating `\n` has arrived). Malformed completed lines
    /// are skipped silently — use [`parse`] if you need the error positions.
    pub fn push(&mut self, chunk: &str) -> Vec<Value> {
        self.buffer.push_str(chunk);
        let mut out = Vec::new();
        while let Some(nl) = self.buffer.find('\n') {
            let line: String = self.buffer[..nl].to_string();
            self.buffer.drain(..=nl);
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(v) = serde_json::from_str::<Value>(trimmed) {
                out.push(v);
            }
        }
        out
    }

    /// Flush a final line that arrived without a trailing newline. Returns it if it
    /// parses, else `None`.
    pub fn finish(&mut self) -> Option<Value> {
        let line = std::mem::take(&mut self.buffer);
        let trimmed = line.trim();
        if trimmed.is_empty() {
            return None;
        }
        serde_json::from_str::<Value>(trimmed).ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parse_well_formed() {
        let text = "{\"a\":1}\n{\"b\":2}\n[1,2,3]";
        let (vals, errs) = parse(text);
        assert!(errs.is_empty());
        assert_eq!(vals, vec![json!({"a":1}), json!({"b":2}), json!([1, 2, 3])]);
    }

    #[test]
    fn skips_blank_lines() {
        let text = "{\"a\":1}\n\n   \n{\"b\":2}\n";
        let (vals, errs) = parse(text);
        assert!(errs.is_empty());
        assert_eq!(vals.len(), 2);
    }

    #[test]
    fn reports_bad_lines_but_keeps_good() {
        let text = "{\"a\":1}\nnot json\n{\"b\":2}\n{oops}";
        let (vals, errs) = parse(text);
        assert_eq!(vals, vec![json!({"a":1}), json!({"b":2})]);
        assert_eq!(errs, vec![1, 3]);
    }

    #[test]
    fn strict_errors_on_first_bad_line() {
        let text = "{\"a\":1}\nbroken";
        let e = parse_strict(text).unwrap_err();
        assert_eq!(e.line, 1);
    }

    #[test]
    fn round_trip() {
        let vals = vec![json!({"id": 1, "text": "hi"}), json!([true, null])];
        let text = to_jsonl(&vals);
        let (parsed, errs) = parse(&text);
        assert!(errs.is_empty());
        assert_eq!(parsed, vals);
        // exactly one newline per record, with a trailing one
        assert_eq!(text.matches('\n').count(), 2);
    }

    #[test]
    fn streaming_across_chunks() {
        let mut r = JsonlReader::new();
        assert!(r.push("{\"a\":").is_empty()); // partial line, nothing yet
        let v = r.push("1}\n{\"b\":2}\n");
        assert_eq!(v, vec![json!({"a":1}), json!({"b":2})]);
    }

    #[test]
    fn streaming_finish_flushes_last_line() {
        let mut r = JsonlReader::new();
        // one complete line, then a final line with no trailing newline.
        let done = r.push("{\"x\":1}\n{\"last\":true}");
        assert_eq!(done, vec![json!({"x":1})]);
        assert_eq!(r.finish(), Some(json!({"last":true})));
        // a second finish has nothing left
        assert_eq!(r.finish(), None);
    }

    #[test]
    fn streaming_skips_malformed_lines() {
        let mut r = JsonlReader::new();
        let v = r.push("good: nope\n{\"ok\":1}\n");
        assert_eq!(v, vec![json!({"ok":1})]);
    }

    #[test]
    fn empty_inputs() {
        assert_eq!(parse(""), (Vec::new(), Vec::new()));
        assert_eq!(to_jsonl(&[]), "");
        let mut r = JsonlReader::new();
        assert!(r.push("").is_empty());
        assert_eq!(r.finish(), None);
    }
}
