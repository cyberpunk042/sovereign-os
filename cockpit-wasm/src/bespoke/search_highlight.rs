//! Bespoke wasm bridge for `sovereign-cockpit-search-highlight` (no uniform validate()).
//! Exposes the crate's REAL subsequence highlighter + range validator so the panel
//! computes highlight ranges with the same Rust logic the daemon uses (F-2026-001),
//! instead of a drifting JS re-implementation. No clock, no fs.
//!
//! NOTE: `HighlightResult::validate` takes an EXTRA `haystack_len` arg, so it can't
//! use the uniform `validate(&self)` bridge — it is exposed as
//! `search_highlight_validate(json, haystack_len)` per the audit's bespoke path.
use sovereign_cockpit_search_highlight::{HighlightResult, SearchHighlight};
use wasm_bindgen::prelude::*;

/// Compute the highlight ranges for `query` against `haystack` via the crate's real
/// greedy subsequence matcher `SearchHighlight::highlight`. Returns the serialized
/// `HighlightResult` JSON (`{"schema_version","ranges":[{start,end}...],"matched_all"}`).
#[wasm_bindgen]
pub fn search_highlight_highlight(query: &str, haystack: &str) -> String {
    let result = SearchHighlight::highlight(query, haystack);
    serde_json::to_string(&result).unwrap_or_else(|e| format!("{{\"error\":\"{e}\"}}"))
}

/// Validate a `HighlightResult` JSON against a haystack length via the crate's real
/// `HighlightResult::validate(haystack_len)` (checks schema + in-bounds + non-overlap).
/// `haystack_len` is the byte length, passed as `u32` and cast to `usize`.
/// Returns JSON `{"ok":true,"value":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn search_highlight_validate(json: &str, haystack_len: u32) -> String {
    match serde_json::from_str::<HighlightResult>(json) {
        Ok(result) => match result.validate(haystack_len as usize) {
            Ok(()) => {
                serde_json::json!({ "ok": true, "value": serde_json::Value::Null }).to_string()
            }
            Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
        },
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}
