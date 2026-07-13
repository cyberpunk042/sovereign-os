//! Compute wrapper for `sovereign-cockpit-status-aggregator` — roll N subsystem statuses
//! into one headline + percentage breakdown via wasm, beyond validate() (F-2026-001).
use sovereign_cockpit_status_aggregator::{StatusAggregator, Subsystem};
use wasm_bindgen::prelude::*;

/// `subsystems_json` is a JSON array of `{"id","name","status"}` where status is one of
/// `ok|degraded|unknown|down`. Returns the crate's real
/// `{"ok":true,"headline":"...","percentages":{ok,degraded,unknown,down}}`.
/// A parse error or empty/invalid set returns `{"ok":false,"error":"..."}`. Never panics.
#[wasm_bindgen]
pub fn status_aggregator_headline(subsystems_json: &str) -> String {
    let subs: Vec<Subsystem> = match serde_json::from_str(subsystems_json) {
        Ok(v) => v,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let agg = match StatusAggregator::new(subs) {
        Ok(a) => a,
        Err(e) => return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    };
    serde_json::json!({
        "ok": true,
        "headline": serde_json::to_value(agg.headline()).unwrap_or(serde_json::Value::Null),
        "percentages": serde_json::to_value(agg.percentages()).unwrap_or(serde_json::Value::Null),
    })
    .to_string()
}
