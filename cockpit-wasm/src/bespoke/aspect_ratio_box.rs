//! Bespoke wasm bridge for `sovereign-cockpit-aspect-ratio-box` (no uniform validate()).
//! Exposes the real `fit` box-sizing computation so the panel runs the crate's
//! REAL logic instead of a JS re-implementation (F-2026-001).
use sovereign_cockpit_aspect_ratio_box::{fit, validate_schema_version};
use wasm_bindgen::prelude::*;

/// Compute the centered inner box for a target ratio `w_num:w_den` inside an
/// `outer_w x outer_h` container. Returns JSON `{"ok":true,"value":{x,y,w,h}}`
/// on success or `{"ok":false,"error":"..."}` on a domain error.
#[wasm_bindgen]
pub fn aspect_ratio_box_fit(outer_w: u32, outer_h: u32, w_num: u32, w_den: u32) -> String {
    match fit(outer_w, outer_h, w_num, w_den) {
        Ok(b) => serde_json::json!({
            "ok": true,
            "value": serde_json::to_value(b).unwrap()
        })
        .to_string(),
        Err(e) => serde_json::json!({"ok": false, "error": e.to_string()}).to_string(),
    }
}

/// Validate a schema-version string against the crate's `SCHEMA_VERSION`.
/// Returns JSON `{"ok":true,"value":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn aspect_ratio_box_validate_schema_version(version: &str) -> String {
    match validate_schema_version(version) {
        Ok(()) => serde_json::json!({"ok": true, "value": serde_json::Value::Null}).to_string(),
        Err(e) => serde_json::json!({"ok": false, "error": e.to_string()}).to_string(),
    }
}
