//! `sovereign-whitelabel` — M081: the whitelabel mechanism.
//!
//! Rebranding the station is not a global find-and-replace. Every surface is
//! categorized by how it must be treated, rendered by a strategy suited to its
//! kind, and applied at the right lifecycle stage. The load-bearing safety rule
//! is `MustNotTouch` — upstream licenses, third-party code, and protocol
//! identifiers that a rebrand must never rewrite. This crate fixes the
//! taxonomy, the strategies, and the stages.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// How a surface must be treated during a rebrand (E0779).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RebrandCategory {
    /// Must be rebranded (operator-visible brand surfaces).
    MustRebrand,
    /// Should be rebranded (recommended, not blocking).
    ShouldRebrand,
    /// May be left as-is (optional).
    MayLeave,
    /// Must NOT be touched (licenses, third-party code, protocol identifiers).
    MustNotTouch,
}

impl RebrandCategory {
    /// All 4 categories.
    pub const ALL: [RebrandCategory; 4] = [
        RebrandCategory::MustRebrand,
        RebrandCategory::ShouldRebrand,
        RebrandCategory::MayLeave,
        RebrandCategory::MustNotTouch,
    ];

    /// Whether a rebrand pass is permitted to modify this surface at all. The
    /// safety rule: `MustNotTouch` is never modifiable.
    #[must_use]
    pub fn may_modify(self) -> bool {
        self != RebrandCategory::MustNotTouch
    }

    /// Whether a rebrand is *required* (not merely allowed) for this surface.
    #[must_use]
    pub fn is_required(self) -> bool {
        self == RebrandCategory::MustRebrand
    }
}

/// How a surface is rendered with the brand (E0782).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RenderStrategy {
    /// Substitute brand tokens in a template.
    TemplateSubstitution,
    /// Overlay a replacement file.
    FileOverlay,
    /// Replace a whole package.
    PackageReplacement,
    /// Flip a build-time flag.
    BuildTimeFlag,
}

impl RenderStrategy {
    /// All 4 strategies.
    pub const ALL: [RenderStrategy; 4] = [
        RenderStrategy::TemplateSubstitution,
        RenderStrategy::FileOverlay,
        RenderStrategy::PackageReplacement,
        RenderStrategy::BuildTimeFlag,
    ];
}

/// When a rebrand is applied (E0783).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LifecycleStage {
    /// Pre-build patches.
    PreBuild,
    /// Install-time substitutions.
    InstallTime,
    /// First-boot scripts.
    FirstBoot,
}

impl LifecycleStage {
    /// All 3 stages, in apply order.
    pub const ALL: [LifecycleStage; 3] = [
        LifecycleStage::PreBuild,
        LifecycleStage::InstallTime,
        LifecycleStage::FirstBoot,
    ];
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts() {
        assert_eq!(RebrandCategory::ALL.len(), 4);
        assert_eq!(RenderStrategy::ALL.len(), 4);
        assert_eq!(LifecycleStage::ALL.len(), 3);
    }

    #[test]
    fn must_not_touch_is_never_modifiable() {
        assert!(!RebrandCategory::MustNotTouch.may_modify());
        for c in RebrandCategory::ALL
            .into_iter()
            .filter(|c| *c != RebrandCategory::MustNotTouch)
        {
            assert!(c.may_modify(), "{c:?}");
        }
    }

    #[test]
    fn only_must_rebrand_is_required() {
        assert!(RebrandCategory::MustRebrand.is_required());
        for c in RebrandCategory::ALL
            .into_iter()
            .filter(|c| *c != RebrandCategory::MustRebrand)
        {
            assert!(!c.is_required(), "{c:?}");
        }
    }

    #[test]
    fn stages_apply_in_order() {
        assert!(LifecycleStage::PreBuild < LifecycleStage::InstallTime);
        assert!(LifecycleStage::InstallTime < LifecycleStage::FirstBoot);
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&RebrandCategory::MustNotTouch).unwrap(),
            "\"must-not-touch\""
        );
        assert_eq!(
            serde_json::to_string(&RenderStrategy::TemplateSubstitution).unwrap(),
            "\"template-substitution\""
        );
        assert_eq!(
            serde_json::to_string(&LifecycleStage::FirstBoot).unwrap(),
            "\"first-boot\""
        );
    }
}
