//! Bespoke wasm bridge for `sovereign-cockpit-shortcut-cheatsheet` (no uniform validate()).
//! Exposes the crate's REAL `render` so the cockpit's `?` overlay builds its per-scope,
//! chord-sorted cheatsheet with the same Rust logic the daemon uses (F-2026-001),
//! instead of a drifting JS re-implementation. No clock, no fs.
//!
//! DEP NOTE: `render(map: &KeystrokeMap, fmt: Format)` takes a foreign `KeystrokeMap`
//! from `sovereign-cockpit-keystroke-map` (the cheatsheet crate imports it but does NOT
//! re-export it). Building the argument therefore requires that transitive crate in
//! scope — so cockpit-wasm must depend on BOTH `sovereign-cockpit-shortcut-cheatsheet`
//! AND `sovereign-cockpit-keystroke-map`. There is no render surface that avoids it.
use sovereign_cockpit_keystroke_map::KeystrokeMap;
use sovereign_cockpit_shortcut_cheatsheet::{render, Format};
use wasm_bindgen::prelude::*;

/// Render a `KeystrokeMap` JSON as an operator cheatsheet via the crate's real
/// `render`. `fmt` is the kebab token `"markdown"` or `"plain-text"`. Returns JSON
/// `{"value":"<cheatsheet text>"}`, or `{"ok":false,"error":"..."}` on a bad map/format.
#[wasm_bindgen]
pub fn shortcut_cheatsheet_render(map_json: &str, fmt: &str) -> String {
    let map: KeystrokeMap = match serde_json::from_str(map_json) {
        Ok(m) => m,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let fmt_enum: Format = match serde_json::from_value(serde_json::Value::String(fmt.to_string()))
    {
        Ok(f) => f,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("format: {e}") }).to_string()
        }
    };
    let out = render(&map, fmt_enum);
    serde_json::json!({ "value": out }).to_string()
}
