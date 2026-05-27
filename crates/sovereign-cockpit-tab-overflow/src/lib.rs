//! `sovereign-cockpit-tab-overflow` — tab strip + chevron overflow.
//!
//! Partition tabs into inline + overflow under a measured container
//! width. The active tab is always kept inline. Reserves
//! OVERFLOW_CHEVRON_PX when overflow is needed.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Px reserved for the overflow chevron when overflow is shown.
pub const OVERFLOW_CHEVRON_PX: u32 = 24;

/// One tab.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tab {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Visual width in px.
    pub width_px: u32,
}

/// Partition output.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Partition {
    /// Schema version.
    pub schema_version: String,
    /// Inline tab ids in display order.
    pub inline: Vec<String>,
    /// Overflow tab ids in display order.
    pub overflow: Vec<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TabOverflowError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("tab id empty")]
    EmptyId,
    /// Empty label.
    #[error("tab {0} label empty")]
    EmptyLabel(String),
    /// Width zero.
    #[error("tab {0} width_px zero")]
    WidthZero(String),
    /// Duplicate id.
    #[error("duplicate tab id: {0}")]
    DuplicateId(String),
    /// Active tab not found.
    #[error("active tab id {0} not in tabs")]
    ActiveUnknown(String),
    /// Container zero.
    #[error("container_width_px zero")]
    ContainerZero,
}

/// Stateless computer.
#[derive(Debug, Clone, Default)]
pub struct TabOverflow;

impl TabOverflow {
    /// Partition.
    pub fn partition(
        tabs: &[Tab],
        active: &str,
        container_width_px: u32,
    ) -> Result<Partition, TabOverflowError> {
        check_tabs(tabs)?;
        if !tabs.iter().any(|t| t.id == active) {
            return Err(TabOverflowError::ActiveUnknown(active.into()));
        }
        if container_width_px == 0 {
            return Err(TabOverflowError::ContainerZero);
        }
        let total: u32 = tabs.iter().map(|t| t.width_px).sum();
        if total <= container_width_px {
            return Ok(Partition {
                schema_version: SCHEMA_VERSION.into(),
                inline: tabs.iter().map(|t| t.id.clone()).collect(),
                overflow: Vec::new(),
            });
        }
        // Need overflow; reserve chevron px.
        let budget = container_width_px.saturating_sub(OVERFLOW_CHEVRON_PX);
        // Start with active inline.
        let active_tab = tabs.iter().find(|t| t.id == active).unwrap();
        let mut used = active_tab.width_px.min(budget);
        let mut inline_ids: Vec<&str> = vec![active];
        // Walk display order; add each tab whose width still fits.
        for t in tabs {
            if t.id == active {
                continue;
            }
            if used.saturating_add(t.width_px) <= budget {
                used += t.width_px;
                inline_ids.push(t.id.as_str());
            }
        }
        // Preserve original display order.
        let inline_set: std::collections::HashSet<&str> = inline_ids.iter().copied().collect();
        let mut inline: Vec<String> = Vec::new();
        let mut overflow: Vec<String> = Vec::new();
        for t in tabs {
            if inline_set.contains(t.id.as_str()) {
                inline.push(t.id.clone());
            } else {
                overflow.push(t.id.clone());
            }
        }
        Ok(Partition {
            schema_version: SCHEMA_VERSION.into(),
            inline,
            overflow,
        })
    }
}

impl Partition {
    /// Validate.
    pub fn validate(&self) -> Result<(), TabOverflowError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TabOverflowError::SchemaMismatch);
        }
        Ok(())
    }
}

fn check_tabs(tabs: &[Tab]) -> Result<(), TabOverflowError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for t in tabs {
        if t.id.is_empty() {
            return Err(TabOverflowError::EmptyId);
        }
        if t.label.is_empty() {
            return Err(TabOverflowError::EmptyLabel(t.id.clone()));
        }
        if t.width_px == 0 {
            return Err(TabOverflowError::WidthZero(t.id.clone()));
        }
        if !seen.insert(t.id.as_str()) {
            return Err(TabOverflowError::DuplicateId(t.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(id: &str, w: u32) -> Tab {
        Tab {
            id: id.into(),
            label: format!("L-{id}"),
            width_px: w,
        }
    }

    #[test]
    fn all_fit_no_overflow() {
        let tabs = vec![t("a", 50), t("b", 60), t("c", 70)];
        let p = TabOverflow::partition(&tabs, "b", 200).unwrap();
        assert_eq!(p.inline, vec!["a", "b", "c"]);
        assert!(p.overflow.is_empty());
    }

    #[test]
    fn active_always_inline() {
        let tabs = vec![t("a", 100), t("b", 100), t("c", 100)];
        let p = TabOverflow::partition(&tabs, "c", 100).unwrap();
        assert!(p.inline.contains(&"c".to_string()));
    }

    #[test]
    fn overflow_takes_excess() {
        let tabs = vec![t("a", 100), t("b", 100), t("c", 100), t("d", 100)];
        let p = TabOverflow::partition(&tabs, "a", 200).unwrap();
        // 200 - 24 (chevron) = 176 budget; active a=100 in, then b=100 doesn't fit (100+100>176).
        assert!(p.inline.contains(&"a".to_string()));
        assert!(!p.inline.contains(&"b".to_string()));
    }

    #[test]
    fn order_preserved_in_outputs() {
        let tabs = vec![
            t("a", 100),
            t("b", 100),
            t("c", 100),
            t("d", 100),
            t("e", 100),
        ];
        let p = TabOverflow::partition(&tabs, "c", 324).unwrap();
        // budget = 324 - 24 = 300; active c (100), then a fits (200), then b fits (300), d doesn't.
        let inline_str: Vec<&str> = p.inline.iter().map(|s| s.as_str()).collect();
        // Display order means a,b,c stay in original positions.
        assert_eq!(inline_str, vec!["a", "b", "c"]);
        assert_eq!(p.overflow, vec!["d", "e"]);
    }

    #[test]
    fn active_unknown_rejected() {
        let tabs = vec![t("a", 50)];
        assert!(matches!(
            TabOverflow::partition(&tabs, "z", 100).unwrap_err(),
            TabOverflowError::ActiveUnknown(_)
        ));
    }

    #[test]
    fn container_zero_rejected() {
        let tabs = vec![t("a", 50)];
        assert!(matches!(
            TabOverflow::partition(&tabs, "a", 0).unwrap_err(),
            TabOverflowError::ContainerZero
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = t("a", 50);
        x.id = String::new();
        assert!(matches!(
            TabOverflow::partition(&[x], "", 100).unwrap_err(),
            TabOverflowError::EmptyId
        ));
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            TabOverflow::partition(&[t("a", 50), t("a", 50)], "a", 100).unwrap_err(),
            TabOverflowError::DuplicateId(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let p = Partition {
            schema_version: "9.9.9".into(),
            inline: vec![],
            overflow: vec![],
        };
        assert!(matches!(
            p.validate().unwrap_err(),
            TabOverflowError::SchemaMismatch
        ));
    }

    #[test]
    fn partition_serde_roundtrip() {
        let tabs = vec![t("a", 50), t("b", 60)];
        let p = TabOverflow::partition(&tabs, "a", 200).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: Partition = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
