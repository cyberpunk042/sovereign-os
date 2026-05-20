//! `sovereign-cockpit-swipe-gesture` — swipe gesture detector.
//!
//! down(x, y, t) starts; move(x, y, t) updates; up(x, y, t)
//! evaluates. A swipe fires when total distance >= min_distance,
//! velocity (px/ms) >= min_velocity, AND the dominant axis ratio
//! >= 2:1 (otherwise classified as Diagonal — no swipe).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Direction.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Direction {
    /// Left.
    Left,
    /// Right.
    Right,
    /// Up.
    Up,
    /// Down.
    Down,
}

/// Outcome.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind", content = "direction")]
pub enum Outcome {
    /// Detected swipe.
    Swipe(Direction),
    /// Too short.
    TooShort,
    /// Too slow.
    TooSlow,
    /// Diagonal (neither axis dominates).
    Diagonal,
    /// Not active (no down).
    NotActive,
}

/// Config.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SwipeConfig {
    /// Minimum displacement magnitude px.
    pub min_distance: u32,
    /// Minimum velocity in px/sec.
    pub min_velocity_pps: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SwipeGesture {
    /// Schema version.
    pub schema_version: String,
    /// Config.
    pub config: SwipeConfig,
    /// Start, if active.
    pub start: Option<(i32, i32, u64)>,
    /// Last move, if any.
    pub last: Option<(i32, i32, u64)>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SwipeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero config.
    #[error("min_distance and min_velocity_pps must be >= 1")]
    ZeroCfg,
}

impl SwipeGesture {
    /// New.
    pub fn new(config: SwipeConfig) -> Result<Self, SwipeError> {
        if config.min_distance == 0 || config.min_velocity_pps == 0 {
            return Err(SwipeError::ZeroCfg);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            config,
            start: None,
            last: None,
        })
    }

    /// Down.
    pub fn down(&mut self, x: i32, y: i32, t_ms: u64) {
        self.start = Some((x, y, t_ms));
        self.last = Some((x, y, t_ms));
    }

    /// Move.
    pub fn r#move(&mut self, x: i32, y: i32, t_ms: u64) {
        if self.start.is_some() {
            self.last = Some((x, y, t_ms));
        }
    }

    /// Up — evaluates and clears active state.
    pub fn up(&mut self, x: i32, y: i32, t_ms: u64) -> Outcome {
        let (sx, sy, st) = match self.start.take() {
            Some(s) => s,
            None => return Outcome::NotActive,
        };
        self.last = None;
        let dx = (x - sx) as i64;
        let dy = (y - sy) as i64;
        let dt_ms = (t_ms.saturating_sub(st)).max(1) as i64;
        let abs_x = dx.unsigned_abs();
        let abs_y = dy.unsigned_abs();
        let dist_sq = abs_x.saturating_mul(abs_x) + abs_y.saturating_mul(abs_y);
        let min_d = self.config.min_distance as u64;
        if dist_sq < min_d.saturating_mul(min_d) {
            return Outcome::TooShort;
        }
        // Approximate distance as max axis (avoids sqrt) for velocity check;
        // exact would be sqrt(dist_sq).
        let dist_approx = abs_x.max(abs_y) as i64;
        // px per second = dist * 1000 / dt_ms.
        let vel_pps = (dist_approx.saturating_mul(1000)) / dt_ms;
        if vel_pps < self.config.min_velocity_pps as i64 {
            return Outcome::TooSlow;
        }
        // Dominant axis with 2:1 ratio.
        if abs_x >= abs_y.saturating_mul(2) {
            Outcome::Swipe(if dx > 0 { Direction::Right } else { Direction::Left })
        } else if abs_y >= abs_x.saturating_mul(2) {
            Outcome::Swipe(if dy > 0 { Direction::Down } else { Direction::Up })
        } else {
            Outcome::Diagonal
        }
    }

    /// Cancel.
    pub fn cancel(&mut self) {
        self.start = None;
        self.last = None;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SwipeError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SwipeError::SchemaMismatch); }
        if self.config.min_distance == 0 || self.config.min_velocity_pps == 0 {
            return Err(SwipeError::ZeroCfg);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn g() -> SwipeGesture {
        SwipeGesture::new(SwipeConfig { min_distance: 50, min_velocity_pps: 200 }).unwrap()
    }

    #[test]
    fn right_swipe_detected() {
        let mut s = g();
        s.down(0, 0, 0);
        // 200px in 200ms → 1000 px/s.
        let o = s.up(200, 0, 200);
        assert_eq!(o, Outcome::Swipe(Direction::Right));
    }

    #[test]
    fn left_up_down_directions() {
        let mut s = g();
        s.down(200, 200, 0);
        assert_eq!(s.up(0, 200, 200), Outcome::Swipe(Direction::Left));
        s.down(0, 200, 0);
        assert_eq!(s.up(0, 0, 200), Outcome::Swipe(Direction::Up));
        s.down(0, 0, 0);
        assert_eq!(s.up(0, 200, 200), Outcome::Swipe(Direction::Down));
    }

    #[test]
    fn too_short_rejected() {
        let mut s = g();
        s.down(0, 0, 0);
        assert_eq!(s.up(10, 0, 100), Outcome::TooShort);
    }

    #[test]
    fn too_slow_rejected() {
        let mut s = g();
        s.down(0, 0, 0);
        // 100px in 5000ms → 20 px/s (below 200).
        assert_eq!(s.up(100, 0, 5000), Outcome::TooSlow);
    }

    #[test]
    fn diagonal_classified() {
        let mut s = g();
        s.down(0, 0, 0);
        // 100x, 100y → ratio 1:1 → diagonal.
        assert_eq!(s.up(100, 100, 200), Outcome::Diagonal);
    }

    #[test]
    fn not_active_without_down() {
        let mut s = g();
        assert_eq!(s.up(100, 100, 200), Outcome::NotActive);
    }

    #[test]
    fn cancel_clears_active() {
        let mut s = g();
        s.down(0, 0, 0);
        s.cancel();
        assert_eq!(s.up(200, 0, 100), Outcome::NotActive);
    }

    #[test]
    fn zero_cfg_rejected() {
        assert!(matches!(
            SwipeGesture::new(SwipeConfig { min_distance: 0, min_velocity_pps: 10 }).unwrap_err(),
            SwipeError::ZeroCfg
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = g();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SwipeError::SchemaMismatch));
    }

    #[test]
    fn swipe_serde_roundtrip() {
        let s = g();
        let j = serde_json::to_string(&s).unwrap();
        let back: SwipeGesture = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
