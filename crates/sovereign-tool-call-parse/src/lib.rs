//! `sovereign-tool-call-parse` — pull function calls out of model output.
//!
//! When a model decides to call a tool it emits JSON: either a `tool_calls` array
//! (`{"tool_calls":[{"function":{"name":"search","arguments":"{\"q\":\"x\"}"}}]}`)
//! or a single bare call (`{"name":"search","arguments":{"q":"x"}}`). An agent
//! runtime has to turn that text — which may be wrapped in a code fence, prefixed
//! with prose, or truncated — into structured calls it can dispatch. This crate
//! does that, leaning on [`sovereign_json_repair`] so a missing brace or a
//! trailing comma doesn't drop the call.
//!
//! It handles the two shapes and the awkward-but-common case where `arguments` is
//! itself a JSON *string* rather than an object (it re-parses it). Each result is
//! a [`ToolCall`] with the tool `name` and its `arguments` as a
//! [`serde_json::Value`]; [`ToolCall::arg_str`] and [`ToolCall::arg_i64`] are
//! small helpers for reading common argument types. [`parse_tool_calls`] returns
//! every call found, in order; [`parse_first`] the first.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Schema version of the tool-call-parse surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A parsed tool/function call.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolCall {
    /// The tool/function name.
    pub name: String,
    /// The call arguments as a JSON value (an object for well-formed calls).
    pub arguments: Value,
}

impl ToolCall {
    /// Read a string argument by key.
    pub fn arg_str(&self, key: &str) -> Option<&str> {
        self.arguments.get(key).and_then(Value::as_str)
    }

    /// Read an integer argument by key.
    pub fn arg_i64(&self, key: &str) -> Option<i64> {
        self.arguments.get(key).and_then(Value::as_i64)
    }

    /// Read a floating-point argument by key.
    pub fn arg_f64(&self, key: &str) -> Option<f64> {
        self.arguments.get(key).and_then(Value::as_f64)
    }
}

/// Normalize an `arguments` field: if it is a JSON *string*, parse it; otherwise
/// take it as-is. A non-parseable string becomes a string value.
fn normalize_arguments(v: Value) -> Value {
    match v {
        Value::String(s) => serde_json::from_str(&s).unwrap_or(Value::String(s)),
        other => other,
    }
}

/// Try to extract one tool call from a JSON object that is either
/// `{"name":.., "arguments":..}` or `{"function":{"name":.., "arguments":..}}`.
fn call_from_object(obj: &Value) -> Option<ToolCall> {
    // unwrap an OpenAI-style {"type":"function","function":{...}} wrapper
    let inner = obj.get("function").unwrap_or(obj);
    let name = inner.get("name").and_then(Value::as_str)?.to_string();
    let arguments = inner
        .get("arguments")
        .cloned()
        .map(normalize_arguments)
        .unwrap_or(Value::Object(Default::default()));
    Some(ToolCall { name, arguments })
}

/// Parse all tool calls from `text` (repairing JSON as needed), in order.
pub fn parse_tool_calls(text: &str) -> Vec<ToolCall> {
    let repaired = sovereign_json_repair::repair(text);
    let Ok(value) = serde_json::from_str::<Value>(&repaired) else {
        return Vec::new();
    };

    // case 1: an object with a `tool_calls` array.
    if let Some(arr) = value.get("tool_calls").and_then(Value::as_array) {
        return arr.iter().filter_map(call_from_object).collect();
    }
    // case 2: a top-level array of calls.
    if let Some(arr) = value.as_array() {
        return arr.iter().filter_map(call_from_object).collect();
    }
    // case 3: a single bare call object.
    if let Some(call) = call_from_object(&value) {
        return vec![call];
    }
    Vec::new()
}

/// Parse the first tool call from `text`, if any.
pub fn parse_first(text: &str) -> Option<ToolCall> {
    parse_tool_calls(text).into_iter().next()
}

/// Whether `text` contains at least one parseable tool call.
pub fn has_tool_call(text: &str) -> bool {
    parse_first(text).is_some()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn bare_call_with_object_arguments() {
        let t = r#"{"name": "search", "arguments": {"q": "rust traits"}}"#;
        let c = parse_first(t).unwrap();
        assert_eq!(c.name, "search");
        assert_eq!(c.arg_str("q"), Some("rust traits"));
    }

    #[test]
    fn arguments_as_json_string_are_reparsed() {
        // the common case: arguments is a stringified JSON object
        let t = r#"{"name": "lookup", "arguments": "{\"id\": 42}"}"#;
        let c = parse_first(t).unwrap();
        assert_eq!(c.name, "lookup");
        assert_eq!(c.arg_i64("id"), Some(42));
    }

    #[test]
    fn openai_tool_calls_array() {
        let t = r#"{"tool_calls":[
            {"type":"function","function":{"name":"a","arguments":"{\"x\":1}"}},
            {"type":"function","function":{"name":"b","arguments":{"y":2}}}
        ]}"#;
        let calls = parse_tool_calls(t);
        assert_eq!(calls.len(), 2);
        assert_eq!(calls[0].name, "a");
        assert_eq!(calls[0].arg_i64("x"), Some(1));
        assert_eq!(calls[1].name, "b");
        assert_eq!(calls[1].arg_i64("y"), Some(2));
    }

    #[test]
    fn fenced_and_prose_wrapped() {
        let t = "Sure, I'll call it:\n```json\n{\"name\":\"now\",\"arguments\":{}}\n```";
        let c = parse_first(t).unwrap();
        assert_eq!(c.name, "now");
        assert_eq!(c.arguments, json!({}));
    }

    #[test]
    fn malformed_but_repairable() {
        // missing closing brace (truncation) — json-repair fixes it
        let t = r#"{"name": "fetch", "arguments": {"url": "http://x""#;
        let c = parse_first(t).unwrap();
        assert_eq!(c.name, "fetch");
        assert_eq!(c.arg_str("url"), Some("http://x"));
    }

    #[test]
    fn top_level_array_of_calls() {
        let t = r#"[{"name":"one","arguments":{}},{"name":"two","arguments":{}}]"#;
        let calls = parse_tool_calls(t);
        assert_eq!(
            calls.iter().map(|c| c.name.as_str()).collect::<Vec<_>>(),
            vec!["one", "two"]
        );
    }

    #[test]
    fn missing_arguments_defaults_to_empty_object() {
        let t = r#"{"name": "ping"}"#;
        let c = parse_first(t).unwrap();
        assert_eq!(c.name, "ping");
        assert_eq!(c.arguments, json!({}));
    }

    #[test]
    fn no_tool_call_in_plain_text() {
        assert!(!has_tool_call("I think the answer is 42."));
        assert!(parse_tool_calls("just chatting").is_empty());
    }

    #[test]
    fn arg_helpers_read_types() {
        let t = r#"{"name":"f","arguments":{"s":"hi","n":3,"f":1.5}}"#;
        let c = parse_first(t).unwrap();
        assert_eq!(c.arg_str("s"), Some("hi"));
        assert_eq!(c.arg_i64("n"), Some(3));
        assert_eq!(c.arg_f64("f"), Some(1.5));
        assert_eq!(c.arg_str("missing"), None);
    }

    #[test]
    fn serde_round_trip() {
        let c = ToolCall {
            name: "x".into(),
            arguments: json!({"a": 1}),
        };
        let j = serde_json::to_string(&c).unwrap();
        let back: ToolCall = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
