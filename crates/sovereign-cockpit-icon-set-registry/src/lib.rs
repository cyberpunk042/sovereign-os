//! `sovereign-cockpit-icon-set-registry` — named icon variants.
//!
//! Each icon id has a set of `Variant { size_px, color_token,
//! url_or_data }`. `lookup(id, size, color)` returns the exact
//! variant if available, otherwise the closest size (variants are
//! ordered ascending by size). `register(id, variant)` adds.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One variant.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Variant {
    /// Size in px.
    pub size_px: u32,
    /// Colour token (e.g. "fg", "danger").
    pub color_token: String,
    /// URL or data uri.
    pub url_or_data: String,
}

/// Per-icon entry.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Icon {
    /// Sorted by size_px.
    pub variants: Vec<Variant>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct IconSetRegistry {
    /// Schema version.
    pub schema_version: String,
    /// id → icon.
    pub icons: BTreeMap<String, Icon>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum IconError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("icon id empty")]
    EmptyId,
    /// Empty colour.
    #[error("colour token empty")]
    EmptyColor,
    /// Empty url.
    #[error("url empty")]
    EmptyUrl,
    /// Zero size.
    #[error("size must be > 0")]
    ZeroSize,
}

impl IconSetRegistry {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            icons: BTreeMap::new(),
        }
    }

    /// Register a variant (replaces matching size+color if present).
    pub fn register(&mut self, id: &str, variant: Variant) -> Result<(), IconError> {
        if id.is_empty() {
            return Err(IconError::EmptyId);
        }
        if variant.size_px == 0 {
            return Err(IconError::ZeroSize);
        }
        if variant.color_token.is_empty() {
            return Err(IconError::EmptyColor);
        }
        if variant.url_or_data.is_empty() {
            return Err(IconError::EmptyUrl);
        }
        let icon = self.icons.entry(id.into()).or_default();
        // Replace if same size + color exists.
        icon.variants
            .retain(|v| !(v.size_px == variant.size_px && v.color_token == variant.color_token));
        icon.variants.push(variant);
        icon.variants.sort_by(|a, b| {
            a.size_px
                .cmp(&b.size_px)
                .then(a.color_token.cmp(&b.color_token))
        });
        Ok(())
    }

    /// Lookup.
    pub fn lookup(&self, id: &str, size_px: u32, color_token: &str) -> Option<&Variant> {
        let icon = self.icons.get(id)?;
        // Exact match first.
        if let Some(exact) = icon
            .variants
            .iter()
            .find(|v| v.size_px == size_px && v.color_token == color_token)
        {
            return Some(exact);
        }
        // Closest size, preferring colour match.
        let mut best: Option<(&Variant, u32, bool)> = None; // (variant, |delta|, color_matches)
        for v in &icon.variants {
            let delta = if v.size_px >= size_px {
                v.size_px - size_px
            } else {
                size_px - v.size_px
            };
            let cmatch = v.color_token == color_token;
            let is_better = match best {
                None => true,
                Some((_, bdelta, bc)) => {
                    if cmatch != bc {
                        cmatch
                    } else {
                        delta < bdelta
                    }
                }
            };
            if is_better {
                best = Some((v, delta, cmatch));
            }
        }
        best.map(|(v, _, _)| v)
    }

    /// Remove an icon entirely.
    pub fn remove(&mut self, id: &str) -> bool {
        self.icons.remove(id).is_some()
    }

    /// Variants of an icon.
    pub fn variants_of(&self, id: &str) -> Vec<Variant> {
        self.icons
            .get(id)
            .map(|i| i.variants.clone())
            .unwrap_or_default()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), IconError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(IconError::SchemaMismatch);
        }
        for (id, icon) in &self.icons {
            if id.is_empty() {
                return Err(IconError::EmptyId);
            }
            for v in &icon.variants {
                if v.size_px == 0 {
                    return Err(IconError::ZeroSize);
                }
                if v.color_token.is_empty() {
                    return Err(IconError::EmptyColor);
                }
                if v.url_or_data.is_empty() {
                    return Err(IconError::EmptyUrl);
                }
            }
        }
        Ok(())
    }
}

