//! Compute wrappers for `sovereign-cockpit-tree-view` — expose its real
//! visible-row flattening to the panel via wasm, beyond validate()
//! (audit F-2026-001).
//!
//! The panel already holds the full tree state (nodes + per-node `expanded`);
//! this parses that state and runs the crate's own `visible_rows()` DFS
//! projection, so the panel renders exactly the flattened rows the crate
//! computes rather than a hand-written JS re-implementation that can drift.
use sovereign_cockpit_tree_view::TreeView;
use wasm_bindgen::prelude::*;

/// Flatten a `TreeView` to its visible rows via the crate's real
/// `visible_rows()`. `tree_json` is a serialized `TreeView`
/// (`{"schema_version":"1.0.0","nodes":[{"id","label","parent_id","expanded"}],"selected":null}`);
/// each node's own `expanded` flag drives whether its children are visible.
/// Returns a JSON array of visible rows
/// (`[{"id","depth","has_children","expanded"}, ...]`) in DFS order on success,
/// or `{"ok":false,"error":"..."}` on a parse/serialize error — never panics.
#[wasm_bindgen]
pub fn tree_view_visible(tree_json: &str) -> String {
    match serde_json::from_str::<TreeView>(tree_json) {
        Ok(tree) => match serde_json::to_string(&tree.visible_rows()) {
            Ok(rows) => rows,
            Err(e) => {
                serde_json::json!({ "ok": false, "error": format!("serialize: {e}") }).to_string()
            }
        },
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string(),
    }
}
