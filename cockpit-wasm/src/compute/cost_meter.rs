//! Compute wrapper for `sovereign-cockpit-cost-meter` — expose its real budget-gauge
//! verdict (level / usage / remaining) to the panel via wasm, beyond validate() (F-2026-001).
use sovereign_cockpit_cost_meter::CostMeter;
use wasm_bindgen::prelude::*;

/// Build a `CostMeter` for `budget` (warn/critical thresholds in basis points), charge
/// `spent`, and return the crate's real gauge verdict:
/// `{"ok":true,"level":"normal|warning|critical|exceeded","usage_bp":u32,"remaining":u64}`.
/// Bad thresholds return `{"ok":false,"error":"..."}`. Never panics.
#[wasm_bindgen]
pub fn cost_meter_level(budget: f64, spent: f64, warning_bp: u32, critical_bp: u32) -> String {
    let mut m = match CostMeter::new(budget.max(0.0) as u64, warning_bp, critical_bp) {
        Ok(m) => m,
        Err(e) => return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    };
    m.charge(spent.max(0.0) as u64);
    serde_json::json!({
        "ok": true,
        "level": serde_json::to_value(m.level()).unwrap_or(serde_json::Value::Null),
        "usage_bp": m.usage_bp(),
        "remaining": m.remaining(),
    })
    .to_string()
}
