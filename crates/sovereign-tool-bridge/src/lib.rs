//! Schema bridge between the two tool-call dialects in the workspace.
//!
//! The ReAct loop ([`sovereign_tool_dispatch`]) speaks a bespoke
//! `[[tool:NAME|ARGS]]` string convention; the OpenAI/Anthropic wire protocols
//! speak JSON `tool_calls` / `tool_use` (parsed by [`sovereign_tool_call_parse`]).
//! These two islands never met — this crate is the adapter between them, so an
//! OpenAI/Anthropic-compatible daemon can accept `tools` in a request and return
//! standards-shaped `tool_calls` / `tool_use`.
//!
//! It is deliberately **model-free and side-effect-free** — every function here
//! is a pure data transform, unit-tested without a model or a network.
//!
//! Two consumers, sequenced (F-2026-088):
//! - **Single-turn, client-driven** (landed with this crate, SDD-711): the
//!   `sovereign-gatewayd` `/v1/chat/completions` handler uses
//!   [`openai_tools_to_specs`] + [`tool_specs_to_prompt`] +
//!   [`extract_advertised_call`] + [`tool_call_to_openai`] to return a
//!   `tool_calls` response the CLIENT executes (the standard OpenAI tool loop).
//! - **Multi-step agentic** (future increment): compose [`extract_call`] with a
//!   [`sovereign_tool_dispatch::ToolRegistry`] to run the ReAct loop server-side
//!   and render each [`outcome_to_openai`] / [`outcome_to_anthropic`] step —
//!   gated on the daemon model-sharing decision (see SDD-711 design section).
//!
//! Direction map:
//! - request `tools[]`  → [`openai_tools_to_specs`] → [`ToolSpec`] → [`tool_specs_to_prompt`]
//! - model output       → [`extract_call`] (bracket **or** JSON) → [`sovereign_tool_dispatch::ToolCall`]
//! - dispatched outcome → [`outcome_to_openai`] / [`outcome_to_anthropic`] → response blocks

use serde_json::{Value, json};
use sovereign_tool_call_parse as jsonc;
use sovereign_tool_dispatch as brk;

/// Bumped when the transform contract changes; mirrors the sibling crates.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A tool the caller advertised in an OpenAI/Anthropic request `tools[]` array,
/// projected to the fields the bracket-convention prompt + registry need.
#[derive(Debug, Clone, PartialEq)]
pub struct ToolSpec {
    /// The tool name the model must emit (`[[tool:NAME|…]]` / `tool_calls[].function.name`).
    pub name: String,
    /// Human/model-facing description; may be empty.
    pub description: String,
    /// The JSON-Schema parameters object, verbatim (`{}` when absent).
    pub parameters: Value,
}

/// Parse an OpenAI/Anthropic request `tools` array into [`ToolSpec`]s.
///
/// Accepts both the OpenAI shape `{"type":"function","function":{"name",…}}`
/// and a bare `{"name",…}` (Anthropic tool definitions / flattened form).
/// Unnamed / malformed entries are skipped rather than erroring — a caller that
/// wants strictness can compare the returned length to the input length.
pub fn openai_tools_to_specs(tools: &Value) -> Vec<ToolSpec> {
    let Some(arr) = tools.as_array() else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for t in arr {
        // OpenAI nests under "function"; Anthropic puts the fields at top level.
        let f = t.get("function").unwrap_or(t);
        let Some(name) = f.get("name").and_then(Value::as_str) else {
            continue;
        };
        if name.is_empty() {
            continue;
        }
        let description = f
            .get("description")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        // OpenAI: "parameters"; Anthropic: "input_schema".
        let parameters = f
            .get("parameters")
            .or_else(|| f.get("input_schema"))
            .cloned()
            .unwrap_or_else(|| json!({}));
        out.push(ToolSpec {
            name: name.to_string(),
            description,
            parameters,
        });
    }
    out
}

