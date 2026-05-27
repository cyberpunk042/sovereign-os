//! `sovereign-cockpit-auto-link` — autolink URLs in plain text.
//!
//! tokenize(text) returns Vec<Segment>: Plain runs interleaved
//! with Link{url} segments. A "URL" starts at "http://" or
//! "https://" and runs until a whitespace or a trailing
//! punctuation char in [.,;:!?)\]>"']*. Trailing punctuation is
//! intentionally excluded from the link.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Segment.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Segment {
    /// Plain text.
    Plain {
        /// text.
        text: String,
    },
    /// Detected link.
    Link {
        /// URL.
        url: String,
    },
}

/// Errors.
#[derive(Debug, Error)]
pub enum LinkError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

fn is_url_char(c: char) -> bool {
    // Conservative URL char set; trailing punct trimmed separately.
    !c.is_whitespace()
}

fn trim_trailing_punct(s: &str) -> &str {
    let bytes = s.as_bytes();
    let mut end = s.len();
    while end > 0 {
        let c = bytes[end - 1];
        if matches!(
            c,
            b'.' | b',' | b';' | b':' | b'!' | b'?' | b')' | b']' | b'>' | b'"' | b'\''
        ) {
            end -= 1;
        } else {
            break;
        }
    }
    &s[..end]
}

/// Tokenize.
pub fn tokenize(text: &str) -> Vec<Segment> {
    let mut out = Vec::new();
    let mut buf = String::new();
    let mut i = 0;
    let bytes = text.as_bytes();
    while i < bytes.len() {
        let rest = &text[i..];
        if rest.starts_with("http://") || rest.starts_with("https://") {
            // Find run end.
            let chars: Vec<char> = rest.chars().collect();
            let mut j = 0usize;
            let mut consumed_bytes = 0usize;
            for c in &chars {
                if !is_url_char(*c) {
                    break;
                }
                j += 1;
                consumed_bytes += c.len_utf8();
            }
            let _ = j;
            let raw = &rest[..consumed_bytes];
            let url = trim_trailing_punct(raw);
            if url.len() > "https://".len() {
                if !buf.is_empty() {
                    out.push(Segment::Plain {
                        text: std::mem::take(&mut buf),
                    });
                }
                out.push(Segment::Link { url: url.into() });
                // Carry over trailing trimmed punct into buf.
                let trimmed_off = raw.len() - url.len();
                if trimmed_off > 0 {
                    buf.push_str(&raw[url.len()..]);
                }
                i += consumed_bytes;
                continue;
            }
        }
        // Otherwise grab one char into buf.
        let c = text[i..].chars().next().unwrap();
        buf.push(c);
        i += c.len_utf8();
    }
    if !buf.is_empty() {
        out.push(Segment::Plain { text: buf });
    }
    out
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), LinkError> {
    if s != SCHEMA_VERSION {
        return Err(LinkError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_https_link() {
        let toks = tokenize("see https://example.com today");
        assert_eq!(
            toks,
            vec![
                Segment::Plain {
                    text: "see ".into()
                },
                Segment::Link {
                    url: "https://example.com".into()
                },
                Segment::Plain {
                    text: " today".into()
                },
            ]
        );
    }

    #[test]
    fn trailing_punct_excluded() {
        let toks = tokenize("visit https://example.com.");
        assert_eq!(
            toks,
            vec![
                Segment::Plain {
                    text: "visit ".into()
                },
                Segment::Link {
                    url: "https://example.com".into()
                },
                Segment::Plain { text: ".".into() },
            ]
        );
    }

    #[test]
    fn multiple_links() {
        let toks = tokenize("a https://x.com b http://y.com c");
        assert_eq!(
            toks.iter()
                .filter(|s| matches!(s, Segment::Link { .. }))
                .count(),
            2
        );
    }

    #[test]
    fn no_links_all_plain() {
        let toks = tokenize("just some words");
        assert_eq!(
            toks,
            vec![Segment::Plain {
                text: "just some words".into()
            }]
        );
    }

    #[test]
    fn naked_scheme_no_url() {
        // "https://" alone is too short (== prefix only).
        let toks = tokenize("https:// hello");
        assert_eq!(
            toks,
            vec![Segment::Plain {
                text: "https:// hello".into()
            }]
        );
    }

    #[test]
    fn link_at_start_and_end() {
        let toks = tokenize("https://x.com");
        assert_eq!(
            toks,
            vec![Segment::Link {
                url: "https://x.com".into()
            }]
        );
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            LinkError::SchemaMismatch
        ));
    }

    #[test]
    fn segment_serde_roundtrip() {
        let segs = vec![
            Segment::Plain { text: "p".into() },
            Segment::Link {
                url: "https://x".into(),
            },
        ];
        let j = serde_json::to_string(&segs).unwrap();
        let back: Vec<Segment> = serde_json::from_str(&j).unwrap();
        assert_eq!(segs, back);
    }
}
