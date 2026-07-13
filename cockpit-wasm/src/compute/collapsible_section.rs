//! Compute wrapper for `sovereign-cockpit-collapsible-section` — expose its real per-section
//! collapse toggle so a panel's foldable sections make the crate the source of truth for their
//! open/closed state (audit F-2026-001).
use sovereign_cockpit_collapsible_section::CollapsibleState;
use wasm_bindgen::prelude::*;

/// Toggle section `id` in a `CollapsibleState` (JSON) via the crate's real `toggle()`. Returns
/// `{"ok":true,"collapsed":<bool>,"value":<new state>}` (the new collapsed flag), or
/// `{"ok":false,"error":"..."}` on an empty id / unparseable state. Never panics.
#[wasm_bindgen]
pub fn collapsible_toggle(state_json: &str, id: &str) -> String {
    let mut st: CollapsibleState = match serde_json::from_str(state_json) {
        Ok(s) => s,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    match st.toggle(id) {
        Ok(collapsed) => serde_json::json!({
            "ok": true,
            "collapsed": collapsed,
            "value": serde_json::to_value(&st).unwrap_or(serde_json::Value::Null),
        })
        .to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
