//! Compute wrappers for `sovereign-cockpit-segmented-control` — expose its real
//! selection transitions (next / prev / select) to the panel via wasm, beyond
//! validate() (audit F-2026-001).
//!
//! `SegmentedControl` derives `Serialize + Deserialize`, so the state crosses the
//! wasm boundary as JSON. Mutations are functional: parse the state, apply the op
//! on a local copy, return the NEW state plus the resulting active id.
use sovereign_cockpit_segmented_control::SegmentedControl;
use wasm_bindgen::prelude::*;

/// Move the selection of a `SegmentedControl` (JSON). `op` is one of `"next"`,
/// `"prev"`, or `"select:<id>"`:
/// - `next` / `prev` walk to the adjacent ENABLED segment (wrapping) via the
///   crate's real `next()` / `prev()`.
/// - `select:<id>` jumps to `<id>` via the crate's real `select()` (must exist and
///   be enabled).
///
/// Returns JSON `{"ok":true,"selected":<active id>,"value":<new state>}`. An invalid
/// select id (unknown or disabled), an unknown `op`, or an unparseable state
/// returns `{"ok":false,"error":"..."}`. Never panics.
#[wasm_bindgen]
pub fn segmented_control_move(state_json: &str, op: &str) -> String {
    let mut ctrl: SegmentedControl = match serde_json::from_str(state_json) {
        Ok(c) => c,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    if op == "next" {
        ctrl.next();
    } else if op == "prev" {
        ctrl.prev();
    } else if let Some(id) = op.strip_prefix("select:") {
        if let Err(e) = ctrl.select(id) {
            return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string();
        }
    } else {
        return serde_json::json!({ "ok": false, "error": format!("unknown op: {op}") })
            .to_string();
    }
    serde_json::json!({
        "ok": true,
        "selected": ctrl.active,
        "value": serde_json::to_value(&ctrl).unwrap_or(serde_json::Value::Null),
    })
    .to_string()
}
