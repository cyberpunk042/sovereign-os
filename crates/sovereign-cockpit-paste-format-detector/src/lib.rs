//! `sovereign-cockpit-paste-format-detector` — classify pasted text.
//!
//! `detect(text)` returns a `PasteFormat`:
//!
//!   * `Url`        — single-token starting with `http://` / `https://`
//!     / `ftp://` / `mailto:`.
//!   * `Json`       — first non-whitespace char is `{` or `[` and
//!     the text contains at least one `:`.
//!   * `CodeBlock`  — wrapped in triple backticks ``` … ```.
//!   * `Markdown`   — at least one of: heading (`# `), bullet
//!     (`- ` / `* ` at start-of-line), or `[label](url)` link.
//!   * `Csv`        — every non-empty line has the same comma count
//!     (≥1) — minimum 2 lines.
//!   * `PlainText`  — fallback.
//!
//! Pure heuristic. No parsing.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Detected format.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PasteFormat {
    /// URL.
    Url,
    /// JSON.
    Json,
    /// Fenced code block.
    CodeBlock,
    /// Markdown.
    Markdown,
    /// CSV.
    Csv,
    /// Plain text fallback.
    PlainText,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PasteFormatDetector {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DetectError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl PasteFormatDetector {
    /// New.
    pub fn new() -> Self {
        Self { schema_version: SCHEMA_VERSION.into() }
    }

    /// Detect.
    pub fn detect(&self, text: &str) -> PasteFormat {
        let trimmed = text.trim();
        if trimmed.is_empty() { return PasteFormat::PlainText; }

        // URL.
        if !trimmed.contains(char::is_whitespace) {
            let lower = trimmed.to_ascii_lowercase();
            for prefix in ["http://", "https://", "ftp://", "ftps://", "mailto:", "ssh://"] {
                if lower.starts_with(prefix) { return PasteFormat::Url; }
            }
        }

        // Fenced code block.
        if trimmed.starts_with("```") && trimmed.trim_end().ends_with("```") {
            return PasteFormat::CodeBlock;
        }

        // JSON.
        let first = trimmed.chars().next().unwrap();
        if (first == '{' || first == '[') && trimmed.contains(':') {
            return PasteFormat::Json;
        }

        // Markdown.
        let is_md = trimmed.lines().any(|l| {
            let t = l.trim_start();
            t.starts_with("# ") || t.starts_with("## ") || t.starts_with("### ")
                || t.starts_with("- ") || t.starts_with("* ")
        }) || markdown_link(trimmed);
        if is_md { return PasteFormat::Markdown; }

        // CSV.
        let non_empty: Vec<&str> = trimmed.lines().filter(|l| !l.trim().is_empty()).collect();
        if non_empty.len() >= 2 {
            let first_commas = non_empty[0].matches(',').count();
            if first_commas >= 1 && non_empty.iter().all(|l| l.matches(',').count() == first_commas) {
                return PasteFormat::Csv;
            }
        }

        PasteFormat::PlainText
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DetectError> {
        if self.schema_version != SCHEMA_VERSION { return Err(DetectError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for PasteFormatDetector {
    fn default() -> Self { Self::new() }
}

fn markdown_link(s: &str) -> bool {
    // crude `[…](…)` detection.
    let bytes = s.as_bytes();
    let mut i = 0;
    while i + 4 < bytes.len() {
        if bytes[i] == b'[' {
            if let Some(close) = bytes[i + 1..].iter().position(|&b| b == b']') {
                let next = i + 1 + close + 1;
                if next < bytes.len() && bytes[next] == b'(' {
                    if bytes[next + 1..].iter().any(|&b| b == b')') {
                        return true;
                    }
                }
            }
        }
        i += 1;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    fn d() -> PasteFormatDetector { PasteFormatDetector::new() }

    #[test]
    fn url_detected() {
        assert_eq!(d().detect("https://example.com/path"), PasteFormat::Url);
        assert_eq!(d().detect("  mailto:foo@bar.com  "), PasteFormat::Url);
    }

    #[test]
    fn url_with_spaces_not_url() {
        assert_ne!(d().detect("https://example.com and more"), PasteFormat::Url);
    }

    #[test]
    fn json_detected() {
        assert_eq!(d().detect("{\"k\": 1}"), PasteFormat::Json);
        assert_eq!(d().detect("[{\"k\": 1}]"), PasteFormat::Json);
    }

    #[test]
    fn code_block_detected() {
        let s = "```rust\nfn main(){}\n```";
        assert_eq!(d().detect(s), PasteFormat::CodeBlock);
    }

    #[test]
    fn markdown_heading_detected() {
        assert_eq!(d().detect("# Title\nbody"), PasteFormat::Markdown);
    }

    #[test]
    fn markdown_bullets_detected() {
        assert_eq!(d().detect("- one\n- two"), PasteFormat::Markdown);
    }

    #[test]
    fn markdown_link_detected() {
        assert_eq!(d().detect("see [docs](https://x.com)"), PasteFormat::Markdown);
    }

    #[test]
    fn csv_detected() {
        let s = "a,b,c\n1,2,3\n4,5,6";
        assert_eq!(d().detect(s), PasteFormat::Csv);
    }

    #[test]
    fn csv_uneven_falls_back() {
        let s = "a,b,c\n1,2,3,4";
        assert_eq!(d().detect(s), PasteFormat::PlainText);
    }

    #[test]
    fn plain_text_fallback() {
        assert_eq!(d().detect("just some text"), PasteFormat::PlainText);
    }

    #[test]
    fn empty_is_plain() {
        assert_eq!(d().detect(""), PasteFormat::PlainText);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut x = d();
        x.schema_version = "9.9.9".into();
        assert!(matches!(x.validate().unwrap_err(), DetectError::SchemaMismatch));
    }

    #[test]
    fn detector_serde_roundtrip() {
        let x = d();
        let j = serde_json::to_string(&x).unwrap();
        let back: PasteFormatDetector = serde_json::from_str(&j).unwrap();
        assert_eq!(x, back);
    }
}
