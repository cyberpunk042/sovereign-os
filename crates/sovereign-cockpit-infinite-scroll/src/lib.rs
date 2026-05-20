//! `sovereign-cockpit-infinite-scroll` — infinite-scroll bookkeeping.
//!
//! Per scrollable id, the cockpit tracks: the current opaque cursor,
//! how many items are loaded, whether a fetch is in flight, whether
//! the end of the stream has been reached, and last error (if any).
//!
//! `start_fetch(id)` returns Err if already in flight or at end.
//! `complete_fetch(id, new_items, next_cursor)` records success;
//! a None next_cursor means end-of-stream. `fail_fetch(id, error)`
//! records failure. `should_fetch_at(id, distance_from_end, threshold)`
//! reports whether a fetch is warranted given how close we are.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-scroller state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Scroller {
    /// Opaque cursor for the next page (None at end).
    pub next_cursor: Option<String>,
    /// Items loaded so far.
    pub loaded: u64,
    /// Fetch in flight?
    pub in_flight: bool,
    /// Reached end of stream?
    pub at_end: bool,
    /// Last error (if last fetch failed).
    pub last_error: Option<String>,
    /// Successful fetch count.
    pub fetches_ok: u64,
    /// Failed fetch count.
    pub fetches_err: u64,
}

impl Default for Scroller {
    fn default() -> Self {
        Self {
            next_cursor: None,
            loaded: 0,
            in_flight: false,
            at_end: false,
            last_error: None,
            fetches_ok: 0,
            fetches_err: 0,
        }
    }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InfiniteScroll {
    /// Schema version.
    pub schema_version: String,
    /// scroller id → state.
    pub scrollers: BTreeMap<String, Scroller>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum InfiniteScrollError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("scroller id empty")]
    EmptyId,
    /// Unknown scroller.
    #[error("unknown scroller: {0}")]
    UnknownScroller(String),
    /// Already in flight.
    #[error("fetch already in flight: {0}")]
    AlreadyInFlight(String),
    /// Already at end.
    #[error("already at end: {0}")]
    AtEnd(String),
    /// Not in flight (complete/fail called incorrectly).
    #[error("no fetch in flight: {0}")]
    NotInFlight(String),
}

impl InfiniteScroll {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            scrollers: BTreeMap::new(),
        }
    }

    /// Register a scroller (or reset it).
    pub fn register(&mut self, id: &str) -> Result<(), InfiniteScrollError> {
        if id.is_empty() { return Err(InfiniteScrollError::EmptyId); }
        self.scrollers.entry(id.into()).or_default();
        Ok(())
    }

    /// Begin a fetch.
    pub fn start_fetch(&mut self, id: &str) -> Result<(), InfiniteScrollError> {
        let s = self.scrollers.get_mut(id)
            .ok_or_else(|| InfiniteScrollError::UnknownScroller(id.into()))?;
        if s.in_flight {
            return Err(InfiniteScrollError::AlreadyInFlight(id.into()));
        }
        if s.at_end {
            return Err(InfiniteScrollError::AtEnd(id.into()));
        }
        s.in_flight = true;
        Ok(())
    }

    /// Complete a fetch with new items and optional next cursor.
    pub fn complete_fetch(&mut self, id: &str, new_items: u64, next_cursor: Option<String>) -> Result<(), InfiniteScrollError> {
        let s = self.scrollers.get_mut(id)
            .ok_or_else(|| InfiniteScrollError::UnknownScroller(id.into()))?;
        if !s.in_flight {
            return Err(InfiniteScrollError::NotInFlight(id.into()));
        }
        s.in_flight = false;
        s.loaded = s.loaded.saturating_add(new_items);
        s.at_end = next_cursor.is_none();
        s.next_cursor = next_cursor;
        s.last_error = None;
        s.fetches_ok = s.fetches_ok.saturating_add(1);
        Ok(())
    }

    /// Fail a fetch.
    pub fn fail_fetch(&mut self, id: &str, error: &str) -> Result<(), InfiniteScrollError> {
        let s = self.scrollers.get_mut(id)
            .ok_or_else(|| InfiniteScrollError::UnknownScroller(id.into()))?;
        if !s.in_flight {
            return Err(InfiniteScrollError::NotInFlight(id.into()));
        }
        s.in_flight = false;
        s.last_error = Some(error.into());
        s.fetches_err = s.fetches_err.saturating_add(1);
        Ok(())
    }

    /// Should a fetch be initiated?
    pub fn should_fetch_at(&self, id: &str, distance_from_end: u64, threshold: u64) -> bool {
        let Some(s) = self.scrollers.get(id) else { return false; };
        if s.in_flight || s.at_end { return false; }
        distance_from_end <= threshold
    }

    /// Snapshot.
    pub fn get(&self, id: &str) -> Option<&Scroller> {
        self.scrollers.get(id)
    }

    /// Reset a scroller (e.g. user re-queried).
    pub fn reset(&mut self, id: &str) -> bool {
        if let Some(s) = self.scrollers.get_mut(id) {
            *s = Scroller::default();
            true
        } else {
            false
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), InfiniteScrollError> {
        if self.schema_version != SCHEMA_VERSION { return Err(InfiniteScrollError::SchemaMismatch); }
        for k in self.scrollers.keys() {
            if k.is_empty() { return Err(InfiniteScrollError::EmptyId); }
        }
        Ok(())
    }
}

