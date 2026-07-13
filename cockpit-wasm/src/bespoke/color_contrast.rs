//! Bespoke wasm bridge for `sovereign-cockpit-color-contrast` (no uniform validate()).
//! Exposes the real `verdict` WCAG-2.1 contrast computation so the panel runs
//! the crate's REAL logic instead of a JS re-implementation (F-2026-001).
use sovereign_cockpit_color_contrast::{validate_schema_version, verdict, Rgb};
use wasm_bindgen::prelude::*;

/// Compute the WCAG-2.1 contrast verdict (ratio + AA/AAA pass flags) for a
/// foreground/background sRGB pair. `fg_json`/`bg_json` are `{"r","g","b"}`
/// (0..=255). Returns JSON `{"ratio","passes_aa","passes_aaa"}` on success or
/// `{"ok":false,"error":"..."}` on a parse error.
#[wasm_bindgen]
pub fn color_contrast_verdict(fg_json: &str, bg_json: &str, large_text: bool) -> String {
    let fg: Rgb = match serde_json::from_str(fg_json) {
        Ok(c) => c,
        Err(e) => {
            return serde_json::json!({"ok": false, "error": format!("parse: {}", e)}).to_string()
        }
    };
    let bg: Rgb = match serde_json::from_str(bg_json) {
        Ok(c) => c,
        Err(e) => {
            return serde_json::json!({"ok": false, "error": format!("parse: {}", e)}).to_string()
        }
    };
    let v = verdict(fg, bg, large_text);
    serde_json::to_string(&v).unwrap_or_else(|e| format!("{{\"error\":\"{}\"}}", e))
}

/// Validate a schema-version string against the crate's `SCHEMA_VERSION`.
/// Returns JSON `{"ok":true,"value":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn color_contrast_validate_schema_version(version: &str) -> String {
    match validate_schema_version(version) {
        Ok(()) => serde_json::json!({"ok": true, "value": serde_json::Value::Null}).to_string(),
        Err(e) => serde_json::json!({"ok": false, "error": e.to_string()}).to_string(),
    }
}
