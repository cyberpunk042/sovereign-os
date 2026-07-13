//! Bespoke wasm bridge for `sovereign-cockpit-pagination` (no uniform validate()).
//! `Pager` is a stateful value type; this exposes its real constructor + derived
//! state + transitions (new / info / next / prev / goto), plus `total_pages_for`
//! and `validate_schema_version`, so the pager panel runs the crate's REAL page
//! arithmetic instead of a drifting JS re-implementation (F-2026-001).
use sovereign_cockpit_pagination::{total_pages_for, validate_schema_version, Pager};
use wasm_bindgen::prelude::*;

/// Parse a `Pager` from JSON, then re-run it through the crate's REAL `Pager::new`
/// so the invariants (per_page >= 1, page clamped) are enforced exactly as the
/// crate guarantees — and a `per_page == 0` state can never underflow `info()`.
fn load_pager(json: &str) -> Result<Pager, String> {
    let raw: Pager = serde_json::from_str(json).map_err(|e| format!("parse: {e}"))?;
    Pager::new(raw.page, raw.per_page, raw.total).map_err(|e| e.to_string())
}

/// Real `total_pages_for` (ceil(total/per_page), 0 when total = 0). u64 args pass
/// as `f64` cast (saturating) to `u64`. Returns JSON `{"value": <u64>}`.
#[wasm_bindgen]
pub fn pagination_total_pages_for(total: f64, per_page: f64) -> String {
    serde_json::json!({ "value": total_pages_for(total as u64, per_page as u64) }).to_string()
}

/// Construct a validated `Pager` via the crate's real `Pager::new`. Returns JSON
/// `{"ok":true,"value": <Pager>}` or `{"ok":false,"error":"..."}` (per_page = 0).
#[wasm_bindgen]
pub fn pagination_new(page: f64, per_page: f64, total: f64) -> String {
    match Pager::new(page as u64, per_page as u64, total as u64) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// Derived `PageInfo` (total_pages, can_prev/next, range) via the crate's real
/// `Pager::info`. Returns JSON `{"ok":true,"value": <PageInfo>}` or an error.
#[wasm_bindgen]
pub fn pagination_info(pager_json: &str) -> String {
    match load_pager(pager_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.info()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Step forward one page (no-op at last page) via the crate's real `Pager::next`.
/// Returns JSON `{"ok":true,"value": <Pager>}` or an error.
#[wasm_bindgen]
pub fn pagination_next(pager_json: &str) -> String {
    match load_pager(pager_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.next()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Step back one page (no-op at first page) via the crate's real `Pager::prev`.
/// Returns JSON `{"ok":true,"value": <Pager>}` or an error.
#[wasm_bindgen]
pub fn pagination_prev(pager_json: &str) -> String {
    match load_pager(pager_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.prev()).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Jump to a page (clamped into range) via the crate's real `Pager::goto`. `page`
/// passes as `f64` cast to `u64`. Returns JSON `{"ok":true,"value": <Pager>}`.
#[wasm_bindgen]
pub fn pagination_goto(pager_json: &str, page: f64) -> String {
    match load_pager(pager_json) {
        Ok(p) => serde_json::json!({ "ok": true, "value": serde_json::to_value(p.goto(page as u64)).unwrap_or(serde_json::Value::Null) }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}

/// Run the crate's real `validate_schema_version`. Returns JSON
/// `{"ok":true,"value":null}` on match, `{"ok":false,"error":"..."}` on drift.
#[wasm_bindgen]
pub fn pagination_validate_schema_version(schema_version: &str) -> String {
    match validate_schema_version(schema_version) {
        Ok(()) => serde_json::json!({ "ok": true, "value": serde_json::Value::Null }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
