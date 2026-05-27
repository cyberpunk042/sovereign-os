//! `sovereign-cockpit-month-picker` — month/year picker.
//!
//! YearMonth (year, month 1..=12). State{visible_year, selected,
//! min, max, disabled}. select(ym) picks; prev/next_year shifts
//! the visible page; cells(year) returns 12 Cells with enabled
//! flags considering min/max/disabled.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Year-month.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct YearMonth {
    /// Year.
    pub year: i32,
    /// Month 1..=12.
    pub month: u8,
}

impl YearMonth {
    /// Build with validation.
    pub fn new(year: i32, month: u8) -> Result<Self, PickerError> {
        if !(1..=12).contains(&month) {
            return Err(PickerError::BadMonth);
        }
        Ok(Self { year, month })
    }

    /// Total months from year 0 — for comparison without external
    /// time crates.
    pub fn months_since_zero(&self) -> i64 {
        self.year as i64 * 12 + (self.month as i64 - 1)
    }
}

/// Cell.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Cell {
    /// Year-month.
    pub ym: YearMonth,
    /// Selectable.
    pub enabled: bool,
    /// Currently selected.
    pub selected: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MonthPicker {
    /// Schema version.
    pub schema_version: String,
    /// Visible year-page.
    pub visible_year: i32,
    /// Currently selected.
    pub selected: Option<YearMonth>,
    /// Min (inclusive) or None.
    pub min: Option<YearMonth>,
    /// Max (inclusive) or None.
    pub max: Option<YearMonth>,
    /// Explicitly disabled months.
    pub disabled: BTreeSet<YearMonth>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PickerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad month.
    #[error("month must be 1..=12")]
    BadMonth,
    /// Out of range.
    #[error("year-month out of allowed range")]
    OutOfRange,
    /// Disabled.
    #[error("year-month is disabled")]
    Disabled,
}

impl MonthPicker {
    /// New (visible year defaults to current year arg).
    pub fn new(visible_year: i32) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            visible_year,
            selected: None,
            min: None,
            max: None,
            disabled: BTreeSet::new(),
        }
    }

    /// Set bounds.
    pub fn set_bounds(&mut self, min: Option<YearMonth>, max: Option<YearMonth>) {
        self.min = min;
        self.max = max;
    }

    /// Disable a year-month.
    pub fn disable(&mut self, ym: YearMonth) {
        self.disabled.insert(ym);
    }

    fn is_enabled(&self, ym: YearMonth) -> bool {
        if let Some(m) = self.min
            && ym < m
        {
            return false;
        }
        if let Some(m) = self.max
            && ym > m
        {
            return false;
        }
        !self.disabled.contains(&ym)
    }

    /// Select a year-month.
    pub fn select(&mut self, ym: YearMonth) -> Result<(), PickerError> {
        if let Some(m) = self.min
            && ym < m
        {
            return Err(PickerError::OutOfRange);
        }
        if let Some(m) = self.max
            && ym > m
        {
            return Err(PickerError::OutOfRange);
        }
        if self.disabled.contains(&ym) {
            return Err(PickerError::Disabled);
        }
        self.selected = Some(ym);
        self.visible_year = ym.year;
        Ok(())
    }

    /// Cells for the visible year.
    pub fn cells(&self) -> Vec<Cell> {
        (1u8..=12)
            .map(|m| {
                let ym = YearMonth {
                    year: self.visible_year,
                    month: m,
                };
                Cell {
                    ym,
                    enabled: self.is_enabled(ym),
                    selected: self.selected == Some(ym),
                }
            })
            .collect()
    }

    /// Prev year-page.
    pub fn prev_year(&mut self) {
        self.visible_year -= 1;
    }
    /// Next year-page.
    pub fn next_year(&mut self) {
        self.visible_year += 1;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PickerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PickerError::SchemaMismatch);
        }
        for ym in self.disabled.iter() {
            if !(1..=12).contains(&ym.month) {
                return Err(PickerError::BadMonth);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cells_for_visible_year() {
        let p = MonthPicker::new(2026);
        let cells = p.cells();
        assert_eq!(cells.len(), 12);
        assert_eq!(cells[0].ym.month, 1);
        assert_eq!(cells[11].ym.month, 12);
        assert!(cells.iter().all(|c| c.enabled));
    }

    #[test]
    fn select_marks_selected() {
        let mut p = MonthPicker::new(2026);
        p.select(YearMonth::new(2026, 5).unwrap()).unwrap();
        let cells = p.cells();
        assert!(cells[4].selected);
        assert!(!cells[5].selected);
    }

    #[test]
    fn min_max_clamps_enabled() {
        let mut p = MonthPicker::new(2026);
        p.set_bounds(
            Some(YearMonth::new(2026, 3).unwrap()),
            Some(YearMonth::new(2026, 9).unwrap()),
        );
        let cells = p.cells();
        assert!(!cells[0].enabled); // Jan
        assert!(!cells[1].enabled); // Feb
        assert!(cells[2].enabled); // Mar
        assert!(cells[8].enabled); // Sep
        assert!(!cells[9].enabled); // Oct
    }

    #[test]
    fn disabled_overrides() {
        let mut p = MonthPicker::new(2026);
        p.disable(YearMonth::new(2026, 5).unwrap());
        let cells = p.cells();
        assert!(!cells[4].enabled);
        assert!(matches!(
            p.select(YearMonth::new(2026, 5).unwrap()).unwrap_err(),
            PickerError::Disabled
        ));
    }

    #[test]
    fn out_of_range_rejected() {
        let mut p = MonthPicker::new(2026);
        p.set_bounds(Some(YearMonth::new(2026, 6).unwrap()), None);
        assert!(matches!(
            p.select(YearMonth::new(2026, 1).unwrap()).unwrap_err(),
            PickerError::OutOfRange
        ));
    }

    #[test]
    fn navigation_changes_visible() {
        let mut p = MonthPicker::new(2026);
        p.prev_year();
        assert_eq!(p.visible_year, 2025);
        p.next_year();
        p.next_year();
        assert_eq!(p.visible_year, 2027);
    }

    #[test]
    fn bad_month_rejected() {
        assert!(matches!(
            YearMonth::new(2026, 0).unwrap_err(),
            PickerError::BadMonth
        ));
        assert!(matches!(
            YearMonth::new(2026, 13).unwrap_err(),
            PickerError::BadMonth
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = MonthPicker::new(2026);
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PickerError::SchemaMismatch
        ));
    }

    #[test]
    fn picker_serde_roundtrip() {
        let mut p = MonthPicker::new(2026);
        p.select(YearMonth::new(2026, 3).unwrap()).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: MonthPicker = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
