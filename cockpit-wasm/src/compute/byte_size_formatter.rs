//! Compute wrapper for `sovereign-cockpit-byte-size-formatter` — format raw bytes into a
//! human string via the crate's real logic, beyond validate() (F-2026-001).
use sovereign_cockpit_byte_size_formatter::{ByteSizeFormatter, Unit};
use wasm_bindgen::prelude::*;

/// Format `bytes` with `unit` (`si` = 1000-based / `iec` = 1024-based) and `precision`
/// decimal places. Returns the crate's rendered string (e.g. `"1.5 GiB"`), or an
/// `{"ok":false,"error":"..."}` JSON string on a bad unit/precision. Never panics.
#[wasm_bindgen]
pub fn byte_size_format(bytes: f64, unit: &str, precision: u8) -> String {
    let u: Unit = match serde_json::from_value(serde_json::Value::String(unit.to_string())) {
        Ok(u) => u,
        Err(_) => {
            return serde_json::json!({ "ok": false, "error": format!("unknown unit: {unit}") })
                .to_string()
        }
    };
    match ByteSizeFormatter::new(u, precision) {
        Ok(f) => f.format(bytes.max(0.0) as u64),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
