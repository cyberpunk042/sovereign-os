//! `sovereign-module-facets` — E0477 / M00828: the uniform module interface.
//!
//! "Continuity is preserving the chain from intent to action to consequence to
//! learning." For that chain to hold, every module must be legible the same
//! way: the catalogue requires each of the 13 modules to expose six facets —
//! state, events, policy hooks, profile knobs, a rollback story, and a learning
//! signal. This crate fixes those facets and provides a descriptor +
//! completeness validator, so a module that forgets (say) its rollback story
//! is rejected rather than silently becoming an island of un-rollback-able
//! state.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

/// The six facets every module must expose (E0477).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ModuleFacet {
    /// Its observable state.
    State,
    /// The events it emits (the E0470 taxonomy).
    Events,
    /// The policy hooks it honours (the E0473 questions).
    PolicyHooks,
    /// The profile knobs that tune it.
    ProfileKnobs,
    /// Its rollback story (how its actions are reversed).
    Rollback,
    /// The learning signal it feeds back (what adaptation it enables).
    LearningSignal,
}

impl ModuleFacet {
    /// All six required facets.
    pub const ALL: [ModuleFacet; 6] = [
        ModuleFacet::State,
        ModuleFacet::Events,
        ModuleFacet::PolicyHooks,
        ModuleFacet::ProfileKnobs,
        ModuleFacet::Rollback,
        ModuleFacet::LearningSignal,
    ];
}

/// The 13 canonical modules (E0477 module map).
pub const CANONICAL_MODULES: [&str; 13] = [
    "Base OS",
    "Compute Fabric",
    "Sandbox Fabric",
    "Gateway",
    "Memory OS",
    "Workflow Compiler",
    "Eval-Value Plane",
    "Continuity Manager",
    "Observability Fabric",
    "Policy Fabric",
    "Config Resolver",
    "LoRA-Adaptation Foundry",
    "Hardware Profiler",
];

/// A module's declaration of how it exposes each facet (facet → a description /
/// pointer the operator can follow).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ModuleDescriptor {
    /// Module name (ideally one of [`CANONICAL_MODULES`]).
    pub name: String,
    /// Per-facet description; completeness checked by [`Self::validate`].
    pub facets: BTreeMap<ModuleFacet, String>,
}

/// Why a descriptor failed the continuity-of-control contract.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FacetError {
    /// One of the six required facets is undeclared.
    MissingFacet(ModuleFacet),
    /// A required facet was declared with an empty description.
    EmptyFacet(ModuleFacet),
}

impl std::fmt::Display for FacetError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FacetError::MissingFacet(x) => write!(f, "module is missing the {x:?} facet"),
            FacetError::EmptyFacet(x) => write!(f, "module's {x:?} facet has no description"),
        }
    }
}

impl std::error::Error for FacetError {}

impl ModuleDescriptor {
    /// A descriptor for `name` with no facets yet.
    #[must_use]
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            facets: BTreeMap::new(),
        }
    }

    /// Declare one facet.
    #[must_use]
    pub fn with(mut self, facet: ModuleFacet, description: impl Into<String>) -> Self {
        self.facets.insert(facet, description.into());
        self
    }

    /// Validate the continuity-of-control contract: all six facets declared,
    /// each non-empty. A module that can't show one facet breaks the chain.
    pub fn validate(&self) -> Result<(), FacetError> {
        for facet in ModuleFacet::ALL {
            match self.facets.get(&facet) {
                None => return Err(FacetError::MissingFacet(facet)),
                Some(d) if d.trim().is_empty() => return Err(FacetError::EmptyFacet(facet)),
                Some(_) => {}
            }
        }
        Ok(())
    }

    /// True if `name` is one of the 13 canonical modules.
    #[must_use]
    pub fn is_canonical(&self) -> bool {
        CANONICAL_MODULES.contains(&self.name.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn complete(name: &str) -> ModuleDescriptor {
        let mut d = ModuleDescriptor::new(name);
        for f in ModuleFacet::ALL {
            d = d.with(f, format!("{f:?} of {name}"));
        }
        d
    }

    #[test]
    fn six_facets_and_thirteen_modules() {
        assert_eq!(ModuleFacet::ALL.len(), 6);
        assert_eq!(CANONICAL_MODULES.len(), 13);
    }

    #[test]
    fn complete_descriptor_validates_and_is_canonical() {
        let d = complete("Observability Fabric");
        d.validate().unwrap();
        assert!(d.is_canonical());
    }

    #[test]
    fn missing_facet_is_rejected() {
        let d = ModuleDescriptor::new("Memory OS")
            .with(ModuleFacet::State, "kv + episodic + ...")
            .with(ModuleFacet::Events, "memory_read / memory_write")
            .with(ModuleFacet::PolicyHooks, "sensitivity gate")
            .with(ModuleFacet::ProfileKnobs, "retention horizon")
            .with(ModuleFacet::LearningSignal, "retrieval quality");
        // Rollback facet missing → the module is an un-rollback-able island.
        assert_eq!(
            d.validate(),
            Err(FacetError::MissingFacet(ModuleFacet::Rollback))
        );
    }

    #[test]
    fn empty_facet_is_rejected() {
        let d = complete("Gateway").with(ModuleFacet::LearningSignal, "   ");
        assert_eq!(
            d.validate(),
            Err(FacetError::EmptyFacet(ModuleFacet::LearningSignal))
        );
    }

    #[test]
    fn non_canonical_name_still_validates_facets() {
        // A custom module can satisfy the facet contract without being one of
        // the 13 canonical names.
        let d = complete("my-custom-module");
        d.validate().unwrap();
        assert!(!d.is_canonical());
    }

    #[test]
    fn facet_serializes_kebab() {
        assert_eq!(
            serde_json::to_string(&ModuleFacet::PolicyHooks).unwrap(),
            "\"policy-hooks\""
        );
        assert_eq!(
            serde_json::to_string(&ModuleFacet::LearningSignal).unwrap(),
            "\"learning-signal\""
        );
    }
}
