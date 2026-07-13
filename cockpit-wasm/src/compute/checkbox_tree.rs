//! Compute wrappers for `sovereign-cockpit-checkbox-tree` — expose its real
//! tri-state rollup to the panel via wasm, beyond validate() (audit F-2026-001).
//!
//! The panel holds the tree with per-leaf stored states; this parses it and,
//! for every node id, runs the crate's own `compute_state()` (the
//! checked / unchecked / indeterminate parent rollup), so the panel shows
//! exactly the tri-state the crate derives instead of a drifting JS copy.
use sovereign_cockpit_checkbox_tree::CheckboxTree;
use wasm_bindgen::prelude::*;

/// Compute every node's effective tri-state via the crate's real
/// `compute_state()`. `tree_json` is a serialized `CheckboxTree`
/// (`{"schema_version":"1.0.0","nodes":[{"id","label","parent_id","leaf_state"}]}`).
/// Returns a JSON object mapping each node id to its `CheckState` kebab token
/// (`{"<id>":"checked"|"unchecked"|"indeterminate", ...}`); ids whose
/// `compute_state` is `None` are omitted. On a parse error returns
/// `{"ok":false,"error":"..."}` — never panics.
#[wasm_bindgen]
pub fn checkbox_tree_states(tree_json: &str) -> String {
    let tree = match serde_json::from_str::<CheckboxTree>(tree_json) {
        Ok(t) => t,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string();
        }
    };
    let mut out = serde_json::Map::new();
    for node in &tree.nodes {
        if let Some(state) = tree.compute_state(&node.id) {
            // `CheckState` is Serialize + kebab-case, so this yields the bare
            // token string (`"checked"` / `"unchecked"` / `"indeterminate"`).
            out.insert(
                node.id.clone(),
                serde_json::to_value(state).unwrap_or(serde_json::Value::Null),
            );
        }
    }
    serde_json::Value::Object(out).to_string()
}
