//! Compute wrappers for `sovereign-cockpit-filter-state` — expose its real staged
//! apply (pending → applied) to the panel via wasm, beyond validate() (audit
//! F-2026-001).
//!
//! `FilterState` derives `Serialize + Deserialize`, so the state crosses the wasm
//! boundary as JSON. The mutation is functional: parse the state, run the crate's
//! real `apply()` on a local copy, return the NEW state.
use sovereign_cockpit_filter_state::FilterState;
use wasm_bindgen::prelude::*;

/// Commit the pending edits of a `FilterState` (JSON) via the crate's real
/// `apply()` (copies `pending` → `applied`, clearing the dirty flag). Functional:
/// mutates a local copy and returns the NEW state. Returns JSON
/// `{"ok":true,"value":<new state>}` or `{"ok":false,"error":"parse: ..."}` if the
/// state JSON is unparseable. Never panics.
#[wasm_bindgen]
pub fn filter_state_apply(state_json: &str) -> String {
    let mut state: FilterState = match serde_json::from_str(state_json) {
        Ok(s) => s,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    state.apply();
    serde_json::json!({
        "ok": true,
        "value": serde_json::to_value(&state).unwrap_or(serde_json::Value::Null),
    })
    .to_string()
}
