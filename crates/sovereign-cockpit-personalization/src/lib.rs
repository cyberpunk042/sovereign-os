//! `sovereign-cockpit-personalization` — operator UX personalization for the cockpit.
//!
//! Per M060 R10137 + R10140 + R10141 + R10173-R10175 + operator
//! standing direction (verbatim, 2026-05-19):
//!
//! > "endless configurations and options and personalization's"
//!
//! - **Theme** — dark / light / auto-from-system (R10137)
//! - **Accent color** — operator-configurable per-cockpit (R10140)
//! - **Typography scale** — operator-configurable scale 0.85..1.40 (R10141)
//! - **Per-profile preference layering** — each MS040 profile carries
//!   its own theme/accent/typography overrides; switching profile via
//!   `sovereign profile <name>` (R10146) restores the saved overrides.
//! - **Per-D-NN widget ordering** — operator can reorder dashboard
//!   tiles within a slot (configuration depth per R10174).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_dashboard_coverage::CoverageManifest;
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Theme mode per R10137.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ThemeMode {
    /// Dark monochrome (default for sovereignty-clean UX).
    Dark,
    /// Light monochrome.
    Light,
    /// Auto-from-system per OS prefers-color-scheme.
    Auto,
}

/// Typography scale clamp range. 1.0 = default; below 0.85 = unreadable,
/// above 1.40 = layout reflow risk.
pub const TYPOGRAPHY_MIN: f32 = 0.85;
/// Upper bound (inclusive).
pub const TYPOGRAPHY_MAX: f32 = 1.40;

/// A single operator preference block.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Preferences {
    /// Theme mode.
    pub theme: ThemeMode,
    /// Accent color in hex (e.g. "#9bd1ff"). Validated lightly: 7-char form.
    pub accent_hex: String,
    /// Typography scale (clamped to [TYPOGRAPHY_MIN..TYPOGRAPHY_MAX]).
    pub typography_scale: f32,
    /// Per-D-NN dashboard tile ordering — slot id → list of widget ids.
    pub widget_order: BTreeMap<String, Vec<String>>,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            theme: ThemeMode::Dark,
            accent_hex: "#9bd1ff".into(),
            typography_scale: 1.0,
            widget_order: BTreeMap::new(),
        }
    }
}

/// Personalization config: one global block + per-profile overrides
/// keyed by profile name (matches MS040 enum lowercased).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PersonalizationConfig {
    /// Schema version. MUST equal [`SCHEMA_VERSION`].
    pub schema_version: String,
    /// Global defaults.
    pub global: Preferences,
    /// Per-profile overrides keyed by profile name.
    pub per_profile: BTreeMap<String, Preferences>,
    /// Active profile name (drives effective preferences).
    pub active_profile: String,
}

impl Default for PersonalizationConfig {
    fn default() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            global: Preferences::default(),
            per_profile: BTreeMap::new(),
            active_profile: "private".into(),
        }
    }
}

/// Personalization errors.
#[derive(Debug, Error)]
pub enum PersonalizationError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Hex color is not a valid #rrggbb form.
    #[error("accent_hex invalid (expected #rrggbb): {0}")]
    AccentHexInvalid(String),
    /// Typography scale outside [TYPOGRAPHY_MIN..TYPOGRAPHY_MAX].
    #[error("typography_scale {0} outside [{min}..{max}]", min = TYPOGRAPHY_MIN, max = TYPOGRAPHY_MAX)]
    TypographyOutOfRange(f32),
    /// Profile name not in the MS040 6-profile set.
    #[error("profile name not in MS040 six-profile set: {0}")]
    UnknownProfile(String),
    /// Widget-order entry references a slot not in M060 catalog.
    #[error("widget_order slot not in M060 catalog: {0}")]
    UnknownSlot(String),
}

/// Valid MS040 profile names (selfdef-side; we reference the names verbatim).
pub const PROFILE_NAMES: [&str; 6] = [
    "private",
    "fast",
    "careful",
    "autonomous",
    "experimental",
    "production",
];

fn validate_accent(hex: &str) -> Result<(), PersonalizationError> {
    if hex.len() != 7 {
        return Err(PersonalizationError::AccentHexInvalid(hex.into()));
    }
    let bytes = hex.as_bytes();
    if bytes[0] != b'#' {
        return Err(PersonalizationError::AccentHexInvalid(hex.into()));
    }
    for &b in &bytes[1..] {
        if !b.is_ascii_hexdigit() {
            return Err(PersonalizationError::AccentHexInvalid(hex.into()));
        }
    }
    Ok(())
}