impl Default for InfiniteScroll {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_path() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        i.start_fetch("feed").unwrap();
        i.complete_fetch("feed", 20, Some("cursor-a".into())).unwrap();
        let s = i.get("feed").unwrap();
        assert_eq!(s.loaded, 20);
        assert_eq!(s.next_cursor.as_deref(), Some("cursor-a"));
        assert!(!s.at_end);
    }

    #[test]
    fn complete_without_cursor_marks_end() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        i.start_fetch("feed").unwrap();
        i.complete_fetch("feed", 5, None).unwrap();
        assert!(i.get("feed").unwrap().at_end);
    }

    #[test]
    fn double_start_rejected() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        i.start_fetch("feed").unwrap();
        assert!(matches!(i.start_fetch("feed").unwrap_err(), InfiniteScrollError::AlreadyInFlight(_)));
    }

    #[test]
    fn start_at_end_rejected() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        i.start_fetch("feed").unwrap();
        i.complete_fetch("feed", 0, None).unwrap();
        assert!(matches!(i.start_fetch("feed").unwrap_err(), InfiniteScrollError::AtEnd(_)));
    }

    #[test]
    fn fail_records_error() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        i.start_fetch("feed").unwrap();
        i.fail_fetch("feed", "timeout").unwrap();
        let s = i.get("feed").unwrap();
        assert!(!s.in_flight);
        assert_eq!(s.last_error.as_deref(), Some("timeout"));
        assert_eq!(s.fetches_err, 1);
    }

    #[test]
    fn complete_without_in_flight_rejected() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        assert!(matches!(i.complete_fetch("feed", 1, None).unwrap_err(), InfiniteScrollError::NotInFlight(_)));
    }

    #[test]
    fn should_fetch_at_respects_threshold() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        assert!(i.should_fetch_at("feed", 3, 5));
        assert!(!i.should_fetch_at("feed", 10, 5));
    }

    #[test]
    fn should_fetch_false_at_end() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        i.start_fetch("feed").unwrap();
        i.complete_fetch("feed", 0, None).unwrap();
        assert!(!i.should_fetch_at("feed", 0, 100));
    }

    #[test]
    fn reset_clears_all_state() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        i.start_fetch("feed").unwrap();
        i.complete_fetch("feed", 20, None).unwrap();
        assert!(i.reset("feed"));
        let s = i.get("feed").unwrap();
        assert_eq!(s.loaded, 0);
        assert!(!s.at_end);
    }

    #[test]
    fn empty_id_rejected() {
        let mut i = InfiniteScroll::new();
        assert!(matches!(i.register("").unwrap_err(), InfiniteScrollError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut i = InfiniteScroll::new();
        i.schema_version = "9.9.9".into();
        assert!(matches!(i.validate().unwrap_err(), InfiniteScrollError::SchemaMismatch));
    }

    #[test]
    fn scroll_serde_roundtrip() {
        let mut i = InfiniteScroll::new();
        i.register("feed").unwrap();
        i.start_fetch("feed").unwrap();
        i.complete_fetch("feed", 10, Some("c".into())).unwrap();
        let j = serde_json::to_string(&i).unwrap();
        let back: InfiniteScroll = serde_json::from_str(&j).unwrap();
        assert_eq!(i, back);
    }
}
