//! Bespoke wasm bridge for `sovereign-cockpit-word-count` (no uniform validate()).
//! Exposes the real content counter so the panel runs the crate's REAL `count`
//! logic (F-2026-001) — Unicode-aware char/word counts + reading-time — instead
//! of a JS re-implementation.
use sovereign_cockpit_word_count::{count, validate_schema_version};
use wasm_bindgen::prelude::*;

/// Count `text` at `wpm` words-per-minute via the crate's real `count`.
/// Returns JSON `{"ok":true,"value":{chars,chars_no_ws,words,reading_time_ms}}`
/// or `{"ok":false,"error":"..."}` (e.g. wpm must be ≥ 1).
#[wasm_bindgen]
pub fn word_count_count(text: &str, wpm: u32) -> String {
    match count(text, wpm) {
        Ok(stats) => {
            serde_json::json!({ "ok": true, "value": serde_json::to_value(stats).unwrap() })
                .to_string()
        }
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// Run the crate's real `validate_schema_version`. Returns JSON
/// `{"ok":true,"error":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn word_count_validate_schema_version(s: &str) -> String {
    match validate_schema_version(s) {
        Ok(()) => serde_json::json!({ "ok": true, "error": serde_json::Value::Null }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
