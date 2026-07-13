//! Bespoke wasm bridge for `sovereign-cockpit-guardian-panel` (no uniform
//! validate()). Exposes the PURE decision fns — `Entry::all_steps_ok` plus the
//! panel's any_failed / aggregate_color / aggregate_badge / render — over
//! already-parsed state so the M066 panel runs the crate's REAL logic
//! (F-2026-001). The fs loader `Panel::load_from_paths` is NOT bridged (disk).
use sovereign_cockpit_guardian_panel::{Entry, Panel};
use wasm_bindgen::prelude::*;

/// Parse a `Panel` from JSON, mapping a parse failure to a readable error.
fn load_panel(json: &str) -> Result<Panel, String> {
    serde_json::from_str::<Panel>(json).map_err(|e| format!("parse: {e}"))
}

/// Whether all three response steps completed (Ok/Skipped, not Failed) for one
/// verdict, via the crate's real `Entry::all_steps_ok`. Takes an `Entry` JSON.
/// Returns JSON `{"ok":true,"value": <bool>}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn guardian_panel_all_steps_ok(entry_json: &str) -> String {
    match serde_json::from_str::<Entry>(entry_json) {
        Ok(e) => serde_json::json!({ "ok": true, "value": e.all_steps_ok() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Whether any verdict had a failed step, via the crate's real `Panel::any_failed`.
/// Returns JSON `{"ok":true,"value": <bool>}` or an error.
#[wasm_bindgen]
pub fn guardian_panel_any_failed(panel_json: &str) -> String {
    match load_panel(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": p.any_failed() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Top-row color, via the crate's real `Panel::aggregate_color`.
/// Returns JSON `{"ok":true,"value": <color-token>}` or an error.
#[wasm_bindgen]
pub fn guardian_panel_aggregate(panel_json: &str) -> String {
    match load_panel(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.aggregate_color()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Aggregate badge text (OK/DEGRADED/ALERT/—), via the crate's real
/// `Panel::aggregate_badge`. Returns JSON `{"ok":true,"value": <badge>}` or an error.
#[wasm_bindgen]
pub fn guardian_panel_badge(panel_json: &str) -> String {
    match load_panel(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": p.aggregate_badge() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// The M066 render-row sequence (aggregate first, then verdicts), via the crate's
/// real `Panel::render`. Returns JSON `{"ok":true,"value": [RenderRow,...]}` or an error.
#[wasm_bindgen]
pub fn guardian_panel_render(panel_json: &str) -> String {
    match load_panel(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.render()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}