/// Render the advertised tools into a system-prompt snippet that teaches the
/// bracket convention, so a model that only knows `[[tool:…]]` can use tools the
/// caller supplied in JSON. Empty input → empty string (inject nothing).
pub fn tool_specs_to_prompt(specs: &[ToolSpec]) -> String {
    if specs.is_empty() {
        return String::new();
    }
    let mut s = String::from(
        "You can call tools. To call one, emit exactly one line of the form \
         [[tool:NAME|ARGS]] where ARGS is a compact JSON object of the tool's \
         parameters. Available tools:\n",
    );
    for spec in specs {
        s.push_str("- ");
        s.push_str(&spec.name);
        if !spec.description.is_empty() {
            s.push_str(": ");
            s.push_str(&spec.description);
        }
        s.push('\n');
    }
    s
}

/// Serialize a JSON arguments value to the compact string a bracket handler
/// receives. A string argument is passed through as-is (not re-quoted) so
/// `{"arguments":"hello"}` dispatches with `args = "hello"`, matching how a
/// human would write `[[tool:echo|hello]]`.
fn args_value_to_string(arguments: &Value) -> String {
    match arguments {
        Value::String(s) => s.clone(),
        Value::Null => String::new(),
        other => serde_json::to_string(other).unwrap_or_default(),
    }
}

/// Parse a bracket `args` string back into a JSON arguments value: valid JSON is
/// preserved; anything else becomes a JSON string (so the round-trip never loses
/// the operator's literal text).
fn args_string_to_value(args: &str) -> Value {
    let trimmed = args.trim();
    if trimmed.is_empty() {
        return json!({});
    }
    serde_json::from_str::<Value>(trimmed).unwrap_or_else(|_| Value::String(args.to_string()))
}

/// Convert a JSON-dialect tool call ([`jsonc::ToolCall`]) into a bracket-dialect
/// call ([`brk::ToolCall`]) the [`sovereign_tool_dispatch::ToolRegistry`] can run.
pub fn json_call_to_dispatch(c: &jsonc::ToolCall) -> brk::ToolCall {
    brk::ToolCall {
        name: c.name.clone(),
        args: args_value_to_string(&c.arguments),
    }
}

/// Convert a bracket-dialect call into a JSON-dialect call.
pub fn dispatch_call_to_json(c: &brk::ToolCall) -> jsonc::ToolCall {
    jsonc::ToolCall {
        name: c.name.clone(),
        arguments: args_string_to_value(&c.args),
    }
}

/// Render a bracket-dialect call back to the `[[tool:NAME|ARGS]]` text a model
/// is prompted to emit (dispatch has no formatter of its own).
pub fn render_bracket(c: &brk::ToolCall) -> String {
    if c.args.is_empty() {
        format!("{}{}{}", brk::OPEN, c.name, brk::CLOSE)
    } else {
        format!("{}{}|{}{}", brk::OPEN, c.name, c.args, brk::CLOSE)
    }
}

/// Extract the first tool call from raw model output, accepting **either**
/// convention: a `[[tool:…]]` bracket call (preferred, native to the loop) or an
/// OpenAI/Anthropic JSON `tool_calls` / `{name,arguments}` blob. Returns the
/// bracket-dialect call ready for [`sovereign_tool_dispatch::ToolRegistry::call`].
/// `None` when the text contains no tool call in either dialect.
pub fn extract_call(text: &str) -> Option<brk::ToolCall> {
    if let Some(call) = brk::parse_call(text) {
        return Some(call);
    }
    jsonc::parse_first(text).map(|c| json_call_to_dispatch(&c))
}

