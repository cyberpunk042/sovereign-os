//! Bespoke wasm bridge for `sovereign-cockpit-auto-link` (no uniform validate()).
//! Exposes the real `tokenize` autolinker so the panel runs the crate's REAL
//! logic instead of a JS re-implementation (F-2026-001).
use sovereign_cockpit_auto_link::{tokenize, validate_schema_version};
use wasm_bindgen::prelude::*;

/// Tokenize plain text into interleaved plain/link segments using the crate's
/// real autolinker. Returns a JSON array of `{"kind":"plain","text":...}` /
/// `{"kind":"link","url":...}` segments.
#[wasm_bindgen]
pub fn auto_link_tokenize(text: &str) -> String {
    let segments = tokenize(text);
    serde_json::to_string(&segments).unwrap_or_else(|e| format!("{{\"error\":\"{}\"}}", e))
}

/// Validate a schema-version string against the crate's `SCHEMA_VERSION`.
/// Returns JSON `{"ok":true,"value":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn auto_link_validate_schema_version(version: &str) -> String {
    match validate_schema_version(version) {
        Ok(()) => serde_json::json!({"ok": true, "value": serde_json::Value::Null}).to_string(),
        Err(e) => serde_json::json!({"ok": false, "error": e.to_string()}).to_string(),
    }
}
