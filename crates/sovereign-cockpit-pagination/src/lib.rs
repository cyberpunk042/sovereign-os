//! `sovereign-cockpit-pagination` — page-state arithmetic.
//!
//! A cockpit list pager carries 3 inputs:
//!   - `total`     (items in the result set; 0 allowed)
//!   - `per_page`  (items per page; ≥ 1)
//!   - `page`      (1-indexed current page; clamped to [1, total_pages])
//!
//! and emits derived state for the renderer:
//! - `total_pages`  = ceil(total / per_page); 0 → 0; else ≥ 1
//! - `can_prev`     = page > 1
//! - `can_next`     = page < total_pages
//! - `range`        = (start_index, end_index_inclusive) in [0, total-1]
//!   ranges OR None when total = 0
//!
//! Standing rule: we do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum PaginationError {
    /// `per_page` was 0.
    #[error("per_page must be ≥ 1")]
    InvalidPerPage,
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// A pager + its derived state.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pager {
    /// 1-indexed current page (clamped on construction).
    pub page: u64,
    /// Items per page; ≥ 1.
    pub per_page: u64,
    /// Total items in the result set.
    pub total: u64,
}

/// Derived state from a `Pager`.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct PageInfo {
    /// 1-indexed current page.
    pub page: u64,
    /// Items per page.
    pub per_page: u64,
    /// Total items.
    pub total: u64,
    /// Total pages — 0 when total = 0, else ceil(total/per_page).
    pub total_pages: u64,
    /// True iff page > 1.
    pub can_prev: bool,
    /// True iff page < total_pages.
    pub can_next: bool,
    /// (start, end_inclusive) item indices in [0, total-1] for the
    /// current page, OR None when total = 0.
    pub range: Option<(u64, u64)>,
}

impl Pager {
    /// Construct a pager. Returns err if `per_page == 0`. `page`
    /// is clamped into [1, total_pages] (or set to 1 when total =
    /// 0 / pages = 0).
    pub fn new(page: u64, per_page: u64, total: u64) -> Result<Self, PaginationError> {
        if per_page == 0 {
            return Err(PaginationError::InvalidPerPage);
        }
        let total_pages = total_pages_for(total, per_page);
        let clamped_page = if total_pages == 0 {
            1
        } else {
            page.clamp(1, total_pages)
        };
        Ok(Self {
            page: clamped_page,
            per_page,
            total,
        })
    }
    /// Compute the derived `PageInfo`.
    pub fn info(self) -> PageInfo {
        let total_pages = total_pages_for(self.total, self.per_page);
        let can_prev = self.page > 1;
        let can_next = total_pages > 0 && self.page < total_pages;
        let range = if self.total == 0 {
            None
        } else {
            let start = (self.page - 1) * self.per_page;
            let end = (start + self.per_page - 1).min(self.total - 1);
            Some((start, end))
        };
        PageInfo {
            page: self.page,
            per_page: self.per_page,
            total: self.total,
            total_pages,
            can_prev,
            can_next,
            range,
        }
    }
    /// Step forward one page if `can_next`, else no-op.
    pub fn next(mut self) -> Self {
        let info = self.info();
        if info.can_next {
            self.page += 1;
        }
        self
    }
    /// Step back one page if `can_prev`, else no-op.
    pub fn prev(mut self) -> Self {
        let info = self.info();
        if info.can_prev {
            self.page -= 1;
        }
        self
    }
    /// Jump to a specific page (clamped into the valid range).
    pub fn goto(mut self, page: u64) -> Self {
        let total_pages = total_pages_for(self.total, self.per_page);
        self.page = if total_pages == 0 {
            1
        } else {
            page.clamp(1, total_pages)
        };
        self
    }
}

