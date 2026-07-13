//! Bespoke wasm bridge for `sovereign-cockpit-text-truncation` (no uniform validate()).
//! Exposes char-aware truncation so the panel runs the crate's REAL logic (F-2026-001)
//! instead of a JS re-implementation of the ellipsis-placement decision.
use sovereign_cockpit_text_truncation::{
    truncate, truncate_default, validate_schema_version, Strategy,
};
use wasm_bindgen::prelude::*;

/// Parse a bare serde token (`"end"`/`"middle"`/`"start"`) into a `Strategy`.
fn parse_strategy(token: &str) -> Result<Strategy, String> {
    serde_json::from_value(serde_json::Value::String(token.to_string()))
        .map_err(|e| format!("parse: {e}"))
}

/// Truncate `input` to at most `max_chars` chars via the crate's real
/// `truncate`, inserting `ellipsis` at the `strategy` point. Returns JSON
/// `{"ok":true,"value":"<truncated>"}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn text_truncation_truncate(
    input: &str,
    max_chars: u32,
    strategy: &str,
    ellipsis: &str,
) -> String {
    let strat = match parse_strategy(strategy) {
        Ok(s) => s,
        Err(e) => return serde_json::json!({ "ok": false, "error": e }).to_string(),
    };
    match truncate(input, max_chars as usize, strat, ellipsis) {
        Ok(v) => serde_json::json!({ "ok": true, "value": serde_json::to_value(&v).unwrap() })
            .to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// Truncate with the default ellipsis ("…") via the crate's real
/// `truncate_default`. Returns JSON `{"ok":true,"value":"<truncated>"}`
/// or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn text_truncation_truncate_default(input: &str, max_chars: u32, strategy: &str) -> String {
    let strat = match parse_strategy(strategy) {
        Ok(s) => s,
        Err(e) => return serde_json::json!({ "ok": false, "error": e }).to_string(),
    };
    match truncate_default(input, max_chars as usize, strat) {
        Ok(v) => serde_json::json!({ "ok": true, "value": serde_json::to_value(&v).unwrap() })
            .to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// Run the crate's real `validate_schema_version`. Returns JSON
/// `{"ok":true,"error":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn text_truncation_validate_schema_version(s: &str) -> String {
    match validate_schema_version(s) {
        Ok(()) => serde_json::json!({ "ok": true, "error": serde_json::Value::Null }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
