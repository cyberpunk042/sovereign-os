//! Compute wrapper for `sovereign-cockpit-checklist` — expose its real complete/uncomplete +
//! progress rollup so a panel's checklist makes the crate the source of truth for done-state and
//! progress (audit F-2026-001).
use sovereign_cockpit_checklist::Checklist;
use wasm_bindgen::prelude::*;

/// Toggle item `id` in a `Checklist` (JSON): if `currently_done`, uncomplete it, else complete
/// it at `ts_ms`. Runs the crate's real `complete()`/`uncomplete()` (rejecting an unknown id) and
/// `progress()`/`percent()`. Returns `{"ok":true,"done":usize,"total":usize,"percent":u8,
/// "value":<new state>}`, or `{"ok":false,"error":"..."}`. Never panics.
#[wasm_bindgen]
pub fn checklist_toggle(state_json: &str, id: &str, ts_ms: f64, currently_done: bool) -> String {
    let mut list: Checklist = match serde_json::from_str(state_json) {
        Ok(l) => l,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let res = if currently_done {
        list.uncomplete(id)
    } else {
        list.complete(id, ts_ms.max(0.0) as u64)
    };
    if let Err(e) = res {
        return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string();
    }
    let (done, total) = list.progress();
    serde_json::json!({
        "ok": true,
        "done": done,
        "total": total,
        "percent": list.percent(),
        "value": serde_json::to_value(&list).unwrap_or(serde_json::Value::Null),
    })
    .to_string()
}
