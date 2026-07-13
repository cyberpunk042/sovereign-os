//! Compute wrappers exposing the REAL compute logic of high-value cockpit
//! crates (beyond validate) to the panel via wasm (audit F-2026-001).
//! Hand-written; wired under the `bridges` feature.

pub mod alert_group;
pub mod alert_tile_board;
pub mod checkbox_tree;
pub mod facet_counts;
pub mod filter_state;
pub mod multi_select_list;
pub mod progress_tracker;
pub mod radio_group;
pub mod search_filter;
pub mod segmented_control;
pub mod stepper;
pub mod tree_view;
