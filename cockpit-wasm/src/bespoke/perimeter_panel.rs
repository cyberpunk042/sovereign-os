//! Bespoke wasm bridge for `sovereign-cockpit-perimeter-panel` (no uniform
//! validate()). Exposes the panel's PURE decision fns (any_sigkill /
//! aggregate_color / aggregate_badge / render) over an already-parsed `Panel` so
//! the M061 panel runs the crate's REAL logic (F-2026-001). The fs loader
//! `Panel::load_from_paths` is intentionally NOT bridged — it touches disk.
use sovereign_cockpit_perimeter_panel::Panel;
use wasm_bindgen::prelude::*;

/// Parse a `Panel` from JSON, mapping a parse failure to a readable error.
fn load(json: &str) -> Result<Panel, String> {
    serde_json::from_str::<Panel>(json).map_err(|e| format!("parse: {e}"))
}

/// Whether any recent verdict is a SIGKILL, via the crate's real `Panel::any_sigkill`.
/// Returns JSON `{"ok":true,"value": <bool>}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn perimeter_panel_any_sigkill(panel_json: &str) -> String {
    match load(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": p.any_sigkill() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Top-row color, via the crate's real `Panel::aggregate_color`.
/// Returns JSON `{"ok":true,"value": <color-token>}` or an error.
#[wasm_bindgen]
pub fn perimeter_panel_aggregate(panel_json: &str) -> String {
    match load(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.aggregate_color()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Aggregate badge text (OK/EXTENDED/ALERT/—), via the crate's real
/// `Panel::aggregate_badge`. Returns JSON `{"ok":true,"value": <badge>}` or an error.
#[wasm_bindgen]
pub fn perimeter_panel_badge(panel_json: &str) -> String {
    match load(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": p.aggregate_badge() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// The M061 render-row sequence (aggregate, then extensions, then verdicts), via
/// the crate's real `Panel::render`. Returns JSON `{"ok":true,"value": [RenderRow,...]}`.
#[wasm_bindgen]
pub fn perimeter_panel_render(panel_json: &str) -> String {
    match load(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.render()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}
