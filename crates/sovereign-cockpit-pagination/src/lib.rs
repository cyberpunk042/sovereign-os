//! `sovereign-cockpit-pagination` — pagination control state.
//!
//! Holds (total_items, page_size, page). Computes total_pages +
//! offset; bounds navigation; emits a windowed page-number list
//! around the active page. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Rendered token in the page bar.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum PageToken {
    /// Real page (1-based number, active flag).
    Page {
        /// 1-based number.
        n: u32,
        /// Is this the current page?
        active: bool,
    },
    /// Ellipsis collapsed region.
    Ellipsis,
}

/// Pagination state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pagination {
    /// Schema version.
    pub schema_version: String,
    /// Total item count.
    pub total_items: u64,
    /// Page size (≥ 1).
    pub page_size: u32,
    /// Current page (1-based).
    pub page: u32,
    /// Window width on each side of active when rendering page list.
    pub side_window: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PaginationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// page_size zero.
    #[error("page_size is zero")]
    PageSizeZero,
    /// page out of range (1..=total_pages).
    #[error("page {page} out of range (1..={max})")]
    PageOutOfRange {
        /// page.
        page: u32,
        /// max.
        max: u32,
    },
}

impl Pagination {
    /// New pagination. page defaults to 1, side_window to 2.
    pub fn new(total_items: u64, page_size: u32) -> Result<Self, PaginationError> {
        if page_size == 0 {
            return Err(PaginationError::PageSizeZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            total_items,
            page_size,
            page: 1,
            side_window: 2,
        })
    }

    /// Total pages (≥ 1 when total_items > 0, else 1).
    pub fn total_pages(&self) -> u32 {
        if self.total_items == 0 {
            return 1;
        }
        let p = (self.total_items + self.page_size as u64 - 1) / self.page_size as u64;
        p.min(u32::MAX as u64) as u32
    }

    /// Zero-based offset for current page.
    pub fn offset(&self) -> u64 {
        (self.page.saturating_sub(1) as u64) * self.page_size as u64
    }

    /// Items on the current page.
    pub fn current_page_count(&self) -> u32 {
        let start = self.offset();
        if start >= self.total_items {
            return 0;
        }
        ((self.total_items - start).min(self.page_size as u64)) as u32
    }

    /// Go to a specific page (bounds-checked).
    pub fn goto(&mut self, page: u32) -> Result<(), PaginationError> {
        let max = self.total_pages();
        if page == 0 || page > max {
            return Err(PaginationError::PageOutOfRange { page, max });
        }
        self.page = page;
        Ok(())
    }

    /// Next page (no-op at last).
    pub fn next(&mut self) {
        if self.page < self.total_pages() {
            self.page += 1;
        }
    }

    /// Previous page (no-op at first).
    pub fn prev(&mut self) {
        if self.page > 1 {
            self.page -= 1;
        }
    }

    /// First page.
    pub fn first(&mut self) {
        self.page = 1;
    }

    /// Last page.
    pub fn last(&mut self) {
        self.page = self.total_pages();
    }

