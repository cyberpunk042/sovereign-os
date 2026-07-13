//! Compute wrapper for `sovereign-cockpit-autocomplete-list` — expose its real highlight
//! navigation (`arrow_down` / `arrow_up`, wrap-around) so a command-palette-style list can
//! make the crate the source of truth for its keyboard cursor (audit F-2026-001).
use sovereign_cockpit_autocomplete_list::AutocompleteList;
use wasm_bindgen::prelude::*;

/// Move the highlight of an `AutocompleteList` (JSON) via the crate's real `arrow_down()` /
/// `arrow_up()` (which WRAP around the ends). `op` is `"down"` or `"up"`. Returns
/// `{"ok":true,"highlight":<index|null>,"value":<new state>}`, or `{"ok":false,"error":"..."}`
/// on an unknown op / unparseable state. Never panics.
#[wasm_bindgen]
pub fn autocomplete_nav(state_json: &str, op: &str) -> String {
    let mut list: AutocompleteList = match serde_json::from_str(state_json) {
        Ok(l) => l,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    match op {
        "down" => list.arrow_down(),
        "up" => list.arrow_up(),
        _ => {
            return serde_json::json!({ "ok": false, "error": format!("unknown op: {op}") })
                .to_string()
        }
    }
    serde_json::json!({
        "ok": true,
        "highlight": list.highlight,
        "value": serde_json::to_value(&list).unwrap_or(serde_json::Value::Null),
    })
    .to_string()
}