impl Default for IconSetRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn variant(size: u32, color: &str, url: &str) -> Variant {
        Variant {
            size_px: size,
            color_token: color.into(),
            url_or_data: url.into(),
        }
    }

    #[test]
    fn register_and_exact_lookup() {
        let mut r = IconSetRegistry::new();
        r.register("save", variant(16, "fg", "save-16-fg.svg"))
            .unwrap();
        r.register("save", variant(32, "fg", "save-32-fg.svg"))
            .unwrap();
        let v = r.lookup("save", 16, "fg").unwrap();
        assert_eq!(v.url_or_data, "save-16-fg.svg");
    }

    #[test]
    fn lookup_closest_size_when_no_exact() {
        let mut r = IconSetRegistry::new();
        r.register("save", variant(16, "fg", "16.svg")).unwrap();
        r.register("save", variant(48, "fg", "48.svg")).unwrap();
        // Request 24 → 16 is closest (delta 8 vs 24).
        let v = r.lookup("save", 24, "fg").unwrap();
        assert_eq!(v.size_px, 16);
    }

    #[test]
    fn prefer_color_match_over_size() {
        let mut r = IconSetRegistry::new();
        r.register("save", variant(16, "fg", "fg.svg")).unwrap();
        r.register("save", variant(64, "danger", "danger.svg"))
            .unwrap();
        // Want 16, "danger". No 16/danger exists; 64/danger has color
        // match, 16/fg doesn't. Prefer color match.
        let v = r.lookup("save", 16, "danger").unwrap();
        assert_eq!(v.color_token, "danger");
    }

    #[test]
    fn register_replaces_same_size_color() {
        let mut r = IconSetRegistry::new();
        r.register("save", variant(16, "fg", "old.svg")).unwrap();
        r.register("save", variant(16, "fg", "new.svg")).unwrap();
        assert_eq!(r.variants_of("save").len(), 1);
        assert_eq!(r.lookup("save", 16, "fg").unwrap().url_or_data, "new.svg");
    }

    #[test]
    fn unknown_icon_returns_none() {
        let r = IconSetRegistry::new();
        assert!(r.lookup("nope", 16, "fg").is_none());
    }

    #[test]
    fn variants_sorted_by_size() {
        let mut r = IconSetRegistry::new();
        r.register("x", variant(32, "fg", "32.svg")).unwrap();
        r.register("x", variant(16, "fg", "16.svg")).unwrap();
        r.register("x", variant(64, "fg", "64.svg")).unwrap();
        let v = r.variants_of("x");
        assert_eq!(v[0].size_px, 16);
        assert_eq!(v[2].size_px, 64);
    }

    #[test]
    fn remove_clears() {
        let mut r = IconSetRegistry::new();
        r.register("save", variant(16, "fg", "x")).unwrap();
        assert!(r.remove("save"));
        assert!(r.variants_of("save").is_empty());
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut r = IconSetRegistry::new();
        assert!(matches!(
            r.register("", variant(16, "fg", "u")).unwrap_err(),
            IconError::EmptyId
        ));
        assert!(matches!(
            r.register("a", variant(0, "fg", "u")).unwrap_err(),
            IconError::ZeroSize
        ));
        assert!(matches!(
            r.register("a", variant(16, "", "u")).unwrap_err(),
            IconError::EmptyColor
        ));
        assert!(matches!(
            r.register("a", variant(16, "fg", "")).unwrap_err(),
            IconError::EmptyUrl
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = IconSetRegistry::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            IconError::SchemaMismatch
        ));
    }

    #[test]
    fn icon_serde_roundtrip() {
        let mut r = IconSetRegistry::new();
        r.register("save", variant(16, "fg", "s.svg")).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: IconSetRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
