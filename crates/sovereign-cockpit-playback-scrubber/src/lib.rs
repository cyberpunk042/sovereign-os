//! `sovereign-cockpit-playback-scrubber` — playhead UI state.
//!
//! current_ms (0..=total_ms), dragging flag, drag_preview_ms.
//! advance(elapsed) increments current_ms unless dragging.
//! begin_drag() starts; update_drag(ms) sets preview;
//! commit_drag() applies preview to current and clears
//! dragging; cancel_drag() drops preview.
//!
//! progress_bp 0..=10000; click_to_ms(bp) → ms; seek(ms)
//! clamps and sets directly.
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
pub struct PlaybackScrubber {
    /// Schema version.
    pub schema_version: String,
    /// Total ms.
    pub total_ms: u64,
    /// Current ms (0..=total_ms).
    pub current_ms: u64,
    /// Dragging?
    pub dragging: bool,
    /// Drag preview ms.
    pub drag_preview_ms: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ScrubberError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero total.
    #[error("total_ms must be >= 1")]
    ZeroTotal,
}

impl PlaybackScrubber {
    /// New.
    pub fn new(total_ms: u64) -> Result<Self, ScrubberError> {
        if total_ms == 0 {
            return Err(ScrubberError::ZeroTotal);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            total_ms,
            current_ms: 0,
            dragging: false,
            drag_preview_ms: 0,
        })
    }

    /// Advance playhead (no-op while dragging).
    pub fn advance(&mut self, elapsed_ms: u64) {
        if self.dragging {
            return;
        }
        self.current_ms = self
            .current_ms
            .saturating_add(elapsed_ms)
            .min(self.total_ms);
    }

    /// Seek absolute (clamped).
    pub fn seek(&mut self, ms: u64) {
        self.current_ms = ms.min(self.total_ms);
    }

    /// Begin drag (preview = current).
    pub fn begin_drag(&mut self) {
        self.dragging = true;
        self.drag_preview_ms = self.current_ms;
    }

    /// Update drag preview (clamped).
    pub fn update_drag(&mut self, ms: u64) {
        self.drag_preview_ms = ms.min(self.total_ms);
    }

    /// Commit drag — apply preview to current.
    pub fn commit_drag(&mut self) {
        if self.dragging {
            self.current_ms = self.drag_preview_ms;
            self.dragging = false;
        }
    }

    /// Cancel drag.
    pub fn cancel_drag(&mut self) {
        self.dragging = false;
        self.drag_preview_ms = self.current_ms;
    }

    /// Visible playhead: current OR preview when dragging.
    pub fn visible_ms(&self) -> u64 {
        if self.dragging {
            self.drag_preview_ms
        } else {
            self.current_ms
        }
    }

    /// Progress in basis points.
    pub fn progress_bp(&self) -> u32 {
        ((self.visible_ms() as u128 * 10_000) / self.total_ms as u128) as u32
    }

    /// Map a basis-points click → ms.
    pub fn click_to_ms(&self, bp: u32) -> u64 {
        let bp = bp.min(10_000);
        ((self.total_ms as u128 * bp as u128) / 10_000) as u64
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ScrubberError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ScrubberError::SchemaMismatch);
        }
        if self.total_ms == 0 {
            return Err(ScrubberError::ZeroTotal);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_at_zero() {
        let s = PlaybackScrubber::new(1000).unwrap();
        assert_eq!(s.current_ms, 0);
        assert_eq!(s.progress_bp(), 0);
    }

    #[test]
    fn advance_within_total() {
        let mut s = PlaybackScrubber::new(1000).unwrap();
        s.advance(500);
        assert_eq!(s.current_ms, 500);
        assert_eq!(s.progress_bp(), 5000);
    }

    #[test]
    fn advance_clamps_to_total() {
        let mut s = PlaybackScrubber::new(1000).unwrap();
        s.advance(5000);
        assert_eq!(s.current_ms, 1000);
    }

    #[test]
    fn drag_does_not_auto_advance() {
        let mut s = PlaybackScrubber::new(1000).unwrap();
        s.advance(100);
        s.begin_drag();
        s.update_drag(800);
        s.advance(100); // no-op.
        assert_eq!(s.current_ms, 100);
        assert_eq!(s.visible_ms(), 800);
    }

    #[test]
    fn commit_drag_applies() {
        let mut s = PlaybackScrubber::new(1000).unwrap();
        s.begin_drag();
        s.update_drag(500);
        s.commit_drag();
        assert_eq!(s.current_ms, 500);
        assert!(!s.dragging);
    }

    #[test]
    fn cancel_drag_discards_preview() {
        let mut s = PlaybackScrubber::new(1000).unwrap();
        s.advance(100);
        s.begin_drag();
        s.update_drag(900);
        s.cancel_drag();
        assert_eq!(s.current_ms, 100);
        assert!(!s.dragging);
    }

    #[test]
    fn click_to_ms_maps() {
        let s = PlaybackScrubber::new(1000).unwrap();
        assert_eq!(s.click_to_ms(5000), 500);
        assert_eq!(s.click_to_ms(10000), 1000);
        assert_eq!(s.click_to_ms(0), 0);
    }

    #[test]
    fn zero_total_rejected() {
        assert!(matches!(
            PlaybackScrubber::new(0).unwrap_err(),
            ScrubberError::ZeroTotal
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = PlaybackScrubber::new(1000).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            ScrubberError::SchemaMismatch
        ));
    }

    #[test]
    fn scrubber_serde_roundtrip() {
        let mut s = PlaybackScrubber::new(1000).unwrap();
        s.advance(250);
        let j = serde_json::to_string(&s).unwrap();
        let back: PlaybackScrubber = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
