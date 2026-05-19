//! `sovereign-cockpit-toggle-tray` — operator UI tray of feature toggles.
//!
//! Each `Toggle` declares (key, label, category, current_value, default,
//! description). Pure UX surface; the actual signed flip audit lives
//! in `selfdef-toggle-audit-authority`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 6 toggle categories.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Category {
    /// Visual / theme / density.
    Appearance,
    /// Notifications.
    Notifications,
    /// Privacy / telemetry.
    Privacy,
    /// Productivity / shortcuts.
    Productivity,
    /// Experimental / behind-flag.
    Experimental,
    /// Accessibility.
    Accessibility,
}

/// One toggle.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Toggle {
    /// Dotted key (e.g. "appearance.density").
    pub key: String,
    /// Display label.
    pub label: String,
    /// Category.
    pub category: Category,
    /// Current value.
    pub current: bool,
    /// Default value.
    pub default: bool,
    /// Help text (≤ 200 chars).
    pub description: String,
}

/// Toggle tray.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToggleTray {
    /// Schema version.
    pub schema_version: String,
    /// Toggles.
    pub toggles: Vec<Toggle>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToggleTrayError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty key.
    #[error("toggle key empty")]
    EmptyKey,
    /// Empty label.
    #[error("toggle {0} label empty")]
    EmptyLabel(String),
    /// Description too long.
    #[error("toggle {key} description length {len} > 200")]
    DescriptionTooLong {
        /// key.
        key: String,
        /// len.
        len: usize,
    },
    /// Duplicate key.
    #[error("duplicate toggle key: {0}")]
    Duplicate(String),
    /// Unknown.
    #[error("unknown toggle key: {0}")]
    Unknown(String),
}

impl ToggleTray {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            toggles: Vec::new(),
        }
    }

    /// Register a toggle.
    pub fn register(&mut self, t: Toggle) -> Result<(), ToggleTrayError> {
        check_shape(&t)?;
        if self.toggles.iter().any(|x| x.key == t.key) {
            return Err(ToggleTrayError::Duplicate(t.key));
        }
        self.toggles.push(t);
        Ok(())
    }

    /// Flip the current value.
    pub fn flip(&mut self, key: &str) -> Result<bool, ToggleTrayError> {
        let t = self.toggles.iter_mut().find(|x| x.key == key)
            .ok_or_else(|| ToggleTrayError::Unknown(key.into()))?;
        t.current = !t.current;
        Ok(t.current)
    }

    /// Set explicit value.
    pub fn set(&mut self, key: &str, value: bool) -> Result<(), ToggleTrayError> {
        let t = self.toggles.iter_mut().find(|x| x.key == key)
            .ok_or_else(|| ToggleTrayError::Unknown(key.into()))?;
        t.current = value;
        Ok(())
    }

    /// Reset to default.
    pub fn reset(&mut self, key: &str) -> Result<bool, ToggleTrayError> {
        let t = self.toggles.iter_mut().find(|x| x.key == key)
            .ok_or_else(|| ToggleTrayError::Unknown(key.into()))?;
        t.current = t.default;
        Ok(t.current)
    }

    /// Filter by category.
    pub fn by_category(&self, category: Category) -> Vec<&Toggle> {
        self.toggles.iter().filter(|t| t.category == category).collect()
    }

    /// Substring search on label (case-insensitive).
    pub fn search(&self, needle: &str) -> Vec<&Toggle> {
        let n = needle.to_ascii_lowercase();
        self.toggles.iter().filter(|t| t.label.to_ascii_lowercase().contains(&n)).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToggleTrayError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ToggleTrayError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.toggles {
            check_shape(t)?;
            if !seen.insert(t.key.as_str()) {
                return Err(ToggleTrayError::Duplicate(t.key.clone()));
            }
        }
        Ok(())
    }
}

