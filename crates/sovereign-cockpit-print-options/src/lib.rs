//! `sovereign-cockpit-print-options` — print-dialog state.
//!
//! PrintOptions holds orientation, paper size, scale percentage,
//! color mode, copy count, and page range. Setters validate ranges
//! (scale 50..=200, copies ≥ 1, page range from ≤ to).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Orientation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Orientation {
    /// Portrait.
    Portrait,
    /// Landscape.
    Landscape,
}

/// Paper size.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PaperSize {
    /// A4 (ISO).
    A4,
    /// US Letter.
    Letter,
    /// US Legal.
    Legal,
}

/// Color.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ColorMode {
    /// Color.
    Color,
    /// Greyscale.
    Greyscale,
}

/// Page range.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum PageRange {
    /// All pages.
    All,
    /// from..=to (1-based).
    From {
        /// from.
        from: u32,
        /// to.
        to: u32,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PrintOptions {
    /// Schema version.
    pub schema_version: String,
    /// Orientation.
    pub orientation: Orientation,
    /// Paper size.
    pub paper_size: PaperSize,
    /// Scale percent (50..=200).
    pub scale_pct: u16,
    /// Color.
    pub color: ColorMode,
    /// Copies (≥ 1).
    pub copies: u16,
    /// Page range.
    pub page_range: PageRange,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PrintError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Scale out of range.
    #[error("scale_pct {0} not in 50..=200")]
    BadScale(u16),
    /// Copies zero.
    #[error("copies must be ≥ 1")]
    ZeroCopies,
    /// Bad page range.
    #[error("page_range from {0} > to {1}")]
    BadRange(u32, u32),
}

impl PrintOptions {
    /// New (sensible defaults).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            orientation: Orientation::Portrait,
            paper_size: PaperSize::A4,
            scale_pct: 100,
            color: ColorMode::Color,
            copies: 1,
            page_range: PageRange::All,
        }
    }

    /// Set scale.
    pub fn set_scale(&mut self, pct: u16) -> Result<(), PrintError> {
        if !(50..=200).contains(&pct) {
            return Err(PrintError::BadScale(pct));
        }
        self.scale_pct = pct;
        Ok(())
    }

    /// Set copies.
    pub fn set_copies(&mut self, n: u16) -> Result<(), PrintError> {
        if n == 0 {
            return Err(PrintError::ZeroCopies);
        }
        self.copies = n;
        Ok(())
    }

    /// Set page range.
    pub fn set_range(&mut self, range: PageRange) -> Result<(), PrintError> {
        if let PageRange::From { from, to } = &range
            && from > to
        {
            return Err(PrintError::BadRange(*from, *to));
        }
        self.page_range = range;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PrintError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PrintError::SchemaMismatch);
        }
        if !(50..=200).contains(&self.scale_pct) {
            return Err(PrintError::BadScale(self.scale_pct));
        }
        if self.copies == 0 {
            return Err(PrintError::ZeroCopies);
        }
        if let PageRange::From { from, to } = &self.page_range
            && from > to
        {
            return Err(PrintError::BadRange(*from, *to));
        }
        Ok(())
    }
}

impl Default for PrintOptions {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_validate() {
        PrintOptions::new().validate().unwrap();
    }

    #[test]
    fn set_scale_in_range() {
        let mut p = PrintOptions::new();
        p.set_scale(150).unwrap();
        assert_eq!(p.scale_pct, 150);
    }

    #[test]
    fn set_scale_oob_rejected() {
        let mut p = PrintOptions::new();
        assert!(matches!(
            p.set_scale(20).unwrap_err(),
            PrintError::BadScale(_)
        ));
        assert!(matches!(
            p.set_scale(250).unwrap_err(),
            PrintError::BadScale(_)
        ));
    }

    #[test]
    fn copies_zero_rejected() {
        let mut p = PrintOptions::new();
        assert!(matches!(
            p.set_copies(0).unwrap_err(),
            PrintError::ZeroCopies
        ));
    }

    #[test]
    fn range_from_gt_to_rejected() {
        let mut p = PrintOptions::new();
        assert!(matches!(
            p.set_range(PageRange::From { from: 10, to: 5 })
                .unwrap_err(),
            PrintError::BadRange(_, _)
        ));
    }

    #[test]
    fn range_set_valid() {
        let mut p = PrintOptions::new();
        p.set_range(PageRange::From { from: 1, to: 10 }).unwrap();
        assert_eq!(p.page_range, PageRange::From { from: 1, to: 10 });
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = PrintOptions::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PrintError::SchemaMismatch
        ));
    }

    #[test]
    fn options_serde_roundtrip() {
        let p = PrintOptions::new();
        let j = serde_json::to_string(&p).unwrap();
        let back: PrintOptions = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
