//! Compute wrapper for `sovereign-cockpit-keystroke-map` — resolve a keyboard chord to its
//! bound `action_id` via the crate's real `resolve()` (scope match, then Global fallback), so
//! the shared app-shell can make the crate the source of truth for its shortcuts (F-2026-001).
use sovereign_cockpit_keystroke_map::{KeystrokeMap, Modifiers, Scope};
use wasm_bindgen::prelude::*;

/// Resolve `(scope, ctrl/shift/alt/meta, key)` against a `KeystrokeMap` (JSON) via the crate's
/// real `resolve()`. Returns `{"ok":true,"action_id":<id|null>}`, or `{"ok":false,"error":"..."}`
/// on an unparseable map. Unknown scope falls back to `global`. Never panics.
#[wasm_bindgen]
pub fn keystroke_map_resolve(
    map_json: &str,
    scope: &str,
    ctrl: bool,
    shift: bool,
    alt: bool,
    meta: bool,
    key: &str,
) -> String {
    let map: KeystrokeMap = match serde_json::from_str(map_json) {
        Ok(m) => m,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let sc: Scope = serde_json::from_value(serde_json::Value::String(scope.to_string()))
        .unwrap_or(Scope::Global);
    let action = map.resolve(sc, Modifiers { ctrl, shift, alt, meta }, key);
    serde_json::json!({ "ok": true, "action_id": action }).to_string()
}