fn check_shape(t: &Toggle) -> Result<(), ToggleTrayError> {
    if t.key.is_empty() { return Err(ToggleTrayError::EmptyKey); }
    if t.label.is_empty() { return Err(ToggleTrayError::EmptyLabel(t.key.clone())); }
    let len = t.description.chars().count();
    if len > 200 {
        return Err(ToggleTrayError::DescriptionTooLong { key: t.key.clone(), len });
    }
    Ok(())
}

impl Default for ToggleTray {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(key: &str, cat: Category, default: bool) -> Toggle {
        Toggle {
            key: key.into(),
            label: format!("Toggle {key}"),
            category: cat,
            current: default,
            default,
            description: "Description".into(),
        }
    }

    #[test]
    fn empty_tray_validates() {
        ToggleTray::new().validate().unwrap();
    }

    #[test]
    fn register_and_flip() {
        let mut tr = ToggleTray::new();
        tr.register(t("a", Category::Appearance, false)).unwrap();
        let new = tr.flip("a").unwrap();
        assert!(new);
        let new = tr.flip("a").unwrap();
        assert!(!new);
    }

    #[test]
    fn set_explicit() {
        let mut tr = ToggleTray::new();
        tr.register(t("a", Category::Appearance, false)).unwrap();
        tr.set("a", true).unwrap();
        assert!(tr.toggles[0].current);
    }

    #[test]
    fn reset_to_default() {
        let mut tr = ToggleTray::new();
        tr.register(t("a", Category::Appearance, true)).unwrap();
        tr.flip("a").unwrap();
        let v = tr.reset("a").unwrap();
        assert!(v);
    }

    #[test]
    fn by_category_filters() {
        let mut tr = ToggleTray::new();
        tr.register(t("a", Category::Appearance, false)).unwrap();
        tr.register(t("b", Category::Privacy, false)).unwrap();
        tr.register(t("c", Category::Appearance, true)).unwrap();
        assert_eq!(tr.by_category(Category::Appearance).len(), 2);
        assert_eq!(tr.by_category(Category::Privacy).len(), 1);
    }

    #[test]
    fn search_case_insensitive() {
        let mut tr = ToggleTray::new();
        let mut tog = t("a", Category::Appearance, false);
        tog.label = "Show Pretty Things".into();
        tr.register(tog).unwrap();
        assert_eq!(tr.search("pretty").len(), 1);
        assert_eq!(tr.search("PRETTY").len(), 1);
        assert_eq!(tr.search("ugly").len(), 0);
    }

    #[test]
    fn duplicate_rejected() {
        let mut tr = ToggleTray::new();
        tr.register(t("a", Category::Appearance, false)).unwrap();
        assert!(matches!(tr.register(t("a", Category::Privacy, true)).unwrap_err(),
            ToggleTrayError::Duplicate(_)));
    }

    #[test]
    fn unknown_flip_rejected() {
        let mut tr = ToggleTray::new();
        assert!(matches!(tr.flip("none").unwrap_err(), ToggleTrayError::Unknown(_)));
    }

    #[test]
    fn description_too_long_rejected() {
        let mut tr = ToggleTray::new();
        let mut tog = t("a", Category::Appearance, false);
        tog.description = "x".repeat(201);
        assert!(matches!(tr.register(tog).unwrap_err(),
            ToggleTrayError::DescriptionTooLong { .. }));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut tr = ToggleTray::new();
        tr.schema_version = "9.9.9".into();
        assert!(matches!(tr.validate().unwrap_err(), ToggleTrayError::SchemaMismatch));
    }

    #[test]
    fn category_serde_kebab() {
        assert_eq!(serde_json::to_string(&Category::Notifications).unwrap(), "\"notifications\"");
        assert_eq!(serde_json::to_string(&Category::Accessibility).unwrap(), "\"accessibility\"");
    }

    #[test]
    fn tray_serde_roundtrip() {
        let mut tr = ToggleTray::new();
        tr.register(t("a", Category::Appearance, false)).unwrap();
        let j = serde_json::to_string(&tr).unwrap();
        let back: ToggleTray = serde_json::from_str(&j).unwrap();
        assert_eq!(tr, back);
    }
}
