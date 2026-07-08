//! `sovereign-cockpit-json-viewer` — collapsible JSON tree viewer.
//!
//! Path-addressed expanded set, e.g. `"$"` for root, `"$.foo"` for
//! object field, `"$[0]"` for array index. Surface owns the actual
//! JSON; this crate holds expansion state + flatten() that walks
//! the JSON producing Row{depth, path, label, value_preview,
//! expandable, expanded} list per current state.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Row {
    /// Depth.
    pub depth: u32,
    /// JSON path (e.g. "$.a[0].b").
    pub path: String,
    /// Display label (key or "[i]" or "$").
    pub label: String,
    /// Value preview (e.g. "{...}", "[5 items]", or the scalar).
    pub value_preview: String,
    /// Container?
    pub expandable: bool,
    /// Expanded?
    pub expanded: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct JsonViewer {
    /// Schema version.
    pub schema_version: String,
    /// Set of expanded paths.
    pub expanded: BTreeSet<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ViewerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl JsonViewer {
    /// New.
    pub fn new() -> Self {
        let mut s = BTreeSet::new();
        s.insert("$".into());
        Self {
            schema_version: SCHEMA_VERSION.into(),
            expanded: s,
        }
    }

    /// Toggle path.
    pub fn toggle(&mut self, path: &str) {
        if !self.expanded.remove(path) {
            self.expanded.insert(path.into());
        }
    }

    /// Is path expanded?
    pub fn is_expanded(&self, path: &str) -> bool {
        self.expanded.contains(path)
    }

    /// Flatten value into rows.
    pub fn flatten(&self, value: &Value) -> Vec<Row> {
        let mut out = Vec::new();
        walk(value, "$", "$", 0, self, &mut out);
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ViewerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ViewerError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for JsonViewer {
    fn default() -> Self {
        Self::new()
    }
}

fn walk(v: &Value, path: &str, label: &str, depth: u32, vw: &JsonViewer, out: &mut Vec<Row>) {
    let expandable = matches!(v, Value::Object(_) | Value::Array(_));
    let expanded = expandable && vw.is_expanded(path);
    let preview = match v {
        Value::Object(o) => format!("{{{} field(s)}}", o.len()),
        Value::Array(a) => format!("[{} item(s)]", a.len()),
        Value::String(s) => format!("{s:?}"),
        Value::Number(n) => n.to_string(),
        Value::Bool(b) => b.to_string(),
        Value::Null => "null".into(),
    };
    out.push(Row {
        depth,
        path: path.into(),
        label: label.into(),
        value_preview: preview,
        expandable,
        expanded,
    });
    if expanded {
        match v {
            Value::Object(o) => {
                for (k, child) in o {
                    let child_path = format!("{path}.{k}");
                    walk(child, &child_path, k, depth + 1, vw, out);
                }
            }
            Value::Array(a) => {
                for (i, child) in a.iter().enumerate() {
                    let child_path = format!("{path}[{i}]");
                    let lbl = format!("[{i}]");
                    walk(child, &child_path, &lbl, depth + 1, vw, out);
                }
            }
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn root_expanded_shows_children() {
        let v = json!({"a": 1, "b": [2, 3]});
        let view = JsonViewer::new();
        let rows = view.flatten(&v);
        // Root + a + b (b is collapsed).
        assert_eq!(rows.len(), 3);
        assert_eq!(rows[0].label, "$");
        assert!(rows[1].label == "a" || rows[1].label == "b");
    }

    #[test]
    fn expand_array_reveals_items() {
        let v = json!({"b": [2, 3]});
        let mut view = JsonViewer::new();
        view.toggle("$.b");
        let rows = view.flatten(&v);
        // Root + b + b[0] + b[1].
        assert_eq!(rows.len(), 4);
        assert_eq!(rows[2].path, "$.b[0]");
    }

    #[test]
    fn toggle_collapses() {
        let mut view = JsonViewer::new();
        view.toggle("$"); // collapsed
        let v = json!({"a": 1});
        let rows = view.flatten(&v);
        assert_eq!(rows.len(), 1);
        assert!(!rows[0].expanded);
    }

    #[test]
    fn scalars_non_expandable() {
        let v = json!(42);
        let view = JsonViewer::new();
        let rows = view.flatten(&v);
        assert!(!rows[0].expandable);
        assert_eq!(rows[0].value_preview, "42");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut v = JsonViewer::new();
        v.schema_version = "9.9.9".into();
        assert!(matches!(
            v.validate().unwrap_err(),
            ViewerError::SchemaMismatch
        ));
    }

    #[test]
    fn viewer_serde_roundtrip() {
        let mut v = JsonViewer::new();
        v.toggle("$.foo");
        let j = serde_json::to_string(&v).unwrap();
        let back: JsonViewer = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }
}