/// Render a dispatched [`brk::ToolOutcome`] as the pair of OpenAI chat messages a
/// tool-using turn produces: the assistant message carrying the `tool_calls`
/// entry, and the `role:"tool"` message carrying the result. `id` is the
/// `tool_call_id` that links them (the caller mints it, e.g. `call_0`).
pub fn outcome_to_openai(outcome: &brk::ToolOutcome, id: &str) -> (Value, Value) {
    let assistant = json!({
        "role": "assistant",
        "content": Value::Null,
        "tool_calls": [{
            "id": id,
            "type": "function",
            "function": {
                "name": outcome.call.name,
                // OpenAI `arguments` is a JSON string, which is exactly the
                // bracket `args` payload.
                "arguments": outcome.call.args,
            }
        }]
    });
    let tool_result = json!({
        "role": "tool",
        "tool_call_id": id,
        "content": outcome.result,
    });
    (assistant, tool_result)
}

/// Render a dispatched [`brk::ToolOutcome`] as the pair of Anthropic content
/// blocks a tool-using turn produces: the `tool_use` block (for the assistant
/// turn) and the `tool_result` block (for the following user turn). `id` is the
/// `tool_use` id that links them (e.g. `toolu_0`).
pub fn outcome_to_anthropic(outcome: &brk::ToolOutcome, id: &str) -> (Value, Value) {
    let tool_use = json!({
        "type": "tool_use",
        "id": id,
        "name": outcome.call.name,
        // Anthropic `input` is a JSON object, so parse the bracket args.
        "input": args_string_to_value(&outcome.call.args),
    });
    let tool_result = json!({
        "type": "tool_result",
        "tool_use_id": id,
        "content": outcome.result,
    });
    (tool_use, tool_result)
}

/// The OpenAI `tool_calls[]` entry for a single detected call — what an
/// OpenAI-compatible SERVER returns so the CLIENT executes the tool (the
/// standard client-driven tool loop; the daemon does not run the tool here).
/// The caller mints `id` (e.g. `call_0`) to correlate the client's follow-up
/// `role:"tool"` message.
pub fn tool_call_to_openai(call: &brk::ToolCall, id: &str) -> Value {
    json!({
        "id": id,
        "type": "function",
        "function": {
            "name": call.name,
            // OpenAI `arguments` is a JSON string == the bracket `args` payload.
            "arguments": call.args,
        }
    })
}

