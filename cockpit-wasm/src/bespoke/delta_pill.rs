//! Bespoke wasm bridge for `sovereign-cockpit-delta-pill` (no uniform validate()).
//! Exposes `render` (the real Up/Flat/Down + sentiment + magnitude decision) and
//! `validate_schema_version` so the delta-pill panel runs the crate's REAL logic
//! instead of a drifting JS re-implementation (F-2026-001).
use sovereign_cockpit_delta_pill::{render, validate_schema_version};
use wasm_bindgen::prelude::*;

/// Compute the colored `Pill` from current/prior values, running the crate's real
/// `render`. The crate takes `i64`s; wasm passes `f64`s cast (saturating) to `i64`.
/// Returns the `Pill` JSON (`{direction,sentiment,label,magnitude_bp}`).
#[wasm_bindgen]
pub fn delta_pill_render(
    current: f64,
    prior: f64,
    flat_threshold: f64,
    invert_polarity: bool,
) -> String {
    let pill = render(
        current as i64,
        prior as i64,
        flat_threshold as i64,
        invert_polarity,
    );
    serde_json::to_string(&pill).unwrap_or_else(|e| format!("{{\"error\":\"{}\"}}", e))
}

/// Run the crate's real `validate_schema_version`. Returns JSON
/// `{"ok":true,"value":null}` on match, `{"ok":false,"error":"..."}` on drift.
#[wasm_bindgen]
pub fn delta_pill_validate_schema_version(schema_version: &str) -> String {
    match validate_schema_version(schema_version) {
        Ok(()) => serde_json::json!({ "ok": true, "value": serde_json::Value::Null }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
