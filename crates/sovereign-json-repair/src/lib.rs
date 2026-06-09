//! `sovereign-json-repair` — make model JSON parseable.
//!
//! Ask a model for JSON and you often get *nearly* JSON: wrapped in a
//! ```` ```json ```` fence, prefixed with "Sure, here you go:", missing the
//! closing brace because generation hit a length limit, or with a trailing comma
//! before a `}`. A strict parser rejects all of these even though the intent is
//! obvious. This crate is a tolerant pre-parse pass that fixes the common
//! failures and returns a best-effort valid JSON string.
//!
//! It does four things, in order: **strip** Markdown code fences and any prose
//! outside the first JSON value; **scan** the value tracking string state (so
//! structural characters inside strings are left alone); **drop** trailing commas
//! that sit right before a `}` or `]`; and **close** anything still open at the
//! end — an unterminated string gets its closing quote, and unclosed objects and
//! arrays get their `}`/`]` in last-opened-first-closed order. The result parses
//! under [`serde_json`] for the common cases, and [`repair_to_value`] returns the
//! parsed value directly.
//!
//! It is a heuristic, not a grammar: deeply corrupted input may still fail, and
//! the repair reflects the *structure* seen, not the model's true intent. Use it
//! in front of a parser, not as a validator.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the json-repair surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Strip Markdown code fences and any text before the first `{`/`[` and after the
/// matching end, returning the candidate JSON substring.
fn extract_candidate(input: &str) -> &str {
    let trimmed = input.trim();
    // remove a leading ```... fence line and a trailing ``` if present.
    let without_fence = if let Some(rest) = trimmed.strip_prefix("```") {
        // drop up to the first newline (the ```json language tag)
        let rest = match rest.find('\n') {
            Some(nl) => &rest[nl + 1..],
            None => rest,
        };
        rest.strip_suffix("```").unwrap_or(rest)
    } else {
        trimmed
    };
    let without_fence = without_fence.trim();
    // find the first opening bracket and the last closing bracket of the same/any
    // kind; slice to that span to drop surrounding prose.
    let start = without_fence.find(['{', '[']);
    let end = without_fence.rfind(['}', ']']);
    match (start, end) {
        (Some(s), Some(e)) if e >= s => &without_fence[s..=e],
        (Some(s), _) => &without_fence[s..], // no close yet (truncated)
        _ => without_fence,
    }
}

/// Repair `input` into a best-effort valid JSON string.
pub fn repair(input: &str) -> String {
    let candidate = extract_candidate(input);

    let mut out = String::with_capacity(candidate.len() + 8);
    let mut stack: Vec<char> = Vec::new(); // open '{' / '['
    let mut in_string = false;
    let mut escaped = false;

    let chars: Vec<char> = candidate.chars().collect();
    for idx in 0..chars.len() {
        let c = chars[idx];
        if in_string {
            out.push(c);
            if escaped {
                escaped = false;
            } else if c == '\\' {
                escaped = true;
            } else if c == '"' {
                in_string = false;
            }
            continue;
        }
        match c {
            '"' => {
                in_string = true;
                out.push(c);
            }
            '{' | '[' => {
                stack.push(c);
                out.push(c);
            }
            '}' | ']' => {
                // drop a trailing comma just before this closer
                trim_trailing_comma(&mut out);
                stack.pop();
                out.push(c);
            }
            ',' => {
                // keep for now; a trailing comma is removed when a closer follows
                // or at end-of-input.
                out.push(c);
            }
            _ => out.push(c),
        }
    }

    // close an unterminated string
    if in_string {
        out.push('"');
    }
    // remove a dangling trailing comma at the very end
    trim_trailing_comma(&mut out);
    // close any still-open containers, innermost first
    while let Some(open) = stack.pop() {
        out.push(if open == '{' { '}' } else { ']' });
        // a comma could now be trailing before the next closer
        // (rare, but keep it clean)
    }
    out
}

/// Remove a trailing comma (and any whitespace after it) from the end of `out`.
fn trim_trailing_comma(out: &mut String) {
    let trimmed_len = out.trim_end().len();
    if out[..trimmed_len].ends_with(',') {
        out.truncate(trimmed_len - 1);
    }
}

/// Repair `input` and parse it with [`serde_json`].
pub fn repair_to_value(input: &str) -> Result<serde_json::Value, serde_json::Error> {
    serde_json::from_str(&repair(input))
}

/// Whether `input` parses as JSON after repair.
pub fn is_repairable(input: &str) -> bool {
    repair_to_value(input).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn already_valid_passes_through() {
        let v = repair_to_value(r#"{"a":1,"b":[2,3]}"#).unwrap();
        assert_eq!(v, json!({"a":1,"b":[2,3]}));
    }

    #[test]
    fn strips_markdown_fence() {
        let input = "```json\n{\"x\": 1}\n```";
        let v = repair_to_value(input).unwrap();
        assert_eq!(v, json!({"x":1}));
    }

    #[test]
    fn strips_surrounding_prose() {
        let input = "Sure! Here is the result: {\"ok\": true} Hope that helps.";
        let v = repair_to_value(input).unwrap();
        assert_eq!(v, json!({"ok":true}));
    }

    #[test]
    fn removes_trailing_comma_in_object_and_array() {
        let v = repair_to_value(r#"{"a":1, "b":2,}"#).unwrap();
        assert_eq!(v, json!({"a":1,"b":2}));
        let v2 = repair_to_value("[1, 2, 3, ]").unwrap();
        assert_eq!(v2, json!([1, 2, 3]));
    }

    #[test]
    fn closes_unclosed_object() {
        // truncated mid-object (length limit)
        let v = repair_to_value(r#"{"a": 1, "b": 2"#).unwrap();
        assert_eq!(v, json!({"a":1,"b":2}));
    }

    #[test]
    fn closes_unclosed_nested_structures() {
        let v = repair_to_value(r#"{"list": [1, 2, {"k": "v""#).unwrap();
        assert_eq!(v, json!({"list":[1,2,{"k":"v"}]}));
    }

    #[test]
    fn closes_unterminated_string() {
        let v = repair_to_value(r#"{"msg": "hello"#).unwrap();
        assert_eq!(v, json!({"msg":"hello"}));
    }

    #[test]
    fn leaves_structural_chars_inside_strings_alone() {
        // braces/commas inside a string value must not be treated as structure
        let v = repair_to_value(r#"{"text": "a, b, {c}"}"#).unwrap();
        assert_eq!(v, json!({"text":"a, b, {c}"}));
    }

    #[test]
    fn handles_escaped_quotes_in_strings() {
        let v = repair_to_value(r#"{"q": "she said \"hi\""}"#).unwrap();
        assert_eq!(v, json!({"q":"she said \"hi\""}));
    }

    #[test]
    fn array_root_and_fence_combo() {
        let input = "```\n[\"a\", \"b\", ]\n```";
        let v = repair_to_value(input).unwrap();
        assert_eq!(v, json!(["a", "b"]));
    }

    #[test]
    fn is_repairable_reports_success() {
        assert!(is_repairable(r#"{"a":1"#)); // closable
        assert!(is_repairable("```json\n{\"a\":1}\n```"));
        // pure garbage with no JSON structure is not repairable to a value
        assert!(!is_repairable("just some words, nothing structured"));
    }

    #[test]
    fn truncated_deep_nesting_recovers() {
        let input = r#"{"a":{"b":{"c":[1,2,3"#;
        let v = repair_to_value(input).unwrap();
        assert_eq!(v, json!({"a":{"b":{"c":[1,2,3]}}}));
    }
}
