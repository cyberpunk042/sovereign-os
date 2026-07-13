//! Compute wrapper for `sovereign-cockpit-stat-trend` — compute a (previous, current) trend
//! (direction + percent change + color hint) via wasm, beyond validate() (F-2026-001).
use sovereign_cockpit_stat_trend::{Polarity, StatTrend};
use wasm_bindgen::prelude::*;

/// Compute the trend from `previous` -> `current`. `polarity` is `higher-better`,
/// `lower-better`, or `neutral` (which direction counts as "good"). `flat_threshold_x100`
/// is the dead-band in basis-points×100 (50 = 0.50%). Returns the crate's real
/// `{"ok":true,"direction":"up|down|flat","percent_change_x100":i32,"color_hint":"..."}`.
/// An unknown polarity returns `{"ok":false,"error":"..."}`. Never panics.
#[wasm_bindgen]
pub fn stat_trend_compute(
    previous: f64,
    current: f64,
    flat_threshold_x100: u32,
    polarity: &str,
) -> String {
    let pol: Polarity =
        match serde_json::from_value(serde_json::Value::String(polarity.to_string())) {
            Ok(p) => p,
            Err(_) => {
                return serde_json::json!({ "ok": false, "error": format!("unknown polarity: {polarity}") })
                    .to_string()
            }
        };
    let t = StatTrend::new(flat_threshold_x100).trend(previous, current, pol);
    let mut v = serde_json::to_value(t).unwrap_or(serde_json::Value::Null);
    if let Some(obj) = v.as_object_mut() {
        obj.insert("ok".into(), serde_json::Value::Bool(true));
    }
    v.to_string()
}
