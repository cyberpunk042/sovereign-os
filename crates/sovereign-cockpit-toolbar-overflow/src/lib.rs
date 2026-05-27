//! `sovereign-cockpit-toolbar-overflow` — overflow-menu partition.
//!
//! Given a toolbar's items (each with priority + width_px) and the
//! measured container width, computes which items stay visible and
//! which go into an overflow menu (… button). Higher priority wins.
//! Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Reserve for the overflow ("…") button when overflow is required.
pub const OVERFLOW_BUTTON_PX: u32 = 32;

/// One toolbar item.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToolbarItem {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Visual width in px.
    pub width_px: u32,
    /// Priority (lower number = higher priority; ties broken by display order).
    pub priority: u32,
}

/// Partition output: items rendered in the bar and items pushed to
/// the overflow menu. Each preserves original display order.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Partition {
    /// Schema version.
    pub schema_version: String,
    /// Visible item ids in display order.
    pub visible: Vec<String>,
    /// Overflow item ids in display order.
    pub overflow: Vec<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToolbarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("item id empty")]
    EmptyId,
    /// Empty label.
    #[error("item {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate item id: {0}")]
    DuplicateId(String),
    /// Width zero.
    #[error("item {0} width_px zero")]
    WidthZero(String),
    /// Container width zero.
    #[error("container_width_px zero")]
    ContainerZero,
}

/// Toolbar overflow computer (stateless).
#[derive(Debug, Clone, Default)]
pub struct ToolbarOverflow;

impl ToolbarOverflow {
    /// Partition.
    pub fn partition(
        items: &[ToolbarItem],
        container_width_px: u32,
    ) -> Result<Partition, ToolbarError> {
        check_items(items)?;
        if container_width_px == 0 {
            return Err(ToolbarError::ContainerZero);
        }
        // Total of all widths.
        let total: u32 = items.iter().map(|i| i.width_px).sum();
        if total <= container_width_px {
            // Everything fits.
            return Ok(Partition {
                schema_version: SCHEMA_VERSION.into(),
                visible: items.iter().map(|i| i.id.clone()).collect(),
                overflow: Vec::new(),
            });
        }
        // Reserve for overflow button.
        let budget = container_width_px.saturating_sub(OVERFLOW_BUTTON_PX);
        // Order by priority (asc) then original index (asc).
        let mut indexed: Vec<(usize, &ToolbarItem)> = items.iter().enumerate().collect();
        indexed.sort_by(|(ia, a), (ib, b)| a.priority.cmp(&b.priority).then(ia.cmp(ib)));
        let mut visible_indices: Vec<usize> = Vec::new();
        let mut used: u32 = 0;
        for (idx, item) in &indexed {
            if used.saturating_add(item.width_px) <= budget {
                used += item.width_px;
                visible_indices.push(*idx);
            }
        }
        visible_indices.sort_unstable();
        let mut visible: Vec<String> = Vec::with_capacity(visible_indices.len());
        let mut overflow: Vec<String> = Vec::new();
        for (i, item) in items.iter().enumerate() {
            if visible_indices.binary_search(&i).is_ok() {
                visible.push(item.id.clone());
            } else {
                overflow.push(item.id.clone());
            }
        }
        Ok(Partition {
            schema_version: SCHEMA_VERSION.into(),
            visible,
            overflow,
        })
    }
}

impl Partition {
    /// Validate.
    pub fn validate(&self) -> Result<(), ToolbarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToolbarError::SchemaMismatch);
        }
        Ok(())
    }
}

