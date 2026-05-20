//! `sovereign-cockpit-drag-handle` — press/move/release → drag-start gesture.
//!
//! State machine:
//!
//!   `Idle`  --press(x,y)-->  `Pressed{origin}`
//!   `Pressed{o}`  --move(p)-->  `Pressed{o}`     (if |p-o| < activation_px)
//!   `Pressed{o}`  --move(p)-->  `Dragging{o,p}`  (if |p-o| ≥ activation_px) → DragStart
//!   `Dragging{o,_}`  --move(p)-->  `Dragging{o,p}` → DragMove
//!   `Pressed{_}`  --release-->  `Idle`            → Click
//!   `Dragging{_,_}`  --release-->  `Idle`         → DragEnd
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Point.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pt {
    /// x px.
    pub x: i32,
    /// y px.
    pub y: i32,
}

/// Phase.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Pressed (no drag yet).
    Pressed {
        /// origin.
        origin: Pt,
    },
    /// Dragging.
    Dragging {
        /// origin.
        origin: Pt,
        /// last cursor.
        cur: Pt,
    },
}

/// Event emitted by transitions.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum DragEvent {
    /// No-op.
    None,
    /// Drag begins.
    DragStart {
        /// origin.
        origin: Pt,
        /// current cursor.
        at: Pt,
    },
    /// Drag continues.
    DragMove {
        /// current cursor.
        at: Pt,
    },
    /// Drag ends.
    DragEnd {
        /// release point.
        at: Pt,
    },
    /// Click (press → release without drag).
    Click {
        /// release point.
        at: Pt,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DragHandle {
    /// Schema version.
    pub schema_version: String,
    /// Activation distance (px).
    pub activation_px: u32,
    /// Current phase.
    pub phase: Phase,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HandleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// activation_px zero.
    #[error("activation_px must be > 0")]
    ActivationZero,
}

impl DragHandle {
    /// New.
    pub fn new(activation_px: u32) -> Result<Self, HandleError> {
        if activation_px == 0 { return Err(HandleError::ActivationZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            activation_px,
            phase: Phase::Idle,
        })
    }

    /// Press.
    pub fn press(&mut self, x: i32, y: i32) -> DragEvent {
        self.phase = Phase::Pressed { origin: Pt { x, y } };
        DragEvent::None
    }

    /// Move cursor.
    pub fn r#move(&mut self, x: i32, y: i32) -> DragEvent {
        let p = Pt { x, y };
        match self.phase {
            Phase::Idle => DragEvent::None,
            Phase::Pressed { origin } => {
                if dist2(origin, p) >= (self.activation_px as i64).pow(2) {
                    self.phase = Phase::Dragging { origin, cur: p };
                    DragEvent::DragStart { origin, at: p }
                } else {
                    DragEvent::None
                }
            }
            Phase::Dragging { origin, .. } => {
                self.phase = Phase::Dragging { origin, cur: p };
                DragEvent::DragMove { at: p }
            }
        }
    }

    /// Release.
    pub fn release(&mut self) -> DragEvent {
        let ev = match self.phase {
            Phase::Idle => DragEvent::None,
            Phase::Pressed { origin } => DragEvent::Click { at: origin },
            Phase::Dragging { cur, .. } => DragEvent::DragEnd { at: cur },
        };
        self.phase = Phase::Idle;
        ev
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HandleError> {
        if self.schema_version != SCHEMA_VERSION { return Err(HandleError::SchemaMismatch); }
        if self.activation_px == 0 { return Err(HandleError::ActivationZero); }
        Ok(())
    }
}

fn dist2(a: Pt, b: Pt) -> i64 {
    let dx = (a.x - b.x) as i64;
    let dy = (a.y - b.y) as i64;
    dx * dx + dy * dy
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn activation_zero_rejected() {
        assert!(matches!(DragHandle::new(0).unwrap_err(), HandleError::ActivationZero));
    }

    #[test]
    fn press_then_small_move_no_drag() {
        let mut h = DragHandle::new(10).unwrap();
        h.press(100, 100);
        let v = h.r#move(102, 101);
        assert_eq!(v, DragEvent::None);
    }

    #[test]
    fn cross_threshold_fires_dragstart() {
        let mut h = DragHandle::new(10).unwrap();
        h.press(0, 0);
        let v = h.r#move(11, 0);
        assert_eq!(v, DragEvent::DragStart { origin: Pt { x: 0, y: 0 }, at: Pt { x: 11, y: 0 } });
    }

    #[test]
    fn drag_then_move_fires_dragmove() {
        let mut h = DragHandle::new(10).unwrap();
        h.press(0, 0);
        h.r#move(20, 0);
        let v = h.r#move(30, 0);
        assert_eq!(v, DragEvent::DragMove { at: Pt { x: 30, y: 0 } });
    }

    #[test]
    fn release_without_drag_is_click() {
        let mut h = DragHandle::new(10).unwrap();
        h.press(5, 5);
        let v = h.release();
        assert_eq!(v, DragEvent::Click { at: Pt { x: 5, y: 5 } });
    }

    #[test]
    fn release_after_drag_is_dragend() {
        let mut h = DragHandle::new(10).unwrap();
        h.press(0, 0);
        h.r#move(20, 0);
        let v = h.release();
        assert_eq!(v, DragEvent::DragEnd { at: Pt { x: 20, y: 0 } });
    }

    #[test]
    fn idle_move_no_event() {
        let mut h = DragHandle::new(10).unwrap();
        let v = h.r#move(100, 100);
        assert_eq!(v, DragEvent::None);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = DragHandle::new(10).unwrap();
        h.schema_version = "9.9.9".into();
        assert!(matches!(h.validate().unwrap_err(), HandleError::SchemaMismatch));
    }

    #[test]
    fn drag_serde_roundtrip() {
        let mut h = DragHandle::new(10).unwrap();
        h.press(0, 0);
        h.r#move(20, 0);
        let j = serde_json::to_string(&h).unwrap();
        let back: DragHandle = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
