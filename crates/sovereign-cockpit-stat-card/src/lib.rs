//! `sovereign-cockpit-stat-card` — single-stat KPI descriptor.
//!
//! `StatCard{id, label, value_text, hint, trend_chip, sparkline_source_id}`.
//! register/update/get/list — the chrome renders the card per the
//! captured fields.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Trend chip direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TrendDirection {
    /// Up.
    Up,
    /// Down.
    Down,
    /// Flat.
    Flat,
}

/// One trend chip.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct TrendChip {
    /// Direction.
    pub direction: TrendDirection,
    /// Percent change × 100 (e.g. 1234 = 12.34%).
    pub percent_x100: i32,
}

/// One stat card.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatCard {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Pre-formatted value text.
    pub value_text: String,
    /// Hint text under the value.
    pub hint: String,
    /// Optional trend chip.
    pub trend_chip: Option<TrendChip>,
    /// Optional sparkline source id.
    pub sparkline_source_id: Option<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatCardRegistry {
    /// Schema version.
    pub schema_version: String,
    /// id → card.
    pub cards: BTreeMap<String, StatCard>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CardError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("card id empty")]
    EmptyId,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Empty value.
    #[error("value_text empty")]
    EmptyValue,
    /// Duplicate.
    #[error("duplicate card id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown card id: {0}")]
    UnknownId(String),
}

impl StatCardRegistry {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            cards: BTreeMap::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, card: StatCard) -> Result<(), CardError> {
        if card.id.is_empty() { return Err(CardError::EmptyId); }
        if card.label.is_empty() { return Err(CardError::EmptyLabel); }
        if card.value_text.is_empty() { return Err(CardError::EmptyValue); }
        if self.cards.contains_key(&card.id) {
            return Err(CardError::DuplicateId(card.id));
        }
        self.cards.insert(card.id.clone(), card);
        Ok(())
    }

    /// Update an existing card.
    pub fn update(&mut self, card: StatCard) -> Result<(), CardError> {
        if !self.cards.contains_key(&card.id) {
            return Err(CardError::UnknownId(card.id));
        }
        if card.label.is_empty() { return Err(CardError::EmptyLabel); }
        if card.value_text.is_empty() { return Err(CardError::EmptyValue); }
        self.cards.insert(card.id.clone(), card);
        Ok(())
    }

    /// Get.
    pub fn get(&self, id: &str) -> Option<&StatCard> { self.cards.get(id) }

    /// List in id order.
    pub fn list(&self) -> Vec<StatCard> { self.cards.values().cloned().collect() }

    /// Validate.
    pub fn validate(&self) -> Result<(), CardError> {
        if self.schema_version != SCHEMA_VERSION { return Err(CardError::SchemaMismatch); }
        for (id, c) in &self.cards {
            if id.is_empty() { return Err(CardError::EmptyId); }
            if c.label.is_empty() { return Err(CardError::EmptyLabel); }
            if c.value_text.is_empty() { return Err(CardError::EmptyValue); }
        }
        Ok(())
    }
}

impl Default for StatCardRegistry {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn card(id: &str) -> StatCard {
        StatCard {
            id: id.into(),
            label: format!("Label {id}"),
            value_text: "42".into(),
            hint: "".into(),
            trend_chip: None,
            sparkline_source_id: None,
        }
    }

    #[test]
    fn register_and_get() {
        let mut r = StatCardRegistry::new();
        r.register(card("a")).unwrap();
        assert!(r.get("a").is_some());
    }

    #[test]
    fn duplicate_rejected() {
        let mut r = StatCardRegistry::new();
        r.register(card("a")).unwrap();
        assert!(matches!(r.register(card("a")).unwrap_err(), CardError::DuplicateId(_)));
    }

    #[test]
    fn update_replaces_value() {
        let mut r = StatCardRegistry::new();
        r.register(card("a")).unwrap();
        let mut c = card("a");
        c.value_text = "100".into();
        r.update(c).unwrap();
        assert_eq!(r.get("a").unwrap().value_text, "100");
    }

    #[test]
    fn update_unknown_rejected() {
        let mut r = StatCardRegistry::new();
        assert!(matches!(r.update(card("a")).unwrap_err(), CardError::UnknownId(_)));
    }

    #[test]
    fn empty_fields_rejected() {
        let mut r = StatCardRegistry::new();
        let mut bad = card("a");
        bad.id = "".into();
        assert!(matches!(r.register(bad).unwrap_err(), CardError::EmptyId));
        let mut bad2 = card("a");
        bad2.label = "".into();
        assert!(matches!(r.register(bad2).unwrap_err(), CardError::EmptyLabel));
        let mut bad3 = card("a");
        bad3.value_text = "".into();
        assert!(matches!(r.register(bad3).unwrap_err(), CardError::EmptyValue));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = StatCardRegistry::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), CardError::SchemaMismatch));
    }

    #[test]
    fn card_serde_roundtrip() {
        let mut r = StatCardRegistry::new();
        let mut c = card("a");
        c.trend_chip = Some(TrendChip { direction: TrendDirection::Up, percent_x100: 1234 });
        c.sparkline_source_id = Some("metric.foo".into());
        r.register(c).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: StatCardRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