fn check_items(items: &[ToolbarItem]) -> Result<(), ToolbarError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for it in items {
        if it.id.is_empty() {
            return Err(ToolbarError::EmptyId);
        }
        if it.label.is_empty() {
            return Err(ToolbarError::EmptyLabel(it.id.clone()));
        }
        if it.width_px == 0 {
            return Err(ToolbarError::WidthZero(it.id.clone()));
        }
        if !seen.insert(it.id.as_str()) {
            return Err(ToolbarError::DuplicateId(it.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn it(id: &str, w: u32, p: u32) -> ToolbarItem {
        ToolbarItem {
            id: id.into(),
            label: format!("L-{id}"),
            width_px: w,
            priority: p,
        }
    }

    #[test]
    fn everything_fits_no_overflow() {
        let items = vec![it("a", 50, 0), it("b", 50, 0)];
        let p = ToolbarOverflow::partition(&items, 200).unwrap();
        assert_eq!(p.visible, vec!["a", "b"]);
        assert!(p.overflow.is_empty());
    }

    #[test]
    fn highest_priority_wins_visible() {
        let items = vec![it("a", 100, 5), it("b", 100, 1), it("c", 100, 9)];
        // Container 150 -> budget after overflow button (32) = 118.
        // Only one 100-wide item fits (the highest priority = "b").
        let p = ToolbarOverflow::partition(&items, 150).unwrap();
        assert_eq!(p.visible, vec!["b"]);
        assert!(p.overflow.contains(&"a".to_string()));
        assert!(p.overflow.contains(&"c".to_string()));
    }

    #[test]
    fn ties_broken_by_display_order() {
        let items = vec![it("a", 100, 0), it("b", 100, 0), it("c", 100, 0)];
        // Container 250 -> budget 218 -> two fit ("a" then "b").
        let p = ToolbarOverflow::partition(&items, 250).unwrap();
        assert_eq!(p.visible, vec!["a", "b"]);
        assert_eq!(p.overflow, vec!["c"]);
    }

    #[test]
    fn partition_preserves_display_order_in_outputs() {
        let items = vec![
            it("a", 100, 5),
            it("b", 100, 1),
            it("c", 100, 3),
            it("d", 100, 9),
        ];
        // Container 350 -> budget 318 -> 3 fit (by priority): b, c, a.
        // In display order they appear as a, b, c.
        let p = ToolbarOverflow::partition(&items, 350).unwrap();
        assert_eq!(p.visible, vec!["a", "b", "c"]);
        assert_eq!(p.overflow, vec!["d"]);
    }

    #[test]
    fn empty_items_returns_empty_partition() {
        let p = ToolbarOverflow::partition(&[], 100).unwrap();
        assert!(p.visible.is_empty());
        assert!(p.overflow.is_empty());
    }

    #[test]
    fn container_zero_rejected() {
        assert!(matches!(
            ToolbarOverflow::partition(&[it("a", 10, 0)], 0).unwrap_err(),
            ToolbarError::ContainerZero
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = it("a", 10, 0);
        x.id = String::new();
        assert!(matches!(
            ToolbarOverflow::partition(&[x], 100).unwrap_err(),
            ToolbarError::EmptyId
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut x = it("a", 10, 0);
        x.label = String::new();
        assert!(matches!(
            ToolbarOverflow::partition(&[x], 100).unwrap_err(),
            ToolbarError::EmptyLabel(_)
        ));
    }

    #[test]
    fn width_zero_rejected() {
        let x = it("a", 0, 0);
        assert!(matches!(
            ToolbarOverflow::partition(&[x], 100).unwrap_err(),
            ToolbarError::WidthZero(_)
        ));
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            ToolbarOverflow::partition(&[it("a", 10, 0), it("a", 10, 0)], 100).unwrap_err(),
            ToolbarError::DuplicateId(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = Partition {
            schema_version: "9.9.9".into(),
            visible: vec![],
            overflow: vec![],
        };
        assert!(matches!(
            p.validate().unwrap_err(),
            ToolbarError::SchemaMismatch
        ));
        p.schema_version = SCHEMA_VERSION.into();
        p.validate().unwrap();
    }

    #[test]
    fn partition_serde_roundtrip() {
        let items = vec![it("a", 100, 0), it("b", 100, 1)];
        let p = ToolbarOverflow::partition(&items, 250).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: Partition = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
