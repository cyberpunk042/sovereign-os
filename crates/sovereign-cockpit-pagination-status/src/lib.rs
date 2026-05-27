//! `sovereign-cockpit-pagination-status` — status-text formatter.
//!
//! Given page state, emits operator-facing display strings:
//! * "No items" when 0.
//! * "Showing A-B of N" when no filter.
//! * "Showing A-B of N (filtered from M)" when filtered.
//!
//! Numbers are comma-grouped (1,000,000).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Input.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct PageState {
    /// 1-based page.
    pub page: u32,
    /// Page size.
    pub page_size: u32,
    /// Total items currently visible.
    pub total_items: u64,
    /// Optional pre-filter total (when > total_items).
    pub pre_filter_total: u64,
}

/// Formatted status text.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PaginationStatus {
    /// Schema version.
    pub schema_version: String,
    /// Human-readable status.
    pub display: String,
    /// First visible (0 if no items).
    pub first: u64,
    /// Last visible (0 if no items).
    pub last: u64,
    /// Total.
    pub total: u64,
    /// Pre-filter total (only set when filtered).
    pub pre_filter_total: Option<u64>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StatusError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero page_size.
    #[error("page_size is zero")]
    PageSizeZero,
    /// Zero page.
    #[error("page is zero")]
    PageZero,
    /// pre_filter < total_items.
    #[error("pre_filter_total {pre} < total_items {tot}")]
    BadPreFilter {
        /// pre.
        pre: u64,
        /// tot.
        tot: u64,
    },
}

/// Builder.
#[derive(Debug, Clone, Default)]
pub struct PaginationStatusFormatter;

impl PaginationStatusFormatter {
    /// Format.
    pub fn format(state: PageState) -> Result<PaginationStatus, StatusError> {
        if state.page == 0 {
            return Err(StatusError::PageZero);
        }
        if state.page_size == 0 {
            return Err(StatusError::PageSizeZero);
        }
        if state.pre_filter_total != 0 && state.pre_filter_total < state.total_items {
            return Err(StatusError::BadPreFilter {
                pre: state.pre_filter_total,
                tot: state.total_items,
            });
        }
        if state.total_items == 0 {
            return Ok(PaginationStatus {
                schema_version: SCHEMA_VERSION.into(),
                display: "No items".into(),
                first: 0,
                last: 0,
                total: 0,
                pre_filter_total: None,
            });
        }
        let offset = (state.page as u64 - 1) * state.page_size as u64;
        let first = offset.min(state.total_items.saturating_sub(1)) + 1;
        let last = (offset + state.page_size as u64).min(state.total_items);
        let total_str = group_thousands(state.total_items);
        let pre = if state.pre_filter_total > state.total_items {
            Some(state.pre_filter_total)
        } else {
            None
        };
        let display = if let Some(pre) = pre {
            format!(
                "Showing {}-{} of {} (filtered from {})",
                group_thousands(first),
                group_thousands(last),
                total_str,
                group_thousands(pre)
            )
        } else {
            format!(
                "Showing {}-{} of {}",
                group_thousands(first),
                group_thousands(last),
                total_str
            )
        };
        Ok(PaginationStatus {
            schema_version: SCHEMA_VERSION.into(),
            display,
            first,
            last,
            total: state.total_items,
            pre_filter_total: pre,
        })
    }
}

fn group_thousands(n: u64) -> String {
    let s = n.to_string();
    let bytes = s.as_bytes();
    let mut out = String::with_capacity(s.len() + s.len() / 3);
    let len = bytes.len();
    for (i, b) in bytes.iter().enumerate() {
        let rem = len - i;
        if i > 0 && rem.is_multiple_of(3) {
            out.push(',');
        }
        out.push(*b as char);
    }
    out
}

impl PaginationStatus {
    /// Validate.
    pub fn validate(&self) -> Result<(), StatusError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(StatusError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_items_message() {
        let s = PaginationStatusFormatter::format(PageState {
            page: 1,
            page_size: 50,
            total_items: 0,
            pre_filter_total: 0,
        })
        .unwrap();
        assert_eq!(s.display, "No items");
    }

    #[test]
    fn first_page_unfiltered() {
        let s = PaginationStatusFormatter::format(PageState {
            page: 1,
            page_size: 50,
            total_items: 1000,
            pre_filter_total: 0,
        })
        .unwrap();
        assert_eq!(s.display, "Showing 1-50 of 1,000");
        assert_eq!(s.first, 1);
        assert_eq!(s.last, 50);
    }

    #[test]
    fn last_partial_page() {
        let s = PaginationStatusFormatter::format(PageState {
            page: 21,
            page_size: 50,
            total_items: 1005,
            pre_filter_total: 0,
        })
        .unwrap();
        // page 21 -> offset 1000, last min(1050, 1005) = 1005
        assert_eq!(s.first, 1001);
        assert_eq!(s.last, 1005);
    }

    #[test]
    fn filtered_shows_both() {
        let s = PaginationStatusFormatter::format(PageState {
            page: 1,
            page_size: 50,
            total_items: 1000,
            pre_filter_total: 10000,
        })
        .unwrap();
        assert_eq!(s.display, "Showing 1-50 of 1,000 (filtered from 10,000)");
        assert_eq!(s.pre_filter_total, Some(10000));
    }

    #[test]
    fn pre_filter_equal_to_total_omitted() {
        let s = PaginationStatusFormatter::format(PageState {
            page: 1,
            page_size: 50,
            total_items: 1000,
            pre_filter_total: 1000,
        })
        .unwrap();
        assert!(!s.display.contains("filtered"));
        assert!(s.pre_filter_total.is_none());
    }

    #[test]
    fn page_zero_rejected() {
        assert!(matches!(
            PaginationStatusFormatter::format(PageState {
                page: 0,
                page_size: 50,
                total_items: 100,
                pre_filter_total: 0
            })
            .unwrap_err(),
            StatusError::PageZero
        ));
    }

    #[test]
    fn page_size_zero_rejected() {
        assert!(matches!(
            PaginationStatusFormatter::format(PageState {
                page: 1,
                page_size: 0,
                total_items: 100,
                pre_filter_total: 0
            })
            .unwrap_err(),
            StatusError::PageSizeZero
        ));
    }

    #[test]
    fn bad_pre_filter_rejected() {
        assert!(matches!(
            PaginationStatusFormatter::format(PageState {
                page: 1,
                page_size: 50,
                total_items: 1000,
                pre_filter_total: 500
            })
            .unwrap_err(),
            StatusError::BadPreFilter { .. }
        ));
    }

    #[test]
    fn comma_grouping_correct() {
        assert_eq!(group_thousands(1), "1");
        assert_eq!(group_thousands(999), "999");
        assert_eq!(group_thousands(1000), "1,000");
        assert_eq!(group_thousands(1_000_000), "1,000,000");
        assert_eq!(group_thousands(1_234_567_890), "1,234,567,890");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = PaginationStatusFormatter::format(PageState {
            page: 1,
            page_size: 50,
            total_items: 100,
            pre_filter_total: 0,
        })
        .unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            StatusError::SchemaMismatch
        ));
    }

    #[test]
    fn status_serde_roundtrip() {
        let s = PaginationStatusFormatter::format(PageState {
            page: 5,
            page_size: 50,
            total_items: 1000,
            pre_filter_total: 5000,
        })
        .unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: PaginationStatus = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
