//! Bespoke wasm bridge for `sovereign-cockpit-views` (no uniform validate()).
//! Exposes the E0496 §10 cockpit-coverage gate so the panel runs the crate's
//! REAL `missing_views`/`is_complete` logic (F-2026-001) instead of a JS copy of
//! the required-views set.
use sovereign_cockpit_views::{CockpitCoverage, CockpitView};
use wasm_bindgen::prelude::*;

/// Evaluate a `CockpitCoverage` (JSON `{"surfaced":[...]}`) against the 7
/// required views via the crate's real `missing_views` + `is_complete`.
/// Returns JSON `{"missing":[<kebab tokens>],"complete":bool}` or
/// `{"ok":false,"error":"parse: ..."}` if the coverage JSON is unparseable.
#[wasm_bindgen]
pub fn views_coverage(coverage_json: &str) -> String {
    let coverage: CockpitCoverage = match serde_json::from_str(coverage_json) {
        Ok(c) => c,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let missing = coverage.missing_views();
    let complete = coverage.is_complete();
    serde_json::json!({
        "missing": serde_json::to_value(&missing).unwrap(),
        "complete": complete,
    })
    .to_string()
}

/// Record that `view` (a kebab token, e.g. `"what-can-be-rolled-back"`) is
/// surfaced on a `CockpitCoverage` (JSON) via the crate's real `surface`.
/// Returns JSON `{"ok":true,"value":<new coverage>}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn views_surface(coverage_json: &str, view: &str) -> String {
    let mut coverage: CockpitCoverage = match serde_json::from_str(coverage_json) {
        Ok(c) => c,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let v: CockpitView = match serde_json::from_value(serde_json::Value::String(view.to_string())) {
        Ok(v) => v,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    coverage.surface(v);
    serde_json::json!({ "ok": true, "value": serde_json::to_value(&coverage).unwrap() }).to_string()
}
