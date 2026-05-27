//! `sovereign-cockpit-column-pin` — Left/Right/None column pinning.
//!
//! Each column is `Pinned::Left{order}`, `Pinned::Right{order}`, or
//! `Pinned::None`. `pin(id, side, order)` updates; `unpin(id)` clears.
//! `ordered_by_side(side)` returns the columns on that side sorted
//! by `order` then by id.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Side.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Side {
    /// Left.
    Left,
    /// Right.
    Right,
}

/// Pin state.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Pinned {
    /// Not pinned.
    None,
    /// Pinned to a side at an order.
    On {
        /// side.
        side: Side,
        /// 0-based order within side.
        order: u32,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColumnPin {
    /// Schema version.
    pub schema_version: String,
    /// id → Pinned.
    pub columns: BTreeMap<String, Pinned>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PinError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("column id empty")]
    EmptyId,
}

impl ColumnPin {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            columns: BTreeMap::new(),
        }
    }

    /// Pin.
    pub fn pin(&mut self, id: &str, side: Side, order: u32) -> Result<(), PinError> {
        if id.is_empty() {
            return Err(PinError::EmptyId);
        }
        self.columns.insert(id.into(), Pinned::On { side, order });
        Ok(())
    }

    /// Unpin.
    pub fn unpin(&mut self, id: &str) {
        if let Some(p) = self.columns.get_mut(id) {
            *p = Pinned::None;
        }
    }

    /// Pinning of a column.
    pub fn pinning(&self, id: &str) -> Pinned {
        self.columns.get(id).copied().unwrap_or(Pinned::None)
    }

    /// Ordered ids on a side.
    pub fn ordered_by_side(&self, side: Side) -> Vec<String> {
        let mut v: Vec<(u32, &str)> = self
            .columns
            .iter()
            .filter_map(|(id, p)| match p {
                Pinned::On { side: s, order } if *s == side => Some((*order, id.as_str())),
                _ => None,
            })
            .collect();
        v.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(b.1)));
        v.into_iter().map(|(_, id)| id.to_string()).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PinError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PinError::SchemaMismatch);
        }
        for k in self.columns.keys() {
            if k.is_empty() {
                return Err(PinError::EmptyId);
            }
        }
        Ok(())
    }
}

impl Default for ColumnPin {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pin_and_ordered() {
        let mut c = ColumnPin::new();
        c.pin("a", Side::Left, 1).unwrap();
        c.pin("b", Side::Left, 0).unwrap();
        c.pin("c", Side::Right, 0).unwrap();
        assert_eq!(c.ordered_by_side(Side::Left), vec!["b", "a"]);
        assert_eq!(c.ordered_by_side(Side::Right), vec!["c"]);
    }

    #[test]
    fn unpin_clears() {
        let mut c = ColumnPin::new();
        c.pin("a", Side::Left, 0).unwrap();
        c.unpin("a");
        assert_eq!(c.ordered_by_side(Side::Left), Vec::<String>::new());
        assert_eq!(c.pinning("a"), Pinned::None);
    }

    #[test]
    fn pinning_default_none() {
        let c = ColumnPin::new();
        assert_eq!(c.pinning("missing"), Pinned::None);
    }

    #[test]
    fn ties_broken_by_id() {
        let mut c = ColumnPin::new();
        c.pin("zz", Side::Left, 0).unwrap();
        c.pin("aa", Side::Left, 0).unwrap();
        assert_eq!(c.ordered_by_side(Side::Left), vec!["aa", "zz"]);
    }

    #[test]
    fn empty_id_rejected() {
        let mut c = ColumnPin::new();
        assert!(matches!(
            c.pin("", Side::Left, 0).unwrap_err(),
            PinError::EmptyId
        ));
    }

    #[test]
    fn pin_replaces() {
        let mut c = ColumnPin::new();
        c.pin("a", Side::Left, 0).unwrap();
        c.pin("a", Side::Right, 5).unwrap();
        assert_eq!(
            c.pinning("a"),
            Pinned::On {
                side: Side::Right,
                order: 5
            }
        );
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ColumnPin::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            PinError::SchemaMismatch
        ));
    }

    #[test]
    fn pin_serde_roundtrip() {
        let mut c = ColumnPin::new();
        c.pin("a", Side::Left, 0).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: ColumnPin = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
