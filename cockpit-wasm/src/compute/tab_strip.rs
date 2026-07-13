//! Compute wrapper for `sovereign-cockpit-tab-strip` — expose its real `activate()` transition
//! (validate the tab id, move the active pointer) to the panel via wasm, so a panel's tab bar
//! can make the crate the source of truth for which tab is active (audit F-2026-001).
use sovereign_cockpit_tab_strip::TabStrip;
use wasm_bindgen::prelude::*;

/// Activate the tab `id` in a `TabStrip` (JSON) via the crate's real `activate()`, which
/// REJECTS an unknown id (the invariant a hand-rolled tab bar can silently violate). Returns
/// `{"ok":true,"active_id":<id|null>,"value":<new state>}`, or `{"ok":false,"error":"..."}` on
/// an unknown id / unparseable state. Never panics.
#[wasm_bindgen]
pub fn tab_strip_activate(state_json: &str, id: &str) -> String {
    let mut strip: TabStrip = match serde_json::from_str(state_json) {
        Ok(s) => s,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    if let Err(e) = strip.activate(id) {
        return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string();
    }
    serde_json::json!({
        "ok": true,
        "active_id": strip.active_tab().map(|t| t.id.clone()),
        "value": serde_json::to_value(&strip).unwrap_or(serde_json::Value::Null),
    })
    .to_string()
}
