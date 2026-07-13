//! Compute wrappers for `sovereign-cockpit-facet-counts` — expose its real facet
//! rollup (set_count → top) to the panel via wasm, beyond validate()
//! (audit F-2026-001).
//!
//! Functional: build a local `FacetCounts`, record every bucket count through the
//! crate's real `set_count`, then read `top(facet, n)` per facet. Holds no state
//! across calls; never panics.
use sovereign_cockpit_facet_counts::FacetCounts;
use wasm_bindgen::prelude::*;

/// Rank each facet's buckets using the crate's REAL `top` (count desc, ties broken
/// by bucket name asc), keeping the top `n` per facet.
///
/// Input: a JSON object `{ "<facet>": { "<bucket>": number, ... }, ... }`. Returns a
/// JSON object `{ "<facet>": [ [bucket, count], ... top n ... ], ... }`, or
/// `{"ok":false,"error":"..."}` on any parse/domain error.
#[wasm_bindgen]
pub fn facet_counts_top(counts_json: &str, n: u32) -> String {
    let input: serde_json::Map<String, serde_json::Value> = match serde_json::from_str(counts_json)
    {
        Ok(v) => v,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };

    let mut fc = FacetCounts::new();
    for (facet, buckets) in &input {
        let obj = match buckets.as_object() {
            Some(o) => o,
            None => {
                return serde_json::json!({
                    "ok": false,
                    "error": format!("facet {facet:?}: expected an object of bucket->count"),
                })
                .to_string()
            }
        };
        for (bucket, count) in obj {
            let c =
                match count.as_u64().or_else(|| count.as_f64().map(|f| f as u64)) {
                    Some(c) => c,
                    None => return serde_json::json!({
                        "ok": false,
                        "error": format!("facet {facet:?} bucket {bucket:?}: expected a number"),
                    })
                    .to_string(),
                };
            if let Err(e) = fc.set_count(facet, bucket, c) {
                return serde_json::json!({
                    "ok": false,
                    "error": format!("facet {facet:?} bucket {bucket:?}: {e}"),
                })
                .to_string();
            }
        }
    }

    // Emit the top-n per facet, preserving every facet present in the input.
    let mut out = serde_json::Map::new();
    for facet in input.keys() {
        let top = fc.top(facet, n as usize);
        match serde_json::to_value(&top) {
            Ok(v) => {
                out.insert(facet.clone(), v);
            }
            Err(e) => {
                return serde_json::json!({ "ok": false, "error": format!("serialize: {e}") })
                    .to_string()
            }
        }
    }

    serde_json::Value::Object(out).to_string()
}
