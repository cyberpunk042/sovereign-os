//! `sovereign-json-extract` — pull the first balanced JSON value out of text.
//!
//! Models emit JSON wrapped in prose — `Sure! {"city":"Paris"} is the call.`
//! — and a runtime needs just the JSON. This crate scans for the first `{` or
//! `[`, then walks forward tracking nesting depth while **respecting string
//! literals and escapes** (so a `}` inside `"a}b"` doesn't end the value), and
//! returns the balanced span — or parses it straight to a [`serde_json::Value`].
//!
//! It is deliberately a *scanner*, not a parser: it finds where the JSON is by
//! brace/bracket balance, and only then hands the span to `serde_json` to
//! validate. That makes it robust to leading/trailing prose, nested structures,
//! and braces that appear inside strings.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use thiserror::Error;

/// Schema version of the json-extract surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Why extraction failed.
#[derive(Debug, Error, PartialEq)]
pub enum ExtractError {
    /// No `{` or `[` was found.
    #[error("no JSON value found in text")]
    NotFound,
    /// A value started but its brackets never balanced.
    #[error("unbalanced JSON: opened at byte {open} but never closed")]
    Unbalanced {
        /// Byte offset where the value started.
        open: usize,
    },
    /// The balanced span did not parse as JSON.
    #[error("invalid JSON: {0}")]
    Invalid(String),
}

/// The byte span `[start, end)` of the first balanced JSON value in `text`.
pub fn find_span(text: &str) -> Result<(usize, usize), ExtractError> {
    let bytes = text.as_bytes();
    let start = bytes
        .iter()
        .position(|&b| b == b'{' || b == b'[')
        .ok_or(ExtractError::NotFound)?;

    let mut depth = 0i32;
    let mut in_string = false;
    let mut escaped = false;

    for (i, &b) in bytes.iter().enumerate().skip(start) {
        if in_string {
            if escaped {
                escaped = false;
            } else if b == b'\\' {
                escaped = true;
            } else if b == b'"' {
                in_string = false;
            }
            continue;
        }
        match b {
            b'"' => in_string = true,
            b'{' | b'[' => depth += 1,
            b'}' | b']' => {
                depth -= 1;
                if depth == 0 {
                    return Ok((start, i + 1));
                }
            }
            _ => {}
        }
    }
    Err(ExtractError::Unbalanced { open: start })
}

/// The first balanced JSON value in `text`, as a string slice.
pub fn extract(text: &str) -> Result<&str, ExtractError> {
    let (s, e) = find_span(text)?;
    Ok(&text[s..e])
}

/// The first balanced JSON value in `text`, parsed and validated.
pub fn extract_value(text: &str) -> Result<serde_json::Value, ExtractError> {
    let span = extract(text)?;
    serde_json::from_str(span).map_err(|e| ExtractError::Invalid(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn extracts_object_from_prose() {
        let text = r#"Sure! {"city":"Paris","n":2} is the call."#;
        assert_eq!(extract(text).unwrap(), r#"{"city":"Paris","n":2}"#);
        assert_eq!(extract_value(text).unwrap(), json!({"city":"Paris","n":2}));
    }

    #[test]
    fn extracts_array() {
        let text = "result: [1, 2, 3] done";
        assert_eq!(extract(text).unwrap(), "[1, 2, 3]");
        assert_eq!(extract_value(text).unwrap(), json!([1, 2, 3]));
    }

    #[test]
    fn handles_nested_structures() {
        let text = r#"x {"a":{"b":[1,{"c":2}]}} y"#;
        assert_eq!(extract(text).unwrap(), r#"{"a":{"b":[1,{"c":2}]}}"#);
    }

    #[test]
    fn braces_inside_strings_do_not_end_the_value() {
        let text = r#"{"k":"a}b{c","d":"]"}"#;
        assert_eq!(extract(text).unwrap(), text);
        assert_eq!(extract_value(text).unwrap(), json!({"k":"a}b{c","d":"]"}));
    }

    #[test]
    fn escaped_quote_inside_string_is_respected() {
        let text = r#"pre {"q":"he said \"hi\" }"} post"#;
        let span = extract(text).unwrap();
        assert_eq!(span, r#"{"q":"he said \"hi\" }"}"#);
        assert_eq!(
            extract_value(text).unwrap(),
            json!({"q":"he said \"hi\" }"})
        );
    }

    #[test]
    fn takes_the_first_value_only() {
        let text = r#"{"a":1} and {"b":2}"#;
        assert_eq!(extract(text).unwrap(), r#"{"a":1}"#);
    }

    #[test]
    fn no_json_is_not_found() {
        assert_eq!(
            extract("just plain text").unwrap_err(),
            ExtractError::NotFound
        );
    }

    #[test]
    fn unbalanced_is_reported() {
        let err = extract(r#"{"a": [1, 2"#).unwrap_err();
        assert!(matches!(err, ExtractError::Unbalanced { .. }));
    }

    #[test]
    fn balanced_but_invalid_json_is_reported() {
        // brackets balance, but it isn't valid JSON (bare word)
        let text = "{ not json }";
        // span is found (balanced) but parse fails
        assert!(find_span(text).is_ok());
        assert!(matches!(
            extract_value(text).unwrap_err(),
            ExtractError::Invalid(_)
        ));
    }

    #[test]
    fn span_offsets_are_correct() {
        let text = "abc[42]def";
        let (s, e) = find_span(text).unwrap();
        assert_eq!((s, e), (3, 7));
        assert_eq!(&text[s..e], "[42]");
    }
}
