//! `sovereign-cockpit-step-dots` — page-indicator dots.
//!
//! Total N dots. State{total, current, visited: Vec<bool>}.
//! goto(i) advances to i (records visited). next/prev shift by 1.
//! render() yields a Dot kind per index: Active (current), Visited,
//! Unvisited.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Dot.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Dot {
    /// Active (current).
    Active,
    /// Visited.
    Visited,
    /// Unvisited.
    Unvisited,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StepDots {
    /// Schema version.
    pub schema_version: String,
    /// Total dots (>= 1).
    pub total: u32,
    /// Current index (< total).
    pub current: u32,
    /// Visited flags (len == total).
    pub visited: Vec<bool>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DotsError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero total.
    #[error("total must be >= 1")]
    ZeroTotal,
    /// Out of range.
    #[error("index out of range")]
    OutOfRange,
    /// Bad geometry.
    #[error("visited length must equal total")]
    BadGeometry,
}

impl StepDots {
    /// New.
    pub fn new(total: u32) -> Result<Self, DotsError> {
        if total == 0 {
            return Err(DotsError::ZeroTotal);
        }
        let mut visited = vec![false; total as usize];
        visited[0] = true;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            total,
            current: 0,
            visited,
        })
    }

    /// Goto.
    pub fn goto(&mut self, i: u32) -> Result<(), DotsError> {
        if i >= self.total {
            return Err(DotsError::OutOfRange);
        }
        self.current = i;
        self.visited[i as usize] = true;
        Ok(())
    }

    /// Next (saturates at total-1).
    pub fn next(&mut self) {
        if self.current + 1 < self.total {
            self.current += 1;
            self.visited[self.current as usize] = true;
        }
    }

    /// Prev (saturates at 0).
    pub fn prev(&mut self) {
        if self.current > 0 {
            self.current -= 1;
        }
    }

    /// Render.
    pub fn render(&self) -> Vec<Dot> {
        (0..self.total as usize)
            .map(|i| {
                if i as u32 == self.current {
                    Dot::Active
                } else if self.visited[i] {
                    Dot::Visited
                } else {
                    Dot::Unvisited
                }
            })
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DotsError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DotsError::SchemaMismatch);
        }
        if self.total == 0 {
            return Err(DotsError::ZeroTotal);
        }
        if self.current >= self.total {
            return Err(DotsError::OutOfRange);
        }
        if self.visited.len() != self.total as usize {
            return Err(DotsError::BadGeometry);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn render_initial_state() {
        let d = StepDots::new(5).unwrap();
        let r = d.render();
        assert_eq!(r[0], Dot::Active);
        for r in &r[1..] {
            assert_eq!(*r, Dot::Unvisited);
        }
    }

    #[test]
    fn next_advances_and_marks_visited() {
        let mut d = StepDots::new(3).unwrap();
        d.next();
        d.next();
        let r = d.render();
        assert_eq!(r[0], Dot::Visited);
        assert_eq!(r[1], Dot::Visited);
        assert_eq!(r[2], Dot::Active);
    }

    #[test]
    fn prev_does_not_unvisit() {
        let mut d = StepDots::new(3).unwrap();
        d.next();
        d.prev();
        let r = d.render();
        assert_eq!(r[0], Dot::Active);
        assert_eq!(r[1], Dot::Visited);
    }

    #[test]
    fn next_saturates_at_end() {
        let mut d = StepDots::new(2).unwrap();
        d.next();
        d.next(); // no-op
        assert_eq!(d.current, 1);
    }

    #[test]
    fn goto_jumps() {
        let mut d = StepDots::new(5).unwrap();
        d.goto(3).unwrap();
        assert_eq!(d.current, 3);
        let r = d.render();
        assert_eq!(r[3], Dot::Active);
    }

    #[test]
    fn out_of_range_rejected() {
        let mut d = StepDots::new(3).unwrap();
        assert!(matches!(d.goto(5).unwrap_err(), DotsError::OutOfRange));
    }

    #[test]
    fn zero_total_rejected() {
        assert!(matches!(
            StepDots::new(0).unwrap_err(),
            DotsError::ZeroTotal
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = StepDots::new(2).unwrap();
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DotsError::SchemaMismatch
        ));
    }

    #[test]
    fn dots_serde_roundtrip() {
        let mut d = StepDots::new(4).unwrap();
        d.next();
        let j = serde_json::to_string(&d).unwrap();
        let back: StepDots = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
