//! `sovereign-cockpit-search-highlight` — subsequence highlight ranges.
//!
//! Computes the byte ranges in a candidate `haystack` that should
//! be highlighted as the operator's query subsequence. ASCII-only
//! query is case-insensitive. Returns ranges in ascending order
//! (non-overlapping, ready for direct render).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One contiguous highlight range.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Range {
    /// Byte offset start (inclusive).
    pub start: usize,
    /// Byte offset end (exclusive).
    pub end: usize,
}

/// Result.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HighlightResult {
    /// Schema version.
    pub schema_version: String,
    /// Matched ranges (ascending, non-overlapping).
    pub ranges: Vec<Range>,
    /// Did every query character match?
    pub matched_all: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HighlightError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Range exceeds haystack length.
    #[error("range {start}..{end} exceeds haystack length {len}")]
    RangeOutOfBounds {
        /// start.
        start: usize,
        /// end.
        end: usize,
        /// len.
        len: usize,
    },
    /// Range overlaps previous.
    #[error("range {start}..{end} overlaps previous {prev_end}")]
    RangeOverlap {
        /// start.
        start: usize,
        /// end.
        end: usize,
        /// prev end.
        prev_end: usize,
    },
}

/// Highlighter (stateless).
#[derive(Debug, Clone, Default)]
pub struct SearchHighlight;

impl SearchHighlight {
    /// Compute the highlight ranges for `query` against `haystack`.
    ///
    /// Greedy left-to-right subsequence matcher. Adjacent matches
    /// collapse into a single range.
    pub fn highlight(query: &str, haystack: &str) -> HighlightResult {
        let q: Vec<u8> = query.bytes().map(|b| b.to_ascii_lowercase()).collect();
        let h: Vec<u8> = haystack.bytes().collect();
        let mut ranges: Vec<Range> = Vec::new();
        if q.is_empty() {
            return HighlightResult {
                schema_version: SCHEMA_VERSION.into(),
                ranges,
                matched_all: true,
            };
        }
        let mut qi = 0;
        let mut current: Option<Range> = None;
        for (hi, &hb) in h.iter().enumerate() {
            if qi < q.len() && hb.to_ascii_lowercase() == q[qi] {
                qi += 1;
                match &mut current {
                    Some(r) if r.end == hi => {
                        r.end = hi + 1;
                    }
                    _ => {
                        if let Some(r) = current.take() {
                            ranges.push(r);
                        }
                        current = Some(Range {
                            start: hi,
                            end: hi + 1,
                        });
                    }
                }
            }
        }
        if let Some(r) = current {
            ranges.push(r);
        }
        HighlightResult {
            schema_version: SCHEMA_VERSION.into(),
            ranges,
            matched_all: qi == q.len(),
        }
    }
}

impl HighlightResult {
    /// Validate.
    pub fn validate(&self, haystack_len: usize) -> Result<(), HighlightError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HighlightError::SchemaMismatch);
        }
        let mut prev_end = 0usize;
        for r in &self.ranges {
            if r.end > haystack_len {
                return Err(HighlightError::RangeOutOfBounds {
                    start: r.start,
                    end: r.end,
                    len: haystack_len,
                });
            }
            if r.start < prev_end {
                return Err(HighlightError::RangeOverlap {
                    start: r.start,
                    end: r.end,
                    prev_end,
                });
            }
            prev_end = r.end;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_query_matches() {
        let r = SearchHighlight::highlight("", "hello");
        assert!(r.matched_all);
        assert!(r.ranges.is_empty());
    }

    #[test]
    fn empty_haystack_unless_query_empty() {
        let r = SearchHighlight::highlight("x", "");
        assert!(!r.matched_all);
        assert!(r.ranges.is_empty());
    }

    #[test]
    fn exact_match_single_range() {
        let r = SearchHighlight::highlight("ell", "hello");
        assert!(r.matched_all);
        assert_eq!(r.ranges, vec![Range { start: 1, end: 4 }]);
    }

    #[test]
    fn case_insensitive() {
        let r = SearchHighlight::highlight("HELLO", "hello world");
        assert!(r.matched_all);
        assert_eq!(r.ranges, vec![Range { start: 0, end: 5 }]);
    }

    #[test]
    fn subsequence_match_multiple_ranges() {
        // "abc" subsequence inside "axbycz" -> ranges at 0, 2, 4.
        let r = SearchHighlight::highlight("abc", "axbycz");
        assert!(r.matched_all);
        assert_eq!(
            r.ranges,
            vec![
                Range { start: 0, end: 1 },
                Range { start: 2, end: 3 },
                Range { start: 4, end: 5 },
            ]
        );
    }

    #[test]
    fn unmatched_query_flagged() {
        let r = SearchHighlight::highlight("zzz", "abc");
        assert!(!r.matched_all);
    }

    #[test]
    fn adjacent_chars_collapse() {
        let r = SearchHighlight::highlight("hel", "helxx");
        assert_eq!(r.ranges.len(), 1);
        assert_eq!(r.ranges[0], Range { start: 0, end: 3 });
    }

    #[test]
    fn validate_in_bounds_ok() {
        let r = SearchHighlight::highlight("hel", "hello");
        r.validate(5).unwrap();
    }

    #[test]
    fn validate_out_of_bounds_rejected() {
        let mut r = SearchHighlight::highlight("hel", "hello");
        r.ranges[0].end = 99;
        assert!(matches!(
            r.validate(5).unwrap_err(),
            HighlightError::RangeOutOfBounds { .. }
        ));
    }

    #[test]
    fn validate_overlap_rejected() {
        let r = HighlightResult {
            schema_version: SCHEMA_VERSION.into(),
            ranges: vec![Range { start: 0, end: 3 }, Range { start: 2, end: 5 }],
            matched_all: true,
        };
        assert!(matches!(
            r.validate(10).unwrap_err(),
            HighlightError::RangeOverlap { .. }
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = SearchHighlight::highlight("hel", "hello");
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate(5).unwrap_err(),
            HighlightError::SchemaMismatch
        ));
    }

    #[test]
    fn result_serde_roundtrip() {
        let r = SearchHighlight::highlight("axb", "axbycz");
        let j = serde_json::to_string(&r).unwrap();
        let back: HighlightResult = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
