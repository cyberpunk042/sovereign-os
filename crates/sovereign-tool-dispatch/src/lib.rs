//! `sovereign-tool-dispatch` — parse and execute tool calls from model output.
//!
//! A tool *catalog* says what tools exist; this crate *runs* one. When a model
//! emits a call in the form `[[tool:NAME|ARGS]]`, [`parse_call`] extracts the
//! name and arguments, and a [`ToolRegistry`] invokes the handler registered
//! under that name, returning its result string — which a runtime feeds back
//! into the conversation as the tool's observation. That parse → dispatch →
//! result step is the core of an agent's tool-use loop.
//!
//! The call syntax is deliberately simple and unambiguous: everything between
//! `[[tool:` and the first following `]]`, split on the first `|` into name and
//! args (args optional). Unknown tools are a typed error, not a silent no-op.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version of the tool-dispatch surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Opening marker of a tool call.
pub const OPEN: &str = "[[tool:";
/// Closing marker of a tool call.
pub const CLOSE: &str = "]]";

/// A parsed tool call.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ToolCall {
    /// The tool name.
    pub name: String,
    /// The raw argument string (may be empty).
    pub args: String,
}

/// Dispatch errors.
#[derive(Debug, Error, PartialEq)]
pub enum ToolError {
    /// No handler is registered under this name.
    #[error("unknown tool '{0}'")]
    UnknownTool(String),
}

/// The outcome of dispatching one call.
#[derive(Debug, Clone, PartialEq)]
pub struct ToolOutcome {
    /// The call that was run.
    pub call: ToolCall,
    /// The handler's result string.
    pub result: String,
}

/// Find the first `[[tool:NAME|ARGS]]` call in `text`, if any.
pub fn parse_call(text: &str) -> Option<ToolCall> {
    let start = text.find(OPEN)?;
    let inner_start = start + OPEN.len();
    let end_rel = text[inner_start..].find(CLOSE)?;
    let inner = &text[inner_start..inner_start + end_rel];
    let (name, args) = match inner.find('|') {
        Some(b) => (inner[..b].to_string(), inner[b + 1..].to_string()),
        None => (inner.to_string(), String::new()),
    };
    if name.is_empty() {
        return None;
    }
    Some(ToolCall { name, args })
}

/// A tool handler: maps an argument string to a result string.
pub type Handler = Box<dyn Fn(&str) -> String + Send + Sync>;

/// A registry of named tool handlers.
#[derive(Default)]
pub struct ToolRegistry {
    handlers: HashMap<String, Handler>,
}

impl std::fmt::Debug for ToolRegistry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut names: Vec<&str> = self.handlers.keys().map(|s| s.as_str()).collect();
        names.sort_unstable();
        f.debug_struct("ToolRegistry")
            .field("tools", &names)
            .finish()
    }
}

impl ToolRegistry {
    /// An empty registry.
    pub fn new() -> Self {
        Self::default()
    }

    /// Register `handler` under `name` (replacing any prior handler).
    pub fn register<F>(&mut self, name: impl Into<String>, handler: F)
    where
        F: Fn(&str) -> String + Send + Sync + 'static,
    {
        self.handlers.insert(name.into(), Box::new(handler));
    }

    /// The registered tool names, sorted.
    pub fn names(&self) -> Vec<String> {
        let mut n: Vec<String> = self.handlers.keys().cloned().collect();
        n.sort();
        n
    }

    /// Whether `name` is registered.
    pub fn has(&self, name: &str) -> bool {
        self.handlers.contains_key(name)
    }

    /// Suggest the closest registered tool name to `name` within `max_distance`
    /// edits — for recovering a model's misspelled tool call. Returns `None` if
    /// `name` is already registered or nothing is close enough.
    pub fn suggest(&self, name: &str, max_distance: usize) -> Option<String> {
        if self.has(name) {
            return None;
        }
        let names = self.names();
        let refs: Vec<&str> = names.iter().map(String::as_str).collect();
        sovereign_edit_distance::did_you_mean(name, &refs, max_distance).map(str::to_string)
    }

