//! `sovereign-cockpit-object-fit` — object-fit geometry helper.
//!
//! Mode{Contain/Cover/Fill/None/ScaleDown}. compute(container,
//! intrinsic) returns rendered (w, h) and (off_x, off_y) inside
//! the container.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Mode.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Contain (fit inside, preserve aspect, may letterbox).
    Contain,
    /// Cover (fill container, preserve aspect, may crop).
    Cover,
    /// Fill (stretch to container).
    Fill,
    /// None (use intrinsic size).
    None,
    /// Scale-down (smaller of Contain or None).
    ScaleDown,
}

/// Rendered.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Rendered {
    /// Width (px).
    pub w: u32,
    /// Height (px).
    pub h: u32,
    /// Offset x in container.
    pub off_x: i32,
    /// Offset y in container.
    pub off_y: i32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FitError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad dim.
    #[error("dimensions must be >= 1")]
    BadDim,
}

/// Versioned wrapper.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectFit {
    /// Schema version.
    pub schema_version: String,
}

impl ObjectFit {
    /// New.
    pub fn new() -> Self {
        Self { schema_version: SCHEMA_VERSION.into() }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FitError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FitError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for ObjectFit {
    fn default() -> Self { Self::new() }
}

/// Compute.
pub fn compute(container_w: u32, container_h: u32, intrinsic_w: u32, intrinsic_h: u32, mode: Mode) -> Result<Rendered, FitError> {
    if container_w == 0 || container_h == 0 || intrinsic_w == 0 || intrinsic_h == 0 {
        return Err(FitError::BadDim);
    }
    let cw = container_w as f64;
    let ch = container_h as f64;
    let iw = intrinsic_w as f64;
    let ih = intrinsic_h as f64;
    let (w, h) = match mode {
        Mode::Fill => (cw, ch),
        Mode::None => (iw, ih),
        Mode::Contain => {
            let s = (cw / iw).min(ch / ih);
            (iw * s, ih * s)
        }
        Mode::Cover => {
            let s = (cw / iw).max(ch / ih);
            (iw * s, ih * s)
        }
        Mode::ScaleDown => {
            // smaller of Contain or None.
            let s_contain = (cw / iw).min(ch / ih);
            let s = if s_contain < 1.0 { s_contain } else { 1.0 };
            (iw * s, ih * s)
        }
    };
    let off_x = ((cw - w) / 2.0) as i32;
    let off_y = ((ch - h) / 2.0) as i32;
    Ok(Rendered {
        w: w.round() as u32,
        h: h.round() as u32,
        off_x,
        off_y,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fill_stretches() {
        let r = compute(100, 50, 200, 100, Mode::Fill).unwrap();
        assert_eq!(r.w, 100);
        assert_eq!(r.h, 50);
        assert_eq!(r.off_x, 0);
        assert_eq!(r.off_y, 0);
    }

    #[test]
    fn none_keeps_intrinsic() {
        let r = compute(100, 100, 50, 50, Mode::None).unwrap();
        assert_eq!(r.w, 50);
        assert_eq!(r.h, 50);
        assert_eq!(r.off_x, 25);
        assert_eq!(r.off_y, 25);
    }

    #[test]
    fn contain_letterboxes() {
        // Container 100x100, intrinsic 200x100 (wider). Scale = 100/200 = 0.5 → 100x50.
        let r = compute(100, 100, 200, 100, Mode::Contain).unwrap();
        assert_eq!(r.w, 100);
        assert_eq!(r.h, 50);
        assert_eq!(r.off_y, 25);
    }

    #[test]
    fn cover_crops() {
        // Container 100x100, intrinsic 200x100. Scale = max(100/200, 100/100) = 1 → 200x100.
        let r = compute(100, 100, 200, 100, Mode::Cover).unwrap();
        assert_eq!(r.w, 200);
        assert_eq!(r.h, 100);
    }

    #[test]
    fn scale_down_small_keeps_intrinsic() {
        // Intrinsic smaller than container → no scale.
        let r = compute(200, 200, 50, 50, Mode::ScaleDown).unwrap();
        assert_eq!(r.w, 50);
        assert_eq!(r.h, 50);
    }

    #[test]
    fn scale_down_big_uses_contain() {
        // Intrinsic 400x200 in 100x100 → scale 0.25 → 100x50.
        let r = compute(100, 100, 400, 200, Mode::ScaleDown).unwrap();
        assert_eq!(r.w, 100);
        assert_eq!(r.h, 50);
    }

    #[test]
    fn bad_dim_rejected() {
        assert!(matches!(compute(0, 50, 100, 100, Mode::Fill).unwrap_err(), FitError::BadDim));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut o = ObjectFit::new();
        o.schema_version = "9.9.9".into();
        assert!(matches!(o.validate().unwrap_err(), FitError::SchemaMismatch));
    }

    #[test]
    fn obj_serde_roundtrip() {
        let o = ObjectFit::new();
        let j = serde_json::to_string(&o).unwrap();
        let back: ObjectFit = serde_json::from_str(&j).unwrap();
        assert_eq!(o, back);
    }
}