fn validate_typography(scale: f32) -> Result<(), PersonalizationError> {
    if !(TYPOGRAPHY_MIN..=TYPOGRAPHY_MAX).contains(&scale) || scale.is_nan() {
        return Err(PersonalizationError::TypographyOutOfRange(scale));
    }
    Ok(())
}

fn validate_preferences(
    p: &Preferences,
    catalog: &CoverageManifest,
) -> Result<(), PersonalizationError> {
    validate_accent(&p.accent_hex)?;
    validate_typography(p.typography_scale)?;
    let known: std::collections::HashSet<&str> =
        catalog.entries.iter().map(|e| e.slot.as_str()).collect();
    for slot in p.widget_order.keys() {
        if !known.contains(slot.as_str()) {
            return Err(PersonalizationError::UnknownSlot(slot.clone()));
        }
    }
    Ok(())
}

impl PersonalizationConfig {
    /// Validate every invariant.
    pub fn validate(&self) -> Result<(), PersonalizationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PersonalizationError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        // Profile name set
        if !PROFILE_NAMES.iter().any(|&n| n == self.active_profile) {
            return Err(PersonalizationError::UnknownProfile(
                self.active_profile.clone(),
            ));
        }
        // Per-profile override keys must be in the canonical 6-profile set.
        for name in self.per_profile.keys() {
            if !PROFILE_NAMES.iter().any(|&n| n == name) {
                return Err(PersonalizationError::UnknownProfile(name.clone()));
            }
        }
        let catalog = CoverageManifest::canonical();
        validate_preferences(&self.global, &catalog)?;
        for prefs in self.per_profile.values() {
            validate_preferences(prefs, &catalog)?;
        }
        Ok(())
    }

    /// Effective preferences for the active profile — overrides win when present.
    pub fn effective(&self) -> Preferences {
        self.per_profile
            .get(&self.active_profile)
            .cloned()
            .unwrap_or_else(|| self.global.clone())
    }

    /// Apply a profile transition by name. Returns the new effective prefs.
    pub fn switch_profile(&mut self, name: &str) -> Result<Preferences, PersonalizationError> {
        if !PROFILE_NAMES.iter().any(|&n| n == name) {
            return Err(PersonalizationError::UnknownProfile(name.into()));
        }
        self.active_profile = name.into();
        Ok(self.effective())
    }

    /// Update the widget order for a slot (validated against catalog).
    pub fn set_widget_order(
        &mut self,
        slot: &str,
        order: Vec<String>,
    ) -> Result<(), PersonalizationError> {
        let catalog = CoverageManifest::canonical();
        let known: std::collections::HashSet<&str> =
            catalog.entries.iter().map(|e| e.slot.as_str()).collect();
        if !known.contains(slot) {
            return Err(PersonalizationError::UnknownSlot(slot.into()));
        }
        self.global.widget_order.insert(slot.into(), order);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        PersonalizationConfig::default().validate().unwrap();
    }

    #[test]
    fn six_profile_names_match_ms040() {
        assert_eq!(PROFILE_NAMES.len(), 6);
        for name in [
            "private",
            "fast",
            "careful",
            "autonomous",
            "experimental",
            "production",
        ] {
            assert!(PROFILE_NAMES.contains(&name));
        }
    }

    #[test]
    fn invalid_accent_rejected() {
        for bad in ["9bd1ff", "#9b", "#xyzxyz", "#9bd1f", "ffffff#"] {
            let mut c = PersonalizationConfig::default();
            c.global.accent_hex = bad.into();
            assert!(
                matches!(
                    c.validate().unwrap_err(),
                    PersonalizationError::AccentHexInvalid(_)
                ),
                "bad: {bad}"
            );
        }
    }

    #[test]
    fn valid_accent_accepted() {
        for ok in ["#9bd1ff", "#000000", "#FFFFFF", "#7ad17a"] {
            let mut c = PersonalizationConfig::default();
            c.global.accent_hex = ok.into();
            c.validate()
                .unwrap_or_else(|e| panic!("{ok} rejected: {e}"));
        }
    }

    #[test]
    fn typography_out_of_range_rejected() {
        let mut c = PersonalizationConfig::default();
        c.global.typography_scale = 0.50;
        assert!(matches!(
            c.validate().unwrap_err(),
            PersonalizationError::TypographyOutOfRange(_)
        ));
        c.global.typography_scale = 2.00;
        assert!(matches!(
            c.validate().unwrap_err(),
            PersonalizationError::TypographyOutOfRange(_)
        ));
        c.global.typography_scale = f32::NAN;
        assert!(matches!(
            c.validate().unwrap_err(),
            PersonalizationError::TypographyOutOfRange(_)
        ));
    }

    #[test]
    fn typography_boundary_inclusive() {
        let mut c = PersonalizationConfig::default();
        c.global.typography_scale = TYPOGRAPHY_MIN;
        c.validate().unwrap();
        c.global.typography_scale = TYPOGRAPHY_MAX;
        c.validate().unwrap();
    }

    #[test]
    fn unknown_active_profile_rejected() {
        let mut c = PersonalizationConfig::default();
        c.active_profile = "ghost".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            PersonalizationError::UnknownProfile(_)
        ));
    }

    #[test]
    fn unknown_per_profile_override_rejected() {
        let mut c = PersonalizationConfig::default();
        c.per_profile.insert("ghost".into(), Preferences::default());
        assert!(matches!(
            c.validate().unwrap_err(),
            PersonalizationError::UnknownProfile(_)
        ));
    }

    #[test]
    fn unknown_slot_in_widget_order_rejected() {
        let mut c = PersonalizationConfig::default();
        c.global
            .widget_order
            .insert("D-99".into(), vec!["w1".into()]);
        assert!(matches!(
            c.validate().unwrap_err(),
            PersonalizationError::UnknownSlot(_)
        ));
    }

    #[test]
    fn known_slot_in_widget_order_accepted() {
        let mut c = PersonalizationConfig::default();
        c.global
            .widget_order
            .insert("D-03".into(), vec!["w-models".into(), "w-kv".into()]);
        c.validate().unwrap();
    }

    #[test]
    fn effective_returns_global_when_no_override() {
        let c = PersonalizationConfig::default();
        let eff = c.effective();
        assert_eq!(eff.theme, ThemeMode::Dark);
        assert_eq!(eff.accent_hex, "#9bd1ff");
    }

    #[test]
    fn effective_returns_per_profile_override() {
        let mut c = PersonalizationConfig::default();
        let mut over = Preferences::default();
        over.theme = ThemeMode::Light;
        over.accent_hex = "#7ad17a".into();
        c.per_profile.insert("careful".into(), over);
        c.active_profile = "careful".into();
        let eff = c.effective();
        assert_eq!(eff.theme, ThemeMode::Light);
        assert_eq!(eff.accent_hex, "#7ad17a");
    }

    #[test]
    fn switch_profile_returns_new_effective() {
        let mut c = PersonalizationConfig::default();
        let mut prod = Preferences::default();
        prod.accent_hex = "#ff7676".into();
        c.per_profile.insert("production".into(), prod);
        let eff = c.switch_profile("production").unwrap();
        assert_eq!(eff.accent_hex, "#ff7676");
        assert_eq!(c.active_profile, "production");
    }

    #[test]
    fn switch_profile_to_unknown_refused() {
        let mut c = PersonalizationConfig::default();
        assert!(c.switch_profile("ghost").is_err());
    }

    #[test]
    fn set_widget_order_known_slot() {
        let mut c = PersonalizationConfig::default();
        c.set_widget_order("D-12", vec!["w-rings".into(), "w-rules".into()])
            .unwrap();
        assert_eq!(c.global.widget_order["D-12"], vec!["w-rings", "w-rules"]);
    }

    #[test]
    fn set_widget_order_unknown_slot_refused() {
        let mut c = PersonalizationConfig::default();
        assert!(matches!(
            c.set_widget_order("D-XX", vec!["w".into()]).unwrap_err(),
            PersonalizationError::UnknownSlot(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = PersonalizationConfig::default();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            PersonalizationError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn theme_serde_kebab_case() {
        assert_eq!(serde_json::to_string(&ThemeMode::Auto).unwrap(), "\"auto\"");
        assert_eq!(serde_json::to_string(&ThemeMode::Dark).unwrap(), "\"dark\"");
        assert_eq!(
            serde_json::to_string(&ThemeMode::Light).unwrap(),
            "\"light\""
        );
    }

    #[test]
    fn full_config_serde_roundtrip() {
        let mut c = PersonalizationConfig::default();
        c.per_profile.insert("experimental".into(), {
            let mut p = Preferences::default();
            p.theme = ThemeMode::Light;
            p.typography_scale = 1.15;
            p.widget_order
                .insert("D-15".into(), vec!["tier-a".into(), "tier-d".into()]);
            p
        });
        c.active_profile = "experimental".into();
        let j = serde_json::to_string(&c).unwrap();
        let back: PersonalizationConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
