//! `sovereign-cockpit-linkify` — detect spans in text.
//!
//! scan(text) emits ordered, non-overlapping Spans for:
//! - URL: starts with `http://` or `https://`, runs until first
//!   whitespace or one of `<>()`.
//! - Mention: `@` followed by [A-Za-z0-9_]+ (>=1 char).
//! - Hashtag: `#` followed by [A-Za-z0-9_]+ (>=1 char).
//! Non-matched ranges are emitted as Span::Text.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Span kind.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind", content = "value")]
pub enum Span {
    /// Plain text.
    Text(String),
    /// URL.
    Url(String),
    /// @mention (without the @).
    Mention(String),
    /// #hashtag (without the #).
    Hashtag(String),
}

/// State (versioned).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Linkify {
    /// Schema version.
    pub schema_version: String,
    /// Last scanned input.
    pub last_input: String,
    /// Last spans.
    pub last_spans: Vec<Span>,
    /// Scans performed.
    pub scans: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LinkifyError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

fn is_word_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

fn url_break(c: char) -> bool {
    c.is_whitespace() || c == '<' || c == '>' || c == '(' || c == ')'
}

/// Scan and emit Spans.
pub fn scan(text: &str) -> Vec<Span> {
    let chars: Vec<char> = text.chars().collect();
    let mut spans = Vec::new();
    let mut text_buf = String::new();
    let mut i = 0usize;
    let n = chars.len();
    while i < n {
        // Try URL.
        if chars[i] == 'h'
            && (chars[i..].iter().take(7).collect::<String>() == "http://"
                || chars[i..].iter().take(8).collect::<String>() == "https://")
        {
            if !text_buf.is_empty() {
                spans.push(Span::Text(std::mem::take(&mut text_buf)));
            }
            let mut j = i;
            while j < n && !url_break(chars[j]) {
                j += 1;
            }
            spans.push(Span::Url(chars[i..j].iter().collect()));
            i = j;
            continue;
        }
        // Try @mention.
        if chars[i] == '@' && i + 1 < n && is_word_char(chars[i + 1]) {
            let mut j = i + 1;
            while j < n && is_word_char(chars[j]) {
                j += 1;
            }
            if !text_buf.is_empty() {
                spans.push(Span::Text(std::mem::take(&mut text_buf)));
            }
            spans.push(Span::Mention(chars[i + 1..j].iter().collect()));
            i = j;
            continue;
        }
        // Try #hashtag.
        if chars[i] == '#' && i + 1 < n && is_word_char(chars[i + 1]) {
            let mut j = i + 1;
            while j < n && is_word_char(chars[j]) {
                j += 1;
            }
            if !text_buf.is_empty() {
                spans.push(Span::Text(std::mem::take(&mut text_buf)));
            }
            spans.push(Span::Hashtag(chars[i + 1..j].iter().collect()));
            i = j;
            continue;
        }
        text_buf.push(chars[i]);
        i += 1;
    }
    if !text_buf.is_empty() {
        spans.push(Span::Text(text_buf));
    }
    spans
}

impl Linkify {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            last_input: String::new(),
            last_spans: Vec::new(),
            scans: 0,
        }
    }

    /// Scan + store.
    pub fn scan_and_store(&mut self, text: &str) -> &[Span] {
        self.last_input = text.into();
        self.last_spans = scan(text);
        self.scans = self.scans.saturating_add(1);
        &self.last_spans
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LinkifyError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LinkifyError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for Linkify {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plain_text_passthrough() {
        let s = scan("hello world");
        assert_eq!(s, vec![Span::Text("hello world".into())]);
    }

    #[test]
    fn detects_url() {
        let s = scan("see https://example.com/foo for info");
        assert_eq!(
            s,
            vec![
                Span::Text("see ".into()),
                Span::Url("https://example.com/foo".into()),
                Span::Text(" for info".into()),
            ]
        );
    }

    #[test]
    fn detects_mention() {
        let s = scan("hi @alice!");
        assert_eq!(
            s,
            vec![
                Span::Text("hi ".into()),
                Span::Mention("alice".into()),
                Span::Text("!".into()),
            ]
        );
    }

    #[test]
    fn detects_hashtag() {
        let s = scan("#rust is great");
        assert_eq!(
            s,
            vec![Span::Hashtag("rust".into()), Span::Text(" is great".into()),]
        );
    }

    #[test]
    fn at_without_word_is_text() {
        let s = scan("@ alone");
        assert_eq!(s, vec![Span::Text("@ alone".into())]);
    }

    #[test]
    fn http_only_detected() {
        let s = scan("http://x.test/path");
        assert_eq!(s, vec![Span::Url("http://x.test/path".into())]);
    }

    #[test]
    fn url_break_on_paren() {
        let s = scan("see (https://x.test) here");
        assert_eq!(
            s,
            vec![
                Span::Text("see (".into()),
                Span::Url("https://x.test".into()),
                Span::Text(") here".into()),
            ]
        );
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = Linkify::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            LinkifyError::SchemaMismatch
        ));
    }

    #[test]
    fn linkify_serde_roundtrip() {
        let mut l = Linkify::new();
        l.scan_and_store("hi @bob check https://x.test #rust");
        let j = serde_json::to_string(&l).unwrap();
        let back: Linkify = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
