//! `sovereign-cockpit-agenda-view` — chronological agenda groups.
//!
//! Each item has an id, title, and a `start_ms` timestamp (UTC).
//! Items are grouped into days using a configurable day length
//! (default 86_400_000 ms = 24h) and a `day_start_offset_ms` to
//! locale-shift midnight (default 0). `groups()` returns days in
//! ascending order; each day's items are ordered by start_ms.
//!
//! The intent is a cockpit "next 7 days" agenda — agnostic of any
//! particular timezone library; the operator chooses the offset to
//! match their locale.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 24 hours in milliseconds.
pub const DAY_MS: u64 = 86_400_000;

/// One agenda item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Item {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Start ts.
    pub start_ms: u64,
}

/// One day group.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DayGroup {
    /// Day index (0-based since epoch / day_length_ms).
    pub day_index: u64,
    /// Items.
    pub items: Vec<Item>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgendaView {
    /// Schema version.
    pub schema_version: String,
    /// Day length (default DAY_MS).
    pub day_length_ms: u64,
    /// Offset applied before bucketing (e.g. shift midnight).
    pub day_start_offset_ms: u64,
    /// id → item.
    pub items: BTreeMap<String, Item>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AgendaError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("item id empty")]
    EmptyId,
    /// Empty title.
    #[error("item title empty")]
    EmptyTitle,
    /// Duplicate.
    #[error("duplicate item id: {0}")]
    DuplicateId(String),
    /// Zero day length.
    #[error("day_length_ms must be > 0")]
    ZeroDay,
}

impl AgendaView {
    /// New (24h day, no offset).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            day_length_ms: DAY_MS,
            day_start_offset_ms: 0,
            items: BTreeMap::new(),
        }
    }

    /// Configure.
    pub fn with_day(day_length_ms: u64, day_start_offset_ms: u64) -> Result<Self, AgendaError> {
        if day_length_ms == 0 {
            return Err(AgendaError::ZeroDay);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            day_length_ms,
            day_start_offset_ms,
            items: BTreeMap::new(),
        })
    }

    /// Add an item.
    pub fn add(&mut self, item: Item) -> Result<(), AgendaError> {
        if item.id.is_empty() {
            return Err(AgendaError::EmptyId);
        }
        if item.title.is_empty() {
            return Err(AgendaError::EmptyTitle);
        }
        if self.items.contains_key(&item.id) {
            return Err(AgendaError::DuplicateId(item.id));
        }
        self.items.insert(item.id.clone(), item);
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.items.remove(id).is_some()
    }

    /// Day index for an absolute ts under this view's config.
    pub fn day_index_for(&self, ts_ms: u64) -> u64 {
        ts_ms.saturating_sub(self.day_start_offset_ms) / self.day_length_ms
    }

    /// Grouped agenda — ascending day, then ascending start_ms.
    pub fn groups(&self) -> Vec<DayGroup> {
        let mut by_day: BTreeMap<u64, Vec<Item>> = BTreeMap::new();
        for item in self.items.values() {
            by_day
                .entry(self.day_index_for(item.start_ms))
                .or_default()
                .push(item.clone());
        }
        let mut out = Vec::with_capacity(by_day.len());
        for (day_index, mut items) in by_day {
            items.sort_by(|a, b| a.start_ms.cmp(&b.start_ms).then(a.id.cmp(&b.id)));
            out.push(DayGroup { day_index, items });
        }
        out
    }

    /// Items occurring in `[from_ms, to_ms)`.
    pub fn between(&self, from_ms: u64, to_ms: u64) -> Vec<Item> {
        let mut v: Vec<Item> = self
            .items
            .values()
            .filter(|i| i.start_ms >= from_ms && i.start_ms < to_ms)
            .cloned()
            .collect();
        v.sort_by(|a, b| a.start_ms.cmp(&b.start_ms).then(a.id.cmp(&b.id)));
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AgendaError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(AgendaError::SchemaMismatch);
        }
        if self.day_length_ms == 0 {
            return Err(AgendaError::ZeroDay);
        }
        for (id, i) in &self.items {
            if id.is_empty() {
                return Err(AgendaError::EmptyId);
            }
            if i.title.is_empty() {
                return Err(AgendaError::EmptyTitle);
            }
        }
        Ok(())
    }
}

