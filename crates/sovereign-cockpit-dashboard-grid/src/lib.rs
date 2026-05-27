//! `sovereign-cockpit-dashboard-grid` — widget placement grid.
//!
//! N×M cell grid. Each widget occupies a rectangle (x, y, w, h).
//! place rejects off-grid or overlapping placements; remove and
//! move_to mutate. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One widget placement.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Placement {
    /// Stable id.
    pub id: String,
    /// x col (0-based).
    pub x: u32,
    /// y row (0-based).
    pub y: u32,
    /// Width in cells (>=1).
    pub w: u32,
    /// Height in cells (>=1).
    pub h: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DashboardGrid {
    /// Schema version.
    pub schema_version: String,
    /// Grid columns.
    pub cols: u32,
    /// Grid rows.
    pub rows: u32,
    /// Placements.
    pub placements: Vec<Placement>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GridError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero grid dim.
    #[error("grid dims zero")]
    DimsZero,
    /// Empty widget id.
    #[error("widget id empty")]
    EmptyId,
    /// Duplicate widget id.
    #[error("duplicate widget id: {0}")]
    DuplicateId(String),
    /// Width/height zero.
    #[error("widget {0} w or h zero")]
    SizeZero(String),
    /// Off-grid.
    #[error("widget {id} placement off-grid (x+w {xw}, y+h {yh}, cols {cols}, rows {rows})")]
    OffGrid {
        /// id.
        id: String,
        /// x+w.
        xw: u32,
        /// y+h.
        yh: u32,
        /// cols.
        cols: u32,
        /// rows.
        rows: u32,
    },
    /// Overlap.
    #[error("widget {a} overlaps {b}")]
    Overlap {
        /// a.
        a: String,
        /// b.
        b: String,
    },
    /// Unknown.
    #[error("unknown widget id: {0}")]
    Unknown(String),
}

impl DashboardGrid {
    /// New empty.
    pub fn new(cols: u32, rows: u32) -> Result<Self, GridError> {
        if cols == 0 || rows == 0 {
            return Err(GridError::DimsZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            cols,
            rows,
            placements: Vec::new(),
        })
    }

    /// Place a widget.
    pub fn place(&mut self, p: Placement) -> Result<(), GridError> {
        check_one(&p, self.cols, self.rows)?;
        if self.placements.iter().any(|x| x.id == p.id) {
            return Err(GridError::DuplicateId(p.id));
        }
        for other in &self.placements {
            if rects_overlap(&p, other) {
                return Err(GridError::Overlap {
                    a: p.id.clone(),
                    b: other.id.clone(),
                });
            }
        }
        self.placements.push(p);
        Ok(())
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> Result<(), GridError> {
        let pos = self
            .placements
            .iter()
            .position(|p| p.id == id)
            .ok_or_else(|| GridError::Unknown(id.into()))?;
        self.placements.remove(pos);
        Ok(())
    }

    /// Move widget to new (x, y).
    pub fn move_to(&mut self, id: &str, x: u32, y: u32) -> Result<(), GridError> {
        let pos = self
            .placements
            .iter()
            .position(|p| p.id == id)
            .ok_or_else(|| GridError::Unknown(id.into()))?;
        let p_orig = self.placements[pos].clone();
        let mut p = p_orig.clone();
        p.x = x;
        p.y = y;
        check_one(&p, self.cols, self.rows)?;
        for (i, other) in self.placements.iter().enumerate() {
            if i == pos {
                continue;
            }
            if rects_overlap(&p, other) {
                return Err(GridError::Overlap {
                    a: p.id.clone(),
                    b: other.id.clone(),
                });
            }
        }
        self.placements[pos] = p;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GridError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GridError::SchemaMismatch);
        }
        if self.cols == 0 || self.rows == 0 {
            return Err(GridError::DimsZero);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for p in &self.placements {
            check_one(p, self.cols, self.rows)?;
            if !seen.insert(p.id.as_str()) {
                return Err(GridError::DuplicateId(p.id.clone()));
            }
        }
        for i in 0..self.placements.len() {
            for j in (i + 1)..self.placements.len() {
                if rects_overlap(&self.placements[i], &self.placements[j]) {
                    return Err(GridError::Overlap {
                        a: self.placements[i].id.clone(),
                        b: self.placements[j].id.clone(),
                    });
                }
            }
        }
        Ok(())
    }
}

