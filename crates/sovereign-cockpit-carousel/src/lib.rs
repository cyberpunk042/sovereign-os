//! `sovereign-cockpit-carousel` — current-slide + auto-advance state.
//!
//! Each call to `next()` / `prev()` shifts `current` by ±1, wrapping
//! or clamping per `wrap_around`. `tick(now_ms)` advances by 1 when
//! `enable_autoplay` is true and `now_ms - last_tick_ms ≥
//! autoplay_ms`. Returns whether the slide actually changed.
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
pub struct Carousel {
    /// Schema version.
    pub schema_version: String,
    /// Number of slides (≥ 1).
    pub slide_count: u32,
    /// Current 0-based index.
    pub current: u32,
    /// Wrap at edges?
    pub wrap_around: bool,
    /// Autoplay enabled?
    pub enable_autoplay: bool,
    /// Autoplay interval (ms).
    pub autoplay_ms: u64,
    /// Last tick we acted on.
    pub last_tick_ms: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CarouselError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// No slides.
    #[error("slide_count must be ≥ 1")]
    NoSlides,
    /// Index out of range.
    #[error("current {0} >= slide_count {1}")]
    IndexOutOfRange(u32, u32),
}

impl Carousel {
    /// New.
    pub fn new(slide_count: u32, wrap_around: bool, autoplay_ms: u64, enable_autoplay: bool) -> Result<Self, CarouselError> {
        if slide_count == 0 { return Err(CarouselError::NoSlides); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            slide_count,
            current: 0,
            wrap_around,
            enable_autoplay,
            autoplay_ms,
            last_tick_ms: 0,
        })
    }

    /// Go next.
    pub fn next(&mut self) -> bool {
        if self.current + 1 < self.slide_count {
            self.current += 1;
            true
        } else if self.wrap_around {
            self.current = 0;
            true
        } else {
            false
        }
    }

    /// Go prev.
    pub fn prev(&mut self) -> bool {
        if self.current > 0 {
            self.current -= 1;
            true
        } else if self.wrap_around {
            self.current = self.slide_count - 1;
            true
        } else {
            false
        }
    }

    /// Jump to a specific slide.
    pub fn jump_to(&mut self, index: u32) -> Result<(), CarouselError> {
        if index >= self.slide_count {
            return Err(CarouselError::IndexOutOfRange(index, self.slide_count));
        }
        self.current = index;
        Ok(())
    }

    /// Tick — advance when interval elapsed.
    pub fn tick(&mut self, now_ms: u64) -> bool {
        if !self.enable_autoplay { return false; }
        if now_ms.saturating_sub(self.last_tick_ms) < self.autoplay_ms { return false; }
        self.last_tick_ms = now_ms;
        self.next()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CarouselError> {
        if self.schema_version != SCHEMA_VERSION { return Err(CarouselError::SchemaMismatch); }
        if self.slide_count == 0 { return Err(CarouselError::NoSlides); }
        if self.current >= self.slide_count {
            return Err(CarouselError::IndexOutOfRange(self.current, self.slide_count));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_slides_rejected() {
        assert!(matches!(Carousel::new(0, false, 1000, false).unwrap_err(), CarouselError::NoSlides));
    }

    #[test]
    fn next_advances() {
        let mut c = Carousel::new(3, false, 1000, false).unwrap();
        assert!(c.next());
        assert_eq!(c.current, 1);
    }

    #[test]
    fn next_clamps_no_wrap() {
        let mut c = Carousel::new(2, false, 1000, false).unwrap();
        c.next();
        assert!(!c.next());
        assert_eq!(c.current, 1);
    }

    #[test]
    fn next_wraps() {
        let mut c = Carousel::new(2, true, 1000, false).unwrap();
        c.next();
        assert!(c.next());
        assert_eq!(c.current, 0);
    }

    #[test]
    fn prev_clamps() {
        let mut c = Carousel::new(2, false, 1000, false).unwrap();
        assert!(!c.prev());
        assert_eq!(c.current, 0);
    }

    #[test]
    fn prev_wraps() {
        let mut c = Carousel::new(2, true, 1000, false).unwrap();
        assert!(c.prev());
        assert_eq!(c.current, 1);
    }

    #[test]
    fn jump_to_works() {
        let mut c = Carousel::new(5, false, 1000, false).unwrap();
        c.jump_to(3).unwrap();
        assert_eq!(c.current, 3);
        assert!(matches!(c.jump_to(10).unwrap_err(), CarouselError::IndexOutOfRange(_, _)));
    }

    #[test]
    fn tick_disabled_does_nothing() {
        let mut c = Carousel::new(3, true, 1000, false).unwrap();
        assert!(!c.tick(5000));
        assert_eq!(c.current, 0);
    }

    #[test]
    fn tick_advances_on_interval() {
        let mut c = Carousel::new(3, true, 1000, true).unwrap();
        assert!(c.tick(1000));
        assert_eq!(c.current, 1);
        assert!(!c.tick(1500));
        assert!(c.tick(2500));
        assert_eq!(c.current, 2);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = Carousel::new(2, false, 1000, false).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), CarouselError::SchemaMismatch));
    }

    #[test]
    fn carousel_serde_roundtrip() {
        let mut c = Carousel::new(3, true, 1000, true).unwrap();
        c.tick(1000);
        let j = serde_json::to_string(&c).unwrap();
        let back: Carousel = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
