//! `sovereign-cockpit-result-page-cursor` — bidirectional page cursor.
//!
//! Tracks position over a virtually-paginated result stream. The
//! cursor holds the current `page` (1-based), `page_size`, and an
//! optional `total_pages` if known. Operations:
//!   * `next` → page+1 if more remain.
//!   * `prev` → page-1 if > 1.
//!   * `jump_to(p)` → bounded by [1, total_pages].
//!   * `update_total(n)` shrinks the cursor (e.g. result set
//!     changed after a filter): if current page now exceeds total,
//!     jump to last available page.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ResultPageCursor {
    /// Schema version.
    pub schema_version: String,
    /// Current page (1-based).
    pub page: u64,
    /// Items per page.
    pub page_size: u64,
    /// Total pages (None = unknown / unbounded stream).
    pub total_pages: Option<u64>,
}

/// Move verdict.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum MoveVerdict {
    /// Moved.
    Moved {
        /// from.
        from: u64,
        /// to.
        to: u64,
    },
    /// Already at edge.
    AtEdge,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CursorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero page size.
    #[error("page_size must be > 0")]
    ZeroPageSize,
    /// Bad page index.
    #[error("page must be >= 1, got {0}")]
    ZeroPage(u64),
}

impl ResultPageCursor {
    /// New.
    pub fn new(page_size: u64) -> Result<Self, CursorError> {
        if page_size == 0 { return Err(CursorError::ZeroPageSize); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            page: 1,
            page_size,
            total_pages: None,
        })
    }

    /// Set total pages.
    pub fn update_total(&mut self, total_pages: Option<u64>) {
        self.total_pages = total_pages;
        // If current page exceeds total, snap back.
        if let Some(t) = total_pages {
            if self.page > t.max(1) {
                self.page = t.max(1);
            }
        }
    }

    /// Next page.
    pub fn next(&mut self) -> MoveVerdict {
        if let Some(total) = self.total_pages {
            if self.page >= total {
                return MoveVerdict::AtEdge;
            }
        }
        let from = self.page;
        self.page = self.page.saturating_add(1);
        MoveVerdict::Moved { from, to: self.page }
    }

    /// Previous page.
    pub fn prev(&mut self) -> MoveVerdict {
        if self.page <= 1 {
            return MoveVerdict::AtEdge;
        }
        let from = self.page;
        self.page -= 1;
        MoveVerdict::Moved { from, to: self.page }
    }

    /// Jump.
    pub fn jump_to(&mut self, page: u64) -> Result<MoveVerdict, CursorError> {
        if page == 0 { return Err(CursorError::ZeroPage(page)); }
        let bounded = match self.total_pages {
            Some(t) => page.min(t.max(1)),
            None => page,
        };
        if bounded == self.page {
            return Ok(MoveVerdict::AtEdge);
        }
        let from = self.page;
        self.page = bounded;
        Ok(MoveVerdict::Moved { from, to: bounded })
    }

    /// First / last in window.
    pub fn first_item_index(&self) -> u64 {
        (self.page - 1).saturating_mul(self.page_size)
    }

    /// One-past-last index in the page.
    pub fn end_item_index(&self) -> u64 {
        self.first_item_index().saturating_add(self.page_size)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CursorError> {
        if self.schema_version != SCHEMA_VERSION { return Err(CursorError::SchemaMismatch); }
        if self.page_size == 0 { return Err(CursorError::ZeroPageSize); }
        if self.page == 0 { return Err(CursorError::ZeroPage(self.page)); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn next_and_prev() {
        let mut c = ResultPageCursor::new(10).unwrap();
        assert!(matches!(c.next(), MoveVerdict::Moved { from: 1, to: 2 }));
        assert!(matches!(c.prev(), MoveVerdict::Moved { from: 2, to: 1 }));
        assert_eq!(c.prev(), MoveVerdict::AtEdge);
    }

    #[test]
    fn next_stops_at_total() {
        let mut c = ResultPageCursor::new(10).unwrap();
        c.update_total(Some(3));
        c.next();
        c.next();
        assert!(matches!(c.next(), MoveVerdict::Moved { from: 3, to: 3 }) || c.next() == MoveVerdict::AtEdge);
    }

    #[test]
    fn jump_bounded_by_total() {
        let mut c = ResultPageCursor::new(10).unwrap();
        c.update_total(Some(5));
        let v = c.jump_to(100).unwrap();
        // Bounded to 5.
        assert_eq!(c.page, 5);
        assert!(matches!(v, MoveVerdict::Moved { to: 5, .. }));
    }

    #[test]
    fn jump_unbounded() {
        let mut c = ResultPageCursor::new(10).unwrap();
        // No total set.
        c.jump_to(100).unwrap();
        assert_eq!(c.page, 100);
    }

    #[test]
    fn update_total_snaps_back() {
        let mut c = ResultPageCursor::new(10).unwrap();
        c.jump_to(50).unwrap();
        c.update_total(Some(3));
        assert_eq!(c.page, 3);
    }

    #[test]
    fn jump_to_zero_rejected() {
        let mut c = ResultPageCursor::new(10).unwrap();
        assert!(matches!(c.jump_to(0).unwrap_err(), CursorError::ZeroPage(_)));
    }

    #[test]
    fn item_indices() {
        let mut c = ResultPageCursor::new(20).unwrap();
        c.jump_to(3).unwrap();
        assert_eq!(c.first_item_index(), 40);
        assert_eq!(c.end_item_index(), 60);
    }

    #[test]
    fn jump_same_page_at_edge() {
        let mut c = ResultPageCursor::new(10).unwrap();
        assert_eq!(c.jump_to(1).unwrap(), MoveVerdict::AtEdge);
    }

    #[test]
    fn zero_page_size_rejected() {
        assert!(matches!(ResultPageCursor::new(0).unwrap_err(), CursorError::ZeroPageSize));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ResultPageCursor::new(10).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), CursorError::SchemaMismatch));
    }

    #[test]
    fn cursor_serde_roundtrip() {
        let mut c = ResultPageCursor::new(10).unwrap();
        c.update_total(Some(5));
        c.jump_to(3).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: ResultPageCursor = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