/// ceil(total / per_page) as u64, except 0 when total = 0.
pub fn total_pages_for(total: u64, per_page: u64) -> u64 {
    if total == 0 || per_page == 0 {
        return 0;
    }
    total.div_ceil(per_page)
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), PaginationError> {
    if s != SCHEMA_VERSION {
        return Err(PaginationError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn total_pages_exact_division() {
        assert_eq!(total_pages_for(100, 10), 10);
    }

    #[test]
    fn total_pages_rounding_up() {
        assert_eq!(total_pages_for(101, 10), 11);
    }

    #[test]
    fn total_pages_zero_when_total_zero() {
        assert_eq!(total_pages_for(0, 10), 0);
    }

    #[test]
    fn total_pages_zero_per_page_returns_zero() {
        assert_eq!(total_pages_for(100, 0), 0);
    }

    #[test]
    fn new_rejects_zero_per_page() {
        let r = Pager::new(1, 0, 100);
        assert_eq!(r.unwrap_err(), PaginationError::InvalidPerPage);
    }

    #[test]
    fn new_clamps_overshoot_page() {
        let p = Pager::new(999, 10, 100).unwrap();
        assert_eq!(p.page, 10, "must clamp page to total_pages=10");
    }

    #[test]
    fn new_clamps_zero_page_to_one() {
        let p = Pager::new(0, 10, 100).unwrap();
        assert_eq!(p.page, 1);
    }

    #[test]
    fn empty_total_yields_no_range_and_no_navigation() {
        let p = Pager::new(1, 10, 0).unwrap();
        let i = p.info();
        assert_eq!(i.total_pages, 0);
        assert_eq!(i.range, None);
        assert!(!i.can_next);
        assert!(!i.can_prev);
    }

    #[test]
    fn first_page_has_no_prev() {
        let i = Pager::new(1, 10, 100).unwrap().info();
        assert!(!i.can_prev);
        assert!(i.can_next);
        assert_eq!(i.range, Some((0, 9)));
    }

    #[test]
    fn middle_page_can_navigate_both() {
        let i = Pager::new(5, 10, 100).unwrap().info();
        assert!(i.can_prev);
        assert!(i.can_next);
        assert_eq!(i.range, Some((40, 49)));
    }

    #[test]
    fn last_page_has_no_next() {
        let i = Pager::new(10, 10, 100).unwrap().info();
        assert!(i.can_prev);
        assert!(!i.can_next);
        assert_eq!(i.range, Some((90, 99)));
    }

    #[test]
    fn partial_last_page_caps_range_end() {
        // 95 items / 10 per_page → 10 pages; page 10 has only 5 items.
        let i = Pager::new(10, 10, 95).unwrap().info();
        assert_eq!(i.total_pages, 10);
        assert_eq!(i.range, Some((90, 94)));
    }

    #[test]
    fn next_is_no_op_at_last_page() {
        let p = Pager::new(10, 10, 100).unwrap();
        let p2 = p.next();
        assert_eq!(p2.page, 10);
    }

    #[test]
    fn prev_is_no_op_at_first_page() {
        let p = Pager::new(1, 10, 100).unwrap();
        let p2 = p.prev();
        assert_eq!(p2.page, 1);
    }

    #[test]
    fn next_advances_one_page() {
        let p = Pager::new(3, 10, 100).unwrap();
        assert_eq!(p.next().page, 4);
    }

    #[test]
    fn prev_steps_back_one_page() {
        let p = Pager::new(3, 10, 100).unwrap();
        assert_eq!(p.prev().page, 2);
    }

    #[test]
    fn goto_clamps_into_range() {
        let p = Pager::new(1, 10, 100).unwrap();
        assert_eq!(p.goto(999).page, 10);
        assert_eq!(p.goto(0).page, 1);
        assert_eq!(p.goto(5).page, 5);
    }

    #[test]
    fn goto_on_empty_total_stays_at_one() {
        let p = Pager::new(1, 10, 0).unwrap();
        assert_eq!(p.goto(7).page, 1);
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            PaginationError::SchemaMismatch
        ));
    }

    #[test]
    fn page_info_serde_roundtrip() {
        let i = Pager::new(2, 10, 100).unwrap().info();
        let j = serde_json::to_string(&i).unwrap();
        let back: PageInfo = serde_json::from_str(&j).unwrap();
        assert_eq!(i, back);
    }
}