fn check_one(p: &Placement, cols: u32, rows: u32) -> Result<(), GridError> {
    if p.id.is_empty() {
        return Err(GridError::EmptyId);
    }
    if p.w == 0 || p.h == 0 {
        return Err(GridError::SizeZero(p.id.clone()));
    }
    let xw = p.x.saturating_add(p.w);
    let yh = p.y.saturating_add(p.h);
    if xw > cols || yh > rows {
        return Err(GridError::OffGrid {
            id: p.id.clone(),
            xw,
            yh,
            cols,
            rows,
        });
    }
    Ok(())
}

fn rects_overlap(a: &Placement, b: &Placement) -> bool {
    let a_right = a.x + a.w;
    let a_bottom = a.y + a.h;
    let b_right = b.x + b.w;
    let b_bottom = b.y + b.h;
    !(a_right <= b.x || b_right <= a.x || a_bottom <= b.y || b_bottom <= a.y)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p(id: &str, x: u32, y: u32, w: u32, h: u32) -> Placement {
        Placement {
            id: id.into(),
            x,
            y,
            w,
            h,
        }
    }

    #[test]
    fn empty_dims_rejected() {
        assert!(matches!(
            DashboardGrid::new(0, 5).unwrap_err(),
            GridError::DimsZero
        ));
    }

    #[test]
    fn place_basic() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.place(p("a", 0, 0, 2, 2)).unwrap();
        assert_eq!(g.placements.len(), 1);
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.place(p("a", 0, 0, 2, 2)).unwrap();
        assert!(matches!(
            g.place(p("a", 5, 5, 1, 1)).unwrap_err(),
            GridError::DuplicateId(_)
        ));
    }

    #[test]
    fn off_grid_rejected() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        assert!(matches!(
            g.place(p("a", 8, 8, 5, 5)).unwrap_err(),
            GridError::OffGrid { .. }
        ));
    }

    #[test]
    fn size_zero_rejected() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        assert!(matches!(
            g.place(p("a", 0, 0, 0, 2)).unwrap_err(),
            GridError::SizeZero(_)
        ));
    }

    #[test]
    fn overlap_rejected() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.place(p("a", 0, 0, 3, 3)).unwrap();
        assert!(matches!(
            g.place(p("b", 2, 2, 2, 2)).unwrap_err(),
            GridError::Overlap { .. }
        ));
    }

    #[test]
    fn touching_edges_not_overlap() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.place(p("a", 0, 0, 3, 3)).unwrap();
        g.place(p("b", 3, 0, 3, 3)).unwrap();
        assert_eq!(g.placements.len(), 2);
    }

    #[test]
    fn remove_and_re_place() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.place(p("a", 0, 0, 3, 3)).unwrap();
        g.remove("a").unwrap();
        g.place(p("b", 1, 1, 2, 2)).unwrap();
        assert_eq!(g.placements.len(), 1);
    }

    #[test]
    fn move_works() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.place(p("a", 0, 0, 2, 2)).unwrap();
        g.move_to("a", 5, 5).unwrap();
        assert_eq!(g.placements[0].x, 5);
    }

    #[test]
    fn move_into_overlap_rejected() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.place(p("a", 0, 0, 2, 2)).unwrap();
        g.place(p("b", 5, 5, 2, 2)).unwrap();
        assert!(matches!(
            g.move_to("a", 5, 5).unwrap_err(),
            GridError::Overlap { .. }
        ));
    }

    #[test]
    fn move_unknown_rejected() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        assert!(matches!(
            g.move_to("z", 0, 0).unwrap_err(),
            GridError::Unknown(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        assert!(matches!(
            g.place(p("", 0, 0, 1, 1)).unwrap_err(),
            GridError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            GridError::SchemaMismatch
        ));
    }

    #[test]
    fn grid_serde_roundtrip() {
        let mut g = DashboardGrid::new(10, 10).unwrap();
        g.place(p("a", 0, 0, 3, 3)).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: DashboardGrid = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
