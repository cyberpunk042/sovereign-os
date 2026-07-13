//! Bespoke wasm bridge for `sovereign-cockpit-friction-audit-panel` (no uniform
//! validate()). Exposes the panel's PURE decision fns (any_failing /
//! aggregate_color / render) over an already-parsed `Panel` so the M060 panel
//! runs the crate's REAL logic (F-2026-001). The fs loader `Panel::load_from_ring`
//! is intentionally NOT bridged — it touches disk and has no place in wasm.
use sovereign_cockpit_friction_audit_panel::Panel;
use wasm_bindgen::prelude::*;

/// Parse a `Panel` from JSON, mapping a parse failure to a readable error.
fn load(json: &str) -> Result<Panel, String> {
    serde_json::from_str::<Panel>(json).map_err(|e| format!("parse: {e}"))
}

/// Whether any gate is currently FAIL, via the crate's real `Panel::any_failing`.
/// Returns JSON `{"ok":true,"value": <bool>}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn friction_audit_panel_any_failing(panel_json: &str) -> String {
    match load(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": p.any_failing() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Worst-of-all top-row color, via the crate's real `Panel::aggregate_color`.
/// Returns JSON `{"ok":true,"value": <color-token>}` or an error.
#[wasm_bindgen]
pub fn friction_audit_panel_aggregate(panel_json: &str) -> String {
    match load(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.aggregate_color()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// The M060 render-row sequence, via the crate's real `Panel::render`.
/// Returns JSON `{"ok":true,"value": [RenderRow,...]}` or an error.
#[wasm_bindgen]
pub fn friction_audit_panel_render(panel_json: &str) -> String {
    match load(panel_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.render()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}
