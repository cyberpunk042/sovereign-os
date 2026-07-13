//! Compute wrappers for `sovereign-cockpit-radio-group` — expose its real selection
//! transitions (arrow navigation / select) to the panel via wasm, beyond validate()
//! (audit F-2026-001).
//!
//! `RadioGroup` derives `Serialize + Deserialize` and `Arrow` crosses as its serde
//! kebab tokens, so the state crosses the wasm boundary as JSON. Mutations are
//! functional: parse the state, apply the op on a local copy, return the NEW state
//! plus the resulting selection and its form-validity.
use sovereign_cockpit_radio_group::{Arrow, RadioGroup};
use wasm_bindgen::prelude::*;

/// Move the selection of a `RadioGroup` (JSON). `target` is either an arrow token
/// (`"up"` / `"left"` → `Arrow::Prev`, `"down"` / `"right"` → `Arrow::Next`) which
/// walks to the adjacent ENABLED option (wrapping) via the crate's real `arrow()`,
/// or any other value which is treated as an option id and passed to the crate's
/// real `select()` (must exist and be enabled).
///
/// Returns JSON `{"ok":true,"selected":<id|null>,"valid":<is_valid()>,"value":
/// <new state>}`. A bad id (unknown or disabled) or an unparseable state returns
/// `{"ok":false,"error":"..."}`. Never panics.
#[wasm_bindgen]
pub fn radio_group_select(state_json: &str, target: &str) -> String {
    let mut group: RadioGroup = match serde_json::from_str(state_json) {
        Ok(g) => g,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    match target {
        "up" | "left" => {
            group.arrow(Arrow::Prev);
        }
        "down" | "right" => {
            group.arrow(Arrow::Next);
        }
        id => {
            if let Err(e) = group.select(id) {
                return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string();
            }
        }
    }
    serde_json::json!({
        "ok": true,
        "selected": serde_json::to_value(&group.selected).unwrap_or(serde_json::Value::Null),
        "valid": group.is_valid(),
        "value": serde_json::to_value(&group).unwrap_or(serde_json::Value::Null),
    })
    .to_string()
}
