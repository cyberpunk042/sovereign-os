//! Compute wrappers for `sovereign-cockpit-alert-tile-board` — expose its real
//! display ordering (add → ordered) to the panel via wasm, beyond validate()
//! (audit F-2026-001).
//!
//! Functional: build a local `AlertTileBoard`, `add` each tile through the crate's
//! real insert (empty-field + duplicate-id guards run in Rust), then return
//! `ordered()`. Holds no state across calls; never panics.
use sovereign_cockpit_alert_tile_board::{AlertTile, AlertTileBoard};
use wasm_bindgen::prelude::*;

/// Order a batch of alert tiles for display using the crate's REAL ordering:
/// pinned-first, then unacked-before-acked, higher-severity, newer-ts, title alpha.
///
/// Input: a JSON array of `AlertTile` objects
/// `[{ "id","title","severity":"<kebab>","summary","pinned","acknowledged","ts_ms" }, ...]`
/// (severity kebab tokens: `info` / `notice` / `warn` / `error` / `critical`).
/// Returns the ordered JSON array of tiles, or `{"ok":false,"error":"..."}` on any
/// parse/domain error.
#[wasm_bindgen]
pub fn alert_tile_board_ordered(tiles_json: &str) -> String {
    // `AlertTile` derives Deserialize — parse the batch directly.
    let tiles: Vec<AlertTile> = match serde_json::from_str(tiles_json) {
        Ok(v) => v,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };

    let mut board = AlertTileBoard::new();
    for (i, tile) in tiles.into_iter().enumerate() {
        if let Err(e) = board.add(tile) {
            return serde_json::json!({ "ok": false, "error": format!("tile {i}: {e}") })
                .to_string();
        }
    }

    // `AlertTile` derives Serialize — the ordered slice serializes directly.
    serde_json::to_string(&board.ordered()).unwrap_or_else(|e| {
        serde_json::json!({ "ok": false, "error": format!("serialize: {e}") }).to_string()
    })
}
