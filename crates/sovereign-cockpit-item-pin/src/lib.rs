//! `sovereign-cockpit-item-pin` — pin/unpin items.
//!
//! pin(id) appends to ordered pinned list iff not pinned, errors
//! AtCapacity when len >= max_pins. unpin(id) drops. is_pinned
//! checks. ordered(items) yields pinned items in pin-order
//! first, then remaining items in original order.
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
pub struct ItemPin {
    /// Schema version.
    pub schema_version: String,
    /// Max pins.
    pub max_pins: u32,
    /// Pinned ids in pin order.
    pub pinned: Vec<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PinError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Zero max.
    #[error("max_pins must be >= 1")]
    ZeroMax,
    /// At cap.
    #[error("at capacity: {0}")]
    AtCapacity(u32),
}

impl ItemPin {
    /// New.
    pub fn new(max_pins: u32) -> Result<Self, PinError> {
        if max_pins == 0 { return Err(PinError::ZeroMax); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            max_pins,
            pinned: Vec::new(),
        })
    }

    /// Pin.
    pub fn pin(&mut self, id: &str) -> Result<(), PinError> {
        if id.is_empty() { return Err(PinError::EmptyId); }
        if self.pinned.iter().any(|p| p == id) { return Ok(()); }
        if (self.pinned.len() as u32) >= self.max_pins {
            return Err(PinError::AtCapacity(self.max_pins));
        }
        self.pinned.push(id.into());
        Ok(())
    }

    /// Unpin.
    pub fn unpin(&mut self, id: &str) -> bool {
        if let Some(pos) = self.pinned.iter().position(|p| p == id) {
            self.pinned.remove(pos);
            true
        } else {
            false
        }
    }

    /// Is pinned?
    pub fn is_pinned(&self, id: &str) -> bool {
        self.pinned.iter().any(|p| p == id)
    }

    /// Returns items in pinned-first order. Items not in input are dropped
    /// from pinned-output if not in the input list.
    pub fn ordered<'a>(&'a self, items: &'a [String]) -> Vec<&'a str> {
        let mut out: Vec<&str> = Vec::with_capacity(items.len());
        // Pinned first (in pin order), but only if still in `items`.
        for p in &self.pinned {
            if items.iter().any(|i| i == p) { out.push(p.as_str()); }
        }
        // Remaining items.
        for i in items {
            if !self.pinned.iter().any(|p| p == i) { out.push(i.as_str()); }
        }
        out
    }

    /// Count.
    pub fn len(&self) -> usize { self.pinned.len() }

    /// Validate.
    pub fn validate(&self) -> Result<(), PinError> {
        if self.schema_version != SCHEMA_VERSION { return Err(PinError::SchemaMismatch); }
        if self.max_pins == 0 { return Err(PinError::ZeroMax); }
        for p in &self.pinned {
            if p.is_empty() { return Err(PinError::EmptyId); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn items(ids: &[&str]) -> Vec<String> {
        ids.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn pin_and_order() {
        let mut p = ItemPin::new(5).unwrap();
        p.pin("b").unwrap();
        let v = items(&["a", "b", "c", "d"]);
        assert_eq!(p.ordered(&v), vec!["b", "a", "c", "d"]);
    }

    #[test]
    fn unpin_works() {
        let mut p = ItemPin::new(5).unwrap();
        p.pin("a").unwrap();
        assert!(p.unpin("a"));
        assert!(!p.unpin("a"));
    }

    #[test]
    fn pin_idempotent() {
        let mut p = ItemPin::new(5).unwrap();
        p.pin("a").unwrap();
        p.pin("a").unwrap();
        assert_eq!(p.len(), 1);
    }

    #[test]
    fn at_capacity_rejected() {
        let mut p = ItemPin::new(2).unwrap();
        p.pin("a").unwrap();
        p.pin("b").unwrap();
        assert!(matches!(p.pin("c").unwrap_err(), PinError::AtCapacity(2)));
    }

    #[test]
    fn ordered_skips_pinned_not_in_items() {
        let mut p = ItemPin::new(5).unwrap();
        p.pin("ghost").unwrap();
        let v = items(&["a", "b"]);
        assert_eq!(p.ordered(&v), vec!["a", "b"]);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut p = ItemPin::new(2).unwrap();
        assert!(matches!(p.pin("").unwrap_err(), PinError::EmptyId));
        assert!(matches!(ItemPin::new(0).unwrap_err(), PinError::ZeroMax));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ItemPin::new(2).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), PinError::SchemaMismatch));
    }

    #[test]
    fn pin_serde_roundtrip() {
        let mut p = ItemPin::new(5).unwrap();
        p.pin("a").unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: ItemPin = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