    /// Render a windowed page bar.
    ///
    /// Always emits page 1 and the last page. Around the active page
    /// emits `side_window` pages on each side. Gaps become an
    /// Ellipsis token.
    pub fn render(&self) -> Vec<PageToken> {
        let max = self.total_pages();
        let mut indices: Vec<u32> = Vec::new();
        indices.push(1);
        let lo = self.page.saturating_sub(self.side_window).max(1);
        let hi = self.page.saturating_add(self.side_window).min(max);
        for n in lo..=hi {
            if !indices.contains(&n) {
                indices.push(n);
            }
        }
        if !indices.contains(&max) {
            indices.push(max);
        }
        indices.sort_unstable();
        indices.dedup();

        let mut out: Vec<PageToken> = Vec::with_capacity(indices.len() * 2);
        let mut last: Option<u32> = None;
        for n in indices {
            if let Some(prev) = last {
                if n > prev + 1 {
                    out.push(PageToken::Ellipsis);
                }
            }
            out.push(PageToken::Page { n, active: n == self.page });
            last = Some(n);
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PaginationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PaginationError::SchemaMismatch);
        }
        if self.page_size == 0 {
            return Err(PaginationError::PageSizeZero);
        }
        let max = self.total_pages();
        if self.page == 0 || self.page > max {
            return Err(PaginationError::PageOutOfRange { page: self.page, max });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_page_size_rejected() {
        assert!(matches!(Pagination::new(0, 0).unwrap_err(), PaginationError::PageSizeZero));
    }

    #[test]
    fn total_pages_for_zero_items() {
        let p = Pagination::new(0, 10).unwrap();
        assert_eq!(p.total_pages(), 1);
    }

    #[test]
    fn total_pages_rounds_up() {
        let p = Pagination::new(95, 10).unwrap();
        assert_eq!(p.total_pages(), 10);
        let p = Pagination::new(100, 10).unwrap();
        assert_eq!(p.total_pages(), 10);
        let p = Pagination::new(101, 10).unwrap();
        assert_eq!(p.total_pages(), 11);
    }

    #[test]
    fn offset_and_count() {
        let mut p = Pagination::new(95, 10).unwrap();
        p.goto(10).unwrap();
        assert_eq!(p.offset(), 90);
        assert_eq!(p.current_page_count(), 5);
    }

    #[test]
    fn next_caps_at_last() {
        let mut p = Pagination::new(50, 10).unwrap();
        for _ in 0..10 { p.next(); }
        assert_eq!(p.page, 5);
    }

    #[test]
    fn prev_caps_at_first() {
        let mut p = Pagination::new(50, 10).unwrap();
        for _ in 0..10 { p.prev(); }
        assert_eq!(p.page, 1);
    }

    #[test]
    fn goto_out_of_range_rejected() {
        let mut p = Pagination::new(50, 10).unwrap();
        assert!(matches!(p.goto(0).unwrap_err(), PaginationError::PageOutOfRange { .. }));
        assert!(matches!(p.goto(99).unwrap_err(), PaginationError::PageOutOfRange { .. }));
    }

    #[test]
    fn first_last_jumps() {
        let mut p = Pagination::new(50, 10).unwrap();
        p.last();
        assert_eq!(p.page, 5);
        p.first();
        assert_eq!(p.page, 1);
    }

    #[test]
    fn render_small_no_ellipsis() {
        let p = Pagination::new(30, 10).unwrap();
        let r = p.render();
        // 1,2,3 with 1 active.
        assert_eq!(r.len(), 3);
        for t in &r {
            assert!(!matches!(t, PageToken::Ellipsis));
        }
    }

    #[test]
    fn render_large_with_ellipsis() {
        let mut p = Pagination::new(1000, 10).unwrap();
        p.goto(50).unwrap();
        let r = p.render();
        // Should contain Ellipsis tokens on both sides.
        assert!(r.iter().filter(|t| matches!(t, PageToken::Ellipsis)).count() == 2);
        // First token should be page 1 (not active), last should be page 100.
        assert!(matches!(r.first().unwrap(), PageToken::Page { n: 1, active: false }));
        assert!(matches!(r.last().unwrap(), PageToken::Page { n: 100, active: false }));
        assert!(r.iter().any(|t| matches!(t, PageToken::Page { n: 50, active: true })));
    }

    #[test]
    fn render_active_at_start() {
        let p = Pagination::new(1000, 10).unwrap();
        let r = p.render();
        assert!(matches!(r.first().unwrap(), PageToken::Page { n: 1, active: true }));
        assert!(r.iter().any(|t| matches!(t, PageToken::Ellipsis)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = Pagination::new(10, 10).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), PaginationError::SchemaMismatch));
    }

    #[test]
    fn token_serde_kebab() {
        let t = PageToken::Ellipsis;
        assert_eq!(serde_json::to_string(&t).unwrap(), "{\"kind\":\"ellipsis\"}");
        let t = PageToken::Page { n: 3, active: true };
        let j = serde_json::to_string(&t).unwrap();
        assert!(j.contains("\"kind\":\"page\""));
    }

    #[test]
    fn pagination_serde_roundtrip() {
        let mut p = Pagination::new(100, 10).unwrap();
        p.goto(5).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: Pagination = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
