//! Compute wrappers for `sovereign-cockpit-multi-select-list` — expose its real
//! click-driven selection to the panel via wasm, beyond validate()
//! (audit F-2026-001).
//!
//! The panel holds the list state (items + anchor + selected); this parses it,
//! replays a sequence of clicks through the crate's own `click()` — where the
//! plain / ctrl-toggle / shift-range logic actually lives (range select reads
//! the real anchor) — and returns the resulting selection, so the panel never
//! re-implements range-select in drifting JS.
use sovereign_cockpit_multi_select_list::{ClickKind, MultiSelectList};
use wasm_bindgen::prelude::*;

/// Replay clicks over a `MultiSelectList` via the crate's real `click()`.
/// `list_json` is a serialized `MultiSelectList`
/// (`{"schema_version":"1.0.0","items":[...],"anchor":null,"selected":[...]}`);
/// `clicks_json` is `[{"id":"<item>","kind":"plain"|"toggle"|"range"}, ...]`
/// applied in order (this is where the crate's shift/ctrl range-select runs).
/// Returns `{"selected":[...sorted ids],"count":<n>}` on success, or
/// `{"ok":false,"error":"..."}` on a parse / unknown-token / unknown-id error —
/// never panics.
#[wasm_bindgen]
pub fn multi_select_apply(list_json: &str, clicks_json: &str) -> String {
    let mut list = match serde_json::from_str::<MultiSelectList>(list_json) {
        Ok(l) => l,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse list: {e}") })
                .to_string();
        }
    };
    let clicks = match serde_json::from_str::<serde_json::Value>(clicks_json) {
        Ok(serde_json::Value::Array(items)) => items,
        Ok(_) => {
            return serde_json::json!({ "ok": false, "error": "clicks: expected a JSON array" })
                .to_string();
        }
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse clicks: {e}") })
                .to_string();
        }
    };
    for (i, click) in clicks.iter().enumerate() {
        let id = match click.get("id").and_then(serde_json::Value::as_str) {
            Some(s) => s,
            None => {
                return serde_json::json!({
                    "ok": false,
                    "error": format!("clicks[{i}]: missing string field \"id\"")
                })
                .to_string();
            }
        };
        let kind_token = match click.get("kind").and_then(serde_json::Value::as_str) {
            Some(s) => s,
            None => {
                return serde_json::json!({
                    "ok": false,
                    "error": format!("clicks[{i}]: missing string field \"kind\"")
                })
                .to_string();
            }
        };
        // Cross the enum as its serde kebab token, exactly like the rest of the
        // bridge — an unknown token is a readable error, never a panic.
        let kind: ClickKind =
            match serde_json::from_value(serde_json::Value::String(kind_token.to_string())) {
                Ok(k) => k,
                Err(_) => {
                    return serde_json::json!({
                        "ok": false,
                        "error": format!("clicks[{i}]: unknown kind {kind_token:?}")
                    })
                    .to_string();
                }
            };
        if let Err(e) = list.click(id, kind) {
            return serde_json::json!({ "ok": false, "error": format!("clicks[{i}]: {e}") })
                .to_string();
        }
    }
    // `selected` is a BTreeSet, so iteration is already sorted.
    let selected: Vec<&String> = list.selected.iter().collect();
    serde_json::json!({ "selected": selected, "count": list.count() }).to_string()
}
