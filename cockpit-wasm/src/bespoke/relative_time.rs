//! Bespoke wasm bridge for `sovereign-cockpit-relative-time` (no uniform validate()).
//! Exposes the crate's REAL relative-time formatter/classifier so the panel renders
//! the same "X ago / in X / on YYYY-MM-DD" ladder the crate defines (F-2026-001),
//! instead of a drifting JS re-implementation.
//!
//! Clock note: the crate is pure arithmetic over an EXPLICIT `now_ms` — there is no
//! wall clock in wasm, so the caller passes the current epoch-ms as an `f64`
//! (epoch-ms exceeds u32; f64 represents it exactly below 2^53). No fs, no syscalls.
use sovereign_cockpit_relative_time::{classify, format, validate_schema_version};
use wasm_bindgen::prelude::*;

/// Render a timestamp as a human relative string ("5 minutes ago" / "in 3 hours"
/// / "on YYYY-MM-DD"), running the crate's real `format`. `now_ms`/`item_ms` are
/// epoch-ms passed as `f64`. Returns JSON `{"value":"<string>"}`.
#[wasm_bindgen]
pub fn relative_time_format(now_ms: f64, item_ms: f64) -> String {
    let s = format(now_ms as u64, item_ms as u64);
    serde_json::json!({ "value": s }).to_string()
}

/// Classify a timestamp's tense + absolute delta relative to `now` via the crate's
/// real `classify`. Returns JSON `{"tense":"now"|"past"|"future","delta_ms":<i64>}`.
#[wasm_bindgen]
pub fn relative_time_classify(now_ms: f64, item_ms: f64) -> String {
    let (tense, delta) = classify(now_ms as u64, item_ms as u64);
    let tense_tok = serde_json::to_value(tense).unwrap_or(serde_json::Value::Null);
    serde_json::json!({ "tense": tense_tok, "delta_ms": delta as i64 }).to_string()
}

/// Check a schema-version string against the crate's `SCHEMA_VERSION`.
/// Returns JSON `{"ok":true,"value":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn relative_time_validate_schema_version(s: &str) -> String {
    match validate_schema_version(s) {
        Ok(()) => serde_json::json!({ "ok": true, "value": serde_json::Value::Null }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
