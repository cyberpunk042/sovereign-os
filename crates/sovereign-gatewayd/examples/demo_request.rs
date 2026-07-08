//! Emit a real `infer` envelope (the first cortex demo request) as one line of
//! NDJSON — a copy-paste client payload for `sovereign-gatewayd`.
//!
//! ```text
//! cargo run -p sovereign-gatewayd --example demo_request | \
//!   sovereign-gatewayd --stdio
//! ```

fn main() {
    let req = &sovereign_cortex::demo_requests()[0];
    let line = serde_json::json!({ "op": "infer", "request": req });
    println!("{line}");
}
