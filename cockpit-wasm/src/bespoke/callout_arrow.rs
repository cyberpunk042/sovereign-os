//! Bespoke wasm bridge for `sovereign-cockpit-callout-arrow` (no uniform validate()).
//! Exposes the real `place` arrow-placement computation so the panel runs the
//! crate's REAL logic instead of a JS re-implementation (F-2026-001).
use sovereign_cockpit_callout_arrow::{place, validate_schema_version, Rect};
use wasm_bindgen::prelude::*;

/// Decide which balloon side an arrow protrudes from and its clamped edge
/// offset toward a target point. `balloon_json` is `{"x","y","w","h"}` (i32).
/// Returns JSON `{"ok":true,"value":{"side","offset"}}` on success or
/// `{"ok":false,"error":"..."}` on a parse/domain error.
#[wasm_bindgen]
pub fn callout_arrow_place(
    balloon_json: &str,
    target_x: i32,
    target_y: i32,
    arrow_margin: i32,
) -> String {
    let balloon: Rect = match serde_json::from_str(balloon_json) {
        Ok(r) => r,
        Err(e) => {
            return serde_json::json!({"ok": false, "error": format!("parse: {}", e)}).to_string()
        }
    };
    match place(balloon, target_x, target_y, arrow_margin) {
        Ok(p) => serde_json::json!({
            "ok": true,
            "value": serde_json::to_value(p).unwrap()
        })
        .to_string(),
        Err(e) => serde_json::json!({"ok": false, "error": e.to_string()}).to_string(),
    }
}

/// Validate a schema-version string against the crate's `SCHEMA_VERSION`.
/// Returns JSON `{"ok":true,"value":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn callout_arrow_validate_schema_version(version: &str) -> String {
    match validate_schema_version(version) {
        Ok(()) => serde_json::json!({"ok": true, "value": serde_json::Value::Null}).to_string(),
        Err(e) => serde_json::json!({"ok": false, "error": e.to_string()}).to_string(),
    }
}
