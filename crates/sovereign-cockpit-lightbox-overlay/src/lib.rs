//! `sovereign-cockpit-lightbox-overlay` — fullscreen image lightbox.
//!
//! items: Vec<String> (urls/ids). open(i) opens at index, close
//! dismisses. next/prev advance the index (wraps if cyclic config
//! is set). current returns the current item when open.
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
pub struct LightboxOverlay {
    /// Schema version.
    pub schema_version: String,
    /// Items.
    pub items: Vec<String>,
    /// Open at index; None means closed.
    pub open_at: Option<usize>,
    /// Wrap at boundaries.
    pub cyclic: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LightboxError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty items list.
    #[error("items empty")]
    EmptyItems,
    /// Out of range.
    #[error("index out of range")]
    OutOfRange,
    /// Not open.
    #[error("lightbox not open")]
    NotOpen,
}

impl LightboxOverlay {
    /// New (closed) — items must be non-empty.
    pub fn new(items: Vec<String>, cyclic: bool) -> Result<Self, LightboxError> {
        if items.is_empty() {
            return Err(LightboxError::EmptyItems);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            items,
            open_at: None,
            cyclic,
        })
    }

    /// Open at index i.
    pub fn open(&mut self, i: usize) -> Result<(), LightboxError> {
        if i >= self.items.len() {
            return Err(LightboxError::OutOfRange);
        }
        self.open_at = Some(i);
        Ok(())
    }

    /// Close.
    pub fn close(&mut self) {
        self.open_at = None;
    }

    /// True iff open.
    pub fn is_open(&self) -> bool {
        self.open_at.is_some()
    }

    /// Current item.
    pub fn current(&self) -> Option<&str> {
        self.open_at.map(|i| self.items[i].as_str())
    }

    /// Next; wraps if cyclic, returns NotOpen if closed.
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Result<&str, LightboxError> {
        let i = self.open_at.ok_or(LightboxError::NotOpen)?;
        let last = self.items.len() - 1;
        let new_i = if i < last {
            i + 1
        } else if self.cyclic {
            0
        } else {
            last
        };
        self.open_at = Some(new_i);
        Ok(&self.items[new_i])
    }

    /// Prev.
    pub fn prev(&mut self) -> Result<&str, LightboxError> {
        let i = self.open_at.ok_or(LightboxError::NotOpen)?;
        let new_i = if i > 0 {
            i - 1
        } else if self.cyclic {
            self.items.len() - 1
        } else {
            0
        };
        self.open_at = Some(new_i);
        Ok(&self.items[new_i])
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LightboxError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LightboxError::SchemaMismatch);
        }
        if self.items.is_empty() {
            return Err(LightboxError::EmptyItems);
        }
        if let Some(i) = self.open_at
            && i >= self.items.len()
        {
            return Err(LightboxError::OutOfRange);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lb(cyclic: bool) -> LightboxOverlay {
        LightboxOverlay::new(vec!["a".into(), "b".into(), "c".into()], cyclic).unwrap()
    }

    #[test]
    fn open_close() {
        let mut l = lb(false);
        l.open(1).unwrap();
        assert!(l.is_open());
        assert_eq!(l.current(), Some("b"));
        l.close();
        assert!(!l.is_open());
    }

    #[test]
    fn next_advances() {
        let mut l = lb(false);
        l.open(0).unwrap();
        assert_eq!(l.next().unwrap(), "b");
        assert_eq!(l.next().unwrap(), "c");
    }

    #[test]
    fn next_at_end_non_cyclic_stays() {
        let mut l = lb(false);
        l.open(2).unwrap();
        assert_eq!(l.next().unwrap(), "c");
    }

    #[test]
    fn next_at_end_cyclic_wraps() {
        let mut l = lb(true);
        l.open(2).unwrap();
        assert_eq!(l.next().unwrap(), "a");
    }

    #[test]
    fn prev_at_start_cyclic_wraps_to_end() {
        let mut l = lb(true);
        l.open(0).unwrap();
        assert_eq!(l.prev().unwrap(), "c");
    }

    #[test]
    fn out_of_range_open_rejected() {
        let mut l = lb(false);
        assert!(matches!(l.open(99).unwrap_err(), LightboxError::OutOfRange));
    }

    #[test]
    fn next_when_closed_rejected() {
        let mut l = lb(false);
        assert!(matches!(l.next().unwrap_err(), LightboxError::NotOpen));
    }

    #[test]
    fn empty_items_rejected() {
        assert!(matches!(
            LightboxOverlay::new(vec![], false).unwrap_err(),
            LightboxError::EmptyItems
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = lb(false);
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            LightboxError::SchemaMismatch
        ));
    }

    #[test]
    fn lightbox_serde_roundtrip() {
        let mut l = lb(true);
        l.open(1).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: LightboxOverlay = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
