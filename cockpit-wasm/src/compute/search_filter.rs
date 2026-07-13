//! Compute wrappers for `sovereign-cockpit-search-filter` — expose its real resolved
//! filter spec (effective query + active facets + sort) to the panel via wasm,
//! beyond validate() (audit F-2026-001).
//!
//! `SearchFilter` derives `Serialize + Deserialize`, so the state crosses the wasm
//! boundary as JSON and the derived spec is built from the crate's own public
//! fields + accessors (`is_active`) — the panel gets the crate's canonical filter
//! spec instead of re-deriving it in drifting JS.
use sovereign_cockpit_search_filter::SearchFilter;
use wasm_bindgen::prelude::*;

/// Resolve a `SearchFilter` (JSON) to its canonical spec: the effective query, the
/// crate-ordered/deduped active facets, and the effective sort (`null` when
/// `sort_key` is empty — the crate ignores `sort_direction` there), plus the
/// `is_active()` flag. The state is first run through the crate's real `validate()`
/// so only a canonical filter yields a spec. Returns JSON
/// `{"ok":true,"spec":{...},"value":<validated state>}` or
/// `{"ok":false,"error":"..."}` on a parse or validate failure. Never panics.
#[wasm_bindgen]
pub fn search_filter_spec(state_json: &str) -> String {
    let filter: SearchFilter = match serde_json::from_str(state_json) {
        Ok(f) => f,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    if let Err(e) = filter.validate() {
        return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string();
    }
    // Effective sort: the crate ignores `sort_direction` when `sort_key` is empty.
    let sort = if filter.sort_key.is_empty() {
        serde_json::Value::Null
    } else {
        serde_json::json!({
            "key": filter.sort_key,
            "direction": serde_json::to_value(filter.sort_direction)
                .unwrap_or(serde_json::Value::Null),
        })
    };
    let spec = serde_json::json!({
        "query": filter.query_text,
        "facets": serde_json::to_value(&filter.facets).unwrap_or(serde_json::Value::Null),
        "sort": sort,
        "active": filter.is_active(),
    });
    serde_json::json!({
        "ok": true,
        "spec": spec,
        "value": serde_json::to_value(&filter).unwrap_or(serde_json::Value::Null),
    })
    .to_string()
}
