//! Bespoke wasm bridge for `sovereign-cockpit-scheduler-panel` (no uniform validate()).
//! Exposes the panel's REAL render + decision aggregates so the cockpit runs the
//! crate's own row-building and color/backpressure/override rules (F-2026-001),
//! instead of a drifting JS re-implementation.
//!
//! FS note: the crate's `Panel::load_from_paths` reads the selfdef ring dir + audit
//! log off disk — there is no filesystem in wasm, so it is deliberately NOT bridged.
//! The browser feeds the already-loaded `Panel` / `Entry` JSON directly (exactly the
//! fs-boundary the crate is designed around); `Panel::now_ms` carries its own clock.
use sovereign_cockpit_scheduler_panel::{Entry, Panel};
use wasm_bindgen::prelude::*;

/// Build the cockpit row sequence (aggregate + 6 backpressure surfaces + decisions)
/// via the crate's real `Panel::render`. Returns the JSON array of render rows, or
/// `{"ok":false,"error":"parse: ..."}` if the panel JSON is malformed.
#[wasm_bindgen]
pub fn scheduler_panel_render(panel_json: &str) -> String {
    match serde_json::from_str::<Panel>(panel_json) {
        Ok(panel) => serde_json::to_string(&panel.render())
            .unwrap_or_else(|e| format!("{{\"error\":\"{e}\"}}")),
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Real `Panel::aggregate_color` — the top-row color semantic.
/// Returns a JSON string token (`"green"`/`"yellow"`/`"red"`/`"gray"`), or a
/// `{"ok":false,"error":"parse: ..."}` object on malformed input.
#[wasm_bindgen]
pub fn scheduler_panel_aggregate_color(panel_json: &str) -> String {
    match serde_json::from_str::<Panel>(panel_json) {
        Ok(panel) => serde_json::to_string(&panel.aggregate_color())
            .unwrap_or_else(|e| format!("{{\"error\":\"{e}\"}}")),
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Real `Panel::aggregate_badge` — the top-row badge text.
/// Returns JSON `{"value":"OK"|"OVERRIDE"|"BACKPRESSURE"|"ALERT"|"—"}`.
#[wasm_bindgen]
pub fn scheduler_panel_aggregate_badge(panel_json: &str) -> String {
    match serde_json::from_str::<Panel>(panel_json) {
        Ok(panel) => serde_json::json!({ "value": panel.aggregate_badge() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Real `Panel::any_backpressure` — whether any recent decision hit backpressure.
/// Returns JSON `{"value":<bool>}`.
#[wasm_bindgen]
pub fn scheduler_panel_any_backpressure(panel_json: &str) -> String {
    match serde_json::from_str::<Panel>(panel_json) {
        Ok(panel) => serde_json::json!({ "value": panel.any_backpressure() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Real `Panel::any_overridden` — whether any recent decision was force-overridden.
/// Returns JSON `{"value":<bool>}`.
#[wasm_bindgen]
pub fn scheduler_panel_any_overridden(panel_json: &str) -> String {
    match serde_json::from_str::<Panel>(panel_json) {
        Ok(panel) => serde_json::json!({ "value": panel.any_overridden() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Real `Entry::is_overridden` — whether a single decision was operator-overridden.
/// Returns JSON `{"value":<bool>}`.
#[wasm_bindgen]
pub fn scheduler_panel_entry_is_overridden(entry_json: &str) -> String {
    match serde_json::from_str::<Entry>(entry_json) {
        Ok(entry) => serde_json::json!({ "value": entry.is_overridden() }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}