impl Default for AgendaView {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn it(id: &str, t: u64) -> Item {
        Item {
            id: id.into(),
            title: id.into(),
            start_ms: t,
        }
    }

    #[test]
    fn groups_by_day() {
        let mut a = AgendaView::new();
        a.add(it("a", 0)).unwrap();
        a.add(it("b", DAY_MS + 1)).unwrap();
        a.add(it("c", 2 * DAY_MS + 5)).unwrap();
        let g = a.groups();
        assert_eq!(g.len(), 3);
        assert_eq!(g[0].day_index, 0);
        assert_eq!(g[2].day_index, 2);
    }

    #[test]
    fn within_day_sort_by_start() {
        let mut a = AgendaView::new();
        a.add(it("late", 100)).unwrap();
        a.add(it("early", 50)).unwrap();
        let g = a.groups();
        assert_eq!(g[0].items[0].id, "early");
        assert_eq!(g[0].items[1].id, "late");
    }

    #[test]
    fn between_window() {
        let mut a = AgendaView::new();
        a.add(it("a", 100)).unwrap();
        a.add(it("b", 500)).unwrap();
        a.add(it("c", 1000)).unwrap();
        let r = a.between(100, 1000);
        assert_eq!(r.len(), 2);
        assert_eq!(r[0].id, "a");
        assert_eq!(r[1].id, "b");
    }

    #[test]
    fn duplicate_rejected() {
        let mut a = AgendaView::new();
        a.add(it("a", 0)).unwrap();
        assert!(matches!(
            a.add(it("a", 1)).unwrap_err(),
            AgendaError::DuplicateId(_)
        ));
    }

    #[test]
    fn day_offset_shifts_bucketing() {
        let mut a = AgendaView::with_day(DAY_MS, DAY_MS / 2).unwrap();
        // ts = DAY_MS/4 → after offset becomes "negative" via saturating_sub → 0, day_index 0
        a.add(it("morning", DAY_MS / 4)).unwrap();
        // ts = DAY_MS → after offset = DAY_MS/2, day_index 0
        a.add(it("noon", DAY_MS)).unwrap();
        // ts = DAY_MS + DAY_MS/2 + 1 → after offset = DAY_MS+1, day_index 1
        a.add(it("next", DAY_MS + DAY_MS / 2 + 1)).unwrap();
        let g = a.groups();
        assert_eq!(g.len(), 2);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut a = AgendaView::new();
        assert!(matches!(
            a.add(Item {
                id: "".into(),
                title: "x".into(),
                start_ms: 0
            })
            .unwrap_err(),
            AgendaError::EmptyId
        ));
        assert!(matches!(
            a.add(Item {
                id: "a".into(),
                title: "".into(),
                start_ms: 0
            })
            .unwrap_err(),
            AgendaError::EmptyTitle
        ));
    }

    #[test]
    fn zero_day_rejected() {
        assert!(matches!(
            AgendaView::with_day(0, 0).unwrap_err(),
            AgendaError::ZeroDay
        ));
    }

    #[test]
    fn remove_works() {
        let mut a = AgendaView::new();
        a.add(it("a", 0)).unwrap();
        assert!(a.remove("a"));
        assert!(a.groups().is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut a = AgendaView::new();
        a.schema_version = "9.9.9".into();
        assert!(matches!(
            a.validate().unwrap_err(),
            AgendaError::SchemaMismatch
        ));
    }

    #[test]
    fn agenda_serde_roundtrip() {
        let mut a = AgendaView::new();
        a.add(it("a", 100)).unwrap();
        let j = serde_json::to_string(&a).unwrap();
        let back: AgendaView = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
