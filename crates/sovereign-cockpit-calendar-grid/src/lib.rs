//! `sovereign-cockpit-calendar-grid` — month-grid cells.
//!
//! Build a 6×7 grid for a given (year, month) and
//! first_day_of_week (0=Sun, 6=Sat). Each Cell carries
//! day, is_current_month. days_in_month / first_weekday
//! computed by simple Zeller's-style formula (Gregorian).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Cell.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Cell {
    /// Day of month (1..=31).
    pub day: u8,
    /// Day belongs to the queried month (vs prev/next overflow).
    pub is_current_month: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CalendarGrid {
    /// Schema version.
    pub schema_version: String,
    /// Year (Gregorian).
    pub year: i32,
    /// Month 1..=12.
    pub month: u8,
    /// First day of week (0=Sun..6=Sat).
    pub first_day_of_week: u8,
    /// 42 cells (6 weeks x 7 days).
    pub cells: Vec<Cell>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GridError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad month.
    #[error("month must be 1..=12")]
    BadMonth,
    /// Bad start.
    #[error("first_day_of_week must be 0..=6")]
    BadFirstDay,
}

/// Is leap year (Gregorian).
pub fn is_leap_year(y: i32) -> bool {
    (y % 4 == 0 && y % 100 != 0) || (y % 400 == 0)
}

/// Days in month.
pub fn days_in_month(year: i32, month: u8) -> Result<u8, GridError> {
    if month == 0 || month > 12 {
        return Err(GridError::BadMonth);
    }
    Ok(match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            if is_leap_year(year) {
                29
            } else {
                28
            }
        }
        _ => unreachable!(),
    })
}

/// Day of week (0=Sun) for (year, month, day=1) — Zeller's via reframing.
pub fn weekday_of_first(year: i32, month: u8) -> Result<u8, GridError> {
    if month == 0 || month > 12 {
        return Err(GridError::BadMonth);
    }
    let q = 1i32; // day 1
    let mut m = month as i32;
    let mut y = year;
    if m < 3 {
        m += 12;
        y -= 1;
    }
    let k = y.rem_euclid(100);
    let j = y.div_euclid(100);
    // Zeller's h: 0=Sat, 1=Sun, 2=Mon, ... 6=Fri
    let h = (q + (13 * (m + 1)) / 5 + k + k / 4 + j / 4 + 5 * j).rem_euclid(7);
    // Convert to 0=Sun..6=Sat: zeller(h) → (h+6) mod 7.
    Ok(((h + 6) % 7) as u8)
}

impl CalendarGrid {
    /// Build the grid.
    pub fn build(year: i32, month: u8, first_day_of_week: u8) -> Result<Self, GridError> {
        if first_day_of_week > 6 {
            return Err(GridError::BadFirstDay);
        }
        let dim = days_in_month(year, month)?;
        let first_wd = weekday_of_first(year, month)?;
        // Leading offset.
        let lead = ((7 + first_wd as i32 - first_day_of_week as i32) % 7) as usize;
        let mut cells: Vec<Cell> = Vec::with_capacity(42);
        // Prev-month tail.
        let (prev_year, prev_month) = if month == 1 {
            (year - 1, 12)
        } else {
            (year, month - 1)
        };
        let prev_dim = days_in_month(prev_year, prev_month)?;
        for i in 0..lead {
            let day = prev_dim - (lead as u8 - 1 - i as u8);
            cells.push(Cell {
                day,
                is_current_month: false,
            });
        }
        // Current month.
        for d in 1..=dim {
            cells.push(Cell {
                day: d,
                is_current_month: true,
            });
        }
        // Next-month head fill to 42.
        let mut next_day: u8 = 1;
        while cells.len() < 42 {
            cells.push(Cell {
                day: next_day,
                is_current_month: false,
            });
            next_day = next_day.saturating_add(1);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            year,
            month,
            first_day_of_week,
            cells,
        })
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GridError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GridError::SchemaMismatch);
        }
        if self.month == 0 || self.month > 12 {
            return Err(GridError::BadMonth);
        }
        if self.first_day_of_week > 6 {
            return Err(GridError::BadFirstDay);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn leap_years() {
        assert!(is_leap_year(2000));
        assert!(is_leap_year(2024));
        assert!(!is_leap_year(2100));
        assert!(!is_leap_year(2023));
    }

    #[test]
    fn days_in_months() {
        assert_eq!(days_in_month(2024, 1).unwrap(), 31);
        assert_eq!(days_in_month(2024, 2).unwrap(), 29);
        assert_eq!(days_in_month(2023, 2).unwrap(), 28);
        assert_eq!(days_in_month(2024, 4).unwrap(), 30);
    }

    #[test]
    fn weekday_known() {
        // 2024-01-01 was Monday → 0=Sun → Monday=1.
        assert_eq!(weekday_of_first(2024, 1).unwrap(), 1);
        // 2024-02-01 was Thursday → 4.
        assert_eq!(weekday_of_first(2024, 2).unwrap(), 4);
    }

    #[test]
    fn grid_42_cells() {
        let g = CalendarGrid::build(2024, 1, 0).unwrap();
        assert_eq!(g.cells.len(), 42);
    }

    #[test]
    fn current_month_cells_count() {
        let g = CalendarGrid::build(2024, 1, 0).unwrap();
        let count = g.cells.iter().filter(|c| c.is_current_month).count();
        assert_eq!(count, 31);
    }

    #[test]
    fn jan_2024_starts_with_monday_lead_sunday() {
        // Sun-start grid, first weekday Mon → 1 leading day (prev month).
        let g = CalendarGrid::build(2024, 1, 0).unwrap();
        assert!(!g.cells[0].is_current_month);
        assert_eq!(
            g.cells[1],
            Cell {
                day: 1,
                is_current_month: true
            }
        );
    }

    #[test]
    fn bad_inputs_rejected() {
        assert!(matches!(
            CalendarGrid::build(2024, 0, 0).unwrap_err(),
            GridError::BadMonth
        ));
        assert!(matches!(
            CalendarGrid::build(2024, 13, 0).unwrap_err(),
            GridError::BadMonth
        ));
        assert!(matches!(
            CalendarGrid::build(2024, 1, 7).unwrap_err(),
            GridError::BadFirstDay
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = CalendarGrid::build(2024, 1, 0).unwrap();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            GridError::SchemaMismatch
        ));
    }

    #[test]
    fn grid_serde_roundtrip() {
        let g = CalendarGrid::build(2024, 1, 0).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: CalendarGrid = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
