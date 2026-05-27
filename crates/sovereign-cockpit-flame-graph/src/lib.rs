//! `sovereign-cockpit-flame-graph` — flame-graph layout.
//!
//! Frame{name, weight, children}. layout(viewport_w) returns a
//! Vec<Box2D> in left-to-right depth-first order. Each frame's
//! width is proportional to its weight; child x-offsets accumulate
//! relative to parent; depth=0 is the root row.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Frame.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Frame {
    /// Name.
    pub name: String,
    /// Self+children weight.
    pub weight: u64,
    /// Children in display order.
    pub children: Vec<Frame>,
}

/// Layout box.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Box2D {
    /// Left in px.
    pub x: u32,
    /// Depth row.
    pub depth: u32,
    /// Width in px.
    pub w: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FlameError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("name empty")]
    EmptyName,
    /// Zero viewport.
    #[error("viewport_w must be >= 1")]
    ZeroViewport,
}

impl Frame {
    /// Validate.
    pub fn validate(&self) -> Result<(), FlameError> {
        if self.name.is_empty() {
            return Err(FlameError::EmptyName);
        }
        for c in &self.children {
            c.validate()?;
        }
        Ok(())
    }
}

/// Layout.
pub fn layout(root: &Frame, viewport_w: u32) -> Result<Vec<(String, Box2D)>, FlameError> {
    if viewport_w == 0 {
        return Err(FlameError::ZeroViewport);
    }
    if root.weight == 0 {
        return Ok(Vec::new());
    }
    let mut out = Vec::new();
    walk(root, 0, 0, viewport_w, root.weight, &mut out)?;
    Ok(out)
}

fn walk(
    frame: &Frame,
    x: u32,
    depth: u32,
    viewport_w: u32,
    root_weight: u64,
    out: &mut Vec<(String, Box2D)>,
) -> Result<(), FlameError> {
    if frame.name.is_empty() {
        return Err(FlameError::EmptyName);
    }
    let w = ((frame.weight as u128) * (viewport_w as u128) / (root_weight as u128)) as u32;
    out.push((frame.name.clone(), Box2D { x, depth, w }));
    // Children laid out left-to-right starting at x.
    let mut child_x = x;
    for c in &frame.children {
        let cw = ((c.weight as u128) * (viewport_w as u128) / (root_weight as u128)) as u32;
        walk(c, child_x, depth + 1, viewport_w, root_weight, out)?;
        child_x = child_x.saturating_add(cw);
    }
    Ok(())
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), FlameError> {
    if s != SCHEMA_VERSION {
        return Err(FlameError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn root() -> Frame {
        Frame {
            name: "root".into(),
            weight: 100,
            children: vec![
                Frame {
                    name: "a".into(),
                    weight: 60,
                    children: vec![
                        Frame {
                            name: "a1".into(),
                            weight: 30,
                            children: vec![],
                        },
                        Frame {
                            name: "a2".into(),
                            weight: 20,
                            children: vec![],
                        },
                    ],
                },
                Frame {
                    name: "b".into(),
                    weight: 40,
                    children: vec![],
                },
            ],
        }
    }

    #[test]
    fn root_spans_viewport() {
        let l = layout(&root(), 1000).unwrap();
        // First entry is root.
        let (name, b) = &l[0];
        assert_eq!(name, "root");
        assert_eq!(b.w, 1000);
        assert_eq!(b.x, 0);
        assert_eq!(b.depth, 0);
    }

    #[test]
    fn weights_proportional() {
        let l = layout(&root(), 1000).unwrap();
        let a = l.iter().find(|(n, _)| n == "a").unwrap();
        let b = l.iter().find(|(n, _)| n == "b").unwrap();
        assert_eq!(a.1.w, 600);
        assert_eq!(b.1.w, 400);
        assert_eq!(a.1.x, 0);
        assert_eq!(b.1.x, 600);
    }

    #[test]
    fn children_at_deeper_depth() {
        let l = layout(&root(), 1000).unwrap();
        let a1 = l.iter().find(|(n, _)| n == "a1").unwrap();
        assert_eq!(a1.1.depth, 2);
    }

    #[test]
    fn zero_viewport_rejected() {
        assert!(matches!(
            layout(&root(), 0).unwrap_err(),
            FlameError::ZeroViewport
        ));
    }

    #[test]
    fn empty_name_rejected() {
        let f = Frame {
            name: "".into(),
            weight: 1,
            children: vec![],
        };
        assert!(matches!(f.validate().unwrap_err(), FlameError::EmptyName));
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            FlameError::SchemaMismatch
        ));
    }

    #[test]
    fn frame_serde_roundtrip() {
        let r = root();
        let j = serde_json::to_string(&r).unwrap();
        let back: Frame = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
