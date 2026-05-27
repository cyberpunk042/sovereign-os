//! `sovereign-cockpit-tag-cloud` — weighted-tag font-size projection.
//!
//! Linearly maps each tag's weight to a font-size percent in
//! [min_font_pct..max_font_pct] based on the observed min/max
//! of supplied weights. All-equal weights → all rendered at midpoint.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One tag.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tag {
    /// Stable id (also the label).
    pub label: String,
    /// Weight (e.g., occurrence count).
    pub weight: u64,
}

/// Rendered cloud entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudEntry {
    /// Label.
    pub label: String,
    /// Weight.
    pub weight: u64,
    /// Font size percent.
    pub font_size_pct: u8,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TagCloud {
    /// Schema version.
    pub schema_version: String,
    /// min font size pct.
    pub min_font_pct: u8,
    /// max font size pct.
    pub max_font_pct: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TagCloudError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// min >= max.
    #[error("min_font_pct {min} >= max_font_pct {max}")]
    BadFontBounds {
        /// min.
        min: u8,
        /// max.
        max: u8,
    },
    /// Empty label.
    #[error("tag label empty")]
    EmptyLabel,
    /// Duplicate label.
    #[error("duplicate tag label: {0}")]
    DuplicateLabel(String),
}

impl TagCloud {
    /// New.
    pub fn new(min_font_pct: u8, max_font_pct: u8) -> Result<Self, TagCloudError> {
        if min_font_pct >= max_font_pct {
            return Err(TagCloudError::BadFontBounds {
                min: min_font_pct,
                max: max_font_pct,
            });
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            min_font_pct,
            max_font_pct,
        })
    }

    /// Project tags to CloudEntries.
    pub fn project(&self, tags: &[Tag]) -> Result<Vec<CloudEntry>, TagCloudError> {
        check_tags(tags)?;
        if tags.is_empty() {
            return Ok(Vec::new());
        }
        let min_w = tags.iter().map(|t| t.weight).min().unwrap();
        let max_w = tags.iter().map(|t| t.weight).max().unwrap();
        let range = max_w.saturating_sub(min_w);
        let span = (self.max_font_pct - self.min_font_pct) as u64;
        let midpoint = self.min_font_pct + (self.max_font_pct - self.min_font_pct) / 2;
        let mut out: Vec<CloudEntry> = Vec::with_capacity(tags.len());
        for t in tags {
            let font_size_pct = if range == 0 {
                midpoint
            } else {
                let offset = ((t.weight - min_w) * span) / range;
                (self.min_font_pct as u64 + offset).min(self.max_font_pct as u64) as u8
            };
            out.push(CloudEntry {
                label: t.label.clone(),
                weight: t.weight,
                font_size_pct,
            });
        }
        Ok(out)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TagCloudError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TagCloudError::SchemaMismatch);
        }
        if self.min_font_pct >= self.max_font_pct {
            return Err(TagCloudError::BadFontBounds {
                min: self.min_font_pct,
                max: self.max_font_pct,
            });
        }
        Ok(())
    }
}

fn check_tags(tags: &[Tag]) -> Result<(), TagCloudError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for t in tags {
        if t.label.is_empty() {
            return Err(TagCloudError::EmptyLabel);
        }
        if !seen.insert(t.label.as_str()) {
            return Err(TagCloudError::DuplicateLabel(t.label.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(label: &str, weight: u64) -> Tag {
        Tag {
            label: label.into(),
            weight,
        }
    }

    #[test]
    fn bad_bounds_rejected() {
        assert!(matches!(
            TagCloud::new(50, 50).unwrap_err(),
            TagCloudError::BadFontBounds { .. }
        ));
    }

    #[test]
    fn empty_tags_returns_empty() {
        let c = TagCloud::new(80, 200).unwrap();
        assert!(c.project(&[]).unwrap().is_empty());
    }

    #[test]
    fn all_equal_weights_midpoint() {
        let c = TagCloud::new(80, 200).unwrap();
        let out = c.project(&[t("a", 5), t("b", 5), t("c", 5)]).unwrap();
        for e in &out {
            assert_eq!(e.font_size_pct, 140); // midpoint of 80..200
        }
    }

    #[test]
    fn weight_maps_linearly() {
        let c = TagCloud::new(80, 200).unwrap();
        let out = c.project(&[t("low", 0), t("mid", 5), t("hi", 10)]).unwrap();
        assert_eq!(out[0].font_size_pct, 80);
        assert_eq!(out[2].font_size_pct, 200);
        // mid should be ~140.
        assert!(out[1].font_size_pct >= 130 && out[1].font_size_pct <= 150);
    }

    #[test]
    fn duplicate_rejected() {
        let c = TagCloud::new(80, 200).unwrap();
        assert!(matches!(
            c.project(&[t("a", 1), t("a", 2)]).unwrap_err(),
            TagCloudError::DuplicateLabel(_)
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let c = TagCloud::new(80, 200).unwrap();
        assert!(matches!(
            c.project(&[t("", 1)]).unwrap_err(),
            TagCloudError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = TagCloud::new(80, 200).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            TagCloudError::SchemaMismatch
        ));
    }

    #[test]
    fn cloud_serde_roundtrip() {
        let c = TagCloud::new(80, 200).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: TagCloud = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }

    #[test]
    fn entry_serde_roundtrip() {
        let c = TagCloud::new(80, 200).unwrap();
        let out = c.project(&[t("a", 1), t("b", 2)]).unwrap();
        let j = serde_json::to_string(&out).unwrap();
        let back: Vec<CloudEntry> = serde_json::from_str(&j).unwrap();
        assert_eq!(out, back);
    }
}