    /// Invoke the handler for `name` with `args`.
    pub fn call(&self, name: &str, args: &str) -> Result<String, ToolError> {
        match self.handlers.get(name) {
            Some(h) => Ok(h(args)),
            None => Err(ToolError::UnknownTool(name.to_string())),
        }
    }

    /// Parse the first tool call in `text` and run it. Returns `Ok(None)` if no
    /// call is present, `Err` if the call names an unknown tool.
    pub fn dispatch(&self, text: &str) -> Result<Option<ToolOutcome>, ToolError> {
        match parse_call(text) {
            None => Ok(None),
            Some(call) => {
                let result = self.call(&call.name, &call.args)?;
                Ok(Some(ToolOutcome { call, result }))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn registry() -> ToolRegistry {
        let mut r = ToolRegistry::new();
        r.register("echo", |a| a.to_string());
        r.register("len", |a| a.chars().count().to_string());
        r.register("upper", |a| a.to_uppercase());
        r
    }

    #[test]
    fn parses_name_and_args() {
        let c = parse_call("sure: [[tool:search|rust traits]] done").unwrap();
        assert_eq!(c.name, "search");
        assert_eq!(c.args, "rust traits");
    }

    #[test]
    fn parses_call_without_args() {
        let c = parse_call("[[tool:now]]").unwrap();
        assert_eq!(c.name, "now");
        assert_eq!(c.args, "");
    }

    #[test]
    fn no_call_returns_none() {
        assert_eq!(parse_call("just some text, no tools"), None);
        assert_eq!(parse_call("[[tool:]]"), None); // empty name
    }

    #[test]
    fn parses_the_first_call_only() {
        let c = parse_call("[[tool:a|1]] then [[tool:b|2]]").unwrap();
        assert_eq!(c.name, "a");
        assert_eq!(c.args, "1");
    }

    #[test]
    fn dispatch_runs_the_handler() {
        let r = registry();
        let out = r
            .dispatch("call [[tool:upper|hello]] now")
            .unwrap()
            .unwrap();
        assert_eq!(out.call.name, "upper");
        assert_eq!(out.result, "HELLO");
    }

    #[test]
    fn dispatch_no_call_is_ok_none() {
        let r = registry();
        assert_eq!(r.dispatch("no tool here").unwrap(), None);
    }

    #[test]
    fn dispatch_unknown_tool_errors() {
        let r = registry();
        assert_eq!(
            r.dispatch("[[tool:missing|x]]").unwrap_err(),
            ToolError::UnknownTool("missing".to_string())
        );
    }

    #[test]
    fn call_directly() {
        let r = registry();
        assert_eq!(r.call("len", "世界").unwrap(), "2"); // 2 chars
        assert_eq!(r.call("echo", "hi").unwrap(), "hi");
        assert!(r.call("nope", "").is_err());
    }

    #[test]
    fn registry_introspection() {
        let r = registry();
        assert_eq!(r.names(), vec!["echo", "len", "upper"]);
        assert!(r.has("echo") && !r.has("ghost"));
        // Debug lists tools without panicking
        assert!(format!("{r:?}").contains("echo"));
    }

    #[test]
    fn suggests_a_close_tool_name() {
        let r = registry(); // echo, len, upper
        // a misspelled "uppr" → suggest "upper"
        assert_eq!(r.suggest("uppr", 2).as_deref(), Some("upper"));
        // already registered → no suggestion
        assert_eq!(r.suggest("echo", 2), None);
        // nothing close enough
        assert_eq!(r.suggest("xyzzy", 2), None);
    }

    #[test]
    fn toolcall_serde_round_trip() {
        let c = ToolCall {
            name: "search".into(),
            args: "q".into(),
        };
        let j = serde_json::to_string(&c).unwrap();
        let back: ToolCall = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
