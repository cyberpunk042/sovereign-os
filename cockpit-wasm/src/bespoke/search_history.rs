//! Bespoke wasm bridge for `sovereign-cockpit-search-history` (no uniform validate()).
//! Exposes the crate's REAL recents ring buffer (construct / MRU record / read) so the
//! search bar runs the same dedup + capacity + trim state machine the crate defines
//! (F-2026-001), instead of a drifting JS re-implementation. No clock, no fs.
//!
//! The buffer is a value type: the browser round-trips the `SearchHistory` JSON through
//! `search_history_record` (stateless call, returns the updated history) to advance it.
use sovereign_cockpit_search_history::{validate_schema_version, DedupMode, SearchHistory};
use wasm_bindgen::prelude::*;

/// Construct a fresh history via the crate's real `SearchHistory::new`, which rejects
/// `capacity == 0`. `dedup` is the kebab token `"case-sensitive"`/`"case-insensitive"`.
/// Returns JSON `{"ok":true,"value":<history>}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn search_history_new(capacity: u32, dedup: &str) -> String {
    let mode: DedupMode = match serde_json::from_value(serde_json::Value::String(dedup.to_string()))
    {
        Ok(m) => m,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("dedup: {e}") }).to_string()
        }
    };
    match SearchHistory::new(capacity as usize, mode) {
        Ok(h) => serde_json::json!({
            "ok": true,
            "value": serde_json::to_value(&h).unwrap_or(serde_json::Value::Null),
        })
        .to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// Record an executed query via the crate's real `SearchHistory::record` (trim + dedup
/// + MRU move-to-head + capacity evict). Returns the UPDATED history plus whether it
/// changed: JSON `{"ok":true,"changed":<bool>,"history":<history>}`, or a parse error.
#[wasm_bindgen]
pub fn search_history_record(json: &str, query: &str) -> String {
    match serde_json::from_str::<SearchHistory>(json) {
        Ok(mut h) => {
            let changed = h.record(query);
            serde_json::json!({
                "ok": true,
                "changed": changed,
                "history": serde_json::to_value(&h).unwrap_or(serde_json::Value::Null),
            })
            .to_string()
        }
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Snapshot the stored entries (most-recent first) via the crate's real
/// `SearchHistory::entries`. Returns the JSON array of query strings, or a parse error.
#[wasm_bindgen]
pub fn search_history_entries(json: &str) -> String {
    match serde_json::from_str::<SearchHistory>(json) {
        Ok(h) => {
            serde_json::to_string(h.entries()).unwrap_or_else(|e| format!("{{\"error\":\"{e}\"}}"))
        }
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Read the capacity ceiling via the crate's real `SearchHistory::capacity`.
/// Returns JSON `{"value":<number>}`, or a parse error.
#[wasm_bindgen]
pub fn search_history_capacity(json: &str) -> String {
    match serde_json::from_str::<SearchHistory>(json) {
        Ok(h) => serde_json::json!({ "value": h.capacity() as u64 }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}

/// Check a schema-version string against the crate's `SCHEMA_VERSION`.
/// Returns JSON `{"ok":true,"value":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn search_history_validate_schema_version(s: &str) -> String {
    match validate_schema_version(s) {
        Ok(()) => serde_json::json!({ "ok": true, "value": serde_json::Value::Null }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
