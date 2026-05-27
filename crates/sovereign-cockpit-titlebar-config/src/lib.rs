//! `sovereign-cockpit-titlebar-config` — titlebar configuration.
//!
//! The titlebar shows: a `prefix` (app name), an ordered list of
//! `segments` (e.g. workspace > project > page), a `separator`
//! string (default " · "), and an optional `pinned_status` chip on
//! the right (e.g. "Recording", "Offline"). `render_title()` joins
//! prefix + segments with the separator.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Optional pinned status chip.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusChip {
    /// Label.
    pub label: String,
    /// Severity color hint.
    pub severity: ChipSeverity,
}

/// Chip severity.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum ChipSeverity {
    /// Info.
    Info,
    /// Notice.
    Notice,
    /// Warn.
    Warn,
    /// Error.
    Error,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TitlebarConfig {
    /// Schema version.
    pub schema_version: String,
    /// App prefix.
    pub prefix: String,
    /// Path segments (left → right).
    pub segments: Vec<String>,
    /// Separator.
    pub separator: String,
    /// Status chip (right side).
    pub pinned_status: Option<StatusChip>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TitlebarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty prefix.
    #[error("prefix empty")]
    EmptyPrefix,
    /// Empty separator.
    #[error("separator empty")]
    EmptySeparator,
    /// Empty segment.
    #[error("segment empty")]
    EmptySegment,
    /// Empty chip label.
    #[error("status chip label empty")]
    EmptyChipLabel,
}

impl TitlebarConfig {
    /// New with default separator.
    pub fn new(prefix: &str) -> Result<Self, TitlebarError> {
        if prefix.is_empty() {
            return Err(TitlebarError::EmptyPrefix);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            prefix: prefix.into(),
            segments: Vec::new(),
            separator: " · ".into(),
            pinned_status: None,
        })
    }

    /// Append a segment.
    pub fn push_segment(&mut self, seg: &str) -> Result<(), TitlebarError> {
        if seg.is_empty() {
            return Err(TitlebarError::EmptySegment);
        }
        self.segments.push(seg.into());
        Ok(())
    }

    /// Pop last segment.
    pub fn pop_segment(&mut self) -> Option<String> {
        self.segments.pop()
    }

    /// Replace segments.
    pub fn set_segments(&mut self, segs: &[&str]) -> Result<(), TitlebarError> {
        for s in segs {
            if s.is_empty() {
                return Err(TitlebarError::EmptySegment);
            }
        }
        self.segments = segs.iter().map(|s| (*s).into()).collect();
        Ok(())
    }

    /// Set separator.
    pub fn set_separator(&mut self, sep: &str) -> Result<(), TitlebarError> {
        if sep.is_empty() {
            return Err(TitlebarError::EmptySeparator);
        }
        self.separator = sep.into();
        Ok(())
    }

    /// Pin a status chip.
    pub fn pin_status(&mut self, chip: StatusChip) -> Result<(), TitlebarError> {
        if chip.label.is_empty() {
            return Err(TitlebarError::EmptyChipLabel);
        }
        self.pinned_status = Some(chip);
        Ok(())
    }

    /// Clear pinned status.
    pub fn clear_status(&mut self) {
        self.pinned_status = None;
    }

    /// Render the title string.
    pub fn render_title(&self) -> String {
        if self.segments.is_empty() {
            return self.prefix.clone();
        }
        let mut s = String::with_capacity(self.prefix.len() + 64);
        s.push_str(&self.prefix);
        for seg in &self.segments {
            s.push_str(&self.separator);
            s.push_str(seg);
        }
        s
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TitlebarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TitlebarError::SchemaMismatch);
        }
        if self.prefix.is_empty() {
            return Err(TitlebarError::EmptyPrefix);
        }
        if self.separator.is_empty() {
            return Err(TitlebarError::EmptySeparator);
        }
        for s in &self.segments {
            if s.is_empty() {
                return Err(TitlebarError::EmptySegment);
            }
        }
        if let Some(c) = &self.pinned_status {
            if c.label.is_empty() {
                return Err(TitlebarError::EmptyChipLabel);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prefix_only() {
        let t = TitlebarConfig::new("Sovereign").unwrap();
        assert_eq!(t.render_title(), "Sovereign");
    }

    #[test]
    fn with_segments() {
        let mut t = TitlebarConfig::new("Sovereign").unwrap();
        t.push_segment("Workspace A").unwrap();
        t.push_segment("Page 1").unwrap();
        assert_eq!(t.render_title(), "Sovereign · Workspace A · Page 1");
    }

    #[test]
    fn custom_separator() {
        let mut t = TitlebarConfig::new("S").unwrap();
        t.push_segment("a").unwrap();
        t.set_separator(" > ").unwrap();
        assert_eq!(t.render_title(), "S > a");
    }

    #[test]
    fn pop_segment() {
        let mut t = TitlebarConfig::new("S").unwrap();
        t.push_segment("a").unwrap();
        t.push_segment("b").unwrap();
        let p = t.pop_segment().unwrap();
        assert_eq!(p, "b");
        assert_eq!(t.render_title(), "S · a");
    }

    #[test]
    fn set_segments() {
        let mut t = TitlebarConfig::new("S").unwrap();
        t.push_segment("old").unwrap();
        t.set_segments(&["x", "y"]).unwrap();
        assert_eq!(t.render_title(), "S · x · y");
    }

    #[test]
    fn pin_status() {
        let mut t = TitlebarConfig::new("S").unwrap();
        t.pin_status(StatusChip {
            label: "Recording".into(),
            severity: ChipSeverity::Warn,
        })
        .unwrap();
        assert!(t.pinned_status.is_some());
        t.clear_status();
        assert!(t.pinned_status.is_none());
    }

    #[test]
    fn empty_inputs_rejected() {
        let t = TitlebarConfig::new("");
        assert!(matches!(t.unwrap_err(), TitlebarError::EmptyPrefix));
        let mut t = TitlebarConfig::new("S").unwrap();
        assert!(matches!(
            t.push_segment("").unwrap_err(),
            TitlebarError::EmptySegment
        ));
        assert!(matches!(
            t.set_separator("").unwrap_err(),
            TitlebarError::EmptySeparator
        ));
        assert!(matches!(
            t.pin_status(StatusChip {
                label: "".into(),
                severity: ChipSeverity::Info
            })
            .unwrap_err(),
            TitlebarError::EmptyChipLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TitlebarConfig::new("S").unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            TitlebarError::SchemaMismatch
        ));
    }

    #[test]
    fn titlebar_serde_roundtrip() {
        let mut t = TitlebarConfig::new("S").unwrap();
        t.push_segment("a").unwrap();
        t.pin_status(StatusChip {
            label: "X".into(),
            severity: ChipSeverity::Notice,
        })
        .unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: TitlebarConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