/// Extract a tool call from model output **only if its name was advertised** in
/// `specs`. A `[[tool:foo|…]]` for a tool the caller never offered is treated as
/// ordinary text (returns `None`), so a model hallucinating a tool name can't
/// make the server emit a bogus `tool_calls` response. Accepts both dialects via
/// [`extract_call`].
pub fn extract_advertised_call(text: &str, specs: &[ToolSpec]) -> Option<brk::ToolCall> {
    let call = extract_call(text)?;
    if specs.iter().any(|s| s.name == call.name) {
        Some(call)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_openai_function_tools() {
        let tools = json!([
            {"type": "function", "function": {
                "name": "get_weather",
                "description": "Look up weather",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}
            }}
        ]);
        let specs = openai_tools_to_specs(&tools);
        assert_eq!(specs.len(), 1);
        assert_eq!(specs[0].name, "get_weather");
        assert_eq!(specs[0].description, "Look up weather");
        assert_eq!(specs[0].parameters["type"], "object");
    }

    #[test]
    fn parses_anthropic_flat_tools_with_input_schema() {
        let tools = json!([
            {"name": "search", "description": "web search",
             "input_schema": {"type": "object"}}
        ]);
        let specs = openai_tools_to_specs(&tools);
        assert_eq!(specs.len(), 1);
        assert_eq!(specs[0].name, "search");
        assert_eq!(specs[0].parameters["type"], "object");
    }

    #[test]
    fn skips_unnamed_and_nonarray() {
        assert!(openai_tools_to_specs(&json!({})).is_empty());
        assert!(openai_tools_to_specs(&json!("nope")).is_empty());
        let mixed = json!([{"function": {"description": "no name"}}, {"function": {"name": ""}}]);
        assert!(openai_tools_to_specs(&mixed).is_empty());
    }

    #[test]
    fn prompt_lists_tools_and_is_empty_when_none() {
        assert_eq!(tool_specs_to_prompt(&[]), "");
        let specs = openai_tools_to_specs(&json!([
            {"function": {"name": "a", "description": "does a"}},
            {"function": {"name": "b"}}
        ]));
        let p = tool_specs_to_prompt(&specs);
        assert!(p.contains("[[tool:NAME|ARGS]]"));
        assert!(p.contains("- a: does a"));
        assert!(p.contains("- b\n"));
    }

    #[test]
    fn json_call_to_dispatch_object_args_are_compact_json() {
        let c = jsonc::ToolCall {
            name: "upper".into(),
            arguments: json!({"text": "hi"}),
        };
        let d = json_call_to_dispatch(&c);
        assert_eq!(d.name, "upper");
        assert_eq!(d.args, r#"{"text":"hi"}"#);
    }

    #[test]
    fn json_call_string_arg_passes_through_unquoted() {
        let c = jsonc::ToolCall {
            name: "echo".into(),
            arguments: json!("hello world"),
        };
        let d = json_call_to_dispatch(&c);
        assert_eq!(d.args, "hello world");
    }

    #[test]
    fn dispatch_call_to_json_parses_object_else_string() {
        let obj = brk::ToolCall {
            name: "t".into(),
            args: r#"{"a":1}"#.into(),
        };
        assert_eq!(dispatch_call_to_json(&obj).arguments, json!({"a": 1}));
        let raw = brk::ToolCall {
            name: "t".into(),
            args: "plain text".into(),
        };
        assert_eq!(dispatch_call_to_json(&raw).arguments, json!("plain text"));
        let empty = brk::ToolCall {
            name: "t".into(),
            args: "".into(),
        };
        assert_eq!(dispatch_call_to_json(&empty).arguments, json!({}));
    }

    #[test]
    fn render_bracket_round_trips_through_dispatch_parser() {
        let c = brk::ToolCall {
            name: "upper".into(),
            args: r#"{"text":"hi"}"#.into(),
        };
        let text = render_bracket(&c);
        assert_eq!(text, r#"[[tool:upper|{"text":"hi"}]]"#);
        let back = brk::parse_call(&text).expect("re-parses");
        assert_eq!(back.name, c.name);
        assert_eq!(back.args, c.args);
    }

    #[test]
    fn render_bracket_no_args() {
        let c = brk::ToolCall {
            name: "now".into(),
            args: "".into(),
        };
        assert_eq!(render_bracket(&c), "[[tool:now]]");
        let back = brk::parse_call("[[tool:now]]").expect("re-parses");
        assert_eq!(back.name, "now");
        assert_eq!(back.args, "");
    }

    #[test]
    fn extract_call_prefers_bracket() {
        let c = extract_call("sure: [[tool:upper|hi]] done").expect("bracket");
        assert_eq!(c.name, "upper");
        assert_eq!(c.args, "hi");
    }

    #[test]
    fn extract_call_falls_back_to_json() {
        let text =
            r#"{"tool_calls":[{"function":{"name":"upper","arguments":"{\"text\":\"hi\"}"}}]}"#;
        let c = extract_call(text).expect("json");
        assert_eq!(c.name, "upper");
        assert_eq!(c.args, r#"{"text":"hi"}"#);
    }

    #[test]
    fn extract_call_none_when_no_tool() {
        assert!(extract_call("just a normal answer, no tools").is_none());
    }

    #[test]
    fn outcome_to_openai_shapes_tool_calls_and_result() {
        let outcome = brk::ToolOutcome {
            call: brk::ToolCall {
                name: "upper".into(),
                args: r#"{"text":"hi"}"#.into(),
            },
            result: "HI".into(),
        };
        let (assistant, tool_msg) = outcome_to_openai(&outcome, "call_0");
        assert_eq!(assistant["tool_calls"][0]["id"], "call_0");
        assert_eq!(assistant["tool_calls"][0]["type"], "function");
        assert_eq!(assistant["tool_calls"][0]["function"]["name"], "upper");
        assert_eq!(
            assistant["tool_calls"][0]["function"]["arguments"],
            r#"{"text":"hi"}"#
        );
        assert_eq!(assistant["content"], Value::Null);
        assert_eq!(tool_msg["role"], "tool");
        assert_eq!(tool_msg["tool_call_id"], "call_0");
        assert_eq!(tool_msg["content"], "HI");
    }

    #[test]
    fn outcome_to_anthropic_shapes_tool_use_and_result() {
        let outcome = brk::ToolOutcome {
            call: brk::ToolCall {
                name: "upper".into(),
                args: r#"{"text":"hi"}"#.into(),
            },
            result: "HI".into(),
        };
        let (tool_use, tool_result) = outcome_to_anthropic(&outcome, "toolu_0");
        assert_eq!(tool_use["type"], "tool_use");
        assert_eq!(tool_use["id"], "toolu_0");
        assert_eq!(tool_use["name"], "upper");
        assert_eq!(tool_use["input"], json!({"text": "hi"}));
        assert_eq!(tool_result["type"], "tool_result");
        assert_eq!(tool_result["tool_use_id"], "toolu_0");
        assert_eq!(tool_result["content"], "HI");
    }

    #[test]
    fn anthropic_input_wraps_non_json_args_as_string() {
        let outcome = brk::ToolOutcome {
            call: brk::ToolCall {
                name: "echo".into(),
                args: "plain".into(),
            },
            result: "plain".into(),
        };
        let (tool_use, _) = outcome_to_anthropic(&outcome, "toolu_1");
        assert_eq!(tool_use["input"], json!("plain"));
    }

    #[test]
    fn tool_call_to_openai_shapes_a_client_driven_entry() {
        let call = brk::ToolCall {
            name: "get_weather".into(),
            args: r#"{"city":"NYC"}"#.into(),
        };
        let entry = tool_call_to_openai(&call, "call_0");
        assert_eq!(entry["id"], "call_0");
        assert_eq!(entry["type"], "function");
        assert_eq!(entry["function"]["name"], "get_weather");
        assert_eq!(entry["function"]["arguments"], r#"{"city":"NYC"}"#);
    }

    #[test]
    fn extract_advertised_call_gates_on_the_offered_tools() {
        let specs = openai_tools_to_specs(&json!([{"function": {"name": "upper"}}]));
        // advertised → extracted
        let c = extract_advertised_call("ok [[tool:upper|hi]]", &specs).expect("advertised");
        assert_eq!(c.name, "upper");
        // NOT advertised → treated as plain text
        assert!(extract_advertised_call("[[tool:rm_rf|/]]", &specs).is_none());
        // no tool call at all → None
        assert!(extract_advertised_call("plain answer", &specs).is_none());
        // JSON dialect, advertised → extracted
        let json_out = r#"{"tool_calls":[{"function":{"name":"upper","arguments":"{}"}}]}"#;
        assert!(extract_advertised_call(json_out, &specs).is_some());
    }

    #[test]
    fn full_round_trip_json_to_dispatch_to_openai() {
        // A model emits an OpenAI tool_call → we bridge to dispatch → (a registry
        // would run it) → we emit the OpenAI response block. Shapes stay stable.
        let call = jsonc::parse_first(
            r#"{"tool_calls":[{"function":{"name":"len","arguments":"{\"s\":\"abc\"}"}}]}"#,
        )
        .expect("parse");
        let d = json_call_to_dispatch(&call);
        let outcome = brk::ToolOutcome {
            call: d,
            result: "3".into(),
        };
        let (assistant, tool_msg) = outcome_to_openai(&outcome, "call_9");
        assert_eq!(assistant["tool_calls"][0]["function"]["name"], "len");
        assert_eq!(tool_msg["content"], "3");
    }
}
