//! Bespoke wasm bridge for `sovereign-cockpit-day-divider` (no uniform validate()).
//! Exposes the real `classify`/`group` bucket-by-day logic so the panel runs
//! the crate's REAL logic instead of a JS re-implementation (F-2026-001).
use sovereign_cockpit_day_divider::{classify, group, validate_schema_version};
use wasm_bindgen::prelude::*;

/// Classify an item timestamp (ms) into a day bucket relative to `now_ms` (ms).
/// Args are `f64` (JS numbers) cast to `u64`. Returns the bucket as a JSON
/// string, e.g. `"today"`, `"yesterday"`, `"earlier-this-week"`, `"older"`.
#[wasm_bindgen]
pub fn day_divider_classify(now_ms: f64, item_ms: f64) -> String {
    let bucket = classify(now_ms as u64, item_ms as u64);
    serde_json::to_string(&bucket).unwrap_or_else(|e| format!("{{\"error\":\"{}\"}}", e))
}

/// Group newest-first item timestamps into contiguous `(bucket, [ms...])` runs
/// relative to `now_ms`. `items_json` is a JSON array of ms timestamps.
/// Returns a JSON array of `[bucket, [ms...]]` pairs on success or
/// `{"ok":false,"error":"..."}` on a parse error.
#[wasm_bindgen]
pub fn day_divider_group(now_ms: f64, items_json: &str) -> String {
    let items: Vec<u64> = match serde_json::from_str(items_json) {
        Ok(v) => v,
        Err(e) => {
            return serde_json::json!({"ok": false, "error": format!("parse: {}", e)}).to_string()
        }
    };
    let grouped = group(now_ms as u64, &items);
    serde_json::to_string(&grouped).unwrap_or_else(|e| format!("{{\"error\":\"{}\"}}", e))
}

/// Validate a schema-version string against the crate's `SCHEMA_VERSION`.
/// Returns JSON `{"ok":true,"value":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn day_divider_validate_schema_version(version: &str) -> String {
    match validate_schema_version(version) {
        Ok(()) => serde_json::json!({"ok": true, "value": serde_json::Value::Null}).to_string(),
        Err(e) => serde_json::json!({"ok": false, "error": e.to_string()}).to_string(),
    }
}
