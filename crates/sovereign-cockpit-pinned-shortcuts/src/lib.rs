//! `sovereign-cockpit-pinned-shortcuts` — operator-curated top-bar pins.
//!
//! Each `Pin` declares (id, label, icon, command_id, color). Max 8
//! pins; reorderable by `swap(a, b)`; duplicate ids rejected.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max pinned shortcuts.
pub const MAX_PINS: usize = 8;

/// Pin color.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PinColor {
    /// Neutral grey.
    Grey,
    /// Blue.
    Blue,
    /// Green.
    Green,
    /// Orange.
    Orange,
    /// Red.
    Red,
    /// Purple.
    Purple,
}

/// One pinned shortcut.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pin {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Icon glyph name.
    pub icon: String,
    /// Command id fired on click (matches command-palette).
    pub command_id: String,
    /// Color.
    pub color: PinColor,
}

/// Pinned-shortcut bar.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PinnedBar {
    /// Schema version.
    pub schema_version: String,
    /// Pins in display order.
    pub pins: Vec<Pin>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PinError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("pin id empty")]
    EmptyId,
    /// Empty label.
    #[error("pin {0} label empty")]
    EmptyLabel(String),
    /// Empty command_id.
    #[error("pin {0} command_id empty")]
    EmptyCommandId(String),
    /// Duplicate id.
    #[error("duplicate pin id: {0}")]
    DuplicateId(String),
    /// Bar full.
    #[error("pinned bar full ({MAX_PINS} max)")]
    Full,
    /// Pin not found.
    #[error("unknown pin id: {0}")]
    Unknown(String),
    /// Swap indices out of range.
    #[error("swap out of range: a={a} b={b} len={len}")]
    SwapOutOfRange {
        /// a.
        a: usize,
        /// b.
        b: usize,
        /// len.
        len: usize,
    },
}

impl PinnedBar {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            pins: Vec::new(),
        }
    }

    /// Add a pin.
    pub fn add(&mut self, pin: Pin) -> Result<(), PinError> {
        if pin.id.is_empty() { return Err(PinError::EmptyId); }
        if pin.label.is_empty() { return Err(PinError::EmptyLabel(pin.id)); }
        if pin.command_id.is_empty() { return Err(PinError::EmptyCommandId(pin.id)); }
        if self.pins.iter().any(|p| p.id == pin.id) {
            return Err(PinError::DuplicateId(pin.id));
        }
        if self.pins.len() >= MAX_PINS {
            return Err(PinError::Full);
        }
        self.pins.push(pin);
        Ok(())
    }

    /// Remove a pin by id.
    pub fn remove(&mut self, id: &str) -> Result<(), PinError> {
        let pos = self.pins.iter().position(|p| p.id == id)
            .ok_or_else(|| PinError::Unknown(id.into()))?;
        self.pins.remove(pos);
        Ok(())
    }

    /// Swap two pins by index.
    pub fn swap(&mut self, a: usize, b: usize) -> Result<(), PinError> {
        let len = self.pins.len();
        if a >= len || b >= len {
            return Err(PinError::SwapOutOfRange { a, b, len });
        }
        self.pins.swap(a, b);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PinError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PinError::SchemaMismatch);
        }
        if self.pins.len() > MAX_PINS { return Err(PinError::Full); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for p in &self.pins {
            if p.id.is_empty() { return Err(PinError::EmptyId); }
            if p.label.is_empty() { return Err(PinError::EmptyLabel(p.id.clone())); }
            if p.command_id.is_empty() { return Err(PinError::EmptyCommandId(p.id.clone())); }
            if !seen.insert(p.id.as_str()) {
                return Err(PinError::DuplicateId(p.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for PinnedBar {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p(id: &str, color: PinColor) -> Pin {
        Pin {
            id: id.into(),
            label: format!("Label for {id}"),
            icon: "star".into(),
            command_id: format!("cmd:{id}"),
            color,
        }
    }

    #[test]
    fn empty_bar_validates() {
        PinnedBar::new().validate().unwrap();
    }

    #[test]
    fn add_pins() {
        let mut b = PinnedBar::new();
        b.add(p("a", PinColor::Blue)).unwrap();
        b.add(p("b", PinColor::Green)).unwrap();
        assert_eq!(b.pins.len(), 2);
    }

    #[test]
    fn duplicate_rejected() {
        let mut b = PinnedBar::new();
        b.add(p("a", PinColor::Blue)).unwrap();
        assert!(matches!(b.add(p("a", PinColor::Red)).unwrap_err(), PinError::DuplicateId(_)));
    }

    #[test]
    fn max_pins_enforced() {
        let mut b = PinnedBar::new();
        for i in 0..MAX_PINS {
            b.add(p(&format!("p{i}"), PinColor::Grey)).unwrap();
        }
        assert!(matches!(b.add(p("overflow", PinColor::Red)).unwrap_err(), PinError::Full));
    }

    #[test]
    fn remove_pin() {
        let mut b = PinnedBar::new();
        b.add(p("a", PinColor::Blue)).unwrap();
        b.remove("a").unwrap();
        assert!(b.pins.is_empty());
    }

    #[test]
    fn remove_unknown_rejected() {
        let mut b = PinnedBar::new();
        assert!(matches!(b.remove("none").unwrap_err(), PinError::Unknown(_)));
    }

    #[test]
    fn swap_reorders() {
        let mut b = PinnedBar::new();
        b.add(p("a", PinColor::Blue)).unwrap();
        b.add(p("b", PinColor::Green)).unwrap();
        b.swap(0, 1).unwrap();
        assert_eq!(b.pins[0].id, "b");
        assert_eq!(b.pins[1].id, "a");
    }

    #[test]
    fn swap_out_of_range_rejected() {
        let mut b = PinnedBar::new();
        b.add(p("a", PinColor::Blue)).unwrap();
        assert!(matches!(b.swap(0, 5).unwrap_err(), PinError::SwapOutOfRange { .. }));
    }

    #[test]
    fn empty_id_rejected() {
        let mut b = PinnedBar::new();
        let mut bad = p("a", PinColor::Blue);
        bad.id = String::new();
        assert!(matches!(b.add(bad).unwrap_err(), PinError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut b = PinnedBar::new();
        let mut bad = p("a", PinColor::Blue);
        bad.label = String::new();
        assert!(matches!(b.add(bad).unwrap_err(), PinError::EmptyLabel(_)));
    }

    #[test]
    fn empty_command_rejected() {
        let mut b = PinnedBar::new();
        let mut bad = p("a", PinColor::Blue);
        bad.command_id = String::new();
        assert!(matches!(b.add(bad).unwrap_err(), PinError::EmptyCommandId(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = PinnedBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), PinError::SchemaMismatch));
    }

    #[test]
    fn color_serde_kebab() {
        assert_eq!(serde_json::to_string(&PinColor::Grey).unwrap(), "\"grey\"");
        assert_eq!(serde_json::to_string(&PinColor::Purple).unwrap(), "\"purple\"");
    }

    #[test]
    fn bar_serde_roundtrip() {
        let mut b = PinnedBar::new();
        b.add(p("a", PinColor::Blue)).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: PinnedBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
